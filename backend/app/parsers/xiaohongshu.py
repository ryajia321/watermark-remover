"""
小红书（xiaohongshu）parser

原理：
  1. 从分享链接提取 noteId：xhslink.com 短链先跟随重定向到
     www.xiaohongshu.com/explore/{noteId} 或 /discovery/item/{noteId}
     （noteId 为 24 位十六进制）
  2. 调小红书 web 端 feed 接口：
     GET https://edith.xiaohongshu.com/api/sns/web/v1/feed?source_note_id={noteId}
  3. 从返回的 note_card 里取：标题/文案、作者昵称、封面、video.media.stream.h264 的 master_url
     该直链为无水印版本。

已知限制（重要）：
  - 该接口几乎一定需要登录 Cookie（a1、web_session 等），无 Cookie 会返回登录态错误
    → 必须在服务端配置环境变量 COOKIE_XIAOHONGSHU（浏览器登录小红书后复制 Cookie 字符串）
  - Cookie 会过期，需要定期更新；这是小红书解析最常见的"坏了"原因
  - 图文笔记没有视频流，会返回 parse_failed 并说明

坏了先查哪里：
  1. 先检查 Cookie 是否过期：直接调 feed 接口看是否返回登录相关错误码
  2. 再看接口路径/参数是否变化（抓包网页版小红书点开一篇笔记的请求）
  3. x-s / x-t 签名升级时需要更新签名逻辑（本实现未做签名，依赖 Cookie 直调）
"""

import os
import re

from .base import ParseError, fetch_json, parse_cookie_string, resolve_url, deep_find

PLATFORM_ID = "xiaohongshu"
PLATFORM_NAME = "小红书"

API_FEED = "https://edith.xiaohongshu.com/api/sns/web/v1/feed"


async def parse(url: str) -> dict:
    m = re.search(r"/(?:explore|discovery/item)/([0-9a-f]{24})", url)
    if not m:
        # 可能是 xhslink 短链，先还原
        final_url = await resolve_url(url, ua="mobile")
        m = re.search(r"/(?:explore|discovery/item)/([0-9a-f]{24})", final_url)
    if not m:
        raise ParseError("invalid_url", "未能从链接中识别出小红书笔记 ID")
    note_id = m.group(1)

    cookie_str = os.environ.get("COOKIE_XIAOHONGSHU", "")
    if not cookie_str:
        raise ParseError(
            "needs_login",
            "小红书解析需要登录态，请在服务端配置环境变量 COOKIE_XIAOHONGSHU（浏览器登录后复制 Cookie）后再试",
        )
    cookies = parse_cookie_string(cookie_str)

    data = await fetch_json(
        API_FEED,
        params={"source_note_id": note_id, "image_formats": "jpg,webp,avif"},
        ua="desktop",
        headers={
            "Referer": f"https://www.xiaohongshu.com/explore/{note_id}",
            "Origin": "https://www.xiaohongshu.com",
        },
        cookies=cookies,
    )
    items = (data.get("data") or {}).get("items") or []
    if not items:
        raise ParseError(
            "needs_login",
            "小红书接口未返回数据，Cookie 可能已过期或被风控，请更新 COOKIE_XIAOHONGSHU 后重试",
        )
    card = (items[0].get("note_card") or {})

    title = card.get("title") or card.get("desc") or ""
    user = card.get("user") or {}
    author = user.get("nickname", "") or ""
    cover = (((card.get("cover") or {}).get("url_default")) or "") or ""

    video = card.get("video") or {}
    if not video:
        raise ParseError("parse_failed", "该笔记为图文类型，没有可下载的视频")
    media = video.get("media") or {}
    stream = media.get("stream") or {}
    h264 = stream.get("h264") or []
    video_url = ""
    if h264:
        # 取码率最高的一档
        best = max(h264, key=lambda s: s.get("bitrate", 0) or 0)
        video_url = best.get("master_url") or ""
    if not video_url:
        # 兜底：深度查找任意 master_url
        v = deep_find(video, "master_url")
        video_url = v if isinstance(v, str) else ""
    if not video_url:
        raise ParseError("parse_failed", "未能从小红书接口提取到视频直链")

    duration = (video.get("duration") or video.get("media", {}).get("duration"))

    return {
        "platform": PLATFORM_ID,
        "platform_name": PLATFORM_NAME,
        "title": title,
        "author": author,
        "cover": cover,
        "video_url": video_url,
        "duration": duration,
    }
