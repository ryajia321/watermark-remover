"""
B站（bilibili）parser

原理：
  1. 从分享链接提取 BV 号（或 av 号）
  2. 调公开接口 x/web-interface/view 拿视频信息：标题、作者、封面、cid（分P id）、时长
  3. 调公开接口 x/player/playurl（带 Referer 头）拿 durl 直链
  这两个接口免登录可用，返回的直链本身就是无水印的。

已知限制：
  - 未登录时清晰度会被限制（一般最高到 720p/1080p，取决于稿件），qn 参数会被服务端降级
  - 番剧、付费课程、部分限免内容需要登录/大会员 → 返回 needs_login
  - 多分 P 视频默认只取 P1
  - b23.tv 短链由路由层先还原再识别

坏了先查哪里：
  - view 接口返回的 code 字段：0=正常；-404=稿件不存在；62002=稿件不可见；
    -412=请求被拦截（IP 风控，换出口 IP 或加延迟）；412 也可能是缺 Referer
  - playurl 返回空 durl：多半是需要登录的内容，检查 msg 字段
"""

import re

from .base import ParseError, fetch_json, UA_DESKTOP

API_VIEW = "https://api.bilibili.com/x/web-interface/view"
API_PLAYURL = "https://api.bilibili.com/x/player/playurl"

PLATFORM_ID = "bilibili"
PLATFORM_NAME = "哔哩哔哩"


async def parse(url: str) -> dict:
    m = re.search(r"BV[0-9A-Za-z]{10}", url)
    bvid = m.group(0) if m else None
    aid = None
    if not bvid:
        m2 = re.search(r"[Aa][Vv](\d+)", url)
        if not m2:
            raise ParseError("invalid_url", "未在链接中找到 BV 号或 AV 号，请检查链接是否完整")
        aid = m2.group(1)

    ident = {"bvid": bvid} if bvid else {"aid": aid}
    view = await fetch_json(
        API_VIEW,
        params=ident,
        headers={"Referer": "https://www.bilibili.com", "User-Agent": UA_DESKTOP},
    )
    code = view.get("code")
    if code != 0:
        msg = view.get("message", "")
        if code in (-404, 62002):
            raise ParseError("parse_failed", f"该视频不存在或不可见（{msg}）")
        raise ParseError("parse_failed", f"B站视频信息接口异常（code={code}）：{msg}")

    data = view.get("data") or {}
    pages = data.get("pages") or []
    cid = pages[0].get("cid") if pages else data.get("cid")
    if not cid:
        raise ParseError("parse_failed", "未能获取到视频分P信息")

    title = data.get("title", "") or ""
    author = ((data.get("owner") or {}).get("name")) or ""
    cover = data.get("pic", "") or ""
    duration = data.get("duration")

    play_params = dict(ident)
    play_params.update({"cid": cid, "qn": 80, "fnval": 1, "fourk": 1})
    referer = f"https://www.bilibili.com/video/{bvid}" if bvid else f"https://www.bilibili.com/video/av{aid}"
    pu = await fetch_json(
        API_PLAYURL,
        params=play_params,
        headers={"Referer": referer, "User-Agent": UA_DESKTOP},
    )
    if pu.get("code") != 0:
        raise ParseError("needs_login", f"该视频需要登录后才能获取播放地址（{pu.get('message', '')}）")
    durl = ((pu.get("data") or {}).get("durl")) or []
    if not durl or not durl[0].get("url"):
        raise ParseError("parse_failed", "未能获取到视频直链，该内容可能需要登录")

    return {
        "platform": PLATFORM_ID,
        "platform_name": PLATFORM_NAME,
        "title": title,
        "author": author,
        "cover": cover,
        "video_url": durl[0]["url"],
        "duration": duration,
    }
