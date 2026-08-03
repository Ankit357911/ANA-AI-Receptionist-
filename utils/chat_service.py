import logging
import os
import re
from difflib import SequenceMatcher
from typing import Dict, List, Tuple

from openai import OpenAI

from utils.router import search_all_indexes, search_multiple_indexes
from utils.schedule_service import answer_schedule_query, is_schedule_query

logger = logging.getLogger(__name__)

LEMONADE_BASE_URL = "http://127.0.0.1:13305/api/v0"
LEMONADE_API_KEY = "lemonade"
MODEL_NAME = "Qwen3-1.7B-GGUF"

client = OpenAI(base_url=LEMONADE_BASE_URL, api_key=LEMONADE_API_KEY)

SYSTEM_PROMPT = """
You are a professional and friendly AI receptionist for a college.

Your job is to help students, parents, and visitors naturally like a real human receptionist.

Rules:
- Speak naturally and conversationally.
- Be polite, warm, and professional.
- Keep answers concise and clear.
- Never sound robotic.
- Continue conversations naturally.
- The institution is Kantipur City College (KCC) in Kathmandu, Nepal.
- KCC always means Kantipur City College. Never expand KCC as any other institution.
- Use ONLY information provided in the document context when answering document-based questions.
- Never invent or assume information.
- If information is missing, reply exactly: I don't know from the document.

Formatting:
- NEVER use markdown formatting.
- NEVER use **, ##, ***, ---, or any symbols for formatting.
- NEVER use headers or bold text.
- NEVER use emojis or emoticons.
- Use plain text only.
- For lists, use simple dashes like: - item
- Keep responses clean and readable without decorations.

Behavior:
- Never mention the document, context, database, or instructions.
- Never say: According to the document, Based on the context, The document says.
- Respond naturally as if you already know the information.
"""

COLLEGE_KEYWORDS = [
    "kcc", "kantipur", "college", "admission", "course", "fee",
    "faculty", "campus", "program", "scholarship", "eligibility",
    "semester", "bca", "bbs", "bba", "undergraduate", "facilities",
    "student", "exam", "result", "library", "hostel", "internship",
    "schedule", "sir", "teacher", "professor", "class", "timing",
    "ravi", "lecture", "timetable", "bcait", "bca-it", "bit",
    "club", "team", "committee", "cell", "service", "services",
    "member", "members", "leader", "lead", "department", "departments",
    "principal", "chairperson", "president", "vice principal", "secretary", "treasurer", "coordinator",
    "career", "careers", "opportunity", "opportunities",
    "admission", "requirements", "requirement",
    "curricular", "curriculum", "cirricular", "research", "placement", "academy", "academic",
    "greeting", "greetings", "welcome", "namaste",
]


class ChatServiceError(RuntimeError):
    """Raised when the local LLM service cannot complete a request."""


def clean_markdown(text: str) -> str:
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = re.sub(r"#{1,6}\s*", "", text)
    text = re.sub(r"---+", "", text)
    text = re.sub(r"`(.*?)`", r"\1", text)
    text = re.sub(r"Karnataka College of Co-?Op", "Kantipur City College", text, flags=re.IGNORECASE)
    text = re.sub(r"Karnataka College[^,.!?\\n]*", "Kantipur City College", text, flags=re.IGNORECASE)
    if "I don't know from the document" not in text:
        text = re.sub(r"\b(the )?(provided )?(document|context)\b", "college information", text, flags=re.IGNORECASE)
    text = re.sub(r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF]", "", text)
    return text


def normalize_query(query: str) -> str:
    query = re.sub(r"\bB\s*C\s*A\s*[- ]?\s*I\s*T\b", "BCA-IT", query, flags=re.IGNORECASE)
    query = re.sub(r"\bBCA\s*ID\b", "BCA-IT", query, flags=re.IGNORECASE)
    query = re.sub(r"\bBCAID\b", "BCA-IT", query, flags=re.IGNORECASE)
    query = re.sub(r"\bBCAIT\b", "BCA-IT", query, flags=re.IGNORECASE)
    query = re.sub(r"\bcarrer\b", "career", query, flags=re.IGNORECASE)
    query = re.sub(r"\bcarear\b", "career", query, flags=re.IGNORECASE)
    query = re.sub(r"\bopportunit(?:y|ies|ues)\b", "opportunities", query, flags=re.IGNORECASE)
    query = re.sub(r"\boppertun(?:ity|ities|ities)\b", "opportunities", query, flags=re.IGNORECASE)
    query = re.sub(r"\bcurriculum\b", "cirricular", query, flags=re.IGNORECASE)
    query = re.sub(r"\bcurricular\b", "cirricular", query, flags=re.IGNORECASE)
    query = re.sub(r"\bstudents?\s+service(s)?\b", "student services", query, flags=re.IGNORECASE)
    return query.strip()


def _collapse_repeated_letters(text: str) -> str:
    return re.sub(r"(.)\1{2,}", r"\1\1", text)


def is_bca_it_query(query: str) -> bool:
    return bool(re.search(r"\b(BCA|BCA-IT|BCAIT)\b", query, flags=re.IGNORECASE))


def is_simple_greeting(query: str) -> bool:
    normalized = _collapse_repeated_letters(re.sub(r"[^a-z\s]", "", query.lower()).strip())
    return _greeting_kind(normalized) is not None


def _greeting_kind(normalized: str) -> str | None:
    simple_greetings = {
        "hi": "hello",
        "hello": "hello",
        "hey": "hello",
        "namaste": "namaste",
        "good morning": "morning",
        "good afternoon": "afternoon",
        "good evening": "evening",
        "good night": "night",
    }

    if normalized in simple_greetings:
        return simple_greetings[normalized]

    if normalized.startswith("good "):
        tail = normalized[5:].strip()
        greeting_tails = {
            "morning": "morning",
            "afternoon": "afternoon",
            "evening": "evening",
            "night": "night",
        }
        for candidate, kind in greeting_tails.items():
            if SequenceMatcher(None, tail, candidate).ratio() >= 0.8:
                return kind

    return None


