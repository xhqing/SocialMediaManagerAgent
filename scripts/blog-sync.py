#!/usr/bin/env python3
"""同步个人博客（藏经阁）的文章，统计文字习惯，更新写作样本文件。

博客地址：https://xhqing.github.io/blog/
内容仓库：xhqing/blog 的 docs/post/ 目录（docsify 站点，文章是 Markdown）

用法：
    python3 scripts/blog-sync.py            同步 + 统计 + 更新 docs/brand/writing-samples.md
    python3 scripts/blog-sync.py --check    只检查有没有新文章 / 改动，不写文件
    python3 scripts/blog-sync.py --no-pull  跳过同步，直接用本地缓存重算统计

设计要点：
- 只拉 docs/post/，用 sparse-checkout 把仓库体积压到最小（整个仓库含图片约 160MB，文章只有 200KB）
- 缓存放 tmp/blog-cache/（tmp/ 已在 .gitignore，不进仓库）
- 统计结果写进 writing-samples.md 的标记区间，区间外的内容不碰（人工分析的段落安全）
- 文章原文不进本项目仓库：博客本身就是公开的，复制一份只会过期和重复
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "tmp" / "blog-cache"
STATE = CACHE / ".synced.json"
REPORT = ROOT / "docs" / "brand" / "writing-samples.md"
REPO = "https://github.com/xhqing/blog.git"
POST_DIR = "docs/post"

BEGIN = "<!-- STATS:BEGIN 以下由 scripts/blog-sync.py 自动生成，勿手改 -->"
END = "<!-- STATS:END -->"

# 统计用的关键词表：前一组看他爱用什么连接，后一组看 AI 腔他几乎不用什么
CONNECT = ["所以", "但是", "因此", "也就是说", "其实", "不过", "然而", "显然",
           "同理", "简单来说", "举个例子", "注意", "最后", "首先", "接下来"]
AI_ISM = ["值得注意的是", "需要指出的是", "总的来说", "综上所述", "不难看出",
          "更重要的是", "换句话说", "这意味着", "旨在于", "赋能", "抓手", "闭环"]


def run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def sync(no_pull: bool) -> None:
    """把博客仓库同步到本地缓存（只取文章目录）。"""
    if CACHE.exists() and (CACHE / ".git").exists():
        if no_pull:
            print("跳过同步（--no-pull）")
            return
        r = run(["git", "-C", str(CACHE), "pull", "--ff-only", "-q"])
        print("缓存已更新" if r.returncode == 0 else f"同步失败：{r.stderr.strip()}")
        return

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    print(f"首次同步，克隆到 {CACHE.relative_to(ROOT)} …")
    r = run(["git", "clone", "-q", "--depth", "1", "--filter=blob:none",
             "--sparse", REPO, str(CACHE)])
    if r.returncode != 0:
        sys.exit(f"克隆失败：{r.stderr.strip()}")
    run(["git", "-C", str(CACHE), "sparse-checkout", "set", POST_DIR])
    print("完成")


def manifest() -> tuple[str, list[str]]:
    """返回（当前提交短哈希，中文文章清单）。"""
    sha = run(["git", "-C", str(CACHE), "rev-parse", "--short", "HEAD"]).stdout.strip()
    names = []
    for f in sorted((CACHE / POST_DIR).rglob("*.md")):
        body = clean(f.read_text(encoding="utf-8", errors="replace"))
        if len(re.findall(r"[\u4e00-\u9fa5]", body)) >= 200:
            names.append(str(f.relative_to(CACHE / POST_DIR)))
    return sha, names


def report_changes(sha: str, names: list[str]) -> None:
    """对比上次同步，报告文章的新增与删除。"""
    if STATE.exists():
        import json
        old = json.loads(STATE.read_text(encoding="utf-8"))
        added = [n for n in names if n not in old.get("docs", [])]
        removed = [n for n in old.get("docs", []) if n not in names]
        if added:
            print(f"\n新增 {len(added)} 篇：")
            for n in added:
                print(f"  + {n}")
        if removed:
            print(f"\n已消失 {len(removed)} 篇：")
            for n in removed:
                print(f"  - {n}")
        if not added and not removed:
            moved = old.get("sha") != sha
            print(f"\n无新增（仓库{'有更新，已有文章可能被修改' if moved else '无变化'}，共 {len(names)} 篇）")
    else:
        print(f"\n首次记录：{len(names)} 篇")

    import json
    STATE.write_text(json.dumps({"sha": sha, "docs": names}, ensure_ascii=False, indent=1), encoding="utf-8")


def clean(text: str) -> str:
    """去掉代码块、公式、图片、链接目标，只留中文正文用于统计。"""
    t = re.sub(r"```.*?```", "", text, flags=re.S)
    t = re.sub(r"\$\$.*?\$\$", "", t, flags=re.S)
    t = re.sub(r"\$[^$\n]*\$", "X", t)
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", t)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"<br\s*/?>", "\n", t)
    return t.strip()


def pct(part: int, whole: int) -> str:
    return f"{part / whole * 100:.1f}%" if whole else "—"


def analyse() -> str:
    files = sorted((CACHE / POST_DIR).rglob("*.md"))
    zh: list[tuple[str, str]] = []      # 中文文章（汉字 >= 200）
    en: list[tuple[str, str]] = []      # 英文文章（英文字母 >= 200、汉字 < 200）

    for f in files:
        raw = f.read_text(encoding="utf-8", errors="replace")
        body = clean(raw)
        body = re.sub(r"^创建于.*\n", "", body)
        body = re.sub(r"^关键词[:：].*\n", "", body)
        cn = len(re.findall(r"[\u4e00-\u9fa5]", body))
        en_letters = len(re.findall(r"[A-Za-z]", body))
        name = str(f.relative_to(CACHE / POST_DIR))
        if cn >= 200:
            zh.append((name, body))
        elif en_letters >= 200:
            en.append((name, body))
        # 两边都不够的（目录页、纯图片页）直接丢弃

    if not zh:
        sys.exit("缓存里没有找到中文文章，检查 sparse-checkout 是否生效")

    sents: list[int] = []
    paras: list[int] = []
    text = ""
    per_doc: list[tuple[str, int, int, float]] = []

    for name, body in zh:
        ps = [p.strip() for p in re.split(r"\n\s*\n", body) if len(p.strip()) > 20]
        ss = [s.strip() for s in re.split(r"[。！？；\n]", body) if len(s.strip()) > 4]
        paras += [len(p) for p in ps]
        sents += [len(s) for s in ss]
        text += body
        avg = sum(len(p) for p in ps) / len(ps) if ps else 0
        per_doc.append((name, len(body), len(ps), avg))

    cn = sum(len(re.findall(r"[\u4e00-\u9fa5]", b)) for _, b in zh)
    sents_sorted = sorted(sents)
    paras_sorted = sorted(paras)
    q = lambda seq, p: seq[min(int(len(seq) * p), len(seq) - 1)]

    lines: list[str] = []
    a = lines.append

    a(f"**同步时间**：{subprocess.run(['date', '+%Y-%m-%d %H:%M'], capture_output=True, text=True).stdout.strip()}")
    a("")
    a(f"**中文样本**：{len(zh)} 篇，正文 {cn:,} 个汉字。")
    a("")
    if en:
        a(f"**另有 {len(en)} 篇英文文章不计入中文统计**（英文标点会把括号、数字、英文词三项密度拉高）：")
        a("")
        for name, _ in en:
            a(f"- `{name}`")
        a("")
    a("| 指标 | 数值 | 读法 |")
    a("|---|---|---|")
    a(f"| 平均句长 | {sum(sents)/len(sents):.1f} 字 | 中位数 {q(sents_sorted, .5)}，说明靠长句拉高均值 |")
    a(f"| 句长分布 | P10 {q(sents_sorted, .1)} / P25 {q(sents_sorted, .25)} / P75 {q(sents_sorted, .75)} / P90 {q(sents_sorted, .9)} / 最长 {sents_sorted[-1]} | 长短混搭，不是均匀长句 |")
    a(f"| 超 40 字的句子 | {pct(sum(1 for s in sents if s > 40), len(sents))} | 约占一半 |")
    a(f"| 超 100 字的句子 | {pct(sum(1 for s in sents if s > 100), len(sents))} | 长句确实存在，不回避 |")
    a(f"| 段落中位长 | {q(paras_sorted, .5)} 字 | P90 {q(paras_sorted, .9)} 字，长段不罕见 |")
    a(f"| 超 200 字的段落 | {pct(sum(1 for p in paras if p > 200), len(paras))} | |")
    a("")
    a("**标点与用字密度（每千汉字）**")
    a("")
    a("| 项 | 每千字 | 项 | 每千字 |")
    a("|---|---|---|---|")
    pairs = [("逗号 ，", text.count("，")), ("句号 。", text.count("。")),
             ("顿号 、", text.count("、")), ("分号 ；", text.count("；")),
             ("冒号 ：", text.count("：")), ("问号 ？", text.count("？")),
             ("感叹号 ！", text.count("！")), ("破折号 ——", text.count("——")),
             ("括号", text.count("（") + text.count("(")), ("引号 “", text.count("“")),
             ("加粗 **", len(re.findall(r"\*\*[^*]+\*\*", text))), ("数字串", len(re.findall(r"\d+", text))),
             ("英文词", len(re.findall(r"[A-Za-z]{2,}", text))), ("的", text.count("的"))]
    for i in range(0, len(pairs), 2):
        left = f"{pairs[i][0]} | {pairs[i][1] / cn * 1000:.1f}"
        right = f"{pairs[i + 1][0]} | {pairs[i + 1][1] / cn * 1000:.1f}" if i + 1 < len(pairs) else " | "
        a(f"| {left} | {right} |")
    a("")
    a("**高频连接词（每千字）**")
    a("")
    liked = [(w, text.count(w)) for w in CONNECT if text.count(w)]
    liked.sort(key=lambda x: -x[1])
    a("常用：" + "、".join(f"{w} {c/cn*1000:.2f}" for w, c in liked[:10]))
    a("")
    avoided = [(w, text.count(w)) for w in AI_ISM if text.count(w)]
    a("几乎不用：" + ("、".join(f"{w} {c/cn*1000:.2f}" for w, c in avoided) if avoided else "上面列的 AI 腔词汇一个都没出现"))
    a("")
    a("**各篇规模（按字数前 8）**")
    a("")
    a("| 字数 | 段数 | 段落均长 | 文章 |")
    a("|---|---|---|---|")
    for name, n, np_, avg in sorted(per_doc, key=lambda x: -x[1])[:8]:
        a(f"| {n:,} | {np_} | {avg:.0f} | {name} |")
    a("")
    return "\n".join(lines)


def update_report(stats: str, check_only: bool, doc_names: list[str]) -> None:
    if check_only:
        print(f"\n统计共 {len(doc_names)} 篇（--check 模式，不写文件）")
        return
    if not REPORT.exists():
        sys.exit(f"找不到 {REPORT.relative_to(ROOT)}，先建好文件再跑")
    text = REPORT.read_text(encoding="utf-8")
    if BEGIN not in text or END not in text:
        sys.exit("writing-samples.md 里缺少 STATS:BEGIN / STATS:END 标记，无法定位插入位置")
    head, rest = text.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    REPORT.write_text(f"{head}{BEGIN}\n\n{stats}\n{END}{tail}", encoding="utf-8")
    print(f"已更新 {REPORT.relative_to(ROOT)}")


def main() -> None:
    ap = argparse.ArgumentParser(description="同步博客并统计文字习惯")
    ap.add_argument("--check", action="store_true", help="只检查，不写文件")
    ap.add_argument("--no-pull", action="store_true", help="跳过同步，用本地缓存重算")
    args = ap.parse_args()

    sync(args.no_pull)
    sha, names = manifest()
    report_changes(sha, names)
    stats = analyse()
    if args.check:
        print(stats)
    update_report(stats, args.check, names)


if __name__ == "__main__":
    main()
