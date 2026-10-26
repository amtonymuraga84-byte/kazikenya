"""
make_cover.py: makes an original 1200x630 cover image for a blog post (no copyright worries).

Use:   python make_cover.py posts/my-post.md
       python make_cover.py --all          (every post that has no image yet)
It saves images/covers/<post-name>.jpg and adds the "image:" line to the post.
Needs: pip install pillow
"""
import re
import sys
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 630
THEMES = {   # background, accent, by tag
    "Money & Law": ("#0b3d2a", "#f2c94c"),
    "Salaries": ("#0b3d2a", "#f2c94c"),
    "Careers": ("#08863f", "#ffffff"),
    "Kenya News": ("#14201a", "#3fbf86"),
}
DEFAULT = ("#08863f", "#ffffff")
FONT_DIRS = ["/usr/share/fonts/opentype/inter", "/usr/share/fonts/truetype/dejavu", "C:/Windows/Fonts", "/Library/Fonts"]


def font(names, size):
    for d in FONT_DIRS:
        for n in names:
            p = Path(d) / n
            if p.exists():
                return ImageFont.truetype(str(p), size)
    return ImageFont.load_default(size)


def meta_of(text):
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.S)
    meta = {}
    for ln in (m.group(1).splitlines() if m else []):
        if ":" in ln:
            k, v = ln.split(":", 1)
            meta[k.strip().lower()] = v.strip().strip('"')
    return meta


def make(post):
    text = post.read_text(encoding="utf-8")
    meta = meta_of(text)
    title, tag = meta.get("title", post.stem), meta.get("tag", "Careers")
    bg, ac = THEMES.get(tag, DEFAULT)
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)
    # simple geometric decoration
    d.ellipse((W - 330, -170, W + 170, 330), outline=ac, width=6)
    d.ellipse((W - 250, -90, W + 90, 250), outline=ac, width=3)
    d.rectangle((0, H - 14, W, H), fill=ac)
    small, big = font(["Inter-Bold.otf", "DejaVuSans-Bold.ttf", "arialbd.ttf"], 30), None
    d.text((70, 60), tag.upper(), font=small, fill=ac)
    for size in (68, 60, 54, 48, 42):
        big = font(["Inter-ExtraBold.otf", "Inter-Bold.otf", "DejaVuSans-Bold.ttf", "arialbd.ttf"], size)
        for chars in range(40, 8, -1):        # keep text clear of the circles on the right
            lines = textwrap.wrap(title, width=chars)
            if max(d.textlength(ln, font=big) for ln in lines) <= 830:
                break
        if len(lines) * size * 1.2 <= 360:
            break
    y = 130 + (360 - len(lines) * size * 1.2) / 2
    for ln in lines:
        d.text((70, y), ln, font=big, fill="#ffffff")
        y += size * 1.2
    brand = font(["Inter-Bold.otf", "DejaVuSans-Bold.ttf", "arialbd.ttf"], 34)
    d.text((70, H - 90), "Remote", font=brand, fill="#ffffff")
    d.text((70 + d.textlength("Remote", font=brand), H - 90), "Kazi", font=brand, fill=ac)
    d.text((W - 70 - d.textlength("remotekazi.com", font=small), H - 86), "remotekazi.com", font=small, fill="#ffffff")
    out = Path("images/covers") / f"{post.stem.rstrip('-')}.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "JPEG", quality=86, optimize=True)
    line = f"image: /{out.as_posix()}"
    if re.search(r"^image:.*$", text, re.M):
        text = re.sub(r"^image:.*$", line, text, count=1, flags=re.M)
    else:
        text = re.sub(r"^(---\s*\n.*?)(\n---)", lambda m: m.group(1) + "\n" + line + m.group(2), text, count=1, flags=re.S)
    post.write_text(text, encoding="utf-8")
    print("made", out)


if __name__ == "__main__":
    if sys.argv[1:] == ["--all"]:
        for p in sorted(Path("posts").glob("*.md")):
            if not re.search(r"^image:\s*\S", p.read_text(encoding="utf-8"), re.M):
                make(p)
    else:
        for a in sys.argv[1:]:
            make(Path(a))