def greeting_answer(query: str) -> str:
    normalized = _collapse_repeated_letters(re.sub(r"[^a-z\s]", "", query.lower()).strip())

    kind = _greeting_kind(normalized)
    if kind in {"hello", "namaste"}:
        return "Namaste. How can I help you today?"

    if kind == "morning":
        return (
            "Hello! Good Morning!\n\n"
            "I hope you have a wonderful day ahead.\n\n"
            "How can I assist you today?"
        )

    if kind == "afternoon":
        return (
            "Hello! Good Afternoon!\n\n"
            "I hope your day is going well.\n\n"
            "How can I assist you today?"
        )

    if kind == "evening":
        return (
            "Hello! Good Evening!\n\n"
            "I hope you had a good day.\n\n"
            "How can I assist you this evening?"
        )

    if kind == "night":
        return (
            "Hello! Good Night!\n\n"
            "I hope you had a pleasant day. If there's anything you need before you call it a day, I'm here to help.\n\n"
            "How can I assist you tonight?"
        )

    return "Namaste. How can I help you today?"


def bca_it_fallback_answer() -> str:
    return (
        "BCA-IT at Kantipur City College is a four-year undergraduate program divided into eight semesters. "
        "It focuses on software development, information technology management, networking, cybersecurity, "
        "cloud computing, and data analytics. The program includes practical lab-based learning, software "
        "development projects, IT workshops and seminars, industry apprenticeship, specialization areas, "
        "internship, and an apprentice project."
    )


def _format_source_title(source_name: str) -> str:
    title = source_name.replace("_", " ").strip()
    if not title:
        return "This section"
    return title[0].upper() + title[1:]


def _list_style_fallback(source_name: str, context_chunks: List[str]) -> str:
    lines: List[str] = []
    for chunk in context_chunks:
        for raw_line in chunk.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.lower().startswith("source:"):
                line = line.split(":", 1)[1].strip()
                if not line:
                    continue
            if line.startswith("#"):
                continue
            if set(line) <= {"-", "=", "•", "|"}:
                continue
            cleaned = re.sub(r"^[\-\d\.\)\s]+", "", line)
            cleaned = cleaned.replace("â€“", "-").replace("â€”", "-")
            if cleaned and cleaned not in lines:
                lines.append(cleaned)

    if not lines:
        return ""

    title = _format_source_title(source_name)
    preview = "; ".join(lines[:8])
    if len(lines) > 8:
        preview += "; and more"
    return f"{title} includes {preview}."


def _has_phrase(text: str, phrase: str) -> bool:
    tokens = phrase.lower().split()
    if not tokens:
        return False
    pattern = r"\b" + r"\s+".join(re.escape(token) for token in tokens) + r"\b"
    return re.search(pattern, text) is not None


