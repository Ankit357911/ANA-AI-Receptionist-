from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter


ROOT = Path(__file__).resolve().parent
OUT_PNG = ROOT / "docs" / "ana_presentation_slide.png"
OUT_PDF = ROOT / "docs" / "ana_presentation_slide.pdf"
AVATAR = ROOT / "assets" / "avatar" / "nepali_receptionist_neutral.png"

W, H = 1920, 1080


def load_font(names, size):
    fonts_dir = Path(r"C:\Windows\Fonts")
    for name in names:
        path = fonts_dir / name
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


FONT_TITLE = load_font(["calibrib.ttf", "arialbd.ttf"], 76)
FONT_SUBTITLE = load_font(["calibri.ttf", "arial.ttf"], 28)
FONT_SECTION = load_font(["calibrib.ttf", "arialbd.ttf"], 30)
FONT_BODY = load_font(["calibri.ttf", "arial.ttf"], 24)
FONT_SMALL = load_font(["calibri.ttf", "arial.ttf"], 20)
FONT_TINY = load_font(["calibri.ttf", "arial.ttf"], 18)
FONT_BADGE = load_font(["calibrib.ttf", "arialbd.ttf"], 22)


def text_height(font):
    bbox = font.getbbox("Ag")
    return bbox[3] - bbox[1]


def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines = []
    current = ""
    for word in words:
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


def draw_wrapped(draw, x, y, text, font, fill, max_width, line_gap=6):
    yy = y
    for line in wrap_text(draw, text, font, max_width):
        draw.text((x, yy), line, font=font, fill=fill)
        yy += text_height(font) + line_gap
    return yy


def shadow_card(base, xy, radius, fill, shadow=(0, 12), blur=26):
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x1, y1, x2, y2 = xy
    ox, oy = shadow
    d.rounded_rectangle((x1 + ox, y1 + oy, x2 + ox, y2 + oy), radius=radius, fill=(0, 0, 0, 100))
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    base.alpha_composite(layer)
    d = ImageDraw.Draw(base)
    d.rounded_rectangle(xy, radius=radius, fill=fill)


def pill(draw, xy, fill, outline, text, text_fill, font):
    draw.rounded_rectangle(xy, radius=20, fill=fill, outline=outline, width=2)
    x1, y1, x2, y2 = xy
    tw = draw.textlength(text, font=font)
    th = text_height(font)
    draw.text((x1 + (x2 - x1 - tw) / 2, y1 + (y2 - y1 - th) / 2 - 2), text, font=font, fill=text_fill)


