"""
抖音（douyin）parser

原理：
  1. 用手机 UA 跟随分享短链（v.douyin.com）重定向，拿到 /video/{item_id} 落地页
  2. 用桌面 UA 请求视频页 HTML，页面内嵌的 JSON 里有 play_addr（含水印版直链，域名含 playwm）
  3. 把 playwm 替换为 play 即得到平台下发的无水印直链
  同时从页面 JSON 提取标题（desc）、作者（nickname）、封面。

已知限制：
  - 抖音反爬最严，页面经常要求 ttwid/msToken 等 Cookie，缺 Cookie 时页面可能返回空数据
    → 可在服务端环境变量 COOKIE_DOUYIN 配置登录后 Cookie（格式：k1=v1; k2=v2）
  - a_bogus 签名机制升级时本方案会整体失效，需要跟进社区方案更新
  - 图集（多图）作品没有视频直链，会返回 parse_failed 并说明

坏了先查哪里：
  1. 先看页面 HTML 是否还能拿到（是否被重定向到登录/验证码页）
  2. 再看页面内 play_addr 字段结构是否变化（在 HTML 里搜 play_addr 看字段名）
  3. 社区开源项目（搜索 douyin parser / TikTokApi 相关仓库）通常 1-2 天内会有人修
"""

import os
import re

from .base import (
    ParseError,
    fetch_text,
    parse_cookie_string,
    resolve_url,
    first_group,
    UA_DESKTOP,
)

PLATFORM_ID = "douyin"
PLATFORM_NAME = "抖音"

# play_addr 的多种可能写法，按优先级尝试
PLAY_PATTERNS = [
    r'"play_addr"\s*:\s*\{\s*"uri"\s*:\s*"[^"]*"\s*,\s*"url_list"\s*:\s*\[\s*"([^"]+)"',
    r'"play_addr"\s*:\s*\{\s*"url_list"\s*:\s*\[\s*"([^"]+)"',
    r'"playAddr"\s*:\s*"([^"]+)"',
    r'"(https?://[^"]*?/playwm/[^"]*?\.mp4[^"]*)"',
]

TITLE_PATTERNS = [r'"desc"\s*:\s*"((?:[^"\\]|\\.)*)"']
AUTHOR_PATTERNS = [r'"nickname"\s*:\s*"([^"]+)"']
COVER_PATTERNS = [
    r'"origin_cover"\s*:\s*\{\s*"url_list"\s*:\s*\[\s*"([^"]+)"',
    r'"cover"\s*:\s*\{\s*"url_list"\s*:\s*\[\s*"([^"]+)"',
    r'"cover"\s*:\s*"([^"]+)"',
]


def _unescape(s: str) -> str:
    # 页面 JSON 里是转义过的 URL：https:\/\/xxx → https://xxx
    return s.replace("\\/", "/").replace("\\u0026", "&") if s else s


async def parse(url: str) -> dict:
    final_url = await resolve_url(url, ua="mobile")
    m = re.search(r"/video/(\d+)", final_url)
    if not m:
        # 也可能是 note/ 分享形态
        m = re.search(r"/note/(\d+)", final_url)
        if not m:
            raise ParseError("invalid_url", "未能从链接中识别出抖音视频 ID")
    item_id = m.group(1)

    cookie_str = os.environ.get("COOKIE_DOUYIN", "")
    cookies = parse_cookie_string(cookie_str) if cookie_str else None

    page_url = f"https://www.douyin.com/video/{item_id}"
    html = await fetch_text(
        page_url,
        ua="desktop",
        headers={"Referer": "https://www.douyin.com/", "User-Agent": UA_DESKTOP},
        cookies=cookies,
    )
    if "验证码" in html and "play_addr" not in html:
        raise ParseError(
            "parse_failed",
            "抖音返回了验证码/风控页，解析被拦截。可尝试在服务端配置 COOKIE_DOUYIN 后重试",
        )

    raw_play = first_group(PLAY_PATTERNS, html)
    if not raw_play:
        raise ParseError(
            "parse_failed",
            "未能从抖音页面提取到播放地址（页面结构可能已变更，或为图集作品）",
        )
    play_url = _unescape(raw_play)
    # playwm（含水印）→ play（无水印）：这是抖音下发直链的固定规律
    video_url = play_url.replace("playwm", "play")

    title = _unescape(first_group(TITLE_PATTERNS, html)) or ""
    author = _unescape(first_group(AUTHOR_PATTERNS, html)) or ""
    cover = _unescape(first_group(COVER_PATTERNS, html)) or ""

    return {
        "platform": PLATFORM_ID,
        "platform_name": PLATFORM_NAME,
        "title": title,
        "author": author,
        "cover": cover,
        "video_url": video_url,
        "duration": None,
    }
