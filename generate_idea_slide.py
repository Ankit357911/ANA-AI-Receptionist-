from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pathlib import Path
import math


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs" / "idea_presentation_slide.png"
AVATAR = ROOT / "assets" / "avatar" / "nepali_receptionist_neutral.png"


W, H = 1920, 1080


def font(name: str, size: int):
    candidates = [
        Path(r"C:\Windows\Fonts") / name,
        Path(r"C:\Windows\Fonts") / "arial.ttf",
        Path(r"C:\Windows\Fonts") / "calibri.ttf",
    ]
    for path in candidates:
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                pass
    return ImageFont.load_default()


FONT_TITLE = font("calibrib.ttf", 74)
FONT_SUB = font("calibri.ttf", 28)
FONT_SECTION = font("calibrib.ttf", 34)
FONT_BODY = font("calibri.ttf", 28)
FONT_SMALL = font("calibri.ttf", 22)
FONT_BADGE = font("calibrib.ttf", 24)
FONT_WORKFLOW = font("calibrib.ttf", 26)


def wrap_text(draw, text, fnt, max_width):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        trial = word if not current else current + " " + word
        if draw.textlength(trial, font=fnt) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def rounded_panel(draw, xy, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def shadow_panel(base, xy, radius, fill, shadow_offset=(0, 12), shadow_blur=28):
    shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sx1, sy1, sx2, sy2 = xy
    ox, oy = shadow_offset
    sdraw.rounded_rectangle(
        (sx1 + ox, sy1 + oy, sx2 + ox, sy2 + oy),
        radius=radius,
        fill=(0, 0, 0, 110),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(shadow_blur))
    base.alpha_composite(shadow)
    draw = ImageDraw.Draw(base)
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


def draw_glow(draw, cx, cy, rx, ry, color):
    draw.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=color)


def place_wrapped(draw, x, y, text, fnt, fill, max_width, line_gap=8):
    lines = wrap_text(draw, text, fnt, max_width)
    yy = y
    for line in lines:
        draw.text((x, yy), line, font=fnt, fill=fill)
        yy += fnt.size + line_gap
    return yy