def main():
    base = Image.new("RGBA", (W, H), (8, 15, 37, 255))
    draw = ImageDraw.Draw(base)

    # Background gradient
    for y in range(H):
        t = y / (H - 1)
        r = int(8 * (1 - t) + 10 * t)
        g = int(15 * (1 - t) + 28 * t)
        b = int(37 * (1 - t) + 62 * t)
        draw.line((0, y, W, y), fill=(r, g, b, 255))

    # Ambient lighting
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((80, 50, 620, 420), fill=(56, 214, 194, 90))
    gd.ellipse((1380, 30, 1930, 450), fill=(255, 171, 58, 70))
    gd.ellipse((1280, 740, 1760, 1120), fill=(91, 126, 255, 55))
    gd.ellipse((120, 760, 520, 1120), fill=(105, 94, 255, 50))
    glow = glow.filter(ImageFilter.GaussianBlur(28))
    base.alpha_composite(glow)
    draw = ImageDraw.Draw(base)

    # Left accent rail
    draw.rounded_rectangle((84, 112, 88, 960), radius=2, fill=(255, 255, 255, 30))
    draw.rounded_rectangle((84, 112, 142, 116), radius=2, fill=(69, 215, 196, 180))
    for cy in (208, 260, 312):
        draw.ellipse((70, cy - 8, 86, cy + 8), fill=(255, 255, 255, 150))

    # Title block
    draw.text((120, 126), "ANA", font=FONT_TITLE, fill=(255, 255, 255, 255))
    draw.text((315, 150), "AI Receptionist", font=FONT_SECTION, fill=(151, 233, 224, 255))
    draw.text((120, 215), "Your Smart College Front Desk Assistant", font=FONT_SECTION, fill=(242, 246, 252, 255))
    draw_wrapped(
        draw,
        120,
        262,
        "BCA 8th Semester Project · Kantipur City College · 2026",
        FONT_SUBTITLE,
        (205, 219, 236, 255),
        1000,
        line_gap=3,
    )
    draw.text((120, 330), "Created by: Ankit Chandra Karn  ·  Srijan Basnet  ·  Suraj Panthi", font=FONT_SUBTITLE, fill=(205, 219, 236, 255))

    # Intro card
    shadow_card(base, (108, 382, 872, 554), 30, (15, 28, 57, 235), blur=22)
    draw.rounded_rectangle((108, 382, 872, 554), radius=30, outline=(69, 215, 196, 80), width=2)
    draw.text((138, 408), "Introduction", font=FONT_SECTION, fill=(255, 255, 255, 255))
    intro = (
        "ANA is an intelligent virtual assistant for Kantipur City College that answers "
        "college-related questions in a natural conversational manner."
    )
    draw_wrapped(draw, 138, 456, intro, FONT_BODY, (226, 235, 245, 255), 680)

    # Right hero panel
    shadow_card(base, (1218, 112, 1812, 972), 40, (12, 24, 47, 248), blur=32)
    draw.rounded_rectangle((1218, 112, 1812, 972), radius=40, outline=(255, 255, 255, 24), width=1)

    # Avatar frame
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
    crop_x = max(0, (nw - tw) // 2)
    crop_y = max(0, (nh - th) // 2)
    avatar = avatar.crop((crop_x, crop_y, crop_x + tw, crop_y + th))
    mask = Image.new("L", (tw, th), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, tw, th), radius=28, fill=255)
    base.paste(avatar, (frame[0] + 12, frame[1] + 12), mask)

    draw.text((1260, 724), "Always-on front desk", font=FONT_SECTION, fill=(255, 255, 255, 255))
    hero = (
        "Supports text chat, voice conversation, and a lifelike animated receptionist "
        "for a more human front-desk experience."
    )
    draw_wrapped(draw, 1260, 776, hero, FONT_BODY, (222, 231, 242, 255), 470)

    # Impact chips under hero
    chip_y = 910
    metrics = [
        ("3", "Interaction Modes"),
        ("Local", "Fully Deployable"),
        ("RAG", "Document-Grounded"),
        ("<2s", "Audio Response"),
    ]
    chip_x = [1260, 1385, 1540, 1700]
    chip_w = [110, 130, 150, 112]
    chip_colors = [(69, 215, 196, 90), (97, 88, 255, 90), (245, 166, 35, 90), (255, 255, 255, 40)]
    for (big, small), x, w, color in zip(metrics, chip_x, chip_w, chip_colors):
        draw.rounded_rectangle((x, chip_y, x + w, chip_y + 84), radius=22, fill=(18, 34, 64, 255), outline=color, width=2)
        draw.text((x + 14, chip_y + 10), big, font=FONT_SECTION, fill=(255, 255, 255, 255))
        draw.text((x + 14, chip_y + 48), small, font=FONT_TINY, fill=(196, 208, 224, 255))

    # Middle column cards
    card_x = 108
    card_w = 760
    card_h = 126
    gap = 16
    y0 = 584
    sections = [
        ("Objectives", "AI receptionist, document-based answering, voice interaction, avatar response, local deployment, maintainability."),
        ("The Problem", "College enquiries are repetitive, generic chatbots lack context, and voice/avatar systems are computationally heavy."),
        ("The Solution", "A local assistant grounded in real college documents using RAG, with text, voice, and avatar modes."),
        ("Key Features", "Smart Chat  ·  Voice Interaction  ·  Avatar Mode  ·  Latency Optimized"),
    ]
    colors = [
        ((69, 215, 196, 30), (69, 215, 196, 130)),
        ((97, 88, 255, 30), (97, 88, 255, 130)),
        ((245, 166, 35, 30), (245, 166, 35, 130)),
        ((255, 255, 255, 18), (255, 255, 255, 70)),
    ]
    for i, ((title, body), (chip_fill, outline)) in enumerate(zip(sections, colors)):
        y = y0 + i * (card_h + gap)
        shadow_card(base, (card_x, y, card_x + card_w, y + card_h), 26, (17, 30, 57, 235), blur=20)
        draw.rounded_rectangle((card_x, y, card_x + card_w, y + card_h), radius=26, outline=outline, width=2)
        draw.rounded_rectangle((card_x + 22, y + 18, card_x + 174, y + 54), radius=16, fill=chip_fill)
        draw.text((card_x + 38, y + 21), title, font=FONT_BADGE, fill=(255, 255, 255, 255))
        if title == "Key Features":
            # compact feature row
            feats = ["Smart Chat", "Voice", "Avatar", "Fast"]
            fx = [card_x + 30, card_x + 215, card_x + 362, card_x + 508]
            fcols = [(69, 215, 196, 120), (97, 88, 255, 120), (245, 166, 35, 120), (255, 255, 255, 65)]
            for feat, x, col in zip(feats, fx, fcols):
                draw.rounded_rectangle((x, y + 68, x + 140, y + 102), radius=16, fill=(20, 35, 63, 255), outline=col, width=2)
                tw = draw.textlength(feat, font=FONT_SMALL)
                draw.text((x + (140 - tw) / 2, y + 75), feat, font=FONT_SMALL, fill=(245, 248, 252, 255))
        else:
            draw_wrapped(draw, card_x + 26, y + 64, body, FONT_BODY, (226, 235, 245, 255), 680)

    # Workflow section
    wf = (108, 1006, 872, 1048)
    draw.rounded_rectangle(wf, radius=20, fill=(14, 26, 50, 235), outline=(255, 255, 255, 28), width=1)
    draw.text((132, 1014), "How It Works", font=FONT_BADGE, fill=(159, 232, 224, 255))
    flow = ["User", "Intent", "FAISS", "LLM", "Audio + Avatar"]
    xs = [286, 396, 532, 680, 786]
    widths = [80, 92, 92, 72, 160]
    cols = [(255, 255, 255, 45), (69, 215, 196, 110), (97, 88, 255, 110), (245, 166, 35, 110), (255, 255, 255, 45)]
    for i, (label, x, wid, col) in enumerate(zip(flow, xs, widths, cols)):
        draw.rounded_rectangle((x, 1005, x + wid, 1041), radius=16, fill=(21, 39, 73, 255), outline=col, width=2)
        tw = draw.textlength(label, font=FONT_TINY)
        draw.text((x + (wid - tw) / 2, 1013), label, font=FONT_TINY, fill=(248, 250, 252, 255))
        if i < len(flow) - 1:
            ax1 = x + wid + 8
            ax2 = ax1 + 24
            ay = 1023
            draw.line((ax1, ay, ax2, ay), fill=(206, 214, 227, 180), width=3)
            draw.polygon([(ax2, ay), (ax2 - 8, ay - 6), (ax2 - 8, ay + 6)], fill=(206, 214, 227, 180))

    # Tech stack / future scope card
    shadow_card(base, (900, 584, 1176, 1048), 28, (15, 28, 57, 235), blur=20)
    draw.rounded_rectangle((900, 584, 1176, 1048), radius=28, outline=(255, 255, 255, 20), width=1)
    draw.text((928, 610), "Technology Stack", font=FONT_SECTION, fill=(255, 255, 255, 255))
    tech = [
        ("Python", (69, 215, 196, 110)),
        ("FastAPI", (97, 88, 255, 110)),
        ("FAISS", (245, 166, 35, 110)),
        ("Qwen3-1.7B-GGUF", (255, 255, 255, 70)),
        ("Sentence Transformers", (69, 215, 196, 110)),
        ("faster-whisper", (97, 88, 255, 110)),
        ("Kokoro TTS", (245, 166, 35, 110)),
        ("Wav2Lip", (255, 255, 255, 70)),
        ("JavaScript", (69, 215, 196, 110)),
        ("Lemonade API", (97, 88, 255, 110)),
    ]
    tx = 928
    ty = 664
    for label, border in tech:
        w = int(draw.textlength(label, font=FONT_SMALL) + 34)
        if tx + w > 1144:
            tx = 928
            ty += 44
        draw.rounded_rectangle((tx, ty, tx + w, ty + 32), radius=14, fill=(20, 35, 63, 255), outline=border, width=2)
        draw.text((tx + 17, ty + 6), label, font=FONT_SMALL, fill=(244, 247, 252, 255))
        tx += w + 10

    draw.text((928, 878), "Future Scope", font=FONT_SECTION, fill=(255, 255, 255, 255))
    future_items = [
        "Multilingual support",
        "Admin dashboard for re-indexing",
        "Kiosk deployment",
        "Real-time avatars",
    ]
    fy = 924
    for item in future_items:
        draw.ellipse((928, fy + 6, 938, fy + 16), fill=(69, 215, 196, 220))
        draw.text((950, fy), item, font=FONT_BODY, fill=(226, 235, 245, 255))
        fy += 32

    # Footer
    draw.text((108, 1062), "ANA - Making college reception smarter, faster, and more human.", font=FONT_SMALL, fill=(178, 190, 206, 255))

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
