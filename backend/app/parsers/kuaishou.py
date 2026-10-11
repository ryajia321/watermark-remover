"""
快手（kuaishou）parser

原理：
  1. 用手机 UA 跟随分享短链（v.kuaishou.com / c.kuaishou.com）重定向，拿到作品落地页
     （形如 https://www.kuaishou.com/short-video/{photoId} 或 https://v.kuaishou.com/xxx）
  2. 请求作品页 HTML，页面内嵌的 window.__APOLLO_STATE__ / __INITIAL_STATE__ 里
     含有 videoUrl 字段，快手下发的该直链本身就是无水印的
  同时提取 caption（文案）、userName（作者）、poster（封面）。

已知限制：
  - 快手页面结构变更频繁，__APOLLO_STATE__ 的字段路径可能变化，
    本实现用深度查找兜底（videoUrl / photoUrl / manifest），尽量兼容
  - 部分私密/删除作品、直播回放无法解析
  - 风控严格时可能需要 Cookie，可配 COOKIE_KUAISHOU

坏了先查哪里：
  1. 在作品页 HTML 里搜索 videoUrl / __APOLLO_STATE__，看字段是否还在
  2. 检查是否被跳转到风控页（页面含"验证"字样且无视频数据）
  3. 抓包对比官方 App/小程序的请求，确认直链字段名
"""

import os
import re

from .base import (
    ParseError,
    fetch_text,
    parse_cookie_string,
    resolve_url,
    extract_window_var,
    deep_find,
    first_group,
    UA_DESKTOP,
)

PLATFORM_ID = "kuaishou"
PLATFORM_NAME = "快手"

TITLE_PATTERNS = [r'"caption"\s*:\s*"((?:[^"\\]|\\.)*)"', r"<title>([^<]+)</title>"]
AUTHOR_PATTERNS = [r'"userName"\s*:\s*"([^"]+)"']


def _unescape(s: str) -> str:
    return s.replace("\\/", "/").replace("\\u0026", "&") if s else s


async def parse(url: str) -> dict:
    final_url = await resolve_url(url, ua="mobile")

    cookie_str = os.environ.get("COOKIE_KUAISHOU", "")
    cookies = parse_cookie_string(cookie_str) if cookie_str else None

    html = await fetch_text(
        final_url,
        ua="desktop",
        headers={"Referer": "https://www.kuaishou.com/", "User-Agent": UA_DESKTOP},
        cookies=cookies,
    )

    video_url = None
    # 策略1：从 __APOLLO_STATE__ 结构化数据里深度查找
    for var in ("__APOLLO_STATE__", "__INITIAL_STATE__"):
        state = extract_window_var(html, var)
        if state:
            for key in ("videoUrl", "photoUrl"):
                v = deep_find(state, key)
                if v and isinstance(v, str) and v.startswith("http"):
                    video_url = v
                    break
        if video_url:
            break

    # 策略2：正则兜底直接扫页面里的直链
    if not video_url:
        raw = first_group(
            [
                r'"videoUrl"\s*:\s*"(https?://[^"]+)"',
                r'"photoUrl"\s*:\s*"(https?://[^"]+?\.mp4[^"]*)"',
                r'"(https?://[^"]*?kwimgs\.com[^"]*?\.mp4[^"]*)"',
            ],
            html,
        )
        if raw:
            video_url = _unescape(raw)

    if not video_url:
        raise ParseError(
            "parse_failed",
            "未能从快手页面提取到视频直链（页面结构可能已变更，或作品已删除/私密）",
        )

    title = _unescape(first_group(TITLE_PATTERNS, html)) or ""
    # 去掉 <title> 里常见的 " - 快手" 后缀
    title = re.sub(r"\s*[-_]\s*快手.*$", "", title)
    author = _unescape(first_group(AUTHOR_PATTERNS, html)) or ""

    return {
        "platform": PLATFORM_ID,
        "platform_name": PLATFORM_NAME,
        "title": title,
        "author": author,
        "cover": "",
        "video_url": _unescape(video_url),
        "duration": None,
    }
