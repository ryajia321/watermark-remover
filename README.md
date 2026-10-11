# 视频去水印工具

粘贴视频分享链接，一键解析出无水印下载地址。支持 **抖音 / 快手 / 小红书 / 哔哩哔哩 / 微博 / 微信视频号**。

## 目录结构

```
watermark-remover/
├── backend/          # 解析后端（Python FastAPI），必须部署到你自己的服务器
│   ├── app/main.py           # 接口入口：POST /api/parse
│   ├── app/parsers/          # 6 个平台解析器（每个文件头部有中文注释：原理/限制/排错）
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── .env.example          # Cookie 配置模板（小红书等需要登录态的平台用）
│   └── TEST_REPORT.md        # 测试报告（含未验证项，如实记录）
├── frontend/
│   └── index.html      # 去水印网站（单文件，手机/电脑都能用）
├── miniprogram/        # 微信小程序源码（原生框架）
│   ├── pages/index/    # 首页：粘贴链接 → 解析 → 预览 → 保存到相册
│   ├── pages/history/  # 历史记录
│   ├── pages/settings/ # 后端接口地址配置
│   └── README.md       # 小程序导入/上传指南
└── DEPLOY.md           # 完整部署指南（后端+网站+小程序上架）
```

## 三端如何配合

```
用户粘贴分享链接
      │ 网站 / 小程序
      ▼
POST {你的后端域名}/api/parse   {"url": "分享链接"}
      │ 后端解析
      ▼
{"ok": true, "video_url": "无水印直链", "title": ..., "cover": ...}
      │ 网站/小程序
      ▼
视频预览 → 下载 / 保存到相册
```

网站和小程序都不直接碰各视频平台（浏览器/小程序会被跨域和反爬拦），所有解析都在你的后端完成。

## 接口契约

- `POST /api/parse` 请求 `{"url": "分享链接"}`
  - 成功：`{"ok": true, "platform": "douyin", "platform_name": "抖音", "title": "标题", "author": "作者", "cover": "封面URL", "video_url": "无水印直链", "duration": 12.5}`
  - 失败：`{"ok": false, "code": "unsupported|parse_failed|needs_login|invalid_url", "error": "中文错误信息"}`
- `GET /api/platforms` 平台列表（含状态）
- `GET /api/health` 健康检查

## 本地快速试跑（5 分钟）

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8000
# 健康检查：curl http://127.0.0.1:8000/api/health  → {"ok":true}
```

然后用浏览器打开 `frontend/index.html`，在 ⚙️ 接口设置里填 `http://127.0.0.1:8000`，粘贴链接即可解析。

## 重要说明

1. **解析能力取决于各平台反爬策略**。平台一改规则，某个解析器就可能失效——每个 parser 文件头部都写了"坏了先查哪里"，按注释修即可。
2. **小红书 / 抖音**在反爬收紧时需要登录 Cookie：把浏览器里对应网站的 Cookie 填进 `.env`（见 `.env.example`），重启后端生效。
3. **微信视频号**服务端常规方案拿不到（需要微信登录态），后端会明确返回中文提示；小程序端可用"本地视频去水印"思路兜底。
4. 仅供学习交流，请勿搬运他人作品用于商用。

详细部署（服务器/域名/备案/小程序上架）见 [DEPLOY.md](DEPLOY.md)。
