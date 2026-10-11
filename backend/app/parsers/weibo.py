"""
微博（weibo）parser

原理：
  1. 从分享链接提取微博 id：
     - m.weibo.cn/status/{数字id} 或 m.weibo.cn/detail/{数字id}：直接就是数字 id
     - weibo.com/{uid}/{mid62}：URL 里的是 base62 编码的 mid，需解码成数字 id
     - t.cn 短链：由路由层先还原再识别
  2. 调移动端公开接口 GET https://m.weibo.cn/statuses/show?id={数字id}
  3. 从 page_info.media_info 取 mp4_hd_url / mp4_sd_url / stream_url（无水印直链），
     文案从 text 字段去 HTML 标签，作者取 user.screen_name，封面取 page_info.page_pic

已知限制：
  - 部分视频（尤其是博主限免/付费内容）需要登录，无 Cookie 时 media_info 为空
    → 可配 COOKIE_WEIBO，缺 Cookie 且拿不到时返回 needs_login
  - 微博经常改版，page_info 结构变化时直链字段名可能变化
  - 已删除/不可见微博返回 parse_failed

坏了先查哪里：
  1. 直接浏览器打开 https://m.weibo.cn/statuses/show?id=xxx 看返回的 JSON 结构
  2. 确认 media_info / page_info 字段是否还在、字段名是否变化
  3. mid62 解码算法是微博固定规则，一般不会变，优先怀疑接口字段变化
"""

import os
import re

from .base import ParseError, fetch_json, parse_cookie_string, strip_html, UA_MOBILE

PLATFORM_ID = "weibo"
PLATFORM_NAME = "微博"

API_SHOW = "https://m.weibo.cn/statuses/show"

# 微博 mid 的 base62 字符表（固定）
_MID62_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def mid62_to_id(mid62: str) -> str:
    """把 weibo.com 链接里的 base62 mid 转成数字 id。"""
    s = mid62.lstrip("0")
    if not s:
        return "0"
    # 从右往左按 4 字符一组切分（微博规则），每组转成 7 位十进制
    out = ""
    while len(s) > 4:
        chunk, s = s[-4:], s[:-4]
        num = 0
        for ch in chunk:
            num = num * 62 + _MID62_ALPHABET.index(ch)
        out = str(num).zfill(7) + out
    num = 0
    for ch in s:
        num = num * 62 + _MID62_ALPHABET.index(ch)
    out = str(num) + out
    return out.lstrip("0") or "0"


async def parse(url: str) -> dict:
    numeric_id = None

    m = re.search(r"m\.weibo\.cn/(?:status|detail)/(\d+)", url)
    if m:
        numeric_id = m.group(1)
    else:
        m = re.search(r"weibo\.com/(?:\d+/)?([0-9A-Za-z]{7,})", url)
        if m:
            token = m.group(1)
            if token.isdigit():
                numeric_id = token
            else:
                try:
                    numeric_id = mid62_to_id(token)
                except ValueError:
                    numeric_id = None
    if not numeric_id:
        raise ParseError("invalid_url", "未能从链接中识别出微博 ID，请使用微博 App/网页的分享链接")

    cookie_str = os.environ.get("COOKIE_WEIBO", "")
    cookies = parse_cookie_string(cookie_str) if cookie_str else None

    data = await fetch_json(
        API_SHOW,
        params={"id": numeric_id},
        ua="mobile",
        headers={"Referer": "https://m.weibo.cn/", "User-Agent": UA_MOBILE},
        cookies=cookies,
    )
    if data.get("ok") == 0:
        raise ParseError("parse_failed", f"微博接口返回异常：{data.get('msg', '')}")

    status = data.get("data") or data
    page_info = status.get("page_info") or {}
    media_info = page_info.get("media_info") or {}

    video_url = (
        media_info.get("mp4_hd_url")
        or media_info.get("mp4_sd_url")
        or media_info.get("stream_url")
        or ""
    )
    if not video_url:
        # 有些视频藏在 url_struct 里
        for u in status.get("url_struct") or []:
            if isinstance(u, dict) and u.get("url_title", "").endswith((".mp4",)):
                video_url = u.get("url_title")
                break
    if not video_url:
        if not cookie_str:
            raise ParseError(
                "needs_login",
                "该微博视频需要登录后才能获取，可在服务端配置 COOKIE_WEIBO 后重试",
            )
        raise ParseError("parse_failed", "未能获取到该微博的视频直链（可能已删除或为纯图文）")

    title = strip_html(status.get("text", "") or page_info.get("title", ""))
    author = ((status.get("user") or {}).get("screen_name")) or ""
    cover = ((page_info.get("page_pic") or {}).get("url")) or ""

    return {
        "platform": PLATFORM_ID,
        "platform_name": PLATFORM_NAME,
        "title": title,
        "author": author,
        "cover": cover,
        "video_url": video_url,
        "duration": media_info.get("duration"),
    }
