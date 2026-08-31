# 14. WebUI 统一部署与 Console 扩展

- **更新日期**：2026-08-31
- **仓库**：`physioflow-biodb-platform`(biodb-main / nginx)
- **范围**：统一 nginx 单入口(同捆 PF Dashboard)、全 UI 统一设计系统、Console 功能扩展
- **BioDB 后端变更**：**无**(仅使用既有端点;字典编辑新调用既有 `POST /experiment/<id>/dictionary`)

## 1. 统一入口(单一 origin)

部署在研究室网络的 BioDB nginx(`:5002`)以单一 origin 提供全部 UI。对外仅暴露 nginx 端口。

| 路径 | 内容 |
|---|---|
| `/` | 统一落地页(日/中切换,`localStorage` 记忆,默认日语) |
| `/pf/` | PhysioFlow Dashboard(PF 的 `dist/` 以相对路径构建直接同捆) |
| `/WebUI/console` | BioDB 控制台(SvelteKit) |
| `/db/`、`/util/` | 既有静态 UI(主题已统一) |
| `/shared/theme.css` | 统一设计 token 分发 |

### 实现要点

- PF 的 `vite.config.js` 是 `base: './'`(相对路径),放子路径 `/pf/` 直接可用。`nginx/nginx.conf` 的 `location /pf/` 带 SPA fallback 静态分发。
- PF 的 BioDB Base URL 是运行时配置(`http://<主机>:5002` 或同源相对路径)。按浏览器 localStorage 保存,每台设备需配置一次。
- 构建步骤:`node nginx/build-pf.cjs`(在 PF 仓库执行 `npm run build` → 拷贝到 `biodb-main/pf-build/`)→ `docker compose build --no-cache nginx` → `docker compose up -d nginx`。
- PF 的 Service Worker(`/sw.js` 绝对路径注册)在子路径下 inert(404 被 `.catch` 吞掉)。离线/PWA 化有意保留。

## 2. 统一设计系统(暗色 + 绿色)

全部 UI(`/WebUI/console`、`/db/`、`/util/`、`/`)统一到同一套 token。

- **Token 契约**：`biodb-main/webui-theme/theme.css`(唯一来源)。`:root` 变量定义 surfaces / text / accent / status / radius / shadow / font / 图表 8 色 / 事件色。
- **分发**：nginx `location /shared/` 提供 `theme.css`。`/db/`、`/util/` 通过 `<link rel="stylesheet" href="/shared/theme.css">` 引用。SvelteKit 因 dev 模式无 nginx,在 `+layout.svelte` 的 `:root` 内联同一份(注释标注同步)。
- **修复的不一致**：
  - 页面背景未上色(白底)→ 全页暗色
  - 绿色 accent 与蓝色 `rgba(76,154,255,…)` 混用(表头等)→ 统一绿色 tint
  - 未定义的「幽灵 token」(`--muted-color` 等)→ 正式定义
  - Bootstrap 亮色 alert(用户管理页)→ 暗色 tint 的单一状态体系
  - 图表色板三处分裂(`console-draw.js` / `common.js`×2)→ 统一同一 8 色 + 事件色(暗 canvas 可读的 Tailwind-400 系)
- **组件统一**：新建 `bio_svelte/src/lib/global.css`(button/.btn、.card、.grid/.field、table、.chip、.link 等)。Console 7 个 tab 的裸按钮/输入/表格立即获得统一样式。

## 3. Console 功能扩展

`/WebUI/console` 的 4 个 tab(全部纯前端,无新 API):

| Tab | 新增功能 |
|---|---|
| 棚卸し(Overview) | 4 张统计卡片(实验注册数 / 参与者数 / 总点数 / 时间范围)、最近活动(最新 5 条)、挂载时自动执行 |
| 数据浏览(DataBrowse) | 摘要新增 mean / std / 缺失数 / 缺失率、**CSV 下载**、**canvas 拖拽选区 → 缩放重新读取**(`console-draw.js` 支持 `window` 裁剪)、通道显示开关 |
| 分析(Analysis) | 频带能量比堆叠条、主导频率徽章、时域指标(mean/std/rms)相对条、质量检查以完整性进度条展示 |
| 事件(Events) | 类型筛选(start/end/marker/note)、**批量删除**(复选框 + 全选) |
| 实验注册(Experiments) | 搜索过滤、**数据字典编辑保存**(`POST /experiment/<id>/dictionary`,需 admin JWT) |

