# D3 实施记录 — 数据管理面板（PF demo 分支）

- **日期**：2026-08-28
- **仓库**：`kyzzz22/physioflow-app`（分支 `demo`，提交 `9508334`）
- **范围**：PF 侧实现 BioDB 数据管理面板（participant 选择 / 读回表格 / SVG 曲线 / 事件 CRUD）
- **BioDB 侧改动**：**无**（复用 D1 已就绪的读回/事件/participant API）

## 设计决策

- 读回为列式 JSON（`{time:[...], [channel]:[...]}`），直接用于表格 + 零依赖 SVG 折线图。
- read JWT 按**请求时间窗**签发（`/auth/jwt/sensors/readjwt` 的窗口即 JWT 有效窗，窗口不一致会报 "Request time out of range"）。
- participant 列表不能用 read JWT（participant_id 不存在则无法签发），改用 admin JWT（`WebUI` claim）调 `GET /auth/participant`（→ auth `/participant`）。
- 事件 JWT 走 `/auth/jwt/events`，事件 CRUD 走 `/event/events`（nginx 转发到 event 服务）。事件创建 body 的 `user_id` 必须是 **participant_id**（JWT claim 的 `user_id` 即 participant_id，必须一致）。

## PF 侧改动（physioflow-app，demo 分支）

### 1. 客户端扩展 — `src/bioDBClient.js`

- `getBioDBAdminJwt(cfg)` — admin JWT（WebUI claim）
- `readBioDBData(cfg, {participantId, startTime, endTime, rows, chunkSeconds})` — 用请求窗口签 read JWT → `/sensor/data/read` → base64 按 UTF-8 解码返回列式 JSON
- `getBioDBEventJwt(cfg, {participantId, startTime, endTime})` — `/auth/jwt/events`
- `listBioDBEvents(cfg, ...)` — `/event/events?role=experimenter&start_time&end_time`
- `createBioDBEvent(cfg, {participantId, startTime, endTime, event, description, experimentId})` — `POST /event/events`（body 的 `user_id` = participant_id，`end_time` 必须晚于 `start_time`）
- `deleteBioDBEvent(cfg, {participantId, eventId, startTime, endTime})` — `DELETE /event/events/<id>`（JWT 窗口须覆盖事件窗口）

### 2. 数据管理面板 — `src/DataPanel.jsx`（新建）

- participant 下拉（admin JWT 拉取，兼容 `id` 字段）
- 时间范围：1h / 6h / 24h 快捷按钮 + datetime-local
- 通道输入（逗号分隔，默认 `eda,hr`）→ 「读取数据」
- 结果：行数 / 通道统计、列式表格（可调最大显示行数）、SVG 折线图（可选通道）
- 事件列表 + 新建（在当前窗口中央时刻创建 1 分钟事件）+ 逐行删除

### 3. 入口 — `src/Dashboard.jsx`

头部「Data」按钮开关面板。与 `BioDBSettings` 共享 settings，未配置时显示引导。

### 4. i18n / CSS

`src/i18n.jsx` 补 zh/ja 词典，`src/questionnaire.css` 补 D3 区块（`.d3-panel`、`.d3-table`、`.d3-chart`、`.d3-event-create`、`.d3-del` 等）。

## 验证

`node e2e-d3.mjs`（凭据经环境变量 `BIO_URL` / `BIO_USER` / `BIO_TOKEN` / `BIO_PID` 注入）：

1. participant 列表（1 名）
2. 列式读回（`rows=eda,hr` → 40 行，通道 eda/hr）
3. 事件列表（空）
4. 事件创建（`e2e-d3-verify`）→ 列表反映
5. 事件删除 → 列表消失

全部 PASS。`npm run build` / lint 通过。

## 依赖

- D1（BioDB 读回 / 事件 CRUD / participant API）— 前提，已完成
- BioDB 测试环境（`localhost:5002`）运行中
- PF 已配置 BioDB 设置（Base URL / user_id / 长期 token）

## 文件清单

| 文件（PF demo 分支） | 类型 |
|---|---|
| `src/bioDBClient.js` | 修改（D3 函数） |
| `src/DataPanel.jsx` | 新建 |
| `src/Dashboard.jsx` | 修改 |
| `src/i18n.jsx` / `src/questionnaire.css` | 修改 |
| `e2e-d3.mjs` | 新建（验证脚本，凭据走环境变量） |
