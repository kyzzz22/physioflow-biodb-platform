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

## 当前进度（2026-08-28）

### BioDB 侧：D1 ✅ 已完成并通过端到端验收
D1（`experiment` tag 维度）已在 BioDB 测试实例完成实施、部署与 6 项功能端到端验收，详见 [`06-biodb-deployment-summary.md`](06-biodb-deployment-summary.md)：

| 能力 | 状态 | 说明 |
|---|---|---|
| 写入带 `experiment` 标签 | ✅ | `p_victoria_metrics.py` 支持 tag；sensor JWT 携带 `experiment` claim，写入即带标签 |
| 读回（含 experiment 过滤） | ✅ | `/sensor/data/read`；48h 大时间窗动态分片读回 6000 点/0.47s（修复时间格式 Bug 与 aiohttp 8KB 行上限 Bug） |
| 事件 + 实验关联 | ✅ | 事件带 `experiment_id` 关联注册表 |
| 实验注册表 | ✅ | MongoDB `event_database.experiments`（含数据字典 `dictionary`） |
| 联合导出 | ✅ | `/sensor/data/export` 返回 sensor 数据 + 事件 + 实验元数据三部分 |
| 特征统计 / ML 分析 | ✅ | `/sensor/data/features`（时域+频域）、KMeans/回归/预测/结果列表与删除 |
| util 可视化页面 | ✅ | `/util/` 历史/实时/事件图表/情感地图（修复 JWT Bearer 前缀 Bug） |

验收过程中修复 5 个问题：① 分片时间无时区+小数秒致维多利亚 export 全 400；② KMeans `label_distribution` 整数键被 BSON 拒绝；③ 测试脚本时间戳截断到秒致维多利亚去重；④ util 页面 `Authorization` 缺 `Bearer ` 前缀；⑤ 48h 大窗读回 `data=null`（aiohttp 逐行迭代单行上限约 8KB，86.4s chunk 8640 点单行 ~95KB 被拒 → 改为 `response.read()` 整读后按行解析）。

### BioDB Console（`/db/`）✅ 新 WebUI（D3 参考实现）
面向日常运维的轻量独立控制台（`biodb-main/bio_console/`，由 nginx `/db/` 分发）：

| 功能 | 说明 |
|---|---|
| 盘点（Discover） | 用长期 token 换取 sensor read JWT 自动发现 participant 与实验（大窗读回解析 `@experiment` 后缀） |
| 浏览 | 按 participant/时间窗/实验读回并绘制曲线（原生 Canvas，无外部图表依赖） |
| 事件 | 基于 event JWT 的列表/创建/删除（仅限删除自己创建的事件，与后端 `created_by` 语义一致） |
| 实验注册 | 实验注册表/数据字典的列表、创建、删除（写操作需管理员：长期 token scope=all 且角色 admin） |
| 分析 | 调用 `/sensor/data/features` 与 `/sensor/data/quality` |
| 导出 | 调用 `/sensor/data/export`（sensor 数据 + 事件 + 实验元数据三部分） |
| 设置 | 长期 token 配置（user_id / token / participant_id） |

开发中放宽的鉴权：
- `GET /auth/participant` 与实验注册表读端点（`GET /experiments`、`GET /experiment/<id>`、`GET /experiment/<id>/dictionary`）由仅 WebUI JWT 放宽为允许 `sensor_read`/`sensor_write`/`event` 角色 JWT（或 WebService）。
- 新增 `POST /auth/jwt/admin`：长期 token（scope=all）+ 角色 admin 换取 10 分钟 WebUI admin JWT，供 Console 进行实验注册表写操作（创建/删除），不依赖 Google OAuth。

