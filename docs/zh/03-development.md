# 需开发的部分（开发清单与路线图）

按依赖关系组织的开发项，每项标注涉及模块、依赖、验收。

## 开发项一览

| # | 开发项 | 模块 | 依赖 | 优先级 |
|---|---|---|---|---|
| D1 | **BioDB `experiment` tag 维度** | `p_victoria_metrics.py` `tag_columns` 加 `experiment`；写入方（BioDbClient）传 experiment_id | BioDB 侧 | P0 |
| D2 | **实验/协作者映射**：PF `protocol.biodb.experimentId` + settings 映射 UI；`pushSession` 注入 experiment | PF `src/biodb/` + ComposerV2 配置 | D1 | P0 |
| D3 | **PF BioDB 数据管理面板**：participant 选择、数据浏览、事件 CRUD、简单曲线 | PF 新 `BioDbPanel` + BioDbClient event/read 方法 | D2 | P1 |
| D4 | **数据字典对接**：channel 清单（dataType/unit/sampleRate）→ 数据字典，随推送/导出 | PF `src/data/` + BioDB 元数据 | D2 | P1 |
| D5 | **真实脑波设备 adapter**（如 Muse）：transport bluetooth/serial，接 device connector | PF `src/devices/` | — | P1 |
| D6 | **联合导出/归档**：PF 会话（协议+事件+device_events）+ BioDB 数据 → 一个数据包 | PF `src/data/` | D3 | P2 |
| D7 | **分析管线**：预处理（重采样/滤波）、特征（HRV/EDA/频谱）、统计/ML；消费 BioDB 读回 | PF `src/biodb/analysis/` | D3 | P2 |
| D8 | **可视化**：历史多列曲线、实时模式、情感地图 | PF 图表组件 | D3/D7/D9 | P2 |
| D9 | **流式推送**：运行中缓冲 flush + 按窗口 JWT | PF `src/runtime/deviceRuntime.js` + `pushSession` | D1/D2 | P3 |
| D10 | **平台级权限/审计/统一认证视图** | PF App + BioDB 认证对接 | D3 | P3 |

## 当前进度（2026-08-26）

### BioDB 侧：D1 ✅ 已完成并通过端到端验收
D1（`experiment` tag 维度）已在 BioDB 测试实例完成实施、部署与 6 项功能端到端验收，详见 [`06-biodb-deployment-summary.md`](06-biodb-deployment-summary.md)：

| 能力 | 状态 | 说明 |
|---|---|---|
| 写入带 `experiment` 标签 | ✅ | `p_victoria_metrics.py` 支持 tag；sensor JWT 携带 `experiment` claim，写入即带标签 |
| 读回（含 experiment 过滤） | ✅ | `/sensor/data/read`；48h 大时间窗动态分片读回 3300 点/378ms（修复时间格式 Bug） |
| 事件 + 实验关联 | ✅ | 事件带 `experiment_id` 关联注册表 |
| 实验注册表 | ✅ | MongoDB `event_database.experiments`（含数据字典 `dictionary`） |
| 联合导出 | ✅ | `/sensor/data/export` 返回 sensor 数据 + 事件 + 实验元数据三部分 |
| 特征统计 / ML 分析 | ✅ | `/sensor/data/features`（时域+频域）、KMeans/回归/预测/结果列表与删除 |
| util 可视化页面 | ✅ | `/util/` 历史/实时/事件图表/情感地图（修复 JWT Bearer 前缀 Bug） |

验收过程中修复 4 个问题：① 分片时间无时区+小数秒致维多利亚 export 全 400；② KMeans `label_distribution` 整数键被 BSON 拒绝；③ 测试脚本时间戳截断到秒致维多利亚去重；④ util 页面 `Authorization` 缺 `Bearer ` 前缀。

### PF 侧：D2~D10 待开发（PF 独立仓库）
BioDB 侧依赖全部就绪，PF 侧可无缝对接：

