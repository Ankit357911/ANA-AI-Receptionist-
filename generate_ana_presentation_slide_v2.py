from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter


ROOT = Path(__file__).resolve().parent
OUT_PNG = ROOT / "docs" / "ana_presentation_slide_v2.png"
OUT_PDF = ROOT / "docs" / "ana_presentation_slide_v2.pdf"
AVATAR = ROOT / "assets" / "avatar" / "nepali_receptionist_neutral.png"

W, H = 1920, 1080


def load_font(names, size):
    windows_fonts = Path(r"C:\Windows\Fonts")
    for name in names:
        path = windows_fonts / name
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


FONT_TITLE = load_font(["calibrib.ttf", "arialbd.ttf"], 74)
FONT_H1 = load_font(["calibrib.ttf", "arialbd.ttf"], 32)
FONT_H2 = load_font(["calibrib.ttf", "arialbd.ttf"], 28)
FONT_BODY = load_font(["calibri.ttf", "arial.ttf"], 23)
FONT_SMALL = load_font(["calibri.ttf", "arial.ttf"], 20)
FONT_TINY = load_font(["calibri.ttf", "arial.ttf"], 17)
FONT_BADGE = load_font(["calibrib.ttf", "arialbd.ttf"], 21)


def text_h(font):
    bb = font.getbbox("Ag")
    return bb[3] - bb[1]


def wrap_text(draw, text, font, max_width):
    lines = []
    current = ""
    for word in text.split():
        trial = word if not current else current + " " + word
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_wrapped(draw, x, y, text, font, fill, max_width, line_gap=5):
    yy = y
    for line in wrap_text(draw, text, font, max_width):
        draw.text((x, yy), line, font=font, fill=fill)
        yy += text_h(font) + line_gap
    return yy


def shadow_card(base, xy, radius, fill, shadow=(0, 12), blur=24):
    shadow_layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow_layer)
    x1, y1, x2, y2 = xy
    ox, oy = shadow
    sdraw.rounded_rectangle((x1 + ox, y1 + oy, x2 + ox, y2 + oy), radius=radius, fill=(0, 0, 0, 100))
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(blur))
    base.alpha_composite(shadow_layer)
    draw = ImageDraw.Draw(base)
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


def pill(draw, xy, text, outline, fill=(20, 35, 63, 255), text_fill=(245, 248, 252, 255), font=FONT_SMALL):
    draw.rounded_rectangle(xy, radius=16, fill=fill, outline=outline, width=2)
    x1, y1, x2, y2 = xy
    tw = draw.textlength(text, font=font)
    th = text_h(font)
    draw.text((x1 + (x2 - x1 - tw) / 2, y1 + (y2 - y1 - th) / 2 - 1), text, font=font, fill=text_fill)


def bullet(draw, x, y, text, font, fill, bullet_fill, max_width, gap=5):
    draw.ellipse((x, y + 9, x + 8, y + 17), fill=bullet_fill)
    return draw_wrapped(draw, x + 18, y, text, font, fill, max_width, line_gap=gap)


