#!/usr/bin/env python3
"""把 Markdown 文章转成公众号草稿并写入草稿箱。

流程：解析 Markdown → 提取公式 → 转公众号行内样式 HTML → 公式渲成 PNG
      → （可选）上传图片到微信图床 → （可选）生成/上传封面 → draft/add 写草稿

用法：
    python3 build_draft.py <article.md> --out tmp/mp-draft [--preview] [--no-upload]
                           [--title T] [--author A] [--digest D] [--cover cover.png]

说明：
- 默认行为：能读到凭证就上传并写草稿；读不到凭证只做本地构建（等同于 --no-upload）。
- 正文里的局部图片（如 img/xxx.png）按文章所在目录解析。
- 输出目录保留：content.html（带本地图片的正文）、preview.html/png（手机宽度预览）、
  article.json（draft/add 的请求体，便于排查）、manifest.json（公式清单）。

样式集中在下面的 STYLE 字典里，改样式只动这里。
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

from bs4 import BeautifulSoup, NavigableString, Tag

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from math_render import render_math  # noqa: E402
from tex2html import ComplexMath, to_text  # noqa: E402

# ---------------------------------------------------------------- 样式（改这里即可调版式）
BRAND = "#B45309"       # 主色（Amber 深）
BRAND_LIGHT = "#FDF9F2"  # 底色
BORDER = "#EFE1C8"       # 边框

# 文末公众号名片：本账号专属数据，存本机（不进 git）。
# 采集方法见 SKILL.md「文末公众号名片」节；文件缺失或 --no-profile-card 时跳过。
PROFILE_CARD_PATH = "~/.wechat-mp/profile_card.html"


def load_profile_card() -> str:
    p = pathlib.Path(PROFILE_CARD_PATH).expanduser()
    return p.read_text(encoding="utf-8").strip() if p.exists() else ""


STYLE = {
    "body": f"font-size:16px;line-height:1.8;color:#3f3f3f;letter-spacing:.3px;word-break:break-word;",
    "p": "margin:0 0 16px;",
    "h2": f"font-size:19px;font-weight:bold;color:#1f1f1f;line-height:1.5;margin:34px 0 16px;"
          f"padding-left:11px;border-left:4px solid {BRAND};",
    "h3": "font-size:17px;font-weight:bold;color:#1f1f1f;line-height:1.5;margin:26px 0 12px;",
    "h4": "font-size:16px;font-weight:bold;color:#1f1f1f;margin:22px 0 10px;",
    "blockquote": f"margin:0 0 20px;padding:14px 16px;border-left:3px solid #EBCB8B;"
                  f"background:{BRAND_LIGHT};color:#6b6257;font-size:15px;line-height:1.78;",
    "blockquote_p": "margin:0 0 8px;",
    "ul": "margin:0 0 18px;padding-left:22px;",
    "ol": "margin:0 0 18px;padding-left:22px;",
    "li": "margin:0 0 8px;line-height:1.78;",
    "table": "width:100%;border-collapse:collapse;margin:6px 0 20px;font-size:13.5px;line-height:1.6;",
    "th": f"border:1px solid {BORDER};background:{BRAND_LIGHT};color:#8a5a12;padding:6px 4px;text-align:center;",
    "td": f"border:1px solid {BORDER};padding:6px 4px;text-align:center;",
    "caption": "margin:-4px 0 24px;font-size:13px;color:#9a9a9a;line-height:1.7;text-align:center;",
    "img": "display:block;width:100%;height:auto;margin:22px auto 8px;border-radius:3px;",
    "math_inline": "vertical-align:middle;max-width:100%;height:auto;",
    "math_display_wrap": "margin:6px 0 20px;text-align:center;",
    "math_display": "max-width:100%;height:auto;vertical-align:middle;",
    "hr": "margin:30px auto;width:60px;border-top:1px solid #dcdcdc;height:0;font-size:0;line-height:0;",
    "a": f"color:{BRAND};text-decoration:none;border-bottom:1px solid {BRAND}33;",
    "strong": "",  # 默认加粗即可，不写 style（省字符）
    "code": "background:#f5f5f5;border-radius:3px;padding:1px 5px;font-size:13.5px;"
            "font-family:Menlo,Consolas,monospace;color:#c7254e;",
    "pre": "background:#f7f7f7;border-radius:4px;padding:12px 14px;margin:0 0 20px;overflow-x:auto;"
           "font-size:13px;line-height:1.6;color:#333;",
}


# ---------------------------------------------------------------- Markdown 解析
def split_title(md_text: str) -> tuple[str, str]:
    m = re.match(r"\s*#\s+(.+?)\s*\n", md_text)
    if not m:
        return "", md_text
    return m.group(1).strip(), md_text[m.end():]


def extract_math(text: str) -> tuple[str, list[dict]]:
    """把 $...$ / $$...$$ 抽成占位符，返回 (带占位符的文本, 公式清单)。"""
    math_items: list[dict] = []

    def repl_display(m: re.Match) -> str:
        key = f"d{len(math_items)}"
        math_items.append({"key": key, "tex": m.group(1).strip(), "display": True})
        return f"@@MATH_{key}@@"

    def repl_inline(m: re.Match) -> str:
        key = f"i{len(math_items)}"
        math_items.append({"key": key, "tex": m.group(1).strip(), "display": False})
        return f"@@MATH_{key}@@"

    text = re.sub(r"\$\$(.+?)\$\$", repl_display, text, flags=re.S)
    text = re.sub(r"(?<!\$)\$(?!\$)([^\n$]+?)(?<!\$)\$(?!\$)", repl_inline, text)
    return text, math_items


def md_to_html(md_text: str) -> str:
    from markdown_it import MarkdownIt

    md = MarkdownIt("commonmark", {"html": False, "linkify": False})
    md.enable(["table", "strikethrough"])
    return md.render(md_text)


# ---------------------------------------------------------------- 站点样式注入
def _set(tag: Tag, key: str) -> None:
    if not STYLE.get(key):
        return
    tag["style"] = STYLE[key] + (tag.get("style") or "")


def style_document(soup: BeautifulSoup) -> None:
    for t in soup.find_all(["p", "h2", "h3", "h4", "h1", "ul", "ol", "li", "strong", "em",
                            "code", "pre", "a", "table", "th", "td", "blockquote", "hr", "img"]):
        if t.name in STYLE:
            _set(t, t.name)
    # 图片：正文里的插图
    for img in soup.find_all("img"):
        img["style"] = STYLE["img"]
    # 表格包一层（移动端窄屏时避免撑破）
    for table in soup.find_all("table"):
        table["style"] = STYLE["table"]
    # 引用块内的段落
    for bq in soup.find_all("blockquote"):
        for p in bq.find_all("p"):
            p["style"] = STYLE["blockquote_p"]
    # 斜体独占一段 → 图注
    for p in soup.find_all("p"):
        kids = [c for c in p.children if not (isinstance(c, NavigableString) and not c.strip())]
        if len(kids) == 1 and isinstance(kids[0], Tag) and kids[0].name == "em":
            p["style"] = STYLE["caption"]
    # 删除空段落
    for p in soup.find_all("p"):
        if not p.get_text(strip=True) and not p.find("img"):
            p.decompose()
    # 去掉 h1（标题单独作为文章 title 字段）
    for h1 in soup.find_all("h1"):
        h1.replace_with(soup.new_tag("span"))


def wrap_soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(f"<section id='mp-root'>{html}</section>", "lxml")


def render_caption_text(soup: BeautifulSoup) -> None:
    pass


# ---------------------------------------------------------------- 图片占位替换
def resolve_images(soup: BeautifulSoup, base_dir: pathlib.Path, out_dir: pathlib.Path) -> list[pathlib.Path]:
    """把正文里的相对图片路径解析成绝对路径，返回图片清单。"""
    files: list[pathlib.Path] = []
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if src.startswith("@@MATH_"):
            continue
        p = (base_dir / src).expanduser()
        if not p.exists():
            print(f"[warn] 图片不存在：{src}")
            continue
        p = p.resolve()
        img["src"] = str(p)
        img["data-local"] = str(p)
        files.append(p)
    return files


def insert_math(soup: BeautifulSoup, math_imgs: dict[str, dict], tex_map: dict[str, dict],
                inline_mode: str = "auto") -> dict:
    """把 @@MATH_x@@ 占位符换成 HTML 文本（简单内联公式）或 <img>（展示公式 / 复杂公式）。"""
    stats = {"text": 0, "img": 0}
    for node in list(soup.find_all(string=re.compile(r"@@MATH_"))):
        text = str(node)
        parts = re.split(r"(@@MATH_\w+@@)", text)
        new_nodes = []
        for part in parts:
            m = re.fullmatch(r"@@MATH_(\w+)@@", part)
            if not m:
                new_nodes.append(NavigableString(part))
                continue
            key = m.group(1)
            info = math_imgs.get(key)
            tex_info = tex_map.get(key, {})
            if not tex_info:
                new_nodes.append(NavigableString(part))
                continue
            # 内联 + 简单 → 文本
            if not tex_info["display"] and inline_mode != "image":
                try:
                    html_text = to_text(tex_info["tex"], wrap=True)
                    frag = BeautifulSoup(f"<span>{html_text}</span>", "lxml").find("span")
                    new_nodes.extend(list(frag.children))
                    stats["text"] += 1
                    continue
                except ComplexMath:
                    pass
            if not info:
                new_nodes.append(NavigableString(part))
                continue
            img = soup.new_tag("img")
            img["src"] = str(info["path"])
            img["data-local"] = str(info["path"])
            img["style"] = (STYLE["math_display"] if info["display"] else STYLE["math_inline"]) + f"width:{info['w']}px;"
            if info["display"]:
                wrapper = soup.new_tag("section")
                wrapper["style"] = STYLE["math_display_wrap"]
                wrapper.append(img)
                new_nodes.append(wrapper)
            else:
                new_nodes.append(img)
            stats["img"] += 1
        node.replace_with(*new_nodes)
    return stats


def _is_simple(tex: str) -> bool:
    try:
        to_text(tex)
        return True
    except ComplexMath:
        return False


# ---------------------------------------------------------------- 预览
def make_preview(content_html: str, out_dir: pathlib.Path, title: str, width: int = 390) -> pathlib.Path:
    page = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>{title}</title></head>
<body style="margin:0;background:#e9e9e9">
<div style="max-width:{width}px;margin:0 auto;background:#fff;padding:20px 16px 40px;">
<h1 style="font-size:22px;line-height:1.45;color:#111;margin:8px 0 22px;">{title}</h1>
{content_html}
</div></body></html>"""
    path = out_dir / "preview.html"
    path.write_text(page, encoding="utf-8")
    return path


