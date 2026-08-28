# D4 实现记录 — 通道数据字典联动（PF demo 分支）

- **日期**：2026-08-28
- **仓库**：`kyzzz22/physioflow-app`（分支 `demo`，基于 D3 提交 `9508334`）
- **目标**：把协议中设备连接器声明的通道信息（`dataType` / `unit` / `sampleRate`）提取为数据字典，并在推送时附加到 BioDB 的实验注册中
- **BioDB 侧改动**：**无**（复用已有的 `GET/POST /experiment/<id>/dictionary`）

## 背景

D2 已支持把会话推送到 BioDB，但实验的字典（通道定义）始终为空，读回端无法得知通道的单位、类型与采样率。
D4 把 PF 的协议定义作为**唯一信息源**，自动生成通道字典并在推送时附加。

## 设计决策

- 字典的键是**通道 ID**（在连接器内唯一），同时保留连接器来源（`connectorId` / `connectorVersion`），便于把通道追溯回具体设备。
- **仅登记输入通道**。`direction: 'output'` 的 marker / trigger 不属于时序流，予以排除。
- V2 Graph 协议优先取图中已接线的设备节点（`node.config.deviceConnectorId`）；尚无设备节点时回退到已安装连接器全量，避免接线前预览时字典为空。
- V1（旧格式）直接使用 `protocol.deviceConnectors`，选择器同时兼容两种格式。
- 字典推送为**尽力而为**：实验未注册或权限不足导致失败时，样本行推送仍视为成功，仅在 UI 显示原因（不破坏推送的主目的）。
- 字典为**整体替换**（`POST` 覆盖已有字典），不做部分更新。

## PF 侧改动

### 1. 核心 — `src/data/channelDictionary.js`（新增）

- `channelDataDictionary(protocol)` — 从连接器的 `channels` 生成 `{ contractVersion, protocol, connectors, channels, inputChannels, outputChannels }`，其中 `channels[id] = { connectorId, connectorVersion, label, dataType, unit, sampleRateHz, direction }`。
- `dictionaryPayload(protocol)` — 返回 BioDB 格式（`{ channelId -> { label, unit, type, sampleRateHz, direction, connectorId, connectorVersion } }`）的输入通道部分，无输入通道时返回 `null`。
- `deviceConnectorsOf(protocol)` — 带上述回退逻辑的连接器解析。

### 2. V2 会话导出 — `src/data/graphExport.js`

- bundle 中新增 `channel_dictionary.json` 与 `channel_dictionary.csv`。
- `manifest.json` 的 `counts` 增加 `channels` / `connectors`。
- `graphDataDictionary()` 的表定义增加 `channels`，并同步反映到 `data_dictionary.json`。

### 3. 通用导出 — `src/exporter.js`

- `bundle()` 输出 `channel_dictionary.json`，并在 `export_manifest.json` 的 `counts`、`files` 说明以及 `data_dictionary.csv` 中补充通道字典条目。

### 4. 推送客户端 — `src/bioDBClient.js`

- `pushExperimentDictionary(cfg, experimentId, dictionary)` — 获取 admin JWT 后调用 `POST /experiment/<id>/dictionary`（body `{dictionary}`）。
- `pushSessionToBioDB(cfg, opts)` 增加 `dictionary` 选项：`/sensor/data/write` 成功后附加字典，返回值包含 `dictionaryPushed` / `dictionaryError`。

### 5. 会话推送 UI — `src/SessionManager.jsx`

- 推送时生成 `dictionaryPayload(protocol_snapshot)` 并传入，结果消息中追加字典的写入状态（成功 / 失败原因）。

## 输出示例

`channel_dictionary.json`：

```json
{
  "contractVersion": "1.0.0",
  "protocol": { "id": "protocol_1", "name": "D4 e2e graph", "version": 1 },
  "connectors": {
    "org.physioflow.simulated-sensor": {
      "connectorId": "org.physioflow.simulated-sensor",
      "version": "1.0.0",
      "name": "Simulated Physiology Sensor",
      "transport": "timer"
    }
  },
  "channels": {
    "signal": {
      "connectorId": "org.physioflow.simulated-sensor",
      "connectorVersion": "1.0.0",
      "label": "signal",
      "dataType": "number",
      "unit": "a.u.",
      "sampleRateHz": 100,
      "direction": "input"
    },
    "marker": { "...": "...", "dataType": "string", "unit": null, "sampleRateHz": null, "direction": "output" }
  },
  "inputChannels": ["signal"],
  "outputChannels": ["marker"]
}
```

## 验证

`node e2e-d4.mjs`（凭据通过环境变量 `BIO_URL` / `BIO_USER` / `BIO_TOKEN` / `BIO_PID` 注入，可选 `BIO_EXPERIMENT`）：

1. 生成通道字典（`signal` / `marker`，输入通道为 `signal`）
2. 获取 admin JWT → 实验列表
3. 注册专用实验 `PF D4 e2e`（**不覆盖既有实验**）
4. 推送字典（`POST /experiment/<id>/dictionary`）
5. 读回比对 → `signal: a.u. @ 100Hz (number)` 一致
6. 确认图会话导出中包含 `channel_dictionary.json`

全部步骤 PASS。

单元测试 `tests/channel-dictionary.test.js`（5 例）：

- 从 V1 `deviceConnectors` 提取（`dataType` / `unit` / `sampleRate` / `direction`）
- 跟随 V2 Graph 的设备节点
- BioDB 格式载荷（仅输入通道，无则 `null`）
- 图导出附带与 manifest counts
- 通用 `bundle()` 附带

`npm run build` / lint / 全量单元测试（245 项中 244 pass、1 skipped、0 fail）均通过。

## 依赖

- D2（实验映射与会话推送）— 前置，已完成
- D1（BioDB 字典 API `GET/POST /experiment/<id>/dictionary`）— 前置，已完成
- BioDB 测试环境（`localhost:5002`，docker compose）已启动
- PF 的 BioDB 配置（Base URL / user_id / 长期 token）已设置

## 已知约束

- 字典为**实验级**：不保存参与者或会话级字典（BioDB 的字典 API 本身按实验组织）。
- `POST` 为整体替换，手工设置的字典条目会在推送时被覆盖。
- 连接器未声明 `sampleRateHz` 的通道保持为 `null`。

## 文件清单

| 文件（PF demo 分支） | 类型 |
|---|---|
| `src/data/channelDictionary.js` | 新增 |
| `src/data/graphExport.js` | 修改（输出 `channel_dictionary.*`、counts） |
| `src/exporter.js` | 修改（`bundle()` 附带） |
| `src/bioDBClient.js` | 修改（`pushExperimentDictionary` 等） |
| `src/SessionManager.jsx` | 修改（推送时附带字典） |
| `tests/channel-dictionary.test.js` | 新增（单元测试 5 例） |
| `e2e-d4.mjs` | 新增（验证脚本，凭据走环境变量） |