def _team_role_fallback(query: str, context_chunks: List[str]) -> str:
    normalized = re.sub(r"[^a-z0-9\s]+", " ", query.lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()

    role_patterns = [
        ("Vice Principal", ("vice principal", "vice-principal")),
        ("Chairperson", ("chairperson",)),
        ("Principal", ("principal",)),
        ("President", ("president",)),
        ("Secretary", ("secretary",)),
        ("Treasurer", ("treasurer",)),
    ]

    target_role = None
    for role, patterns in role_patterns:
        if any(_has_phrase(normalized, pattern) for pattern in patterns):
            target_role = role
            break

    if not target_role:
        return ""

    for chunk in context_chunks:
        previous_line = ""
        for raw_line in chunk.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            lowered = line.lower()
            if lowered.startswith("source:") or line.startswith("#"):
                continue

            if _has_phrase(lowered, target_role.lower()):
                candidate = previous_line.strip()
                if candidate and not candidate.endswith(":"):
                    return f"The {target_role.lower()} is {candidate}."

            previous_line = line

    return ""


def _is_refusal_response(text: str) -> bool:
    lowered = text.lower().strip()
    refusal_phrases = (
        "i don't know",
        "i do not know",
        "i don't have information",
        "i do not have information",
        "i don't have enough information",
        "i do not have enough information",
    )
    return any(phrase in lowered for phrase in refusal_phrases)


LIST_STYLE_SOURCES = {
    "greeting",
    "Greeting",
    "cirricular",
    "creators club",
    "departments",
    "it club",
    "kcc team",
    "research committee",
    "sdsn club",
    "sqc",
    "student services",
    "contact_information",
    "contact information",
}


PROGRAM_STYLE_SOURCES = {
    "bbs_program",
    "bca_program",
    "basw_program",
    "undergraduate_programs",
    "academic_structure",
    "eligibility_criteria",
    "admission_requirements",
    "career_opportunities",
}


ELIGIBILITY_STYLE_SOURCES = {
    "eligibility_criteria",
    "eligibility criteria",
}


ADMISSION_STYLE_SOURCES = {
    "admission_requirements",
    "admission requirements",
}


def _greeting_info_fallback(context_chunks: List[str]) -> str:
    intro = None
    has_rules = False
    has_morning = False
    has_afternoon = False
    has_evening = False
    has_night = False
    has_general = False

    for chunk in context_chunks:
        for raw_line in chunk.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            lowered = line.lower()
            if lowered.startswith("source:"):
                continue
            if "ai receptionist of kantipur city college" in lowered and intro is None:
                intro = "ANA is the AI Receptionist of Kantipur City College."
                continue
            if "greeting rules" in lowered:
                has_rules = True
                continue
            if "morning greeting" in lowered:
                has_morning = True
                continue
            if "afternoon greeting" in lowered:
                has_afternoon = True
                continue
            if "evening greeting" in lowered:
                has_evening = True
                continue
            if "night greeting" in lowered:
                has_night = True
                continue
            if "general greeting" in lowered:
                has_general = True
                continue

    if not intro:
        intro = "ANA is the AI Receptionist of Kantipur City College."

    if has_rules:
        rules = []
        if has_morning:
            rules.append("Good Morning uses the morning greeting.")
        if has_afternoon:
            rules.append("Good Afternoon uses the afternoon greeting.")
        if has_evening:
            rules.append("Good Evening uses the evening greeting.")
        if has_night:
            rules.append("Good Night uses the night greeting.")
        if has_general:
            rules.append("Hello, Hi, and Hey can follow the current local time greeting.")
        if rules:
            return f"{intro} The greeting file says: " + " ".join(rules)

    return (
        f"{intro} The greeting file includes morning, afternoon, evening, night, and general greeting responses "
        f"for welcoming users and helping them start a conversation."
    )


def _extract_contact_details(context_chunks: List[str]) -> Dict[str, str]:
    website = None
    phone = None
    location = None
    tel = None
    fax = None
    email = None

    for chunk in context_chunks:
        for raw_line in chunk.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            lowered = line.lower()
            if lowered.startswith("source:"):
                continue
            if "official website" in lowered and website is None:
                continue
            if re.match(r"^https?://", line) and website is None:
                website = line
                continue
            if lowered.startswith("phone number") and phone is None:
                continue
            if re.fullmatch(r"[0-9+\-() ]{7,}", line) and phone is None:
                phone = line
                continue
            if lowered.startswith("location") and location is None:
                continue
            if lowered.startswith("tel") and tel is None:
                tel = line
                continue
            if lowered.startswith("fax") and fax is None:
                fax = line
                continue
            if lowered.startswith("email") and email is None:
                email = line
                continue
            if "lalupate marga" in lowered and location is None:
                location = line

    return {
        "website": website or "",
        "phone": phone or "",
        "location": location or "",
        "tel": tel or "",
        "fax": fax or "",
        "email": email or "",
    }


def _contact_intent(query: str) -> str:
    normalized = re.sub(r"[^a-z0-9\s]+", " ", query.lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()

    if any(
        phrase in normalized
        for phrase in (
            "contact information",
            "contact info",
            "contact details",
            "how can i contact",
            "how do i contact",
            "how to contact",
            "how to reach",
            "how can i reach",
            "where is",
            "where are",
            "where can i find",
            "contact us",
        )
    ):
        return "all"

    if any(word in normalized.split() for word in ("email", "mail")) or "e mail" in normalized:
        return "email"
    if any(word in normalized.split() for word in ("phone", "tel", "telephone")):
        return "phone"
    if any(word in normalized.split() for word in ("address", "location", "located")):
        return "location"

    return "all"


def _contact_info_fallback(query: str, context_chunks: List[str]) -> str:
    details = _extract_contact_details(context_chunks)
    intent = _contact_intent(query)

    website = details["website"]
    phone = details["phone"]
    location = details["location"]
    tel = details["tel"]
    fax = details["fax"]
    email = details["email"]

    if intent == "email" and email:
        return f"Email: {email.split(':', 1)[1].strip() if ':' in email else email}"

    if intent == "phone" and (phone or tel):
        value = phone or tel
        label = "Phone number" if phone else "Tel"
        return f"{label}: {value.split(':', 1)[1].strip() if ':' in value else value}"

    if intent == "location" and location:
        return f"Location: {location}"

    parts = []
    if website:
        parts.append(f"Website: {website}")
    if phone:
        parts.append(f"Phone number: {phone}")
    if tel:
        parts.append(f"Tel: {tel.split(':', 1)[1].strip() if ':' in tel else tel}")
    if email:
        parts.append(f"Email: {email.split(':', 1)[1].strip() if ':' in email else email}")
    if location:
        parts.append(f"Location: {location}")
    if fax:
        parts.append(f"Fax: {fax.split(':', 1)[1].strip() if ':' in fax else fax}")

    if not parts:
        return ""

    return "Kantipur City College contact information: " + "; ".join(parts) + "."


def _program_info_fallback(source_name: str, context_chunks: List[str]) -> str:
    section_map: Dict[str, List[str]] = {}
    current_section = None

    lead_in_patterns = (
        "students develop",
        "graduates may pursue careers as",
        "career opportunities include",
        "educational objectives",
        "main study areas",
        "program overview",
    )

    for chunk in context_chunks:
        for raw_line in chunk.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            lowered = line.lower()
            if lowered.startswith("source:"):
                continue
            if line.startswith("#"):
                heading = line.lstrip("#").strip()
                if heading:
                    current_section = heading.lower()
                    section_map.setdefault(current_section, [])
                continue
            if current_section:
                if line.startswith("-"):
                    cleaned = line.lstrip("-").strip()
                else:
                    cleaned = line
                if cleaned.endswith(":") or any(cleaned.lower().startswith(pattern) for pattern in lead_in_patterns):
                    continue
                if cleaned:
                    section_map.setdefault(current_section, []).append(cleaned)

    title = source_name.replace("_Program", "").replace("_", " ").strip()
    if not title:
        title = _format_source_title(source_name)
    overview = " ".join(section_map.get("program overview", [])[:2]).strip()
    study_areas = section_map.get("major study areas", [])
    skills = section_map.get("skills developed", [])
    careers = section_map.get("career opportunities", [])
    objectives = section_map.get("educational objectives", [])

    parts = []
    if overview:
        parts.append(overview)
    if study_areas:
        parts.append("Main study areas include " + ", ".join(study_areas[:6]) + ".")
    if skills:
        parts.append("Students develop skills such as " + ", ".join(skills[:6]) + ".")
    if careers:
        parts.append("Career options include " + ", ".join(careers[:6]) + ".")
    if objectives:
        parts.append("Educational goals include " + ", ".join(objectives[:4]) + ".")

    if not parts:
        return _list_style_fallback(source_name, context_chunks)

    return f"{title} at Kantipur City College is an undergraduate program. " + " ".join(parts)


def _eligibility_info_fallback(query: str, context_chunks: List[str]) -> str:
    normalized = re.sub(r"[^a-z0-9\s]+", " ", query.lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()

    if "bbs" in normalized:
        target_label = "### for bbs"
        intro = "For BBS, the eligibility criteria are:"
    elif "bca" in normalized:
        target_label = "### for bca"
        intro = "For BCA, the eligibility criteria are:"
    elif "basw" in normalized:
        target_label = "### for basw"
        intro = "For BASW, the eligibility criteria are:"
    else:
        target_label = "## undergraduate eligibility"
        intro = "The eligibility criteria are:"

    items: List[str] = []
    general_notes: List[str] = []
    collecting_target = False
    collecting_general = False

    for chunk in context_chunks:
        for raw_line in chunk.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            lowered = line.lower()
            if lowered.startswith("source:"):
                continue
            if lowered.startswith("## undergraduate eligibility"):
                collecting_general = False
                collecting_target = False
                continue
            if lowered.startswith("### for "):
                collecting_target = lowered == target_label
                collecting_general = False
                continue
            if lowered.startswith("## general eligibility notes"):
                collecting_general = True
                collecting_target = False
                continue

            if collecting_target and line.startswith("-"):
                cleaned = line.lstrip("-").strip()
                if cleaned and cleaned not in items:
                    items.append(cleaned)
            elif collecting_general and line.startswith("-"):
                cleaned = line.lstrip("-").strip()
                if cleaned and cleaned not in general_notes:
                    general_notes.append(cleaned)

    if not items and not general_notes:
        return ""

    parts = [intro]
    if items:
        parts.append("; ".join(items) + ".")
    if general_notes and "bbs" not in normalized:
        parts.append("General notes: " + "; ".join(general_notes) + ".")

    return " ".join(parts)


def _career_info_fallback(query: str, context_chunks: List[str]) -> str:
    normalized = re.sub(r"[^a-z0-9\s]+", " ", query.lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()

    if "basw" in normalized or "social work" in normalized:
        target_sections = {"social work career paths", "career opportunities"}
        intro = "After BASW, career opportunities include:"
    elif "bbs" in normalized or "business" in normalized or "management" in normalized:
        target_sections = {"business career paths", "career opportunities"}
        intro = "After BBS, career opportunities include:"
    elif "bca" in normalized or "it" in normalized or "computer" in normalized:
        target_sections = {"it career paths", "career opportunities"}
        intro = "After BCA, career opportunities include:"
    else:
        target_sections = {"career opportunities"}
        intro = "Career opportunities include:"

    items: List[str] = []
    current_section = None

    for chunk in context_chunks:
        for raw_line in chunk.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            lowered = line.lower()
            if lowered.startswith("source:"):
                continue
            if line.startswith("##"):
                current_section = line.lstrip("#").strip().lower()
                continue
            if current_section and current_section in target_sections:
                if line.startswith("-"):
                    cleaned = line.lstrip("-").strip()
                    if cleaned and cleaned not in items:
                        items.append(cleaned)

    if not items:
        return ""

    return intro + " " + "; ".join(items) + "."


def _bca_bit_career_info_fallback() -> str:
    path = os.path.join("data", "Collage_info.txt")
    if not os.path.exists(path):
        return ""

    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    def extract_between(start_marker: str, end_markers: List[str]) -> List[str]:
        start = text.find(start_marker)
        if start == -1:
            return []
        end = len(text)
        for marker in end_markers:
            idx = text.find(marker, start + 1)
            if idx != -1:
                end = min(end, idx)
        section = text[start:end]
        items: List[str] = []
        collecting = False
        stop_markers = {
            "special features",
            "program features",
            "course structure",
            "admission requirements",
            "scholarships",
            "faculties",
            "faculty members",
            "semester",
            "year i",
            "year ii",
            "year iii",
            "year iv",
            "====================================================",
        }
        for raw_line in section.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            lowered = line.lower()
            if lowered.startswith("source:"):
                continue
            if line.startswith("CAREER OPPORTUNITIES"):
                collecting = True
                continue
            if collecting and (
                lowered in stop_markers
                or lowered.startswith("special features")
                or lowered.startswith("program features")
                or lowered.startswith("course structure")
                or lowered.startswith("semester")
                or lowered.startswith("year ")
                or lowered.startswith("admission requirements")
                or lowered.startswith("scholarships")
                or lowered.startswith("faculty")
                or lowered.startswith("====================================================")
            ):
                break
            if collecting and line.startswith("-"):
                cleaned = line.lstrip("-").strip()
                if cleaned and cleaned not in items:
                    items.append(cleaned)
        return items

    bca_items = extract_between(
        "3. BACHELOR OF COMPUTER APPLICATION AND INFORMATION TECHNOLOGY (BCA-IT)",
        ["\n====================================================\n4.", "\n4. BACHELOR OF BUSINESS ADMINISTRATION (BBA)"],
    )
    bit_items = extract_between(
        "6. BACHELOR OF INFORMATION TECHNOLOGY (BIT)",
        ["\n====================================================\n7.", "\n7. ADMISSION REQUIREMENTS"],
    )

    if not bca_items and not bit_items:
        return ""

    parts = []
    if bca_items:
        parts.append("After BCA, career opportunities include: " + "; ".join(bca_items) + ".")
    if bit_items:
        parts.append("After BIT, career opportunities include: " + "; ".join(bit_items) + ".")
    return " ".join(parts)


def _read_text_file(path: str) -> str:
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _extract_lines_between(text: str, start_marker: str, end_markers: List[str]) -> str:
    start = text.find(start_marker)
    if start == -1:
        return ""
    end = len(text)
    for marker in end_markers:
        idx = text.find(marker, start + 1)
        if idx != -1:
            end = min(end, idx)
    return text[start:end]


def _clean_bullet_lines(block: str) -> List[str]:
    items: List[str] = []
    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("="):
            continue
        if line.startswith("-"):
            cleaned = line.lstrip("-").strip()
            if cleaned and cleaned not in items:
                items.append(cleaned)
    return items


def _program_comparison_answer(query: str) -> str:
    programs = _mentioned_programs(query)
    if len(programs) < 2:
        return ""

    summaries = []

    if "BCA" in programs:
        bca_text = _read_text_file(os.path.join("data", "BCA_Program.txt"))
        if bca_text:
            bca_overview = _extract_lines_between(
                bca_text,
                "## Program Overview",
                ["## Core Learning Areas", "## Career Opportunities"],
            )
            bca_careers = _extract_lines_between(
                bca_text,
                "## Career Opportunities",
                ["## Higher Education Path", "## Learning Approach"],
            )
            bca_focus = _clean_bullet_lines(_extract_lines_between(bca_text, "## Core Learning Areas", ["## Skills Developed", "## Career Opportunities"]))
            bca_career_items = _clean_bullet_lines(bca_careers)
            summaries.append(
                "BCA: Information Technology focused; "
                + ("".join(["overview: ", " ".join([line for line in bca_overview.splitlines() if line and not line.startswith('-')][:2]).strip()]) if bca_overview else "overview: software development and IT")
                + "; focus: "
                + ", ".join(bca_focus[:5])
                + "; careers: "
                + ", ".join(bca_career_items[:6])
            )

    if "BIT" in programs:
        collage_text = _read_text_file(os.path.join("data", "Collage_info.txt"))
        bit_block = _extract_lines_between(
            collage_text,
            "6. BACHELOR OF INFORMATION TECHNOLOGY (BIT)",
            ["====================================================\n7. ADMISSION REQUIREMENTS", "\n7. ADMISSION REQUIREMENTS"],
        )
        bit_overview = _extract_lines_between(bit_block, "PROGRAM OVERVIEW", ["CAREER OPPORTUNITIES"])
        bit_careers = _extract_lines_between(bit_block, "CAREER OPPORTUNITIES", ["====================================================", "7. ADMISSION REQUIREMENTS"])
        bit_focus = _clean_bullet_lines(_extract_lines_between(bit_block, "The curriculum emphasizes:", ["CAREER OPPORTUNITIES"]))
        bit_career_items = _clean_bullet_lines(bit_careers)
        summaries.append(
            "BIT: broader IT and systems focus; "
            + ("overview: " + " ".join([line for line in bit_overview.splitlines() if line and not line.startswith("-")][:2]).strip() if bit_overview else "overview: programming and networking")
            + "; focus: "
            + ", ".join(bit_focus[:5])
            + "; careers: "
            + ", ".join(bit_career_items[:6])
        )

    if "BASW" in programs:
        basw_text = _read_text_file(os.path.join("data", "BASW_Program.txt"))
        basw_overview = _extract_lines_between(
            basw_text,
            "## Program Overview",
            ["## Core Areas of Study", "## Career Opportunities"],
        )
        basw_focus = _clean_bullet_lines(_extract_lines_between(basw_text, "## Core Areas of Study", ["## Program Objectives", "## Practical Components"]))
        basw_careers = _clean_bullet_lines(_extract_lines_between(basw_text, "## Career Opportunities", []))
        summaries.append(
            "BASW: social work and community development focus; "
            + ("overview: " + " ".join([line for line in basw_overview.splitlines() if line and not line.startswith("-")][:2]).strip() if basw_overview else "overview: community development and counseling")
            + "; focus: "
            + ", ".join(basw_focus[:5])
            + "; careers: "
            + ", ".join(basw_careers[:6])
        )

    if "BBS" in programs:
        bbs_text = _read_text_file(os.path.join("data", "BBS_Program.txt"))
        bbs_overview = _extract_lines_between(
            bbs_text,
            "## Program Overview",
            ["## Major Study Areas", "## Career Opportunities"],
        )
        bbs_focus = _clean_bullet_lines(_extract_lines_between(bbs_text, "## Major Study Areas", ["## Skills Developed", "## Career Opportunities"]))
        bbs_careers = _clean_bullet_lines(_extract_lines_between(bbs_text, "## Career Opportunities", []))
        summaries.append(
            "BBS: business and management focus; "
            + ("overview: " + " ".join([line for line in bbs_overview.splitlines() if line and not line.startswith("-")][:2]).strip() if bbs_overview else "overview: business administration and finance")
            + "; focus: "
            + ", ".join(bbs_focus[:5])
            + "; careers: "
            + ", ".join(bbs_careers[:6])
        )

    if not summaries:
        return ""

    joined = " | ".join(summaries)
    return "Here is the difference in short: " + joined + "."


def _admission_info_fallback(query: str, context_chunks: List[str]) -> str:
    normalized = re.sub(r"[^a-z0-9\s]+", " ", query.lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()

    sections = {
        "general admission requirements": [],
        "required documents": [],
        "admission process": [],
        "important notes": [],
    }
    current_section = None

    for chunk in context_chunks:
        for raw_line in chunk.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            lowered = line.lower()
            if lowered.startswith("source:"):
                continue
            if line.startswith("##"):
                current_section = line.lstrip("#").strip().lower()
                continue
            if current_section in sections:
                if line.startswith("-") or re.match(r"^\d+\.", line):
                    cleaned = re.sub(r"^[\-\d\.\)\s]+", "", line).strip()
                    if cleaned and cleaned not in sections[current_section]:
                        sections[current_section].append(cleaned)
                elif current_section == "important notes" and line not in sections[current_section]:
                    sections[current_section].append(line)

    if "required documents" in normalized:
        items = sections["required documents"]
        if not items:
            return ""
        return "Required documents include: " + "; ".join(items) + "."

    if "process" in normalized or "how to apply" in normalized or "apply" in normalized:
        items = sections["admission process"]
        if not items:
            return ""
        return "Admission process: " + "; ".join(items) + "."

    items = sections["general admission requirements"]
    if not items:
        return ""

    prefix = "For " + ("BBS" if "bbs" in normalized else "BCA" if "bca" in normalized else "BASW" if "basw" in normalized else "undergraduate programs") + ", "
    response = prefix + "the admission requirements are: " + "; ".join(items) + "."
    notes = sections["important notes"]
    if notes:
        response += " Note: " + " ".join(notes) + "."
    return response


def _semester_info_fallback(query: str, context_chunks: List[str]) -> str:
    normalized = re.sub(r"[^a-z0-9\s]+", " ", query.lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()

    semester_line = ""
    learning_line = ""
    for chunk in context_chunks:
        for raw_line in chunk.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            lowered = line.lower()
            if lowered.startswith("source:"):
                continue
            if "semester-based academic structure" in lowered:
                semester_line = "Semester-based academic structure"
            if "practical and theoretical learning" in lowered:
                learning_line = "Practical and theoretical learning"

    if not semester_line and not learning_line:
        if "basw" in normalized:
            return "BASW follows a semester-based academic structure."
        if "bca" in normalized:
            return "BCA follows a semester-based academic structure."
        if "bbs" in normalized:
            return "BBS follows a semester-based academic structure."
        return "The undergraduate programs follow a semester-based academic structure."

    label = "BASW" if "basw" in normalized else "BCA" if "bca" in normalized else "BBS" if "bbs" in normalized else "undergraduate programs"
    parts = [semester_line] if semester_line else []
    if learning_line:
        parts.append(learning_line)
    return f"{label} follows a " + "; ".join(parts) + "."


def _bca_semester_info_fallback() -> str:
    path = os.path.join("data", "Collage_info.txt")
    if not os.path.exists(path):
        return ""

    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    start = text.find("BCA-IT COURSE STRUCTURE")
    if start == -1:
        return ""

    end_markers = [
        "\n====================================================\n4.",
        "\n4. BACHELOR OF INFORMATION TECHNOLOGY",
        "\n====================================================\n4. BACHELOR OF INFORMATION TECHNOLOGY",
    ]
    end = len(text)
    for marker in end_markers:
        idx = text.find(marker, start + 1)
        if idx != -1:
            end = min(end, idx)

    section = text[start:end]
    semesters: List[Tuple[str, List[str]]] = []
    current_label = None
    current_items: List[str] = []
    capture = False

    for raw_line in section.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        semester_match = re.search(r"YEAR\s+([IVX]+)\s*[–-]\s*SEMESTER\s+([IVX]+)", line, flags=re.IGNORECASE)
        if semester_match:
            if current_label:
                semesters.append((current_label, current_items))
            current_label = f"Year {semester_match.group(1).upper()} Semester {semester_match.group(2).upper()}"
            current_items = []
            capture = True
            continue
        if not capture:
            continue
        if line.startswith("-"):
            cleaned = line.lstrip("-").strip()
            if cleaned and cleaned not in current_items:
                current_items.append(cleaned)
        elif line.startswith("Core Courses:") or line.startswith("Humanities & Management:"):
            continue

    if current_label:
        semesters.append((current_label, current_items))

    if not semesters:
        return ""

    summary_parts = []
    for label, items in semesters[:4]:
        if items:
            summary_parts.append(f"{label}: " + ", ".join(items[:4]))
    if len(semesters) > 4:
        summary_parts.append("Later semesters continue with advanced topics, specialization, internship, and an apprentice project")

    return "BCA is a 4-year program divided into 8 semesters. " + ". ".join(summary_parts) + "."


def _program_eligibility_from_collage_info(query: str) -> str:
    path = os.path.join("data", "Collage_info.txt")
    if not os.path.exists(path):
        return ""

    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    start = text.find("PROGRAM ELIGIBILITY")
    if start == -1:
        return ""

    end_markers = [
        "\n====================================================\n8.",
        "\n8. SCHOLARSHIPS",
        "\n====================================================\n8. SCHOLARSHIPS",
    ]
    end = len(text)
    for marker in end_markers:
        idx = text.find(marker, start + 1)
        if idx != -1:
            end = min(end, idx)

    section = text[start:end]
    normalized = re.sub(r"[^a-z0-9\s]+", " ", query.lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()

    target = None
    if "bit" in normalized:
        target = "bit"
    elif "bca" in normalized:
        target = "bca"
    elif "bbs" in normalized:
        target = "bbs"
    elif "be computer" in normalized or ("be" in normalized and "computer" in normalized):
        target = "be computer"

    items: List[str] = []
    collecting = False
    for raw_line in section.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lowered = line.lower()
        if lowered.startswith("source:") or line.startswith("==="):
            continue
        if line in {"BCA", "BIT", "BBA", "BE Computer", "BE COMPUTER"}:
            collecting = target is not None and lowered == target
            continue
        if collecting and line.startswith("-"):
            cleaned = line.lstrip("-").strip()
            if cleaned and cleaned not in items:
                items.append(cleaned)

    if not items:
        return ""

    label = "BIT" if target == "bit" else "BCA" if target == "bca" else "BBS" if target == "bbs" else "BE Computer"
    return f"For {label}, the eligibility criteria are: " + "; ".join(items) + "."


def is_comparison_query(query: str) -> bool:
    lower_query = query.lower()
    comparison_words = ("difference", "compare", "comparison", "versus", "vs", "between", "better")
    return any(word in lower_query for word in comparison_words)


def is_bca_bit_comparison_query(query: str) -> bool:
    lower_query = query.lower()
    return ("bca" in lower_query) and ("bit" in lower_query) and is_comparison_query(query)


def _mentioned_programs(query: str) -> List[str]:
    lower_query = query.lower()
    programs = []
    for key in ("bca", "bit", "basw", "bbs"):
        if re.search(rf"\b{re.escape(key)}\b", lower_query):
            programs.append(key.upper())
    if "bca-it" in lower_query and "BCA" not in programs:
        programs.append("BCA")
    return programs


def is_program_comparison_query(query: str) -> bool:
    return is_comparison_query(query) and len(_mentioned_programs(query)) >= 2


def is_eligibility_query(query: str) -> bool:
    lower_query = query.lower()
    return "eligibility" in lower_query or "eligible" in lower_query


def is_admission_query(query: str) -> bool:
    lower_query = query.lower()
    return "admission" in lower_query or "admissions" in lower_query or "apply" in lower_query


def is_semester_query(query: str) -> bool:
    lower_query = query.lower()
    return "semester" in lower_query or "semesters" in lower_query or "structure" in lower_query


def is_bca_bit_career_query(query: str) -> bool:
    lower_query = query.lower()
    return ("bca" in lower_query) and ("bit" in lower_query) and ("career" in lower_query or "opportunity" in lower_query)


def is_college_related(query: str) -> bool:
    lower_query = query.lower()
    if any(keyword in lower_query for keyword in COLLEGE_KEYWORDS):
        return True

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a classifier. Answer only YES or NO."},
                {
                    "role": "user",
                    "content": f"Is this question about a college or education institution? Question: {query}",
                },
            ],
            max_tokens=5,
            temperature=0,
            timeout=20,
        )
        answer = response.choices[0].message.content.strip().upper()
        return "YES" in answer
    except Exception:
        logger.exception("College intent classifier failed; using general chat path.")
        return False


def _stream_response(messages: List[Dict[str, str]], temperature: float = 0.3) -> str:
    response_text = ""
    try:
        stream = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            stream=True,
            temperature=temperature,
            max_tokens=800,
            timeout=90,
        )

        for chunk in stream:
            token = chunk.choices[0].delta.content
            if token:
                response_text += clean_markdown(token)
    except Exception as exc:
        logger.exception("Local LLM request failed.")
        raise ChatServiceError("The local language model is not responding. Please start Lemonade and try again.") from exc

    return clean_markdown(response_text)


def generate_answer_from_context(query: str, context_chunks: List[str], chat_history: List[Dict[str, str]]) -> str:
    context = "\n\n".join(context_chunks)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += chat_history.copy()
    messages.append(
        {
            "role": "user",
            "content": f"""Known college information:
{context}

Question:
{query}

Answer naturally as the receptionist using ONLY the known college information above.
Do not mention documents, context, database, or sources.
If the answer is not present, reply exactly: I don't know from the document.""",
        }
    )
    return _stream_response(messages, temperature=0.2)


def generate_general_answer(query: str, chat_history: List[Dict[str, str]]) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += chat_history.copy()
    messages.append({"role": "user", "content": query})
    return _stream_response(messages, temperature=0.5)


def generate_comparison_answer(query: str, context_chunks: List[str], chat_history: List[Dict[str, str]]) -> str:
    context = "\n\n".join(context_chunks)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += chat_history.copy()
    messages.append(
        {
            "role": "user",
            "content": f"""Known college information:
{context}

Question:
{query}

Compare the two programs clearly and directly using only the known college information above.
If one detail is not clearly stated, say that it is not clearly stated."""
        }
    )
    return _stream_response(messages, temperature=0.2)


def answer_receptionist(query: str, chat_history: List[Dict[str, str]]) -> Tuple[str, Dict[str, str]]:
    query = normalize_query(query.strip())
    if not query:
        raise ValueError("Message cannot be empty.")

    if is_simple_greeting(query):
        response = greeting_answer(query)
        chat_history.clear()
        chat_history.append({"role": "user", "content": query})
        chat_history.append({"role": "assistant", "content": response})
        return response, {"source": "greeting", "model": "deterministic"}

    if is_schedule_query(query):
        response = answer_schedule_query(query)
        chat_history.append({"role": "user", "content": query})
        chat_history.append({"role": "assistant", "content": response})
        return response, {"source": "schedule_time", "model": "deterministic"}

    if is_program_comparison_query(query):
        response = _program_comparison_answer(query)
        if response:
            chat_history.append({"role": "user", "content": query})
            chat_history.append({"role": "assistant", "content": response})
            return response, {"source": "program_comparison", "model": "deterministic"}

    if is_eligibility_query(query):
        if "bit" in query.lower():
            response = _program_eligibility_from_collage_info(query)
            if response:
                chat_history.append({"role": "user", "content": query})
                chat_history.append({"role": "assistant", "content": response})
                return response, {"source": "Collage_info", "model": MODEL_NAME}
        retrieved_chunks, source_name = search_all_indexes(query)
        if not retrieved_chunks:
            retrieved_chunks, source_name = search_multiple_indexes(query, max_sources=2)
        if retrieved_chunks and source_name and source_name.lower() in ELIGIBILITY_STYLE_SOURCES:
            response = _eligibility_info_fallback(query, retrieved_chunks) or generate_answer_from_context(query, retrieved_chunks, chat_history)
            source = source_name
            chat_history.append({"role": "user", "content": query})
            chat_history.append({"role": "assistant", "content": response})
            return response, {"source": source, "model": MODEL_NAME}

    if is_admission_query(query):
        retrieved_chunks, source_name = search_all_indexes(query)
        if not retrieved_chunks:
            retrieved_chunks, source_name = search_multiple_indexes(query, max_sources=2)
        if retrieved_chunks and source_name and source_name.lower() in ADMISSION_STYLE_SOURCES:
            response = _admission_info_fallback(query, retrieved_chunks) or generate_answer_from_context(query, retrieved_chunks, chat_history)
            source = source_name
            chat_history.append({"role": "user", "content": query})
            chat_history.append({"role": "assistant", "content": response})
            return response, {"source": source, "model": MODEL_NAME}

    if is_semester_query(query):
        if "bca" in query.lower():
            response = _bca_semester_info_fallback() or ""
            if response:
                chat_history.append({"role": "user", "content": query})
                chat_history.append({"role": "assistant", "content": response})
                return response, {"source": "Collage_info", "model": MODEL_NAME}
        retrieved_chunks, source_name = search_all_indexes(query)
        if not retrieved_chunks:
            retrieved_chunks, source_name = search_multiple_indexes(query, max_sources=2)
        if retrieved_chunks and source_name and source_name.lower() in {"undergraduate_programs", "basw_program", "bca_program", "bbs_program"}:
            response = _semester_info_fallback(query, retrieved_chunks) or generate_answer_from_context(query, retrieved_chunks, chat_history)
            source = source_name
            chat_history.append({"role": "user", "content": query})
            chat_history.append({"role": "assistant", "content": response})
            return response, {"source": source, "model": MODEL_NAME}

    if is_bca_bit_career_query(query):
        response = _bca_bit_career_info_fallback()
        if response:
            chat_history.append({"role": "user", "content": query})
            chat_history.append({"role": "assistant", "content": response})
            return response, {"source": "Collage_info", "model": MODEL_NAME}

    if "career" in query.lower() or "opportunity" in query.lower():
        retrieved_chunks, source_name = search_all_indexes(query)
        if not retrieved_chunks:
            retrieved_chunks, source_name = search_multiple_indexes(query, max_sources=2)
        if retrieved_chunks and source_name and source_name.lower() in {
            "career_opportunities",
            "career opportunities",
            "basw_program",
            "bbs_program",
            "bca_program",
            "basw program",
            "bbs program",
            "bca program",
        }:
            response = _career_info_fallback(query, retrieved_chunks) or generate_answer_from_context(query, retrieved_chunks, chat_history)
            source = source_name
            chat_history.append({"role": "user", "content": query})
            chat_history.append({"role": "assistant", "content": response})
            return response, {"source": source, "model": MODEL_NAME}

    source = "general"
    if is_college_related(query):
        if is_bca_bit_comparison_query(query):
            retrieved_chunks, source_name = search_multiple_indexes(query, max_sources=2)
            source = source_name or "college_index"
            if not retrieved_chunks:
                retrieved_chunks, source_name = search_all_indexes(query)
                source = source_name or "college_index"
            response = generate_comparison_answer(query, retrieved_chunks, chat_history)
        else:
            retrieved_chunks, source_name = search_all_indexes(query)
            if not retrieved_chunks:
                retrieved_chunks, source_name = search_multiple_indexes(query, max_sources=2)
            if retrieved_chunks:
                source = source_name or "college_index"
                if source and source.lower() == "greeting":
                    response = _greeting_info_fallback(retrieved_chunks)
                elif source and source.lower() in {"contact_information", "contact information"}:
                    response = _contact_info_fallback(query, retrieved_chunks) or generate_answer_from_context(query, retrieved_chunks, chat_history)
                elif source and source.lower() in PROGRAM_STYLE_SOURCES:
                    response = _program_info_fallback(source, retrieved_chunks) or generate_answer_from_context(query, retrieved_chunks, chat_history)
                elif source and source.lower() in ELIGIBILITY_STYLE_SOURCES:
                    response = _eligibility_info_fallback(query, retrieved_chunks) or generate_answer_from_context(query, retrieved_chunks, chat_history)
                elif source and source.lower() == "collage team":
                    response = _team_role_fallback(query, retrieved_chunks) or _list_style_fallback(source, retrieved_chunks) or generate_answer_from_context(query, retrieved_chunks, chat_history)
                elif source and source.lower() in LIST_STYLE_SOURCES:
                    response = _team_role_fallback(query, retrieved_chunks) or _list_style_fallback(source, retrieved_chunks) or generate_answer_from_context(query, retrieved_chunks, chat_history)
                else:
                    response = generate_answer_from_context(query, retrieved_chunks, chat_history)
                    if _is_refusal_response(response):
                        logger.info("Document context did not answer query; keeping grounded refusal.")
                        fallback_response = _list_style_fallback(source, retrieved_chunks)
                        if fallback_response:
                            response = fallback_response
                            logger.info("Using list-style fallback for %s.", source)
                        if is_bca_it_query(query):
                            response = bca_it_fallback_answer()
            else:
                source = "college_no_retrieval"
                response = bca_it_fallback_answer() if is_bca_it_query(query) else "I don't know from the document."
    else:
        response = generate_general_answer(query, chat_history)

    chat_history.append({"role": "user", "content": query})
    chat_history.append({"role": "assistant", "content": response})
    return response, {"source": source, "model": MODEL_NAME}


def check_llm_health() -> Dict[str, str]:
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "Reply with OK."},
                {"role": "user", "content": "health"},
            ],
            max_tokens=5,
            temperature=0,
            timeout=10,
        )
        return {"status": "ready", "detail": response.choices[0].message.content.strip()}
    except Exception as exc:
        logger.warning("Lemonade health check failed: %s", exc)
        return {"status": "unavailable", "detail": "Start Lemonade on http://127.0.0.1:13305."}