### WebUI 整合：`/WebUI/console` 日语版 ✅（2026-08-27）
`bio_console`（原 `/db/` 中文界面）与现有 SvelteKit WebUI（`/WebUI/`）合并为单一入口，全面日语化（深色主题），实现位于 `bio_svelte/`（新增 10 文件）：
- `src/lib/console-state.svelte.js`（共享状态 + API 模块，对应 bio_console 的 `common.js`/`app.js`）、`src/lib/console-draw.js`（Canvas 曲线绘制，含事件标记叠加）。
- `src/routes/console/`：`+page.svelte`（视图控制器）+ 7 tab：Overview（数据盘点，卡片联动浏览）、DataBrowse（曲线 + 摘要表）、Events（事件 CRUD）、Experiments（实验注册 CRUD + 数据字典）、Analysis（特征统计/质量）、Export（三部分 JSON 下载）、Settings（连接配置 + 连接测试）。
- nginx 修复：`location /WebUI/` 的 `try_files` 增加 `$uri.html`（`adapter-static` 输出扁平 `xxx.html`，否则 `/WebUI/console` 会 fallback 到首页）。
- 验证：`GET /WebUI/console` → 200 且预渲染含全部 7 tab；全链路 readjwt → participant → experiments → sensor/data/read → event/events 均 200。
- 原 `/db/` 中文界面保留可访问；如需彻底移除需另处理（Dockerfile `COPY bio_console/` + nginx `location /db/`）。

### PF 侧：D2 ✅ 实验/协作者映射（demo 分支，2026-08-28）
PF 仓库（`kyzzz22/physioflow-app`、`demo` 分支）已完成 D2 并端到端验证通过。BioDB 侧零改动（复用 D1 已就绪的 `experiment` 标签路径）：

| 实现 | 文件（PF demo 分支） | 说明 |
|---|---|---|
| 协议配置 | `protocol.biodb.experimentId`（`src/core/protocolGraph.js` 生成、`src/domain.js` 默认值、`src/core/protocolSelectors.js` 的 `experimentIdOf`/`experimentLabelOf`/`withBioDBConfig`） | V2 用 camelCase `experimentId`、V1 用 snake_case `experiment_id`，两者兼容 |
| 全局设置 | `src/BioDBSettings.jsx`（Base URL / user_id / 长期 token / 连接测试，从 Dashboard 打开，`loadSettings`/`saveSettings` 持久化） | 集中管理连接配置 |
| 协议→实验映射 | `src/ProtocolBioDBConfig.jsx`（ComposerV2 Header 的 BioDB 按钮） | 读取 BioDB 实验列表，将实验绑定到协议 |
| 推送客户端 | `src/bioDBClient.js`（`getAdminJwt` / `fetchExperiments` / `pushSessionToBioDB` / `rowsFromDeviceEvents`） | admin JWT → writejwt（带 `experiment_id`）→ `/data/write` 推送会话数据 |
| 会话推送 UI | `src/SessionManager.jsx` 的 "Push to BioDB" 按钮 | 未配置时 Alert 引导，成功时显示行数 / channels / experiment |
| i18n / CSS | `src/i18n.jsx`、`src/questionnaire.css`（BioDB D2 区块） | 中/日词典与样式 |

- **验证**：`node e2e-d2.mjs`（admin JWT → 注册实验 → `pushSessionToBioDB` 推送 20 行 → `experiment` 过滤读回）全部 PASS，读回数据与推送一致。
- **提交**：`2faa06e`（D2 主体）+ `5fecf8c`（package-lock 同步 + 凭据环境变量化的 e2e 脚本）。

### PF 侧：D3 ✅ 数据管理面板（demo 分支，2026-08-28）
从 Dashboard 的「Data」按钮打开的数据管理面板。BioDB 侧零改动（复用 D1 已就绪的读回/事件/participant API）：

| 实现 | 文件（PF demo 分支） | 说明 |
|---|---|---|
| 读取客户端 | `src/bioDBClient.js`：`getBioDBAdminJwt` / `readBioDBData` / `getBioDBEventJwt` / `listBioDBEvents` / `createBioDBEvent` / `deleteBioDBEvent` | read JWT 按请求窗口签发（避免窗口越界）；participant 列表走 admin JWT（WebUI claim）；事件走 `/event/events`（CRUD） |
| 数据管理面板 | `src/DataPanel.jsx`（新建） | participant 选择 / 时间范围（1h·6h·24h 快捷 + datetime-local）/ 通道指定读回 |
| 展示 | 列式数据表格 + 零依赖 SVG 折线图（可选通道） | 读回为 `{time:[...], [channel]:[...]}` 列式 JSON |
| 事件管理 | 事件列表 + 新建（取当前窗口中央时刻）/ 逐行删除 | body 的 `user_id` 为 participant_id（JWT claim 约束）；删除按事件窗口签发 JWT |
| 入口 | `src/Dashboard.jsx` 头部「Data」按钮 + 面板挂载 | 与 `BioDBSettings` 共享 settings |
| i18n / CSS | `src/i18n.jsx`、`src/questionnaire.css`（D3 区块） | 中/日词典与样式 |