def main():
    base = Image.new("RGBA", (W, H), (8, 15, 37, 255))
    draw = ImageDraw.Draw(base)

    # Background gradient
    for y in range(H):
        t = y / (H - 1)
        r = int(8 * (1 - t) + 11 * t)
        g = int(15 * (1 - t) + 30 * t)
        b = int(37 * (1 - t) + 60 * t)
        draw.line((0, y, W, y), fill=(r, g, b, 255))

    # Atmosphere
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((40, 30, 620, 420), fill=(50, 214, 194, 92))
    gd.ellipse((1370, 30, 1930, 420), fill=(255, 171, 58, 68))
    gd.ellipse((1230, 680, 1820, 1100), fill=(84, 124, 255, 56))
    gd.ellipse((90, 760, 500, 1100), fill=(105, 94, 255, 48))
    glow = glow.filter(ImageFilter.GaussianBlur(30))
    base.alpha_composite(glow)
    draw = ImageDraw.Draw(base)

    # Left rail
    draw.rounded_rectangle((84, 106, 88, 952), radius=2, fill=(255, 255, 255, 32))
    draw.rounded_rectangle((84, 106, 140, 110), radius=2, fill=(69, 215, 196, 180))
    for cy in (192, 244, 296):
        draw.ellipse((70, cy - 8, 86, cy + 8), fill=(255, 255, 255, 150))

    # Title block
    draw.text((118, 124), "ANA", font=FONT_TITLE, fill=(255, 255, 255, 255))
    draw.text((315, 146), "AI Receptionist", font=FONT_H1, fill=(151, 233, 224, 255))
    draw.text((118, 214), "Your Smart College Front Desk Assistant", font=FONT_H2, fill=(243, 247, 252, 255))
    draw.text((118, 262), "BCA 8th Semester Project · Kantipur City College · 2026", font=FONT_BODY, fill=(205, 219, 236, 255))
    draw.text((118, 318), "Created by: Ankit Chandra Karn  ·  Srijan Basnet  ·  Suraj Panthi", font=FONT_BODY, fill=(205, 219, 236, 255))

    # Intro card
    intro_xy = (108, 382, 1088, 498)
    shadow_card(base, intro_xy, 28, (15, 28, 57, 235), blur=22)
    draw.rounded_rectangle(intro_xy, radius=28, outline=(69, 215, 196, 78), width=2)
    draw.text((138, 406), "Introduction", font=FONT_H1, fill=(255, 255, 255, 255))
    intro = (
        "ANA is an intelligent virtual assistant for Kantipur City College that answers "
        "college-related questions in a natural, conversational manner."
    )
    draw_wrapped(draw, 138, 448, intro, FONT_BODY, (226, 235, 245, 255), 910)

    # Problem / Solution card
    ps_xy = (108, 524, 1088, 724)
    shadow_card(base, ps_xy, 28, (15, 28, 57, 235), blur=22)
    draw.rounded_rectangle(ps_xy, radius=28, outline=(97, 88, 255, 80), width=2)
    mid_x = 598
    draw.line((598, 548, 598, 704), fill=(255, 255, 255, 20), width=2)
    pill(draw, (138, 546, 286, 582), "The Problem", (97, 88, 255, 140), fill=(55, 50, 120, 255), font=FONT_BADGE)
    pill(draw, (626, 546, 802, 582), "The Solution", (245, 166, 35, 140), fill=(88, 60, 20, 255), font=FONT_BADGE)
    problem_lines = [
        "College enquiries are repetitive.",
        "Generic chatbots lack institution context.",
        "Voice and avatar systems can be slow to run.",
    ]
    solution_lines = [
        "Grounded answers from real college documents.",
        "One local app for text, voice, and avatar modes.",
        "Optimized for fast response and low dependency.",
    ]
    yy = 592
    for line in problem_lines:
        yy = bullet(draw, 138, yy, line, FONT_BODY, (233, 238, 246, 255), (97, 88, 255, 255), 420, gap=2) + 8
    yy = 592
    for line in solution_lines:
        yy = bullet(draw, 626, yy, line, FONT_BODY, (233, 238, 246, 255), (245, 166, 35, 255), 430, gap=2) + 8

    # Objectives / Features card
    of_xy = (108, 748, 1088, 902)
    shadow_card(base, of_xy, 28, (15, 28, 57, 235), blur=22)
    draw.rounded_rectangle(of_xy, radius=28, outline=(69, 215, 196, 80), width=2)
    draw.text((138, 772), "Objectives", font=FONT_H1, fill=(255, 255, 255, 255))
    draw.text((628, 772), "Key Features", font=FONT_H1, fill=(255, 255, 255, 255))
    obj_items = [
        "AI-powered receptionist",
        "Document-grounded answers with FAISS",
        "Text and voice interaction",
    ]
    fy = 820
    for item in obj_items:
        fy = bullet(draw, 138, fy, item, FONT_SMALL, (226, 235, 245, 255), (69, 215, 196, 255), 430, gap=3) + 4

    pill(draw, (626, 820, 748, 856), "Smart Chat", (69, 215, 196, 120), font=FONT_SMALL)
    pill(draw, (762, 820, 910, 856), "Voice", (97, 88, 255, 120), font=FONT_SMALL)
    pill(draw, (626, 866, 760, 902), "Avatar", (245, 166, 35, 120), font=FONT_SMALL)
    pill(draw, (774, 866, 930, 902), "Local", (255, 255, 255, 60), font=FONT_SMALL)

    # Workflow strip
    wf_xy = (108, 930, 1088, 1038)
    shadow_card(base, wf_xy, 24, (14, 26, 50, 235), blur=20)
    draw.rounded_rectangle(wf_xy, radius=24, outline=(255, 255, 255, 24), width=1)
    draw.text((132, 950), "Workflow", font=FONT_H1, fill=(159, 232, 224, 255))
    flow = [("User", 300), ("Intent", 398), ("FAISS", 514), ("LLM", 618), ("Voice", 706)]
    widths = {"User": 74, "Intent": 92, "FAISS": 82, "LLM": 64, "Voice": 82}
    outlines = {
        "User": (255, 255, 255, 50),
        "Intent": (69, 215, 196, 110),
        "FAISS": (97, 88, 255, 110),
        "LLM": (245, 166, 35, 110),
        "Voice": (255, 255, 255, 50),
    }
    for i, (label, x) in enumerate(flow):
        w = widths[label]
        pill(draw, (x, 948, x + w, 984), label, outlines[label], font=FONT_TINY)
        if i < len(flow) - 1:
            ax1 = x + w + 8
            ax2 = ax1 + 28
            ay = 966
            draw.line((ax1, ay, ax2, ay), fill=(206, 214, 227, 180), width=3)
            draw.polygon([(ax2, ay), (ax2 - 8, ay - 6), (ax2 - 8, ay + 6)], fill=(206, 214, 227, 180))
    draw.text((132, 1000), "Python · FastAPI · FAISS · Qwen3-1.7B-GGUF · faster-whisper · Kokoro TTS · Wav2Lip · JavaScript", font=FONT_TINY, fill=(184, 194, 208, 255))

    # Right panel
    right_xy = (1218, 112, 1812, 972)
    shadow_card(base, right_xy, 40, (12, 24, 47, 248), blur=32)
    draw.rounded_rectangle(right_xy, radius=40, outline=(255, 255, 255, 24), width=1)

    # Avatar
    frame = (1260, 156, 1770, 690)
    draw.rounded_rectangle(frame, radius=34, fill=(21, 34, 61, 255), outline=(255, 255, 255, 25), width=1)
    avatar = Image.open(AVATAR).convert("RGBA")
    tw = frame[2] - frame[0] - 24
    th = frame[3] - frame[1] - 24
    ar = avatar.width / avatar.height
    tr = tw / th
    if ar > tr:
        nh = th
        nw = int(nh * ar)
    else:
        nw = tw
        nh = int(nw / ar)
    avatar = avatar.resize((nw, nh), Image.Resampling.LANCZOS)
    cx = max(0, (nw - tw) // 2)
    cy = max(0, (nh - th) // 2)
    avatar = avatar.crop((cx, cy, cx + tw, cy + th))
    mask = Image.new("L", (tw, th), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, tw, th), radius=28, fill=255)
    base.paste(avatar, (frame[0] + 12, frame[1] + 12), mask)

    draw.text((1260, 724), "What ANA Delivers", font=FONT_H1, fill=(255, 255, 255, 255))
    desc = (
        "A single local assistant for students, parents, visitors, and staff with "
        "grounded answers, natural speech, and a human-like receptionist experience."
    )
    draw_wrapped(draw, 1260, 772, desc, FONT_BODY, (223, 231, 242, 255), 470)

    draw.text((1260, 852), "Future Scope", font=FONT_H2, fill=(159, 232, 224, 255))
    future_text = "Multilingual; admin dashboard; kiosk; real-time avatars"
    draw.text((1260, 886), future_text, font=FONT_TINY, fill=(226, 235, 245, 255))

    # Impact chips
    chip_y = 904
    chips = [
        ("3 Modes", "Text / Voice / Avatar", 1260, 132),
        ("Local", "On-premise", 1410, 108),
        ("<2s", "Audio response", 1542, 102),
    ]
    chip_colors = [(69, 215, 196, 90), (97, 88, 255, 90), (245, 166, 35, 90)]
    for (big, small, x, w), color in zip(chips, chip_colors):
        draw.rounded_rectangle((x, chip_y, x + w, chip_y + 58), radius=18, fill=(18, 34, 64, 255), outline=color, width=2)
        draw.text((x + 16, chip_y + 10), big, font=FONT_H1, fill=(255, 255, 255, 255))
        draw.text((x + 16, chip_y + 36), small, font=FONT_TINY, fill=(193, 205, 221, 255))

    # Footer
    draw.text((108, 1046), "ANA - Making college reception smarter, faster, and more human.", font=FONT_SMALL, fill=(178, 190, 206, 255))

    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    base.convert("RGB").save(OUT_PNG, quality=95)

    try:
        from fpdf import FPDF

        pdf = FPDF(orientation="L", unit="mm", format="A4")
        pdf.set_auto_page_break(False)
        pdf.add_page()
        pdf.image(str(OUT_PNG), x=0, y=0, w=297, h=210)
        pdf.output(str(OUT_PDF))
    except Exception as exc:
        print(f"PDF export skipped: {exc}")

    print(f"Saved {OUT_PNG}")
    print(f"Saved {OUT_PDF}")


if __name__ == "__main__":
    main()
