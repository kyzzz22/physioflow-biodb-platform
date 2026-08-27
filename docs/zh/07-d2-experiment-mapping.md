# D2 实施记录 — 实验/协作者映射（PF demo 分支）

- **日期**：2026-08-28
- **仓库**：`kyzzz22/physioflow-app`（分支 `demo`，提交 `2faa06e` + `5fecf8c`）
- **范围**：PF 侧配置「协议 → BioDB 实验」映射，并将会话推送到 BioDB
- **BioDB 侧改动**：**无**（复用 D1 已就绪的 `experiment` 标签写入/读回路径）

## 设计决策

- 映射按协议保存：`protocol.biodb.experimentId`（+ 展示用 `experimentLabel`）。
- V2 协议图为 camelCase（`experimentId`）、V1 为 snake_case（`experiment_id`），selectors 两种都接受。
- 连接设置（Base URL / user_id / 长期 token）存入 PF 全局设置（localStorage），与协议设置分离（机密信息不进协议 JSON）。
- 推送时依次获取 admin JWT → sensor write JWT（带 `experiment_id` claim）→ `/data/write` 写入。

## PF 侧改动（physioflow-app，demo 分支）

### 1. 协议配置 — `protocol.biodb`

`src/core/protocolGraph.js`：`createProtocolGraph` 的 metadata 追加（默认空）：

```js
biodb: { experimentId: options.experimentId || '', experimentLabel: options.experimentLabel || '' },
```

`src/domain.js`：`protocol()` 默认值追加 `biodb:{experiment_id:'',experiment_label:''}`（V1 形式）。

### 2. Selectors — `src/core/protocolSelectors.js`

- `bioDBConfigOf(protocol)` — 获取协议 biodb 配置（V2 优先、V1 兜底）
- `experimentIdOf(protocol)` — 兼容 `experimentId` / `experiment_id` 返回实验 ID
- `experimentLabelOf(protocol)` — 返回实验标签
- `withBioDBConfig(protocol, cfg)` — 合并配置返回新协议

### 3. 推送客户端 — `src/bioDBClient.js`（新建）

- `getAdminJwt({baseUrl, userId, token})` → `POST /auth/jwt/admin`
- `fetchExperiments(...)` → 获取实验列表（映射 UI 用）
- `pushSessionToBioDB(settings, {participantId, experimentId, startedAt, endedAt, deviceEvents})`
  - 通过 `POST /jwt/sensors/writejwt`（body 含 `experiment_id`）获取 sensor write JWT
  - 事件经 `rowsFromDeviceEvents` 转成行 → `POST /data/write`（base64）
- `rowsFromDeviceEvents(deviceEvents, ...)` — 兼容 camelCase（`eventType/timestampIso/payload`）与 snake_case（`event_type/timestamp_iso/metadata`）

### 4. 全局设置 — `src/BioDBSettings.jsx`（新建）

Dashboard 头部「BioDB」按钮打开的连接设置弹窗。输入 Base URL / user_id / 长期 token，支持「连接测试」。`loadSettings`/`saveSettings` 持久化到 localStorage。

### 5. 协议→实验映射 — `src/ProtocolBioDBConfig.jsx`（新建）

ComposerV2 头部「BioDB」按钮打开。拉取 BioDB 实验列表供选择，选中后写入 `protocol.biodb`。

### 6. 会话推送 UI — `src/SessionManager.jsx`

`SessionDetail` 增加「Push to BioDB」按钮。未配置时 Alert 引导，成功时显示行数 / channels / experiment。

### 7. i18n / CSS

`src/i18n.jsx` 追加 zh/ja 词典，`src/questionnaire.css` 追加 BioDB（D2）区块（`.bio-btn`、`.field-label` 等）。

## 验证

`node e2e-d2.mjs`（凭据通过环境变量 `BIO_URL` / `BIO_USER` / `BIO_TOKEN` / `BIO_PID` 注入）：

1. 获取 admin JWT（`POST /auth/jwt/admin`）
2. 注册实验（`POST /experiment`）
3. 通过 `pushSessionToBioDB` 推送 20 行
4. 带 `experiment` 过滤读回 → 标签数据一致

全部 PASS。`npm run build` / lint / `rowsFromDeviceEvents` 单测均通过。

## 依赖

- D1（BioDB `experiment` 标签维度）— 前提，已完成
- BioDB 测试环境（`localhost:5002`）运行中

## 文件清单

| 文件（PF demo 分支） | 类型 |
|---|---|
| `src/core/protocolGraph.js` | 修改 |
| `src/domain.js` | 修改 |
| `src/core/protocolSelectors.js` | 修改 |
| `src/bioDBClient.js` | 新建 |
| `src/BioDBSettings.jsx` | 新建 |
| `src/ProtocolBioDBConfig.jsx` | 新建 |
| `src/ComposerV2.jsx` / `src/composer/Header.jsx` | 修改 |
| `src/Dashboard.jsx` | 修改 |
| `src/SessionManager.jsx` | 修改 |
| `src/i18n.jsx` / `src/questionnaire.css` | 修改 |
| `e2e-d2.mjs` | 新建（验证脚本，凭据走环境变量） |
