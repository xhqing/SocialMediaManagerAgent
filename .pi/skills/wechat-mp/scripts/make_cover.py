#!/usr/bin/env python3
"""生成公众号文章封面图（默认 1080×460，2.35:1，微信图文消息封面推荐比例）。

用法：
    from make_cover import make_cover
    make_cover("利滚利的三个开关", "tmp/cover.png", subtitle="AI+X 实战经验交流群")

命令行：python3 make_cover.py "标题" out.png [副标题]
"""

from __future__ import annotations

import pathlib
import sys

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 460
FONT_CANDIDATES = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
]
C1 = (180, 83, 9)      # #B45309
C2 = (120, 53, 15)     # 更暗的棕


def _font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if pathlib.Path(path).exists():
            for index in (0, 1, 2):
                try:
                    return ImageFont.truetype(path, size, index=index)
                except Exception:
                    continue
    return ImageFont.load_default()


def _wrap(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines, cur = [], ""
    for ch in text:
        if font.getlength(cur + ch) <= max_width:
            cur += ch
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines[:3]


def make_cover(title: str, out: str | pathlib.Path, subtitle: str = "",
               size: tuple[int, int] = (W, H)) -> pathlib.Path:
    w, h = size
    img = Image.new("RGB", (w, h), C1)
    d = ImageDraw.Draw(img)

    # 斜向渐变底
    for x in range(w):
        for y in range(0, h, 4):
            t = (x / w * 0.65 + y / h * 0.35)
            d.rectangle([x, y, x + 1, y + 4],
                        fill=(int(C1[0] + (C2[0] - C1[0]) * t),
                              int(C1[1] + (C2[1] - C1[1]) * t),
                              int(C1[2] + (C2[2] - C1[2]) * t)))

    # 右侧装饰圆环
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for r, a in ((260, 26), (190, 22), (120, 18)):
        od.ellipse([w - r - 60, h // 2 - r, w + r - 60, h // 2 + r], outline=(255, 255, 255, a), width=3)
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    d = ImageDraw.Draw(img)

    margin = 78
    tw = w - margin * 2 - 150
    f_title = _font(66)
    lines = _wrap(title, f_title, tw)
    y = h // 2 - len(lines) * 42 - (18 if subtitle else 0)
    for line in lines:
        d.text((margin, y), line, font=f_title, fill=(255, 255, 255))
        y += 84

    # 主色短线
    d.rectangle([margin, y + 4, margin + 96, y + 10], fill=(253, 230, 138))

    if subtitle:
        f_sub = _font(30)
        d.text((margin, y + 34), subtitle, font=f_sub, fill=(255, 240, 215))

    out = pathlib.Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out


if __name__ == "__main__":
    t = sys.argv[1] if len(sys.argv) > 1 else "利滚利的三个开关，多数人只找到一个"
    o = sys.argv[2] if len(sys.argv) > 2 else "tmp/mp-test/cover.png"
    s = sys.argv[3] if len(sys.argv) > 3 else "AI+X 实战经验交流群"
    p = make_cover(t, o, s)
    print("已生成：", p, Image.open(p).size)
