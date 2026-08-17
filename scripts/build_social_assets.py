#!/usr/bin/env python3
"""Generate the favicons and the Open Graph card from the GitHub avatar.

    python scripts/build_social_assets.py

Outputs, all into frontend/public/:

    favicon.ico                 16/32/48, for the browser tab
    favicon-16.png              explicit sizes for browsers that prefer PNG
    favicon-32.png
    apple-touch-icon.png        180x180, iOS home screen
    icon-192.png                Android / PWA
    icon-512.png
    og-card.png                 1200x630, the LinkedIn/WhatsApp/Slack preview

The card is drawn in the site's own CRT palette rather than being the bare
avatar, because a social preview is read at thumbnail size in a feed: it needs a
name and a role legible at a glance, not a portrait. Same phosphor green, same
near-black surface, same scanlines as the site.

The source avatar is kept at data/avatar-source.png — tracked, so the assets can
be rebuilt without network access, and outside frontend/public/ because it is a
build input rather than something the site should serve.

Re-run this if the avatar changes. The outputs are committed, since the SWA serves
them statically and CI does not run this.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "frontend" / "public"
AVATAR_URL = "https://github.com/dominberbel98.png?size=460"

# The site's palette, from frontend/src/styles.css and tailwind.config.js.
SURFACE = (14, 14, 14)
PHOSPHOR = (0, 255, 65)
DIM = (0, 140, 40)

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def fetch_avatar(destination: Path) -> Path:
    """Download the GitHub avatar, or reuse it if already present."""
    if destination.exists():
        return destination
    import urllib.request

    urllib.request.urlretrieve(AVATAR_URL, destination)
    return destination


# ── Favicons ────────────────────────────────────────────────────────────────


def build_favicons(avatar: Image.Image) -> list[Path]:
    """Square icons at the sizes browsers and mobile home screens ask for."""
    written: list[Path] = []
    square = avatar.convert("RGB")

    for size, name in (
        (16, "favicon-16.png"),
        (32, "favicon-32.png"),
        (180, "apple-touch-icon.png"),
        (192, "icon-192.png"),
        (512, "icon-512.png"),
    ):
        # LANCZOS rather than the default: at 16px the avatar's line art turns to
        # mush with a cheaper filter.
        resized = square.resize((size, size), Image.LANCZOS)
        path = PUBLIC / name
        resized.save(path, "PNG", optimize=True)
        written.append(path)

    ico = PUBLIC / "favicon.ico"
    square.save(ico, "ICO", sizes=[(16, 16), (32, 32), (48, 48)])
    written.append(ico)
    return written


# ── Open Graph card ─────────────────────────────────────────────────────────


def _scanlines(card: Image.Image, spacing: int = 3, alpha: int = 16) -> None:
    """The site's CRT scanline overlay, so the preview looks like the page."""
    overlay = Image.new("RGBA", card.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for y in range(0, card.height, spacing):
        draw.line([(0, y), (card.width, y)], fill=(0, 0, 0, alpha), width=1)
    card.alpha_composite(overlay)


def _glow_frame(draw: ImageDraw.ImageDraw, box, radius: int, layers: int = 5) -> None:
    """Fake a phosphor bloom by stacking progressively fainter outlines."""
    left, top, right, bottom = box
    for i in range(layers, 0, -1):
        alpha = int(90 / i)
        draw.rounded_rectangle(
            (left - i, top - i, right + i, bottom + i),
            radius=radius + i,
            outline=(*PHOSPHOR, alpha),
            width=1,
        )


def build_og_card(avatar: Image.Image) -> Path:
    """1200x630 — the size LinkedIn, Slack and WhatsApp expect."""
    width, height = 1200, 630
    card = Image.new("RGBA", (width, height), (*SURFACE, 255))
    draw = ImageDraw.Draw(card)

    # Faint radial-ish wash behind the text, echoing the page's centre glow.
    wash = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    wash_draw = ImageDraw.Draw(wash)
    for i in range(28):
        wash_draw.ellipse(
            (250 - i * 22, 120 - i * 14, 1150 + i * 22, 700 + i * 14),
            outline=(*PHOSPHOR, 2),
            width=2,
        )
    card.alpha_composite(wash)

    _scanlines(card)

    # Outer frame, inset like a terminal bezel.
    draw.rounded_rectangle((18, 18, width - 18, height - 18), radius=10,
                           outline=(*DIM, 170), width=2)

    # ── Avatar ──
    avatar_size = 300
    portrait = avatar.convert("RGB").resize((avatar_size, avatar_size), Image.LANCZOS)
    mask = Image.new("L", (avatar_size, avatar_size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, avatar_size, avatar_size), radius=22, fill=255)
    ax, ay = 84, (height - avatar_size) // 2
    card.paste(portrait, (ax, ay), mask)
    _glow_frame(draw, (ax, ay, ax + avatar_size, ay + avatar_size), radius=22)

    # ── Text column ──
    tx = ax + avatar_size + 68
    name_font = _font(FONT_BOLD, 62)
    role_font = _font(FONT_BOLD, 30)
    detail_font = _font(FONT_REGULAR, 23)
    prompt_font = _font(FONT_BOLD, 24)

    y = ay + 6
    draw.text((tx, y), "DOMINGO", font=name_font, fill=PHOSPHOR)
    y += 70
    draw.text((tx, y), "BERBEL", font=name_font, fill=PHOSPHOR)
    y += 92

    draw.text((tx, y), "DATA SCIENTIST", font=role_font, fill=(*PHOSPHOR, 235))
    y += 46
    draw.line([(tx, y), (tx + 300, y)], fill=(*PHOSPHOR, 120), width=2)
    y += 26

    for line in (
        "Applied AI · RAG · Generative AI",
        "Python · PySpark · Azure · Power BI",
    ):
        draw.text((tx, y), line, font=detail_font, fill=(150, 220, 165))
        y += 34

    y += 16
    draw.text((tx, y), "> domingoberbel.com", font=prompt_font, fill=PHOSPHOR)

    path = PUBLIC / "og-card.png"
    card.convert("RGB").save(path, "PNG", optimize=True)
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--avatar",
        type=Path,
        default=ROOT / "data" / "avatar-source.png",
        help="local copy of the GitHub avatar; downloaded if absent",
    )
    args = parser.parse_args(argv)

    PUBLIC.mkdir(parents=True, exist_ok=True)
    try:
        source = fetch_avatar(args.avatar)
    except Exception as exc:
        print(f"error: could not obtain the avatar ({exc})", file=sys.stderr)
        return 1

    avatar = Image.open(source)
    print(f"avatar: {avatar.size[0]}x{avatar.size[1]}")

    for path in build_favicons(avatar):
        print(f"  wrote {path.relative_to(ROOT)} ({path.stat().st_size:,} bytes)")

    card = build_og_card(avatar)
    print(f"  wrote {card.relative_to(ROOT)} ({card.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
