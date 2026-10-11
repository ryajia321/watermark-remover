# 部署指南：后端 + 网站 + 小程序上架

按顺序做：**① 服务器 → ② 域名/备案 → ③ 后端 → ④ 网站 → ⑤ 小程序**。

---

## ① 准备一台服务器

- 腾讯云 / 阿里云轻量服务器（2 核 2G 足够，系统 Ubuntu 22.04）
- 放行安全组端口：`80`、`443`（网站/接口用），`8000` 仅内网用、不建议直接对外

## ② 域名 + HTTPS + 备案

1. 注册一个域名（如 `api.example.com` 给后端，`tool.example.com` 给网站）
2. **ICP 备案**：服务器在国内就必须备案（腾讯云/阿里云后台提交，约 1–2 周）。小程序的 request 合法域名必须是**已备案**域名。
3. 域名解析：`api.example.com` → 服务器 IP
4. HTTPS 证书（免费）：`apt install certbot && certbot --nginx -d api.example.com`，或用云厂商的免费证书

## ③ 部署后端

```bash
# 服务器上
git clone <你放代码的仓库> watermark-remover   # 或 scp 上传 backend/ 目录
cd watermark-remover/backend
docker build -t wm-backend .
docker run -d --name wm-backend --restart always -p 127.0.0.1:8000:8000 \
  --env-file .env wm-backend
# .env 从 .env.example 复制，需要 Cookie 的平台按注释填写
```

Nginx 反向代理（`/etc/nginx/sites-enabled/wm.conf`）：

```nginx
server {
    listen 443 ssl;
    server_name api.example.com;
    ssl_certificate     /etc/letsencrypt/live/api.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.example.com/privkey.pem;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
    }
}
```

验证：`curl https://api.example.com/api/health` 应返回 `{"ok":true}`。

> 上线后第一件事：用**真实分享链接**逐个平台调一遍 `POST /api/parse`，确认解析正常（开发环境没条件做全链路真机验证，见 `backend/TEST_REPORT.md`）。

## ④ 部署网站

`frontend/index.html` 是纯单文件，直接托管即可：

- **最省事**：腾讯云 CloudBase / 阿里云 OSS 静态网站托管 / GitHub Pages，上传 `index.html`
- **自己服务器**：放到 Nginx 静态目录，配个 `tool.example.com` 的 443 站点

打开网站 → 右上角 ⚙️ 接口设置 → 填 `https://api.example.com` → 保存，开始用。

## ⑤ 小程序上传

1. 注册微信小程序账号（[mp.weixin.qq.com](https://mp.weixin.qq.com)），拿到 **AppID**
2. 下载安装**微信开发者工具**，导入 `miniprogram/` 目录
3. 把 `project.config.json` 里的 `appid` 占位 `wx0000000000000000` 换成你的真实 AppID
4. 在微信公众平台 → 开发 → 开发管理 → 开发设置 → 服务器域名，配置：
   - **request 合法域名**：`https://api.example.com`
   - **downloadFile 合法域名**：`https://api.example.com`（建议后端加个视频代理接口，这样只配一个域名；直链域名各平台经常变，代理更稳）
5. 小程序「设置」页填写后端地址 `https://api.example.com`
6. 真机调试完整走一遍：粘贴 → 解析 → 预览 → 保存到相册（含相册授权弹窗）
7. 提交审核 → 发布。类目建议选"工具"。**注意**：去水印工具审核较严，提交时功能描述写"视频下载/保存工具"，避免出现"去水印""搬运"字样；被驳回就按意见改描述重提。

## 日常维护

- 某平台突然解析失败：先看后端日志（`docker logs wm-backend`），再按对应 `app/parsers/<平台>.py` 头部注释排查（通常是平台改了页面结构或加强了反爬，加 Cookie 或更新选择器即可）
- 建议给后端加个简单的请求频率限制，避免被平台封 IP（同一 IP 高频请求会被限流）

## 费用参考（约）

- 轻量服务器：约 60–100 元/年（腾讯云/阿里云活动价）
- 域名：约 30–60 元/年
- 证书：免费（Let's Encrypt）
- 小程序账号：个人免费，企业 300 元/年认证费
