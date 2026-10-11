# 去水印解析后端测试报告

测试时间：2026-10-11（HKT）
测试环境：本机沙箱 Python 3.12 + venv（fastapi / uvicorn / httpx / pydantic）

## 一、通过的测试

| # | 测试项 | 结果 |
|---|--------|------|
| 1 | `python -m uvicorn app.main:app` 启动 | ✅ 正常启动，8000 端口监听 |
| 2 | `GET /api/health` → `{"ok": true}` | ✅ |
| 3 | `GET /api/platforms` → 6 个平台列表（含 status） | ✅ |
| 4 | CORS：OPTIONS 返回 `access-control-allow-origin: *` | ✅ |
| 5 | 非法链接 → `{"ok": false, "code": "invalid_url", ...}` | ✅ |
| 6 | 不支持的平台（youtube 链接）→ `code: "unsupported"` 中文提示 | ✅ |
| 7 | 微信视频号链接 → `code: "needs_login"` 中文提示 | ✅ |
| 8 | 小红书（未配 Cookie）→ `code: "needs_login"` 中文提示 | ✅ |
| 9 | 抖音失败路径 → `code: "parse_failed"`，服务不崩、后续请求正常 | ✅ |
| 10 | B站 parser 逻辑测试（桩数据，5 用例） | ✅ 全过：BV 解析+字段映射 / av 号格式 / 无BV号→invalid_url / 视频不存在→parse_failed / playurl 失败→needs_login |
| 11 | 微博 mid62 编解码往返一致性（5 组数字 id） | ✅ 全过 |

## 二、未完成的验证（环境限制，如实记录）

1. **B站真实 BV 全链路 live 验证 —— 未完成**
   - 原因：沙箱出口 IP 被 B站 WAF 拦截，`x/web-interface/view` 返回 `412 Precondition Failed`
     （curl 同样 412，可排除客户端问题；`popular` 接口可用，证明网络本身通）。
   - 生产环境（用户自己的服务器 IP）通常不受此限制，代码逻辑已由第 10 项桩测试覆盖。

2. **抖音 / 快手 / 微博真实分享链 live 验证 —— 未完成**
   - 原因：手头没有真实有效的各平台分享链接，且沙箱网络受限（见下）。
   - 代码按公开解析方案实现，失败路径已验证不会崩溃（第 9 项）。

3. **小红书 —— 未完成**
   - 原因：该接口必须登录 Cookie，测试环境没有可用的 `COOKIE_XIAOHONGSHU`。
   - 无 Cookie 时按契约返回 `needs_login` 中文提示（第 8 项已验证）。

4. **Dockerfile —— 未实际构建**
   - 原因：测试环境没有 docker。Dockerfile 按常规写法编写（python:3.11-slim，EXPOSE 8000），
     部署前请在目标机器上 `docker build` 验证一次。

## 三、测试中发现并已修复的问题

1. `kuaishou.py` 有一处括号笔误导致 SyntaxError，服务无法启动 —— 已修复。
2. 沙箱 `no_proxy` 环境变量含 `[::1]`，httpx 解析时抛 `InvalidURL: Invalid port: ':1]'`，
   导致所有出站请求失败 —— 已在 `base.py` 的三个 `httpx.AsyncClient` 构造处加
   `trust_env=False` 规避（不继承系统代理变量，行为更可预期；注释中注明如部署环境必须走代理请改此处）。
3. 沙箱出口为 MITM 代理，自签证书导致 httpx TLS 校验失败 —— 仅测试环境问题，
   生产代码保持证书校验开启；测试时仅在测试脚本内跳过校验。

## 四、结论

- API 契约（成功/失败格式、三个接口、CORS）已按要求实现并验证。
- 6 个 parser 模块齐备；B站 parser 逻辑与微博 mid62 编解码已验证；
  各平台失败路径均返回契约规定的中文错误码，不会导致服务崩溃。
- 真实网络 live 验证受沙箱环境限制未能完成，上线前建议在目标服务器上
  用真实分享链接跑一遍 `POST /api/parse` 做最终确认。
