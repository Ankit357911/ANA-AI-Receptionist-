import re
from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo


BASE_DIR = Path(__file__).resolve().parent.parent
SCHEDULE_PATH = BASE_DIR / "data" / "schedule.txt"
LOCAL_TIMEZONE = ZoneInfo("Asia/Kathmandu")


@dataclass(frozen=True)
class ScheduleEntry:
    teacher: str
    start: time
    end: time
    activity: str


SCHEDULE_QUERY_TERMS = (
    "where",
    "right now",
    "now",
    "currently",
    "schedule",
    "class",
    "available",
    "free",
    "busy",
    "time",
    "teaching",
)


def is_schedule_query(query: str) -> bool:
    lower = query.lower()
    if not any(term in lower for term in SCHEDULE_QUERY_TERMS):
        return False
    return bool(extract_teacher_name(query)) or any(
        term in lower for term in ("teacher", "sir", "maam", "mam", "lecturer", "class", "teaching")
    )


def is_ravi_schedule_query(query: str) -> bool:
    return is_schedule_query(query) and "ravi" in query.lower()


def answer_schedule_query(query: str, now: datetime | None = None) -> str:
    schedules = load_teacher_schedules()
    now = now or datetime.now(LOCAL_TIMEZONE)
    teacher_name = extract_teacher_name(query)
    if teacher_name:
        return answer_teacher_schedule(teacher_name, schedules, now)

    current_entries = []
    for entries in schedules.values():
        current = current_schedule_entry(entries, now.time())
        if current:
            current_entries.append(current)

    clock = now.strftime("%I:%M %p").lstrip("0")
    if not current_entries:
        return f"Right now, it is {clock}. I don't see any teacher scheduled at this exact time."

    items = [
        f"{entry.teacher} is scheduled for {entry.activity} from {format_time(entry.start)} to {format_time(entry.end)}"
        for entry in current_entries
    ]
    return f"Right now, it is {clock}. " + " ".join(items) + "."


def answer_ravi_schedule(query: str, now: datetime | None = None) -> str:
    return answer_teacher_schedule("Ravi Sir", load_teacher_schedules(), now or datetime.now(LOCAL_TIMEZONE))


def answer_teacher_schedule(teacher_name: str, schedules: dict[str, list[ScheduleEntry]], now: datetime) -> str:
    entries = find_teacher_schedule(teacher_name, schedules)
    now = now or datetime.now(LOCAL_TIMEZONE)
    display_name = teacher_name.strip().title()
    if not entries:
        return f"I don't know {display_name}'s schedule from the document."

    current = current_schedule_entry(entries, now.time())
    clock = now.strftime("%I:%M %p").lstrip("0")

    if current:
        return f"Right now, it is {clock}. {current.teacher} is scheduled for {current.activity} from {format_time(current.start)} to {format_time(current.end)}."

    if entries and now.time() < entries[0].start:
        return f"Right now, it is {clock}. {entries[0].teacher}'s scheduled working hours start at {format_time(entries[0].start)}."
    if entries and now.time() >= entries[-1].end:
        return f"Right now, it is {clock}. {entries[-1].teacher}'s scheduled working hours ended at {format_time(entries[-1].end)}."
    return "I don't know from the document."


def load_ravi_schedule() -> list[ScheduleEntry]:
    return find_teacher_schedule("Ravi Sir", load_teacher_schedules())


def load_teacher_schedules() -> dict[str, list[ScheduleEntry]]:
    if not SCHEDULE_PATH.exists():
        return {}

    lines = [line.strip() for line in SCHEDULE_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()]
    schedules: dict[str, list[ScheduleEntry]] = {}
    current_teacher = "Ravi Sir"
    time_pattern = re.compile(r"^(\d{1,2}:\d{2}\s*[AP]M)\s*-\s*(\d{1,2}:\d{2}\s*[AP]M)$", re.IGNORECASE)

    index = 0
    while index < len(lines):
        name_match = re.match(r"^Name:\s*(.+)$", lines[index], flags=re.IGNORECASE)
        if name_match:
            current_teacher = normalize_teacher_name(name_match.group(1))
            schedules.setdefault(current_teacher.lower(), [])
            index += 1
            continue

        match = time_pattern.match(lines[index])
        if not match:
            index += 1
            continue

        activity = ""
        cursor = index + 1
        while cursor < len(lines) and not lines[cursor]:
            cursor += 1
        if cursor < len(lines):
            activity = re.sub(r"^Class:\s*", "", lines[cursor], flags=re.IGNORECASE).strip()

        if activity:
            teacher = normalize_teacher_name(current_teacher)
            schedules.setdefault(teacher.lower(), []).append(
                ScheduleEntry(
                    teacher=teacher,
                    start=parse_time(match.group(1)),
                    end=parse_time(match.group(2)),
                    activity=activity,
                )
            )
        index = cursor + 1

    return schedules


def find_teacher_schedule(teacher_name: str, schedules: dict[str, list[ScheduleEntry]]) -> list[ScheduleEntry]:
    normalized = normalize_teacher_name(teacher_name).lower()
    if normalized in schedules:
        return schedules[normalized]
    short_name = re.sub(r"\b(sir|maam|mam|teacher|lecturer)\b", "", normalized).strip()
    for name, entries in schedules.items():
        if short_name and short_name in name:
            return entries
    return []


def extract_teacher_name(query: str) -> str | None:
    match = re.search(r"\b([A-Za-z][A-Za-z\s]{0,60}?)\s+(sir|maam|mam|teacher|lecturer)\b", query, flags=re.IGNORECASE)
    if match:
        stopwords = {
            "where",
            "what",
            "who",
            "when",
            "how",
            "is",
            "are",
            "was",
            "the",
            "now",
            "right",
            "currently",
            "schedule",
            "class",
            "of",
            "for",
            "busy",
            "free",
        }
        words = [word for word in re.findall(r"[A-Za-z]+", match.group(1).lower()) if word not in stopwords]
        if not words:
            return None
        name_words = words[-3:]
        return normalize_teacher_name(f"{' '.join(name_words)} {match.group(2)}")
    return None


def normalize_teacher_name(value: str) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    if not value:
        return value
    return " ".join(part.capitalize() for part in value.split())


def current_schedule_entry(entries: list[ScheduleEntry], current_time: time) -> ScheduleEntry | None:
    for entry in entries:
        if entry.start <= current_time < entry.end:
            return entry
    return None


def parse_time(value: str) -> time:
    return datetime.strptime(re.sub(r"\s+", " ", value.strip()).upper(), "%I:%M %p").time()


def format_time(value: time) -> str:
    return datetime.combine(datetime.today(), value).strftime("%I:%M %p").lstrip("0")
