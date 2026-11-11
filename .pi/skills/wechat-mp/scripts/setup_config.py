#!/usr/bin/env python3
"""写入公众号 API 凭证到本机配置文件（不进 git）。

用法：python3 setup_config.py
凭据在公众号后台 / 微信开发者平台获取：AppID、AppSecret（重置后只显示一次）。
写入位置：~/.wechat-mp/config.json（权限 600）

输入保护：粘贴时常会带进终端控制序列（bracketed paste 的 ESC[200~、方向键的 ESC[D）、
零宽字符或换行——本脚本会先清洗再存，并回显掩码（前 4 … 后 4 + 长度）供你核对。
"""

from __future__ import annotations

import getpass
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from wx_api import config_path  # noqa: E402

ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b[@-Z\\-_]|\x1b")
INVISIBLE = re.compile(r"[\u200b-\u200f\u2028\u2029\ufeff\x7f]")


def sanitize(raw: str) -> tuple[str, list[str]]:
    """清洗粘贴污染，返回 (干净值, 已清理项说明)。"""
    notes = []
    s = raw
    if ANSI.search(s):
        notes.append("终端控制序列")
        s = ANSI.sub("", s)
    if INVISIBLE.search(s):
        notes.append("零宽字符")
        s = INVISIBLE.sub("", s)
    if re.search(r"\s", s):
        notes.append("空白/换行")
        s = re.sub(r"\s+", "", s)
    return s, notes


def find_repeat(s: str, min_len: int = 12) -> tuple[int, int, int] | None:
    """找最长的重复块，返回 (长度, 位置A, 位置B)；没有则 None。"""
    for L in range(len(s) // 2, min_len - 1, -1):
        seen: dict[str, int] = {}
        for i in range(0, len(s) - L + 1):
            blk = s[i:i + L]
            if blk in seen:
                return L, seen[blk], i
            seen[blk] = i
    return None


def ask(prompt: str, pattern: str, allow_empty: bool = False, secret: bool = False) -> str:
    for attempt in range(4):
        raw = getpass.getpass(prompt) if secret else input(prompt)
        raw = raw.strip()
        if not raw and allow_empty:
            return ""
        val, notes = sanitize(raw)
        mask = (val[:4] + "…" + val[-4:]) if len(val) >= 8 else val
        if notes:
            print(f"  ⚠ 检测到并已清理：{'、'.join(notes)}")
        if not re.fullmatch(pattern, val):
            print(f"  ❌ 格式不对（长度 {len(val)}，掩码 {mask}）；应只含字母数字")
            continue
        if len(val) > 40:
            rep = find_repeat(val)
            if rep:
                L, a, b = rep
                print(f"  ⚠ 值里有长度 {L} 的重复块（位置 {a} 与 {b}），疑似重复粘贴——请确认")
        print(f"  ✓ 采用：{mask}（长度 {len(val)}）")
        return val
    raise SystemExit("连续多次输入不合格，已退出（未改动配置文件）")


def main() -> None:
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    old: dict = {}
    if p.exists():
        old = json.loads(p.read_text(encoding="utf-8"))
        print(f"已存在配置：{p}（直接回车＝保留原值）")

    print("AppID 形如 wx 开头的一串字符；AppSecret 一般是 32 位十六进制。")
    appid = ask(f"AppID（当前 {old.get('appid', '未设置')}），回车保留：",
                r"wx[0-9a-zA-Z]{8,20}", allow_empty=bool(old.get("appid"))) or old.get("appid", "")
    if not appid:
        raise SystemExit("AppID 不能为空")

    if old.get("appsecret"):
        print("AppSecret 输入不回显；直接回车＝保留原值：")
        secret = ask("AppSecret：", r"[0-9A-Za-z]{16,64}", allow_empty=True, secret=True)
        secret = secret or old["appsecret"]
    else:
        print("AppSecret 输入不回显；粘贴后回车即可：")
        secret = ask("AppSecret：", r"[0-9A-Za-z]{16,64}", secret=True)

    cfg = {"appid": appid, "appsecret": secret,
           "use_proxy": bool(old.get("use_proxy", False)),
           "author": old.get("author", "")}
    p.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    p.chmod(0o600)
    print(f"\n已写入 {p}（权限 600，不进 git）；author 字段 = {cfg['author'] or '（空）'}")
    print("下一步：把调用机器的公网出口 IP 加进「IP 白名单」（报错 40164 时会告知实际 IP）")
    print("自检：python3 " + str(pathlib.Path(__file__).parent / "wx_api.py"))


if __name__ == "__main__":
    main()
