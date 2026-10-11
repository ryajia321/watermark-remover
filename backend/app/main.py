"""
去水印视频解析后端服务入口（FastAPI）。

API 契约：
  POST /api/parse      {"url": "视频分享链接"}
    成功 → {"ok": true, "platform": "douyin", "platform_name": "抖音",
            "title": ..., "author": ..., "cover": ..., "video_url": ..., "duration": ...}
    失败 → {"ok": false, "code": "unsupported|parse_failed|needs_login|invalid_url",
            "error": "中文错误信息"}
  GET /api/platforms   {"platforms": [{"id": "douyin", "name": "抖音", "status": "ok"}, ...]}
  GET /api/health       {"ok": true}

CORS 全开（allow_origins=["*"]），方便网页前端与微信小程序直接调用。
注意：生产环境如需收紧跨域，把 allow_origins 改成你的前端域名。
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.parsers import PLATFORMS, parse_url
from app.parsers.base import ParseError

app = FastAPI(title="去水印视频解析服务", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ParseRequest(BaseModel):
    url: str


@app.post("/api/parse")
async def api_parse(req: ParseRequest):
    try:
        data = await parse_url(req.url)
        return {"ok": True, **data}
    except ParseError as e:
        return {"ok": False, "code": e.code, "error": e.message}
    except Exception as e:  # 最后一道防线，保证永远返回契约格式
        return {"ok": False, "code": "parse_failed", "error": f"解析失败：{e}"}


@app.get("/api/platforms")
async def api_platforms():
    return {"platforms": PLATFORMS}


@app.get("/api/health")
async def api_health():
    return {"ok": True}


# 本地开发启动：python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
