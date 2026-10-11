"""
平台路由：按域名/链接特征识别平台，分发到对应 parser。

识别顺序：
  1. 链接格式校验（必须 http/https 开头）
  2. 通用短链（t.cn / b23.tv）先跟随重定向还原，再按落地域名识别
  3. 按域名后缀匹配各平台
  4. 匹配不到 → ParseError(unsupported)
"""

import re
from urllib.parse import urlparse

from . import bilibili, douyin, kuaishou, wechat, weibo, xiaohongshu
from .base import ParseError, resolve_url

# 供 GET /api/platforms 使用；status 字段：ok=可用，login=通常需要登录态
PLATFORMS = [
    {"id": "douyin", "name": "抖音", "status": "ok"},
    {"id": "kuaishou", "name": "快手", "status": "ok"},
    {"id": "xiaohongshu", "name": "小红书", "status": "login"},
    {"id": "bilibili", "name": "哔哩哔哩", "status": "ok"},
    {"id": "weibo", "name": "微博", "status": "ok"},
    {"id": "wechat", "name": "微信视频号", "status": "login"},
]

# 通用短链域名：先还原再识别
_GENERIC_SHORT_HOSTS = {"t.cn", "b23.tv"}

# (域名列表, parser 模块)
_ROUTES = [
    (("v.douyin.com", "douyin.com", "iesdouyin.com"), douyin),
    (("v.kuaishou.com", "c.kuaishou.com", "kuaishou.com", "gifshow.com"), kuaishou),
    (("xhslink.com", "xiaohongshu.com"), xiaohongshu),
    (("bilibili.com",), bilibili),
    (("weibo.com", "m.weibo.cn", "video.weibo.com"), weibo),
    (("channels.weixin.qq.com", "mp.weixin.qq.com", "weixin.qq.com"), wechat),
]


def _match_parser(host: str):
    for domains, mod in _ROUTES:
        for d in domains:
            if host == d or host.endswith("." + d):
                return mod
    return None


async def parse_url(url: str) -> dict:
    """识别平台并调用对应 parser，返回契约中的 data 部分（不含 ok 字段）。"""
    url = (url or "").strip()
    if not re.match(r"^https?://", url, re.I):
        raise ParseError("invalid_url", "链接格式不正确，请粘贴完整的视频分享链接（以 http 开头）")

    host = urlparse(url).netloc.lower()
    # 通用短链先还原
    if host in _GENERIC_SHORT_HOSTS:
        url = await resolve_url(url, ua="mobile")
        host = urlparse(url).netloc.lower()

    mod = _match_parser(host)
    if mod is None:
        raise ParseError(
            "unsupported",
            "暂不支持该平台，当前支持：抖音、快手、小红书、哔哩哔哩、微博、微信视频号",
        )
    try:
        return await mod.parse(url)
    except ParseError:
        raise
    except Exception as e:  # parser 内部未预料的异常统一转成 parse_failed
        raise ParseError("parse_failed", f"{mod.PLATFORM_NAME}解析失败：{e}")