### 3.1 操作上下文统一（2026-08-31）

- 在 Console 顶部新增统一上下文栏，实验、协作者 ID、开始/结束时间只需选择一次；数据浏览、事件、分析和导出共同使用这些条件。
- 实验与协作者输入根据盘点结果和实验注册表提供可搜索候选（`datalist`），同时保留未知 ID 的直接输入能力。
- 新增最近 1 小时 / 24 小时 / 7 天快捷范围、本地时间与 UTC 对照，并通过 `localStorage` 保存选择。
- 点击盘点卡片会更新统一上下文并直接进入数据浏览。
- API 失败时清除旧结果，将“请求成功但无数据”与连接/权限错误明确区分。

### 3.2 Console 后续优化计划

| 优先级 | 计划 | 完成标准 |
|---|---|---|
| P1 | 将连接配置改为分步向导，持续显示连接、权限与服务状态 | 新用户可不依赖说明完成配置并读取数据 |
| P1 | 根据数据字典提供通道分组选择，加入已保存视图与分析预设 | 主要传感器组合无需手工输入且可复用 |
| P1 | 支持在图表上点击创建事件，图表与事件表双向定位 | 无需转抄时间即可添加和核对标注 |
| P1 | 导出前预览记录数、时间范围、预计大小，并提供失败重试 | 大数据导出的影响与失败原因可提前确认 |
| P2 | URL 保存视图状态、键盘操作、响应式布局、日中英 UI | 支持共享链接、多终端和无障碍使用 |
| P2 | 取消长期 token 的持久浏览器存储，引入短期会话与按权限显示 UI | 共享设备不残留长期凭据，可安全运维 |

### 3.3 WebUI 认证基础统一（2026-08-31）

- 在 `auth-state.svelte.js` 集中管理 WebUI 管理 JWT，校验 JWT 的 `exp` 和 `WebUI` claim；有效期 10 分钟的短期 JWT 仅保存在 `sessionStorage`。
- 新增 `api-client.js`，统一处理用户信息、API Token、实验协作者请求的 Authorization、JSON、网络错误与 HTTP 错误；管理页面不再依赖 Axios。
- 收到 401 或在客户端发现 JWT 过期时，清除旧会话并返回登录页；403 / 404 / 429 / 5xx 也会转换成面向用户的说明。
- 对 `/user-info`、`/token-list`、`/participants` 增加客户端路由保护。未登录访问时将原地址保存为 `next`，登录后返回；拒绝利用外部 URL 的开放重定向。
- 导航划分为“研究数据”和“账户管理”，根据登录状态显示菜单、当前位置、角色与退出登录。
- Google 登录页增加脚本加载、认证处理中、成功、失败和重试状态；失败原因会显示在页面上，不再只写浏览器 Console。
- 为避免影响现有用户，Console 暂时继续使用独立的长期 Token 设置。下一阶段再迁移为由 Google 管理会话换取 read / event / admin 短期 JWT。

## 4. 验证状态

- ✅ 已确认 SvelteKit / PF 生产构建、nginx 路由定义及 `/db/`、`/util/` 的主题引用。
- ✅ 已确认统一上下文可静态构建，且各功能页引用同一共享状态。
- ✅ 已通过自动测试确认 JWT 解析、受保护路径、安全重定向、Authorization 注入及 401 后清除会话。
- ⏳ 尚未在最新整合环境完成全部路径的 HTTP 复验。
- ⏳ Google 弹窗成功/拒绝/会话过期后的重新登录、落地页语言切换、统一上下文及 Console 各功能仍需人工浏览器确认。
- ⏳ API 代理与 `/pf/` SPA fallback 的整合回归需在 BioDB 全部服务启动后执行。

## 5. 运维笔记

- **防火墙**(Windows):`New-NetFirewallRule -DisplayName "PhysioFlow BioDB 5002" -Direction Inbound -Protocol TCP -LocalPort 5002 -Action Allow -Profile Public,Private`(管理员权限)。
- nginx 配置/静态文件变更一律 `docker compose build --no-cache nginx && docker compose up -d nginx`(文档记载的可靠 COPY 失效步骤)。
- 落地页语言选择存于 `localStorage["biodb_landing_lang"]`(默认 `ja`)。
