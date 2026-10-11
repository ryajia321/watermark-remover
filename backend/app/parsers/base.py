"""
公共基础模块：统一异常、HTTP 工具函数（httpx + 浏览器 UA + 重定向跟随 + 超时）。

所有 parser 共用这里的工具，保持请求行为一致，便于统一排查网络问题。
"""

import json
import re
from typing import Any, Optional

import httpx

# ---------------------------------------------------------------------------
# 统一异常：main.py 会把它转成 API 契约格式 {"ok": false, "code": ..., "error": ...}
# code 取值必须在契约范围内：unsupported / parse_failed / needs_login / invalid_url
# ---------------------------------------------------------------------------
class ParseError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


# ---------------------------------------------------------------------------
# 浏览器 UA 伪装：各平台对爬虫 UA 会直接拦截，用真实浏览器 UA 是基本要求
# ---------------------------------------------------------------------------
UA_DESKTOP = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
UA_MOBILE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
)
UA_ANDROID = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36"
)

DEFAULT_TIMEOUT = 20.0


def _headers(ua: str = "desktop", extra: Optional[dict] = None) -> dict:
    h = {
        "User-Agent": {"desktop": UA_DESKTOP, "mobile": UA_MOBILE, "android": UA_ANDROID}.get(ua, UA_DESKTOP),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    if extra:
        h.update(extra)
    return h


def parse_cookie_string(cookie_str: str) -> dict:
    """把 'a=1; b=2' 形式的 Cookie 字符串转成 dict。"""
    out = {}
    for part in (cookie_str or "").split(";"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


async def fetch_text(
    url: str,
    *,
    ua: str = "desktop",
    headers: Optional[dict] = None,
    cookies: Optional[dict] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> str:
    """GET 网页文本，自动跟随重定向。失败抛 ParseError(parse_failed)。"""
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout,
            headers=_headers(ua, headers),
            cookies=cookies,
            # 不继承系统代理环境变量：避免脏代理配置导致请求失败，
            # 服务直连公网的行为更可预期；如部署环境必须走代理，请改这里
            trust_env=False,
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.text
    except ParseError:
        raise
    except Exception as e:
        raise ParseError("parse_failed", f"请求页面失败：{e}")


async def fetch_json(
    url: str,
    *,
    params: Optional[dict] = None,
    ua: str = "desktop",
    headers: Optional[dict] = None,
    cookies: Optional[dict] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Any:
    """GET JSON 接口。失败抛 ParseError(parse_failed)。"""
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout,
            headers=_headers(ua, headers),
            cookies=cookies,
            # 不继承系统代理环境变量：避免脏代理配置导致请求失败，
            # 服务直连公网的行为更可预期；如部署环境必须走代理，请改这里
            trust_env=False,
        ) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
    except ParseError:
        raise
    except Exception as e:
        raise ParseError("parse_failed", f"请求接口失败：{e}")


async def resolve_url(url: str, *, ua: str = "mobile", timeout: float = DEFAULT_TIMEOUT) -> str:
    """跟随短链重定向，返回最终落地 URL。失败抛 ParseError(parse_failed)。"""
    try:
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=timeout, headers=_headers(ua), trust_env=False
        ) as client:
            resp = await client.get(url)
            return str(resp.url)
    except Exception as e:
        raise ParseError("parse_failed", f"短链还原失败：{e}")


def first_group(patterns: list, text: str, flags: int = 0) -> Optional[str]:
    """按顺序尝试多个正则，返回第一个命中的第 1 分组。"""
    for p in patterns:
        m = re.search(p, text, flags)
        if m:
            return m.group(1)
    return None


def extract_window_var(html: str, var_name: str) -> Optional[Any]:
    """提取页面中的 window.VAR = {...}; JSON 变量，返回解析后的对象。"""
    m = re.search(r"window\." + re.escape(var_name) + r"\s*=\s*(\{.*?\});", html, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None


def deep_find(obj: Any, key: str, _depth: int = 0, _max: int = 8) -> Optional[Any]:
    """在嵌套 dict/list 中按 key 深度查找第一个命中的值。"""
    if _depth > _max or obj is None:
        return None
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            r = deep_find(v, key, _depth + 1, _max)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = deep_find(v, key, _depth + 1, _max)
            if r is not None:
                return r
    return None


def strip_html(text: str) -> str:
    """去掉微博等平台文案里的 HTML 标签。"""
    text = re.sub(r"<[^>]+>", "", text or "")
    return text.replace("&nbsp;", " ").strip()