def main():
    base = Image.new("RGBA", (W, H), (10, 18, 42, 255))
    draw = ImageDraw.Draw(base)

    # Background gradient
    for y in range(H):
        t = y / (H - 1)
        r = int(8 * (1 - t) + 10 * t)
        g = int(18 * (1 - t) + 30 * t)
        b = int(46 * (1 - t) + 58 * t)
        draw.line((0, y, W, y), fill=(r, g, b, 255))

    # Ambient glows
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    draw_glow(gdraw, 220, 170, 240, 160, (44, 211, 190, 90))
    draw_glow(gdraw, 1660, 160, 260, 220, (245, 166, 35, 70))
    draw_glow(gdraw, 1500, 860, 280, 220, (73, 132, 255, 60))
    draw_glow(gdraw, 320, 900, 320, 240, (97, 88, 255, 50))
    glow = glow.filter(ImageFilter.GaussianBlur(20))
    base.alpha_composite(glow)
    draw = ImageDraw.Draw(base)

    # Decorative lines and nodes
    accent = (69, 215, 196, 160)
    draw.rounded_rectangle((92, 110, 148, 114), radius=2, fill=accent)
    draw.rounded_rectangle((92, 110, 92, 350), radius=2, fill=(255, 255, 255, 30))
    for cy in [200, 250, 300]:
        draw.ellipse((78, cy - 8, 94, cy + 8), fill=(255, 255, 255, 120))

    # Title block
    draw.text((118, 132), "ANA AI Receptionist", font=FONT_SMALL, fill=(159, 232, 224, 255))
    draw.text((118, 168), "Idea Presentation Slide", font=FONT_TITLE, fill=(255, 255, 255, 255))
    subtitle = (
        "A voice-enabled RAG assistant that answers admissions, programs, schedules, "
        "and contact questions from official college documents."
    )
    place_wrapped(draw, 118, 264, subtitle, FONT_SUB, (214, 224, 240, 255), 980)

    # Left panel cards
    card_x1 = 118
    card_w = 760
    card_h = 150
    card_gap = 18
    card_top = 372
    cards = [
        ("Problem", "College enquiries are repetitive, information is scattered, and office support is limited to working hours."),
        ("Idea", "Use one conversational assistant that listens, retrieves grounded answers, and responds naturally in voice or chat."),
        ("Impact", "Faster replies, fewer manual interruptions, and consistent answers for students, parents, and visitors."),
    ]

    fills = [(18, 34, 70, 230), (18, 42, 58, 230), (24, 36, 68, 230)]
    outlines = [(69, 215, 196, 70), (97, 88, 255, 70), (245, 166, 35, 70)]
    for i, ((heading, body), fill, outline) in enumerate(zip(cards, fills, outlines)):
        top = card_top + i * (card_h + card_gap)
        shadow_panel(base, (card_x1, top, card_x1 + card_w, top + card_h), 28, fill)
        draw.rounded_rectangle((card_x1, top, card_x1 + card_w, top + card_h), radius=28, outline=outline, width=2)
        # Section label chip
        chip_fill = (69, 215, 196, 30) if heading == "Problem" else (97, 88, 255, 30) if heading == "Idea" else (245, 166, 35, 34)
        chip_text = (111, 246, 228, 255) if heading == "Problem" else (196, 192, 255, 255) if heading == "Idea" else (255, 213, 143, 255)
        chip_w = 170 if heading != "Impact" else 180
        draw.rounded_rectangle((card_x1 + 28, top + 24, card_x1 + 28 + chip_w, top + 24 + 42), radius=18, fill=chip_fill)
        draw.text((card_x1 + 46, top + 29), heading, font=FONT_SECTION, fill=chip_text)
        place_wrapped(draw, card_x1 + 28, top + 78, body, FONT_BODY, (240, 244, 250, 255), card_w - 56)

    # Workflow strip
    strip_y = 884
    strip_x = 118
    strip_w = 1048
    strip_h = 92
    shadow_panel(base, (strip_x, strip_y, strip_x + strip_w, strip_y + strip_h), 28, (13, 24, 48, 235), shadow_blur=24)
    draw.rounded_rectangle((strip_x, strip_y, strip_x + strip_w, strip_y + strip_h), radius=28, outline=(255, 255, 255, 25), width=1)
    draw.text((144, strip_y + 18), "Workflow", font=FONT_BADGE, fill=(159, 232, 224, 255))

    steps = ["User", "STT", "Retriever", "LLM", "Voice"]
    xs = [290, 430, 600, 780, 930]
    for idx, step in enumerate(steps):
        x = xs[idx]
        label_w = draw.textlength(step, font=FONT_WORKFLOW)
        pill_w = int(label_w + 46)
        pill_x1 = x
        pill_y1 = strip_y + 28
        pill_x2 = pill_x1 + pill_w
        pill_y2 = pill_y1 + 44
        fill = (21, 46, 86, 255) if idx % 2 == 0 else (26, 61, 97, 255)
        outline = (69, 215, 196, 120) if idx == 1 else (97, 88, 255, 110) if idx == 2 else (245, 166, 35, 100) if idx == 3 else (255, 255, 255, 40)
        draw.rounded_rectangle((pill_x1, pill_y1, pill_x2, pill_y2), radius=20, fill=fill, outline=outline, width=2)
        draw.text((pill_x1 + 22, pill_y1 + 8), step, font=FONT_WORKFLOW, fill=(246, 248, 252, 255))
        if idx < len(steps) - 1:
            ax1 = pill_x2 + 12
            ax2 = ax1 + 44
            ay = strip_y + 50
            draw.line((ax1, ay, ax2, ay), fill=(194, 203, 216, 180), width=4)
            draw.polygon([(ax2, ay), (ax2 - 10, ay - 7), (ax2 - 10, ay + 7)], fill=(194, 203, 216, 180))

    # Right hero panel
    hero_x1, hero_y1 = 1208, 120
    hero_x2, hero_y2 = 1810, 980
    shadow_panel(base, (hero_x1, hero_y1, hero_x2, hero_y2), 40, (12, 24, 44, 245), shadow_blur=34)
    draw.rounded_rectangle((hero_x1, hero_y1, hero_x2, hero_y2), radius=40, outline=(255, 255, 255, 22), width=1)

    # Avatar frame
    frame_x1, frame_y1 = hero_x1 + 44, hero_y1 + 50
    frame_x2, frame_y2 = hero_x2 - 44, hero_y1 + 580
    draw.rounded_rectangle((frame_x1, frame_y1, frame_x2, frame_y2), radius=34, fill=(25, 34, 58, 255), outline=(255, 255, 255, 28), width=1)
    avatar = Image.open(AVATAR).convert("RGBA")
    target_w = frame_x2 - frame_x1 - 24
    target_h = frame_y2 - frame_y1 - 24
    avatar_ratio = avatar.width / avatar.height
    target_ratio = target_w / target_h
    if avatar_ratio > target_ratio:
        new_h = target_h
        new_w = int(new_h * avatar_ratio)
    else:
        new_w = target_w
        new_h = int(new_w / avatar_ratio)
    avatar = avatar.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    avatar = avatar.crop((left, top, left + target_w, top + target_h))
    mask = Image.new("L", (target_w, target_h), 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.rounded_rectangle((0, 0, target_w, target_h), radius=28, fill=255)
    base.paste(avatar, (frame_x1 + 12, frame_y1 + 12), mask)
    # subtle highlight
    highlight = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    hdraw = ImageDraw.Draw(highlight)
    hdraw.rounded_rectangle((0, 0, target_w - 1, target_h - 1), radius=28, outline=(255, 255, 255, 30), width=2)
    base.alpha_composite(highlight, (frame_x1 + 12, frame_y1 + 12))

    # Hero caption and badge
    draw.text((hero_x1 + 44, hero_y1 + 610), "Always-on front desk", font=FONT_SECTION, fill=(255, 255, 255, 255))
    hero_text = (
        "The assistant greets users, understands spoken questions, "
        "retrieves trusted context, and replies with a human-like voice."
    )
    place_wrapped(draw, hero_x1 + 44, hero_y1 + 664, hero_text, FONT_BODY, (216, 225, 239, 255), 510)

    # Small metrics
    metric_y = hero_y1 + 806
    metrics = [
        ("24/7", "availability"),
        ("Grounded", "in docs"),
        ("Voice + Chat", "experience"),
    ]
    metric_xs = [hero_x1 + 44, hero_x1 + 220, hero_x1 + 406]
    metric_colors = [(69, 215, 196, 90), (97, 88, 255, 90), (245, 166, 35, 90)]
    for (big, small), x, color in zip(metrics, metric_xs, metric_colors):
        draw.rounded_rectangle((x, metric_y, x + 150, metric_y + 86), radius=22, fill=(18, 34, 64, 255), outline=color, width=2)
        draw.text((x + 18, metric_y + 12), big, font=FONT_SECTION, fill=(255, 255, 255, 255))
        draw.text((x + 18, metric_y + 52), small, font=FONT_SMALL, fill=(193, 205, 221, 255))

    # Footer note
    footer = "Built for college FAQs, admissions, programs, and campus information."
    draw.text((118, 1034), footer, font=FONT_SMALL, fill=(170, 183, 202, 255))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    base.convert("RGB").save(OUT, quality=95)
    print(f"Saved {OUT}")


if __name__ == "__main__":
    main()