| # | 状态 | 对接前提（BioDB 已就绪） |
|---|---|---|
| D2 实验/协作者映射 | 待开发 | `experiment` tag 写入/读回、sensor JWT claim ✅ |
| D3 数据管理面板 | 待开发 | `/sensor/data/read`、事件 CRUD、participant API ✅ |
| D4 数据字典对接 | 待开发 | 注册表 `dictionary` 字段 ✅ |
| D5 脑波设备 adapter | 待开发 | 写入链路（带 experiment/participant）✅ |
| D6 联合导出/归档 | 待开发 | `/sensor/data/export` 三部分已齐 ✅ |
| D7 分析管线 | 待开发 | `/sensor/data/features` + ML 端点可作后端 ✅ |
| D8 可视化 | 待开发 | util 页面可作参考实现 |
| D9 流式推送 | 待开发 | write JWT 按窗授权 ✅ |
| D10 权限/审计 | 待开发 | `/auth` 体系 ✅ |

### 下一步计划
1. **短期（PF 仓库）**：D2 实验/协作者映射 UI → D4 数据字典 → D3 数据管理面板。BioDB 侧依赖均已就绪，可直接调用既有端点。
2. **中期（PF 仓库）**：D5 脑波设备 → D7 分析管线（先消费 BioDB 读回与既有特征/ML 端点）→ D8 可视化。
3. **长期**：D9 流式推送 → D10 平台级权限/审计。
4. **BioDB 侧运维**：清理测试残留数据（`exp_quality` 等）；接入真实实验数据后复验联合导出元数据与 48h 大窗性能。

## 路线图（阶段 → 开发项）

```
Phase 2（P0-P1）   D1 experiment tag → D2 实验/协作者映射 → D3 数据管理面板 → D4 数据字典
Phase 3（P1-P2）   D5 脑波设备 → D7 分析管线 → D8 可视化 → D6 联合导出
Phase 4（P3）      D9 流式推送 → D10 平台权限/审计
```

## 关键开发项详述

### D1 — BioDB `experiment` tag（最低成本，解锁二段标识）
- 改 `p_victoria_metrics.py`：`dataframe_to_line_protocol(data_df, "biodb", tag_columns=["participant","experimenter","experiment"])`。
- 写入方 `BioDbClient.writeChunk`：columns 注入 `experiment` 值（来自 `protocol.biodb.experimentId` 或映射）。
- 读回：`/sensor/data/read` selector 加 `experiment="..."`。
- 验收：同一 participant 两次不同实验数据可分别读回。

### D2 — 实验/协作者映射（让标识可用）
- PF `protocol.biodb`：加 `experimentId`（语义名或协议ID）+ 可选 `experimentLabel`。
- `settings.biodb.participantMapping` UI 化（BioDbConfigPanel 升级）。
- `pushSessionToBioDb`：注入 `experiment` + 解析 participant（已有）。
- 验收：会话完成推送到 BioDB，数据带 experiment+participant 标识，读回一致。

### D3 — PF BioDB 数据管理面板（平台「管理」环节）
- `BioDbClient` 加：`listParticipants`、`readSensor`（分页读回）、事件 CRUD（`/event/events`）。
- `BioDbPanel.jsx`：participant 下拉、时间段浏览、简单曲线（复用 Analytics 图表）、事件列表管理。
- 入口：`App.jsx` `view==='biodb'` + Dashboard "BioDB"。
- 验收：面板可看到 D2 推送的数据，可管理事件。

### D7 — 分析管线（平台「分析」环节）
- `src/biodb/analysis/`：`resample`、`filter`、`hrv`、`eda`、`spectral`、`artifactReject`、`ml`。
- 消费 `readSensor` 读回（对写入方无关）。
- 产出 `.jsonl/.csv` 进会话包；可选写回 BioDB 事件。
- 验收：对模拟信号算出 HRV/频谱特征，统计/ML 在合成数据上可训练/预测。

## 里程碑与验收

| 里程碑 | 内容 | 验收 |
|---|---|---|
| M1（Phase 2） | experiment tag + 映射 + 数据管理面板 | 双实验数据分别读回、面板可浏览管理 |
| M2（Phase 3） | 脑波接入 + 分析 + 可视化 | 真实设备落库、特征可算、曲线/情感地图可渲染 |
| M3（Phase 4） | 流式 + 权限审计 | 实时曲线、平台级权限视图 |

## 不做（明确排除）

- 平台级多租户/云托管（保持研究室本地部署）。
- 任意 JS 注入运行时（保持沙箱）。
- 自动统计结论生成（需谨慎，避免误导）。