- **验证**：`node e2e-d3.mjs`（participant 列表 → 40 行列式读回（eda/hr）→ 事件创建 → 列表反映 → 删除 → 确认消失）全部 PASS。
- **提交**：`9508334`（D3 主体）。

### PF 侧：D4 ✅ 通道数据字典对接（demo 分支，2026-08-28）
协议中设备连接器声明的通道清单（`dataType` / `unit` / `sampleRate`）生成通道字典，导出时附带并在推送时写入实验。BioDB 侧零改动（复用 `GET/POST /experiment/<id>/dictionary`）。详见 [`09-d4-channel-dictionary.md`](09-d4-channel-dictionary.md)。

| 实现 | 文件（PF demo 分支） | 说明 |
|---|---|---|
| 通道字典提取 | `src/data/channelDictionary.js` | 仅输入通道；V2 Graph 设备节点优先，回退已安装连接器；V1 兼容 |
| V2 导出附带 | `src/data/graphExport.js` | `channel_dictionary.json`/`.csv` + manifest `channels`/`connectors` 计数 |
| 通用导出附带 | `src/exporter.js` | `bundle()` 同梱 + 数据字典条目 |
| 推送附加 | `src/bioDBClient.js` | `pushExperimentDictionary()` + `pushSessionToBioDB` 的 `dictionary` 选项（尽力而为） |
| 推送 UI | `src/SessionManager.jsx` | 自动生成并附带字典，结果显示写入状态 |

验证：`node e2e-d4.mjs`（字典生成 → 专用实验 `PF D4 e2e` 注册 → 推送 → 读回 `signal: a.u. @ 100Hz` → 导出附带确认）全部 PASS；单元测试 5 例。**提交**：`2a8b68c`。

### PF 侧：D5 ⚠️ Muse 脑波设备 adapter（demo 分支，2026-08-28，代码完成・未硬件验证）
接入 InteraXon Muse 作为 device connector。BioDB 侧零改动。详见 [`10-d5-eeg-adapter.md`](10-d5-eeg-adapter.md)。

| 实现 | 文件（PF demo 分支） | 说明 |
|---|---|---|
| 协议解码 | `src/devices/museProtocol.js` | Classic 固件：12-bit 解包 → µV、遥测/IMU/PPG、控制命令帧 |
| 传输层 | `src/devices/transports/webBluetooth.js` | Web Bluetooth 实现 + 环境检测；transport 可注入（为 Tauri 原生插件留接口） |
| 连接器与适配器 | `src/devices/museConnector.js` | 4 电极 @256Hz `uV` + marker；通知流转有界队列、包序号重建时间戳 |
| 运行时接入 | `src/GraphRuntimeRunnerPage.jsx` | 按 `transport` 选择适配器（原仅支持 `simulated`） |

**约束**：Tauri 桌面端（WebView2）不暴露 Web Bluetooth，需用浏览器形态或注入原生 transport；Muse S Athena（Gen 3）固件明确不支持（检测到即失败，不猜测解码）。验证：单元测试 12 例通过（含 D5→D4 字典联动），`npm run build` 通过；但未连接真实设备，「真实设备落库」验收未完成。

### PF 侧：D6 ✅ 联合导出/归档（demo 分支，2026-08-29）
把 PF 会话包与 BioDB 导出信封（时序 + 事件 + 实验元数据）合并为单一归档。BioDB 侧零改动（复用 `POST /sensor/data/export`）。详见 [`11-d6-joint-export.md`](11-d6-joint-export.md)。