def screenshot_preview(html_path: pathlib.Path, out_png: pathlib.Path, width: int = 390,
                       slice_height: int = 1500) -> list[pathlib.Path]:
    from playwright.sync_api import sync_playwright
    from PIL import Image

    with sync_playwright() as pw:
        b = pw.chromium.launch(channel="chrome", headless=True)
        pg = b.new_page(viewport={"width": width, "height": 900}, device_scale_factor=2)
        pg.goto(f"file://{html_path}")
        pg.wait_for_timeout(800)
        pg.screenshot(path=str(out_png), full_page=True)
        b.close()
    im = Image.open(out_png)
    slices = []
    for i in range(0, im.height, slice_height * 2):
        s = im.crop((0, i, im.width, min(i + slice_height * 2, im.height)))
        p = out_png.with_name(f"{out_png.stem}-{len(slices)+1:02d}{out_png.suffix}")
        s.save(p)
        slices.append(p)
    return slices


# ---------------------------------------------------------------- 主流程
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("article")
    ap.add_argument("--out", default="tmp/mp-draft")
    ap.add_argument("--title", default=None)
    ap.add_argument("--author", default=None, help="作者字段（≤16 字）；默认取凭证配置里的 author")
    ap.add_argument("--digest", default=None)
    ap.add_argument("--cover", default=None, help="封面图；不传则自动生成")
    ap.add_argument("--preview", action="store_true", help="额外产出手机宽度预览图")
    ap.add_argument("--inline-math", choices=["auto", "image"], default="auto",
                    help="内联公式处理：auto=简单的转文字、复杂的用图片；image=全部用图片")
    ap.add_argument("--no-upload", action="store_true")
    ap.add_argument("--no-draft", action="store_true", help="只上传图片、不建草稿")
    ap.add_argument("--no-profile-card", action="store_true", help="不在正文末尾附加公众号名片")
    ap.add_argument("--update-draft", default=None, metavar="MEDIA_ID",
                    help="更新现有草稿（media_id 不变），而不是新建草稿")
    ap.add_argument("--fake-upload", action="store_true",
                    help="用占位 URL 走完整流程（不调接口），用于验证最终 HTML 体积与结构")
    args = ap.parse_args()

    # 从本机凭证配置取默认作者（--author 优先）
    cfg: dict = {}
    try:
        from wx_api import load_config

        cfg = load_config()
    except Exception:
        pass
    author = args.author or cfg.get("author") or "AI+X 实战经验交流群"
    profile_card = "" if args.no_profile_card else load_profile_card()
    print(f"[build] 文末名片：{'已加载（%d 字符）' % len(profile_card) if profile_card else '无（跳过）'}")

    art = pathlib.Path(args.article).expanduser().resolve()
    base_dir = art.parent
    out_dir = pathlib.Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    md_text = art.read_text(encoding="utf-8")
    title, body_md = split_title(md_text)
    title = args.title or title
    body_md, math_items = extract_math(body_md)
    html = md_to_html(body_md)
    soup = wrap_soup(html)
    style_document(soup)
    resolve_images(soup, base_dir, out_dir)

    # 公式渲图
    uniq = {}
    for it in math_items:
        uniq.setdefault((it["tex"], it["display"]), it["key"])
    render_list = [{"key": k, "tex": tex, "display": disp} for (tex, disp), k in uniq.items()]
    # 先筛：能转文本的内联公式就不必渲图
    render_list = [it for it in render_list if it["display"] or not _is_simple(it["tex"])] \
        if args.inline_math != "image" else render_list
    math_imgs = render_math(render_list, out_dir / "math") if render_list else {}
    tex_map = {it["key"]: it for it in math_items}
    mstats = insert_math(soup, math_imgs, tex_map, inline_mode=args.inline_math)

    root = soup.find("section", id="mp-root")
    root["style"] = STYLE["body"]
    local_imgs = [(img, img["data-local"]) for img in root.find_all("img") if img.get("data-local")]
    for img in root.find_all("img"):
        if img.get("data-local"):
            del img["data-local"]
    content_local = str(root).replace(' id="mp-root"', "")
    if profile_card and "mp-common-profile" not in content_local:
        content_local += profile_card

    (out_dir / "content.html").write_text(content_local, encoding="utf-8")
    preview = make_preview(content_local, out_dir, title)
    print(f"[build] 标题：{title}（{len(title)} 字）")
    print(f"[build] 公式：{len(math_items)} 处 → 文字 {mstats['text']} 处、图片 {mstats['img']} 张（去重后渲染 {len(render_list)} 张）")
    print(f"[build] 正文：{len(content_local)} 字符，HTML 已写入 {out_dir/'content.html'}")
    print(f"[build] 预览：{preview}")

    # 封面
    cover_path = pathlib.Path(args.cover).expanduser() if args.cover else out_dir / "cover.png"
    if not cover_path.exists():
        from make_cover import make_cover

        make_cover(title, cover_path, subtitle="AI+X 实战经验交流群")
        print(f"[build] 封面已生成：{cover_path}")

    if args.preview:
        png = out_dir / "preview.png"
        slices = screenshot_preview(preview, png)
        print(f"[build] 预览图：{png}（{len(slices)} 张切片，同名 -NN 后缀）")

    # 上传 + 写草稿
    upload = not args.no_upload
    if upload and not args.fake_upload:
        try:
            from wx_api import WxClient  # noqa: F401
        except SystemExit as e:
            print(f"[upload] 跳过上传：{e}")
            upload = False

    article_payload: dict = {"title": title, "author": author,
                             "digest": args.digest or (title + "。"), "content": content_local,
                             "thumb_media_id": None}
    if upload:
        client = None if args.fake_upload else WxClient()
        # 1) 正文图（图表 + 公式）全部换成微信图床 URL
        urls: dict[str, str] = {}
        for i, (img, local) in enumerate(local_imgs, 1):
            if local not in urls:
                if client is not None:
                    urls[local] = client.upload_content_image(local)
                    print(f"[upload] 正文图 → {pathlib.Path(local).name} {urls[local][:64]}…")
                else:
                    urls[local] = ("https://mmbiz.qpic.cn/mmbiz_png/FAKE"
                                   f"{i:03d}ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/640?wx_fmt=png&from=appmsg")
                    print(f"[fake] 正文图 → {pathlib.Path(local).name}（占位 URL）")
            img["src"] = urls[local]
        content_remote = str(root).replace(' id="mp-root"', "")
        if profile_card and "mp-common-profile" not in content_remote:
            content_remote += profile_card
        article_payload["content"] = content_remote
        (out_dir / "content.remote.html").write_text(content_remote, encoding="utf-8")
        # 2) 封面 → 永久素材
        thumb = ("FAKE_THUMB_MEDIA_ID_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
                 if client is None else client.upload_permanent_image(cover_path))
        article_payload["thumb_media_id"] = thumb
        print(f"[upload] 封面素材 media_id：{thumb[:24]}…")

        (out_dir / "article.json").write_text(
            json.dumps({"articles": [article_payload]}, ensure_ascii=False, indent=2), encoding="utf-8")
        if client is None:
            print("[fake] 跳过 draft/add（假装上传模式）")
        elif args.update_draft:
            client.update_draft(args.update_draft, article_payload)
            print(f"[draft] ✅ 已更新草稿：media_id={args.update_draft}")
            (out_dir / "draft.txt").write_text(args.update_draft, encoding="utf-8")
        elif not args.no_draft:
            media_id = client.add_draft([article_payload])
            print(f"[draft] ✅ 已写入草稿箱：media_id={media_id}")
            (out_dir / "draft.txt").write_text(media_id, encoding="utf-8")

    print("[done]")


if __name__ == "__main__":
    main()
