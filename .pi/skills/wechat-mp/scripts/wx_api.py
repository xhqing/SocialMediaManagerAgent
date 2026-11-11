#!/usr/bin/env python3
"""微信公众平台 API 客户端（草稿箱链路：token / 正文图 / 永久素材 / 草稿）。

凭证位置（按优先级）：
    1. 环境变量 WECHAT_MP_CONFIG 指定的文件
    2. ~/.wechat-mp/config.json

配置格式：
    {"appid": "wx...", "appsecret": "...", "use_proxy": false}

设计要点：
- 默认直连、绕过系统代理（api.weixin.qq.com 在国内，走代理慢且出口 IP 不同，
  而出口 IP 必须与公众号后台「IP 白名单」一致）；
- access_token 用稳定版接口（/cgi-bin/stable_token）并本地缓存，提前 5 分钟刷新；
- 所有报错统一打印 errcode / errmsg，并对 40164（IP 不在白名单）给出可操作提示。
"""

from __future__ import annotations

import json
import os
import sys
import pathlib
import time
from typing import Any

import requests

BASE = "https://api.weixin.qq.com"
DEFAULT_CONFIG = "~/.wechat-mp/config.json"
TOKEN_CACHE = "~/.wechat-mp/token.json"
TOKEN_SAFETY = 300  # 提前 5 分钟刷新


def config_path() -> pathlib.Path:
    return pathlib.Path(os.environ.get("WECHAT_MP_CONFIG") or DEFAULT_CONFIG).expanduser()


def load_config() -> dict[str, Any]:
    p = config_path()
    if not p.exists():
        raise SystemExit(
            f"未找到凭证文件 {p}\n"
            f"请先运行：python3 {pathlib.Path(__file__).parent / 'setup_config.py'}"
        )
    cfg = json.loads(p.read_text(encoding="utf-8"))
    for k in ("appid", "appsecret"):
        if not cfg.get(k):
            raise SystemExit(f"凭证文件 {p} 缺少 {k}")
    return cfg


class WxError(RuntimeError):
    def __init__(self, errcode: int, errmsg: str, api: str):
        self.errcode, self.errmsg, self.api = errcode, errmsg, api
        hint = ""
        if errcode == 40164 or "not in whitelist" in errmsg:
            hint = "\n  → 这是 IP 白名单问题：把上面报错里的 IP 加进「微信开发者平台 → 我的业务 → 公众号/服务号 → 基础信息 → 开发密钥」的 API IP 白名单（可填 IP 段；白名单为空也会报 40164）"
        elif errcode == 48001:
            hint = "\n  → api unauthorized：该账号没有这个接口权限（个人主体账号常见，见 SKILL.md「账号资质」节）"
        elif errcode == 40007:
            hint = "\n  → 无效 media_id：素材/草稿 id 不对，或素材不属于该账号"
        super().__init__(f"[{api}] errcode={errcode} errmsg={errmsg}{hint}")


