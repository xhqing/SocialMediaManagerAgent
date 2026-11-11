#!/usr/bin/env python3
"""LaTeX 公式 → 透明背景 PNG（KaTeX + Playwright 无头 Chrome）。

为什么这么做：公众号正文是 HTML 白名单，不渲染 LaTeX，公式只能以图片形式进正文。
用 KaTeX 在无头浏览器里排版后再截图，能得到和网页端一致的排版质量。

用法（库）：
    from math_render import render_math
    imgs = render_math([{"key": "f0", "tex": "a^2+b^2", "display": False}], outdir="tmp/math")

返回：{key: {"path": Path, "w": int, "h": int}}（w/h 为 CSS 像素，用于写进 <img> 的宽高）
"""

from __future__ import annotations

import json
import pathlib
from typing import Iterable

KATEX_VER = "0.16.22"
KATEX_CSS = f"https://cdn.jsdelivr.net/npm/katex@{KATEX_VER}/dist/katex.min.css"
KATEX_JS = f"https://cdn.jsdelivr.net/npm/katex@{KATEX_VER}/dist/katex.min.js"

PAGE = """<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="{css}">
<script src="{js}"></script>
<style>
  html, body {{ margin: 0; padding: 0; background: transparent; }}
  #host {{ display: block; width: 2400px; }}
  .fm {{ display: inline-block; padding: 1px; }}
  .fm.display {{ font-size: {dfont}px; }}
  .fm.inline  {{ font-size: {ifont}px; vertical-align: middle; }}
</style></head><body><div id="host"></div></body></html>"""


def render_math(
    items: Iterable[dict],
    outdir: str | pathlib.Path,
    scale: int = 3,
    inline_font: int = 17,
    display_font: int = 23,
    max_display_width: int = 640,
) -> dict[str, dict]:
    """把公式渲成 PNG。items: [{"key","tex","display"}]（key 唯一，可用于去重）。"""
    from playwright.sync_api import sync_playwright

    items = list(items)
    outdir = pathlib.Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    html = PAGE.format(css=KATEX_CSS, js=KATEX_JS, ifont=inline_font, dfont=display_font)
    result: dict[str, dict] = {}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 2400, "height": 1200}, device_scale_factor=scale)
        page.set_content(html, wait_until="load")
        page.wait_for_function("typeof katex !== 'undefined'")

        page.evaluate(
            """(items) => {
                const host = document.getElementById('host');
                for (const it of items) {
                    const el = document.createElement('div');
                    el.id = 'm-' + it.key;
                    el.className = 'fm ' + (it.display ? 'display' : 'inline');
                    host.appendChild(el);
                    katex.render(it.tex, el, {displayMode: it.display, throwOnError: false});
                }
            }""",
            [{"key": it["key"], "tex": it["tex"], "display": bool(it.get("display"))} for it in items],
        )

        # 关键：必须等 KaTeX 字体（woff2）加载完再测量——字体未到位时测得的宽度是回退字体的，
        # 与最终渲染不一致，会导致裁剪偏位（实测踩坑）
        page.evaluate(
            """async () => {
                const fams = ['KaTeX_Main','KaTeX_Math','KaTeX_Size1','KaTeX_Size2','KaTeX_Size3',
                              'KaTeX_Size4','KaTeX_AMS','KaTeX_Caligraphic','KaTeX_Fraktur',
                              'KaTeX_SansSerif','KaTeX_Typewriter','KaTeX_Script','KaTeX_Bold'];
                await Promise.all(fams.map(f => document.fonts.load('20px ' + f).catch(() => {})));
                await document.fonts.ready;
            }"""
        )
        page.wait_for_function("document.fonts.status === 'loaded'", timeout=20000)

        # 测量（CSS 像素）；过宽的展示公式按比例缩小字号后重排
        def measure() -> list[dict]:
            return page.evaluate(
                """() => Array.from(document.querySelectorAll('.fm')).map(el => {
                    const r = el.getBoundingClientRect();
                    return {key: el.id.slice(2), x: r.x + window.scrollX, y: r.y + window.scrollY,
                            w: r.width, h: r.height};
                })"""
            )

        sizes = measure()
        by_key = {it["key"]: it for it in items}
        for s in sizes:
            it = by_key[s["key"]]
            if it.get("display") and s["w"] > max_display_width:
                new_font = max(13, int(display_font * max_display_width / s["w"]))
                page.evaluate(
                    """([key, font]) => { const el = document.getElementById('m-' + key); el.style.fontSize = font + 'px'; }""",
                    [s["key"], new_font],
                )
                page.wait_for_timeout(30)
        sizes = measure()

        pad = 1  # 公式四周留 1px 余量，防裁切
        # 整页截屏一次，再用 PIL 按元素坐标精确裁剪（Playwright 的 clip 坐标系与元素坐标不一致，不用它）
        from PIL import Image

        full = outdir / "_page.png"
        page.screenshot(path=str(full), full_page=True, omit_background=True)
        img = Image.open(full)
        for s in sizes:
            it = by_key[s["key"]]
            box = (
                int(round((s["x"] - pad) * scale)),
                int(round((s["y"] - pad) * scale)),
                int(round((s["x"] + s["w"] + pad) * scale)),
                int(round((s["y"] + s["h"] + pad) * scale)),
            )
            box = (max(0, box[0]), max(0, box[1]), min(img.width, box[2]), min(img.height, box[3]))
            path = outdir / f"{it['key']}.png"
            img.crop(box).save(path)
            result[s["key"]] = {
                "path": path,
                "w": round((box[2] - box[0]) / scale, 1),
                "h": round((box[3] - box[1]) / scale, 1),
                "tex": it["tex"],
                "display": bool(it.get("display")),
            }
        img.close()
        full.unlink(missing_ok=True)
        browser.close()

    return result


if __name__ == "__main__":
    import sys

    demo = [
        {"key": "i0", "tex": "\\mathrm{EV}=\\mathbb{E}[R]", "display": False},
        {"key": "i1", "tex": "W_n/W_0", "display": False},
        {"key": "d0", "tex": r"\frac{W_n}{W_0}\approx e^{\,n g}", "display": True},
        {"key": "d1", "tex": r"g\approx\underbrace{f\cdot\mathrm{EV}}_{\text{算术增长}}-\underbrace{\frac{f^2}{2}\mathbb{E}[R^2]}_{\text{方差惩罚}}", "display": True},
    ]
    out = sys.argv[1] if len(sys.argv) > 1 else "tmp/math-demo"
    res = render_math(demo, out)
    print(json.dumps({k: {"w": v["w"], "h": v["h"], "path": str(v["path"])} for k, v in res.items()},
                     ensure_ascii=False, indent=2))
