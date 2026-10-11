"""
微信视频号（wechat）parser

原理（为什么这里直接返回 needs_login）：
  视频号的 Web 播放接口（channels.weixin.qq.com）需要微信登录态（Cookie 中的
  session 凭证）才能请求，未登录请求会被拒绝或跳转到扫码登录页。
  服务端没有用户扫码授权就拿不到这个登录态，因此常规服务端解析方案对视频号
  基本不可行——这是平台限制，不是代码 bug。

已知限制：
  - 未配置登录 Cookie 时：直接返回 needs_login（当前行为）
  - 即使配置了 Cookie：Cookie 与微信号强绑定、有效期短、异地登录易触发风控，
    不适合作为稳定的服务端方案

坏了先查哪里：
  - 如果未来要支持：需要在服务端维护一个已登录微信的 Cookie 池
    （环境变量 COOKIE_WECHAT），并实现 finder/getFeed 接口的签名逻辑；
    先在浏览器登录视频号网页版抓包确认接口与参数
  - 替代方案：引导用户在微信内用小程序"转发给朋友"式的能力，或让用户
    自行下载后上传（小程序端可直接用 wx.chooseVideo）

当前行为：识别出视频号链接后，直接返回 needs_login 的中文提示，
告诉用户原因和替代办法，不伪装成"解析失败"。
"""

import re

from .base import ParseError

PLATFORM_ID = "wechat"
PLATFORM_NAME = "微信视频号"


async def parse(url: str) -> dict:
    # 能识别即可；真正的拉取需要登录态，这里如实告知
    if not re.search(r"finder|channels|weixin\.qq\.com.*video|mp\.weixin\.qq\.com", url, re.I):
        # 路由层已经判定是视频号域名，走到这里说明链接形态异常
        raise ParseError("invalid_url", "未能识别出有效的微信视频号链接")
    raise ParseError(
        "needs_login",
        "微信视频号需要微信登录态才能解析，服务端暂不支持。"
        "替代办法：在微信内打开该视频后，用转发/收藏方式保存，或在小程序端直接上传本地视频文件",
    )