| 实现 | 文件（PF demo 分支） | 说明 |
|---|---|---|
| 合并逻辑 | `src/data/jointExport.js` | PF 文件保持顶层、`biodb/` 存放平台数据；缺失样本留空不填零；来源与时间窗记入 manifest |
| 信封读取 | `src/bioDBClient.js` | `exportBioDBData()` 一次取回 sensor / events / experiment |
| 导出入口 | `src/SessionManager.jsx` | 「Joint export (BioDB)」按钮；BioDB 失败时仍归档 PF 并说明原因 |

**要点**：BioDB 腿为尽力而为——失败时归档照常生成。验证：`node e2e-d6.mjs` 全部 PASS（20 点时序 + 17 文件 + 降级归档）；单元测试 7 例。过程中确认 **VictoriaMetrics 写入后约 6 秒才可查询**，已在 e2e 加重试、在 UI 与 manifest 中明确提示。

### PF 侧：D7 ✅ 分析管线（demo 分支，2026-08-29）
预处理 → 特征（HRV/EDA/频谱）→ 统计/ML，消费 BioDB 读回，分析结果随导出交付。BioDB 侧零改动。详见 [`12-d7-analysis-pipeline.md`](12-d7-analysis-pipeline.md)。

| 实现 | 文件（PF demo 分支） | 说明 |
|---|---|---|
| 预处理 | `src/analysis/signal/preprocess.js` | 缺失填补、重采样、移动平均/中值、去趋势、伪迹剔除 |
| 频谱 | `src/analysis/signal/spectrum.js` | radix-2 FFT、PSD、频带功率、主频 |
| 特征 | `src/analysis/signal/features.js` | 时域统计、HRV 时域/频域、EDA tonic/phasic 与 SCR |
| 统计/ML | `src/analysis/signal/stats.js` | Pearson、Welch t、Cohen's d、岭回归、k-means |
| 编排 | `src/analysis/signal/pipeline.js` | 通道识别 → 分析 → JSON/CSV |
| 服务端对接 | `src/bioDBClient.js` | `fetchBioDBFeatures` / `trainBioDBModel` / `predictBioDB` / `listBioDBAnalyses` |
| 导出集成 | `src/data/jointExport.js` | 联合导出附带 `analysis/` |

**要点**：零新增依赖（FFT/回归/聚类全部自实现）；未知采样率时降级而非猜测；伪迹剔除改用一阶差分 + MAD（初版用移动中位数残差会误剔 39/100 正常点）。验证：`node e2e-d7.mjs` 全部 PASS——构造 60 bpm / 3 次 SCR / 2 Hz 信号，测得 60.0 bpm / SCR=3 / 1.99 Hz；本地岭回归 r²=1.000000；本地与服务端采样率一致。单元测试 19 例 + 联合导出 2 例。

### PF 侧：D8~D10 待开发（PF 独立仓库）
BioDB 侧依赖全部就绪，PF 侧可无缝对接：

| # | 状态 | 对接前提（BioDB 已就绪） |
|---|---|---|
| D8 可视化 | 待开发 | util 页面可作参考实现 ✅ |
| D9 流式推送 | 待开发 | write JWT 按窗授权 ✅ |
| D10 权限/审计 | 待开发 | `/auth` 体系 ✅ |

### 下一步计划
1. **短期（PF 仓库）**：D5 真实设备联调（需 Muse 硬件，代码已完成）→ D8 可视化。BioDB 侧依赖均已就绪，可直接调用既有端点。
2. **中期（PF 仓库）**：D8 可视化（可直接消费 D7 的分析结果）→ D9 流式推送。
3. **长期**：D9 流式推送 → D10 平台级权限/审计。
4. **BioDB 侧运维**：测试残留数据已清理（删除 `exp_quality`、10:00 无标签窗、单点 `exp_emotion`/`exp_cognition` 等，保留 `exp_emotion_verify` 与 `evt_verify_001` 供联调）；接入真实实验数据后复验联合导出元数据与 48h 大窗性能。

## 路线图（阶段 → 开发项）

```
Phase 2（P0-P1）   D1 experiment tag ✅ → D2 实验/协作者映射 ✅ → D3 数据管理面板 ✅ → D4 数据字典 ✅
Phase 3（P1-P2）   D5 脑波设备 ⚠️（代码完成・未硬件验证）→ D7 分析管线 ✅ → D8 可视化 → D6 联合导出 ✅
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
