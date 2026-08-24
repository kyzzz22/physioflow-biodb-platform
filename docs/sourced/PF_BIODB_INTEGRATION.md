# PhysioFlow × BioDB 对接方案

Date: 2026-08-23
Authoritative plan: `.claude/plans/linked-prancing-floyd.md`

## Context

对接两个项目：**PhysioFlow**（PF，React 实验工作流系统）与 **BioDB**（研究室生体数据仓库：VictoriaMetrics 时序 + MongoDB 事件 + PostgreSQL 用户/权限，JWT 认证，nginx :5002）。

目标：**增加 PF 对传感器数据的支持**——PF 运行时通过 device connectors 采集传感器数据，推送到 BioDB 存储（BioDB = 实验数据仓库）；未来 DB 升级增加研究/数据管理、分析、可视化。

方向（已确认）：**PF 采集 → 推送 BioDB**；本阶段数据源用**模拟连接器**；本轮交付完整分阶段方案 + Phase 1 已实施。

## 架构

```
PF 浏览器 (Vite :5174)
  GraphRuntimeRunnerPage
    ├─ begin() → DeviceConnectorSession(simulated adapter)
    │              └─ deviceSampler (drift-corrected setTimeout @ max sampleRateHz)
    │                   └─ session.read(channelId) → device_sample_received → deviceEventsRef
    └─ 完成 → buildGraphSessionFiles(...device_events) → 本地导出 device_events.jsonl/.csv
             └─ 手动/自动 "Export to BioDB" ──BioDbClient──▶ BioDB nginx (:5002)
                 /auth/jwt/sensors/writejwt（长期 token→10min write JWT，窗口=chunk首末样本）
                 /sensor/data/write（{format:json, compression:gzip, data:base64(gzip(json({time, col...})))}）
```

## Phase 1 — PF 运行时传感器采集 → BioDB 推送（✅ 已实施）

### 已交付
- `src/biodb/`（新）：`base64.js`（bytes/gzip/base64，浏览器原生 CompressionStream）、`encodeSensorContainer.js`（容器编解码，NaN/Infinity→null）、`bioDbClient.js`（BioDbClient：JWT 缓存/8min 刷新、writeChunk 按首末样本窗口发 JWT、readChunk、verifyConnection）、`bioDbSettings.js`（`settings.biodb`，长期 token 仅本地）、`pushSession.js`（组列/≤5000 分块/participant 解析）、`BioDbConfigPanel.jsx`（最小配置 UI）、`index.js` barrel。
- `src/runtime/deviceRuntime.js`（新）：`resolveDeviceConnector`、`maxInputSampleRateHz`（默认 10Hz）、`createDeviceSampler`（drift-corrected 递归 setTimeout，非 setInterval）。
- `src/GraphRuntimeRunnerPage.jsx`：`deviceEventsRef` 缓冲（避免 100Hz 重渲染）+ 设备会话/采样生命周期（begin async、teardown、500ms 节流状态）+ 导出/当前运行/完成对象携带 `device_events` + 完成屏 BioDB 导出按钮与配置面板。
- `src/core/validateProtocolGraph.js`：`protocol.biodb?.enabled` 时要求非空 `participantId`。
- `eslint.config.js`：src globals 加 CompressionStream/DecompressionStream/Response/AbortController/atob/btoa 等。
- `tests/biodb-client.test.js` + `tests/device-runtime.test.js`：9 个测试（容器往返、NaN→null、JWT 缓存/刷新、writeChunk Bearer、pushSession 组列、sampler 驱动/停止）。

### BioDB 连接配置
- `settings.biodb`（本地）：`{baseUrl:'http://localhost:5002', userId, token, participantMapping:{}, defaultParticipantId, autoPush}`——长期 token 只存这里，不进 protocol。
- `protocol.biodb`（协议内）：`{enabled:true, participantId:'<21位BioDB participant>'}`——显式映射。
- 解析顺序：`protocol.biodb.participantId` → `settings.participantMapping[...]` → `defaultParticipantId`。

### BioDB 侧：Phase 1 零代码改动
三个 API server 已开 CORS `*`，仅 nginx :5002 暴露；`.env` 需 `APP_SECRET_KEY/APP_JWT_SECRET_KEY/GOOGLE_CLIENT_ID`；目标 participant 需已存在。

### Phase 1 集成验证
1. `biodb-main` 起栈：`docker compose up`（nginx :5002）。
2. 确认 BioDB 目标 participant 存在（WebUI 或 participants API）。
3. PF：协议安装 simulated connector + 节点设 `deviceConnectorId` + `protocol.biodb.enabled/participantId` + `settings.biodb`（baseUrl/userId/token）。
4. 运行 → 完成 → 本地 `device_events.jsonl/.csv` 出现 → 点 "Export to BioDB" → done。
5. 读回：`POST /sensor/data/read`（rows=['signal']）样本数一致。
6. 门禁：`npm test && npm run build && npm run lint -- --max-warnings=0`（208 测试全过）。

## Phase 2 — PF BioDB 浏览/管理（roadmap）

- `BioDbClient` 加事件 CRUD（`/event/events`，`jwt_role:'event'`）+ `readSensor` + `listParticipants`。
- `BioDbPanel.jsx`：participant 选择、数据浏览（时间段）、简单曲线（复用 Analytics 图表）、事件管理。
- 配置面板升级 + `App.jsx` 加 `view==='biodb'` 路由 + Dashboard "BioDB" 按钮 + SessionManager 每会话导出。

## Phase 3 — DB 功能升级（roadmap）

- **研究/数据管理**：PF protocol ↔ BioDB 实验映射、研究元数据（假设/IRB/条件）、数据字典（`graphDataDictionary` + channel 清单）、检索/导出。
- **预处理/统计/ML**：`src/biodb/analysis/`——消费 BioDB 读回（对写入方无关），重采样/滤波、HRV/EDA/频谱特征、伪迹剔除、可插拔 ML。
- **可视化**：历史多列叠加曲线、实时模式、感情地图（盘点 BioDB util 已有部分后移植）。
- **流式推送**（升级 Phase 1 批量）：运行中缓冲 flush + 按窗口发 JWT，对齐 BioDB 5 秒分块。

## 风险

- 100Hz 重渲染 → `deviceEventsRef` 缓冲 + 节流状态（已处理）。
- **JWT 时间窗口是首要失败点**：每 chunk 用 `[首样本,末样本]` 窗口发 JWT，规避 10min exp 与窗口分离（已处理）。
- participant 身份：PF 自由文本 ≠ BioDB 21 位 ID，始终走 `protocol.biodb.participantId` 解析，未映射报清晰错误（已处理）。
- `device_*` 事件不兼容 hosted appendEvents（缺 protocolId），Phase 1 仅本地导出 + BioDB 推送（有意为之）。
- 模拟连接器先行，真实设备适配器（EEG/脉波）为后续。
