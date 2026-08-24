# D1/D2 实施计划 — BioDB `experiment` 维度 + PF 映射

会议核心需求：**实验ID + 协作者ID 二段结构**。本计划实现：
- **D1**：BioDB 时序加 `experiment` tag 维度（三 tag：experiment + participant + experimenter）。
- **D2**：PF 侧实验/协作者映射 + 推送注入 `experiment`。

## 设计决策

`experiment` 从 **JWT claim** 取（而非请求体直接注入），与 participant/experimenter 一致：
- 更安全（写入者无法伪造 experiment，需由长期 token + writejwt 签发方控制）。
- 读回时按 JWT scope 过滤，天然隔离不同实验。

## BioDB 侧改动（biodb-main）

### 1. 签发 JWT — `bio_api_server/main.py`
`POST /auth/jwt/sensors/writejwt`（与 readjwt 对称）：
- 请求体加可选 `experiment_id`（沿用 `pvalid` 的 `SensorJwtRequestBody` 扩展）。
- 若提供，JWT `additional_claims` 加 `"experiment": request_data.experiment_id`。

```python
additional_claim = {
    "participant_id": request_data.participant_id,
    "experiment": request_data.experiment_id,   # 新增，可空
    "start_time": request_data.start_time.isoformat(),
    "end_time": request_data.end_time.isoformat(),
    "jwt_role": "sensor_write",
}
```

### 2. 写入 — `bio_api_server/victoria_sensor_server.py`
write 时从 JWT 取 `experiment`（有则注入）：
```python
experiment = claims.get("experiment")
if experiment:
    data_df["experiment"] = experiment
# 传给 line protocol 的 tag_columns 加 "experiment"
```

### 3. tag — `bio_api_server/p_victoria_metrics.py`
调用 `dataframe_to_line_protocol(data_df, "biodb", tag_columns=["participant","experimenter"])` 处加 `"experiment"`（条件性：有该列才作 tag）。

### 4. 读回 — `victoria_sensor_server.py` / `p_victoria_metrics.py`
- `read` 请求体可选加 `experiment` 过滤；若 JWT 带 `experiment`，selector 加 `experiment="..."`。
- `victoria_metrics_export_and_format_data` 的 `__name__` selector 追加 `experiment=...` 条件。

## PF 侧改动（physioflow-app）

### 1. 协议配置 — `protocol.biodb`
```js
{ enabled: true, experimentId: 'exp_nomura_ninomiya', participantId: '<21位>', experimentLabel?: '野村二宮実験' }
```
`validateProtocolGraph`：`experimentId` 可选（为空则用 `protocolId` 兜底）。

### 2. BioDbClient — `src/biodb/bioDbClient.js`
- `issueJwt(role, { participantId, startTime, endTime, experimentId })`：body 加 `experiment_id`（可选）。
- JWT 缓存 key 加 `experimentId`。
- `writeChunk({ participantId, experimentId, columns })`：透传。

### 3. pushSession — `src/biodb/pushSession.js`
- `resolveBioDbExperiment(protocol, settings)`：`protocol.biodb.experimentId` → `protocolId` 兜底 → settings 默认。
- 每 chunk 调用 `writeChunk` 时传 `experimentId`。

### 4. 配置面板 — `BioDbConfigPanel.jsx`
加 `experimentId` 输入（默认空 = 用协议ID）。

## 验证

1. BioDB 起栈，`POST /auth/jwt/sensors/writejwt` 带 `experiment_id` → JWT 解码含 `experiment`。
2. PF 跑模拟连接器实验（`protocol.biodb.experimentId` 设好）→ 推送 → 落库。
3. VictoriaMetrics 查询：系列带 `experiment=<id>` tag。
4. 同一 participant 两个不同 experiment 推送 → 可分别按 `experiment` 读回，不串数据。

## 依赖

- BioDB：`pvalid` 请求体 schema、`main.py` writejwt、`victoria_sensor_server.py`、`p_victoria_metrics.py`。
- PF：`protocol.biodb` schema + `bioDbClient`/`pushSession`/`BioDbConfigPanel`。
- 无第三方依赖；改动为增量。

## 文件清单

| 项目 | 文件 | 改动 |
|---|---|---|
| BioDB | `bio_api_server/pvalid.py` | 请求体加 `experiment_id` |
| BioDB | `bio_api_server/main.py` | writejwt/readjwt/events JWT 加 `experiment` claim |
| BioDB | `bio_api_server/victoria_sensor_server.py` | 写入注入 experiment tag；读回过滤 |
| BioDB | `bio_api_server/p_victoria_metrics.py` | tag_columns 加 experiment |
| PF | `src/biodb/bioDbClient.js` | issueJwt/writeChunk 传 experiment |
| PF | `src/biodb/pushSession.js` | resolveBioDbExperiment + 注入 |
| PF | `src/biodb/BioDbConfigPanel.jsx` | experimentId 输入 |
| PF | `src/core/validateProtocolGraph.js` | 校验 experimentId（可选） |