class WxClient:
    def __init__(self, cfg: dict[str, Any] | None = None, verbose: bool = True):
        self.cfg = cfg or load_config()
        self.verbose = verbose
        self.s = requests.Session()
        # 默认绕过系统代理（HTTP_PROXY 等环境变量），保证出口 IP 与白名单一致
        self.s.trust_env = bool(self.cfg.get("use_proxy", False))
        self._token: str | None = None

    # ---------------------------------------------------------------- token
    def token(self, force: bool = False) -> str:
        if self._token and not force:
            return self._token
        cache = pathlib.Path(TOKEN_CACHE).expanduser()
        if not force and cache.exists():
            try:
                data = json.loads(cache.read_text(encoding="utf-8"))
                if data.get("appid") == self.cfg["appid"] and data.get("expire_at", 0) > time.time() + TOKEN_SAFETY:
                    self._token = data["access_token"]
                    return self._token
            except Exception:
                pass
        r = self.s.post(
            f"{BASE}/cgi-bin/stable_token",
            json={"grant_type": "client_credential", "appid": self.cfg["appid"], "secret": self.cfg["appsecret"]},
            timeout=20,
        )
        data = r.json()
        if "access_token" not in data:
            raise WxError(data.get("errcode", -1), data.get("errmsg", str(data)), "stable_token")
        self._token = data["access_token"]
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(
            json.dumps({"appid": self.cfg["appid"], "access_token": self._token,
                        "expire_at": time.time() + int(data.get("expires_in", 7200))}, ensure_ascii=False),
            encoding="utf-8",
        )
        cache.chmod(0o600)
        if self.verbose:
            print(f"[wx] 取到 access_token（有效期 {data.get('expires_in')}s）")
        return self._token

    # ---------------------------------------------------------------- 通用请求
    def _check(self, data: dict, api: str) -> dict:
        if data.get("errcode") not in (0, None):
            raise WxError(int(data["errcode"]), str(data.get("errmsg", "")), api)
        return data

    def _post(self, path: str, api: str, **kw) -> dict:
        kw.setdefault("timeout", 60)
        r = self.s.post(f"{BASE}{path}?access_token={self.token()}", **kw)
        # 微信响应均为 UTF-8 但不总带 charset 声明，显式解码避免中文乱码
        return self._check(json.loads(r.content.decode("utf-8")), api)

    def _get(self, path: str, api: str, **kw) -> dict:
        kw.setdefault("timeout", 30)
        r = self.s.get(f"{BASE}{path}?access_token={self.token()}", **kw)
        return self._check(json.loads(r.content.decode("utf-8")), api)

    # ---------------------------------------------------------------- 素材
    def upload_content_image(self, path: str | pathlib.Path) -> str:
        """上传正文图（不占素材配额），返回 mmbiz 图床 URL。限制：jpg/png，<1MB。"""
        p = pathlib.Path(path)
        with p.open("rb") as f:
            data = self._post("/cgi-bin/media/uploadimg", "media/uploadimg",
                              files={"media": (p.name, f, "image/png")})
        return data["url"]

    def upload_permanent_image(self, path: str | pathlib.Path) -> str:
        """上传永久图片素材（封面用），返回 media_id。"""
        p = pathlib.Path(path)
        with p.open("rb") as f:
            data = self._post("/cgi-bin/material/add_material", "material/add_material",
                              params={"type": "image"},
                              files={"media": (p.name, f, "image/png")})
        return data["media_id"]

    # ---------------------------------------------------------------- 草稿
    def add_draft(self, articles: list[dict]) -> str:
        data = self._post("/cgi-bin/draft/add", "draft/add",
                          data=json.dumps({"articles": articles}, ensure_ascii=False).encode("utf-8"),
                          headers={"Content-Type": "application/json; charset=utf-8"})
        return data["media_id"]

    def get_draft(self, media_id: str) -> dict:
        return self._post("/cgi-bin/draft/get", "draft/get",
                          data=json.dumps({"media_id": media_id}, ensure_ascii=False).encode("utf-8"),
                          headers={"Content-Type": "application/json; charset=utf-8"})

    def update_draft(self, media_id: str, article: dict, index: int = 0) -> dict:
        """更新草稿中第 index 篇（media_id 不变）；articles 为单篇对象（非数组）。"""
        return self._post("/cgi-bin/draft/update", "draft/update",
                          data=json.dumps({"media_id": media_id, "index": index,
                                           "articles": article}, ensure_ascii=False).encode("utf-8"),
                          headers={"Content-Type": "application/json"})

    def delete_draft(self, media_id: str) -> dict:
        return self._post("/cgi-bin/draft/delete", "draft/delete",
                          data=json.dumps({"media_id": media_id}, ensure_ascii=False).encode("utf-8"),
                          headers={"Content-Type": "application/json; charset=utf-8"})

    def list_drafts(self, offset: int = 0, count: int = 20) -> dict:
        return self._post("/cgi-bin/draft/batchget", "draft/batchget",
                          data=json.dumps({"offset": offset, "count": count, "no_content": 1},
                                          ensure_ascii=False).encode("utf-8"),
                          headers={"Content-Type": "application/json; charset=utf-8"})


def show_egress_ip() -> None:
    """打印当前直连出口 IP（配白名单用）。"""
    s = requests.Session()
    s.trust_env = False
    try:
        r = s.get("https://myip.ipip.net", timeout=10)
        print("直连出口 IP：", r.text.strip())
    except Exception as e:
        print("查询失败：", e)


if __name__ == "__main__":
    """自检：取 token → 查草稿总数（只读，不产生任何内容）。

    另：python3 wx_api.py --ip  → 只查当前直连出口 IP（配 IP 白名单用）

    用法：python3 wx_api.py
    用途：配置好凭证与 IP 白名单后，先跑这个确认「凭证 + 草稿接口」是否可用。
    """
    if "--ip" in sys.argv:
        show_egress_ip()
        raise SystemExit(0)

    try:
        c = WxClient()
        tok = c.token()
        print(f"✅ 凭证可用：access_token = {tok[:10]}…（有效期缓存至 {TOKEN_CACHE}）")
        try:
            n = c._post("/cgi-bin/draft/count", "draft/count", data=b"{}",
                        headers={"Content-Type": "application/json"})
            print(f"✅ 草稿箱接口可用：当前草稿总数 {n.get('total_count', '?')}")
        except WxError as e:
            print(f"❌ 草稿箱接口不可用：{e}")
    except WxError as e:
        print(f"❌ 凭证或白名单有问题：{e}")
    except SystemExit as e:
        print(f"❌ 未配置凭证：{e}")
