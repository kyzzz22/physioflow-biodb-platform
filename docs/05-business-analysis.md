# 平台业务分析（v2）

Date: 2026-08-24
Supersedes: `docs/sourced/PLATFORM_BUSINESS_ANALYSIS.md`（v1，2026-08-23）
Related: `MEETING_EXPERIMENT_ID.md`（2026-08-23 会议）、`PF_BIODB_INTEGRATION.md`、`04-d1-experiment-tag.md`

> 本分析是「新系统开发计划」的业务基线：明确**做什么、为谁做、按什么规则做、如何验证**。开发清单与依赖见 `03-development.md`；D1/D2 实施细节见 `04-d1-experiment-tag.md`。

## 1. 业务背景与目标

### 1.1 背景与痛点

研究室开展行为与生理实验（情绪、认知、脑波等），数据产自多个系统、多个被试、多个实验，现状痛点：

| 痛点 | 具体表现 |
|---|---|
| 数据分散、格式不一 | 实验数据、传感器数据、事件标记散落各系统与导出文件，难以统一管理复用 |
| 无法区分「哪个实验、哪个被试」 | 时序库中多块数据并列，缺实验维度，同一被试不同实验的数据无法区分（会议核心问题） |
| 实验不可复现 | 实验条件（刺激集、顺序、参数）只在人脑中/笔记中，事后无法还原 |
| 设备数据未整合 | 脑波等生体设备数据没有统一的采集→存储通路 |
| 分析/可视化要手工搬运 | 数据导出到外部工具才能分析，无法在平台内闭环 |

### 1.2 平台目标

**一个覆盖实验全生命周期的研究数据平台**：设计 → 采集 → 存储 → 管理 → 分析 → 可视化。

**愿景**：生体实验「一次采集、处处可复用」——实验定义、原始数据、分析结果在同一平台闭环，可复现、可共享、可跨实验分析。

### 1.3 两个组件的定位

| 组件 | 定位 | 承担什么 |
|---|---|---|
| **PhysioFlow（PF）** | 实验工作流（前端） | 可视化协议设计、运行、被试交互、设备采集、导出可复现数据包 |
| **BioDB** | 生体数据仓库（后端） | 传感器时序（VictoriaMetrics）、事件（MongoDB）、用户/权限（PostgreSQL）、JWT 认证 |
| **整合层** | PF 采集 → BioDB 存储 → 平台管理/分析/可视化 | 按「实验ID + 协作者ID」二段标识存储 |

**核心原则（会议确认）**：PF 协议 = 领域模型（实验条件的唯一事实源）；BioDB = 数据仓库（只存时序 + 事件，不承载应用逻辑）。

## 2. 干系人与角色

| 角色 | 主要活动 | 关注点 | 平台侧视图 |
|---|---|---|---|
| **实验设计者（研究者）** | 用 PF 设计协议（节点图/问卷/认知任务/条件）、配置设备连接器、冻结版本 | 设计快、可复现、被试体验好 | ComposerV2 编辑器、模板库 |
| **实验操作员** | 运行会话、监控采集、处理设备故障、推送到 BioDB | 流程顺、故障可恢复、数据不丢 | 运行时页、BioDB 导出 |
| **被计测者（協力者）** | 完成实验（界面交互/问卷/认知任务） | 界面友好、不被打断 | Participant 界面（多语言） |
| **数据分析人员** | 从 BioDB 取数、预处理、统计/ML、可视化 | 数据完整、标识清晰、可追溯 | BioDB 数据管理面板、分析/可视化模块 |
| **管理员** | 用户/协作者/长期 token/数据保留管理 | 安全、合规、可控 | BioDB 管理 UI |

权限模型（现状 + 目标）：BioDB 已有「长期 token → 用途 JWT（sensor_read/write/event，时间窗 claim）」；平台侧统一权限/审计视图为 P3 项（D10）。

## 3. 核心业务场景（用例）

### UC-1 设计实验
研究者用模板（Emotion/SAM、Stroop、Go/No-Go）或空白协议搭建实验 → 配置条件/刺激/问卷 →（可选）配置设备连接器 → 冻结协议（不可变，含 configHash）。
- 前置：已登录，有设计权限
- 产出：冻结的 protocol（`protocolId` = 实验ID）
- PF 现有能力全部覆盖（13+ 节点类型、9 题型问卷、PPT 式界面编辑、i18n zh/ja/en）

### UC-2 运行实验并采集
操作员创建会话 → 被试参与 → 节点执行 + 被试交互 +（可选）device sampler 按 sampleRateHz 采集 → 会话完成。
- 特性：确定性运行时（注入时钟/ID）、暂停/恢复/重试/跳过、快照恢复、事件回放
- 产出：本地数据包（events / responses / device_events JSONL+CSV / BIDS / 数据字典）
- 异常：断网、设备掉线、被试中途退出 → 会话可恢复，数据不丢

### UC-3 数据入库（推送到 BioDB）
会话完成后推送：时序 → VictoriaMetrics（tag：`experiment` + `participant` + `experimenter`）；事件 → MongoDB。
- 标识解析：`experimentId`（协议配置 → `protocolId` 兜底 → settings 默认）；`participantId`（协议 → settings 映射 → 默认）
- 安全：长期 token → 按 chunk 时间窗签发 write JWT（8 分钟刷新），`experiment` 从 JWT claim 注入（写入者不可伪造）
- 失败处理：JWT 刷新重试已有；断网/重传/幂等完整策略为 P3（D9）

### UC-4 数据管理（Phase 2，D3）
按实验/协作者浏览 BioDB 数据、时间段查看、事件 CRUD、简单曲线、数据字典浏览。
- 验收：D2 推送的数据在面板可见、可管理事件、同一被试不同实验数据可分别读回

### UC-5 数据分析（Phase 3，D7）
从 BioDB 读回（按 experiment+participant 过滤）→ 预处理（重采样/滤波）→ 特征（HRV/EDA/频谱）→ 统计/ML → 结果导出或写回事件。
- 原则：分析消费读回 API，对写入方无关

### UC-6 可视化（Phase 3，D8）
历史多列叠加曲线、实时模式（流式推送后）、情感地图。

### UC-7 平台管理（Phase 4，D10）
平台级角色/权限/审计视图、统一认证体验。

## 4. 业务规则（关键约束）

| # | 规则 | 依据/落地 |
|---|---|---|
| R1 | **二段标识唯一性**：数据按「experiment + participant」区分；同一 participant 不同 experiment 的数据不得串混 | 会议核心；D1 加 `experiment` tag；读回按 JWT scope 过滤 |
| R2 | **experiment 标识不可伪造**：`experiment` 由 JWT 签发方（长期 token + writejwt）注入，写入请求不直接带 | `04-d1-experiment-tag.md` 设计决策 |
| R3 | **协议冻结不可变**：冻结后协议不可变（含 configHash），是可复现的根基；条件信息只在协议中（不引入 Excel/条件DB） | 会议决定；PF 现有 |
| R4 | **时间戳精度**：BioDB 纳秒；PF 事件 ISO + epoch ms + monotonic 三时钟，不回退精度 | 会议决定；现状已满足 |
| R5 | **数据归属**：experimenter（写者）与 participant（被计测者）双视角；事件记录 created_by（实验者）/user_id（协作者） | BioDB 现有模型 |
| R6 | **权限最小化**：长期 token 不散落协议内（只存 settings 本地）；短命 JWT 带时间窗 | Phase 1 现有 |
| R7 | **可复现导出**：会话数据包 = 协议（冻结）+ 事件 + device_events + BIDS + 数据字典 | PF 现有导出 |

## 5. 数据与标识体系

### 5.1 实体关系

```
protocol（PF，冻结不可变）
  └─ protocolId = 实验ID（ex: exp_nomura_ninomiya）
  └─ protocol.biodb { enabled, experimentId, participantId, experimentLabel? }
  └─ 条件/刺激/问卷/设备配置（领域模型，唯一事实源）
       │
session（一次运行）
  └─ participant（协作者 ID，21 位 nanoid）
  └─ 事件/响应/device_events（三时钟时间戳）
       │  pushSession 推送
       ▼
BioDB
  ├─ VictoriaMetrics 时序：series = biodb_<column>，tag = experiment + participant + experimenter，ns 时间戳
  ├─ MongoDB 事件：user_id（协作者）/ created_by（实验者）/ 时间 / details
  └─ PostgreSQL 用户/权限：21 位 ID、长期 token、scope
```

### 5.2 标识映射链

| 层 | 标识 | 示例 |
|---|---|---|
| PF 协议 | `protocolId` | `exp_nomura_ninomiya` |
| PF 协议配置 | `protocol.biodb.experimentId`（空则用 protocolId 兜底） | `exp_nomura_ninomiya` |
| BioDB 时序 tag | `experiment` | `exp_nomura_ninomiya` |
| BioDB 时序 tag | `participant`（来自协议配置 → settings 映射 → 默认） | `<21位 ID>` |
| BioDB 时序 tag | `experimenter`（= JWT sub） | `<21位 ID>` |

### 5.3 数据字典对接（D4）

PF 已有 `graphDataDictionary`；需对接「时序 channel 清单（dataType/unit/sampleRate）→ 数据字典」，随推送/导出附带，保证通道数据可解释。

## 6. 原型先行计划（会议决定 → 本阶段行动）

会议定案：**不直接做需求定义/DB 设计，先用 PF 做 5 个左右原型实验，从原型抽象需求**（9/1 前后会议整理，担当：古久・なべしま・くおわみ，全员试用）。

### 建议的 5 个原型模式（用 3 模板 + 空白协议即可产出）

| # | 原型 | 覆盖的需求点 | 用到的 PF 能力 |
|---|---|---|---|
| P1 | 情绪问卷型（Emotion/SAM） | 自评量表 + 媒体刺激；事件标记 | 问卷（9 题型/条件跳过/评分）、media 节点 |
| P2 | 认知任务型（Stroop） | RT/准确率、一致性条件、练习块 | cognitive-task 运行器、generateStroopTrials |
| P3 | 抑制任务型（Go/No-Go） | 漏报/误报、Go 比例、抑制窗口 | cognitive-task 运行器、generateGonogoTrials |
| P4 | 多实验对照型（同一被试 × 两个实验） | **验证 experiment tag 隔离**：同一 participant 两次不同实验，数据可分别读回 | protocol.biodb.experimentId 配置 + pushSession（配合 D1/D2） |
| P5 | 设备采集型（模拟连接器 + 传感器） | 设备数据采集 → 推送 BioDB → 读回一致 | device connector、device sampler、BioDB 导出（Phase 1 已通） |

### 从原型抽象的内容（9/1 会议输出）

1. 每种实验需要哪些**标识与元数据**（名称/条件/刺激集/假设/IRB 等，哪些进协议、哪些进 experiment 元数据）。
2. 各实验的**数据形态**（通道、采样率、事件类型）→ 数据字典需求。
3. 被试视角的**界面与流程需求** → 模板化的机会。
4. **跨实验分析**所需的最小标识一致性。
5. 设备采集的实际**质量需求**（丢帧率、时间戳连续性）。

## 7. 功能需求清单

> 状态列：✅ 已有 / 🚧 开发中 / 📋 roadmap。开发项编号与 `03-development.md` 一致。

### 7.1 实验设计（PF 现有，✅）

| 功能 | 说明 |
|---|---|
| 可视化协议设计 | 节点图、13+ 节点类型、拖拽连线、分组、子流程、撤销/重做、pan/zoom/多选/搜索/自动布局/流快照/小地图 |
| PPT 式界面编辑器 | 元素库拖拽、属性面板、全屏节点编辑、真实运行时预览 |
| 问卷设计器 | 9 题型 / 11 预设 / 条件跳过 / 确定性随机 / 逐题限时 / 计分输出 / CSV / 共享库 |
| 认知任务 | Stroop / Go/No-Go 真试次（RT/正确率/漏报/误报）、AttentionCheckRunner |
| 任务模板 | Emotion（SAM）/ Stroop / Go-No-Go |
| 实验结构语义 | block 顺序（固定/随机/latin square）、ITI jitter、practice 标志、性能变量自适应分支 |
| 多语言 | ComposerV2 UI + participant 内容 zh/ja/en |
| 媒体/资产 | stimuli 媒体库、visual angle calculator、主题预设（5 套） |

### 7.2 实验运行（PF 现有，✅）

确定性运行时、暂停/恢复/重试/跳过、快照恢复、事件回放、被试界面渲染、设备采样（device sampler，drift-corrected）。

### 7.3 数据存储（Phase 1 ✅ + D1 🚧）

| 功能 | 状态 | 说明 |
|---|---|---|
| 传感器时序入库 | ✅ | `/sensor/data/write`（容器：format/compression/data），VictoriaMetrics |
| **experiment tag 维度** | 🚧 D1 | `tag_columns` 加 `experiment`；JWT claim 注入；读回过滤 |
| 事件管理 | ✅ | `/event/events` CRUD，协作者/实验者双视角 |
| 用户/权限 | ✅ | PostgreSQL + 长期 token → JWT（scope/时间窗） |
| 数据读回 | ✅ | `/sensor/data/read`（rows/时间窗），列主序 |

### 7.4 数据管理（📋 D3）

participant 选择、数据浏览、事件 CRUD、简单曲线、数据字典对接（D4）。

### 7.5 分析管线（📋 D7）

预处理（重采样/滤波）、特征（HRV/EDA/频谱）、伪迹剔除、统计/ML（消费 BioDB 读回）。

### 7.6 可视化（📋 D8）

历史多列曲线、实时模式、情感地图。

### 7.7 其他（📋）

联合导出/归档（D6）、流式推送（D9）、平台级权限/审计/统一认证（D10）、真实脑波设备 adapter（D5）。

## 8. 非功能需求

| 维度 | 需求 | 现状/目标 |
|---|---|---|
| 性能 | 100Hz 设备采样不卡 UI | ✅ deviceEventsRef 缓冲 + 节流状态 |
| 可复现性 | 冻结协议 + 数据字典 + 导出包 | ✅ PF 现有 |
| 数据完整性 | JWT 时间窗 = chunk 首末样本；断网重试/重传 | ✅ 窗口 JWT 已实现；完整策略 D9 |
| 安全 | experiment 不可伪造（JWT claim）；token 最小化 | 🚧 D1 实施 |
| 部署 | 本地研究室部署（不做云托管）；docker compose 一键 | ✅ BioDB 现有；PF×BioDB 部署协同 📋 |
| 兼容 | 浏览器原生（压缩/Base64/流），CORS 全开 | ✅ Phase 1 验证 |

## 9. 分阶段交付与验收

| 阶段 | 交付 | 验收标准 |
|---|---|---|
| Phase 0 | PF 现有能力基线（已就绪，源码已入库新项目） | 门禁：`npm test && npm run build && npm run lint -- --max-warnings=0` |
| Phase 1 | 运行时采集 → BioDB 推送（已实施） | 模拟连接器数据落库、读回样本数一致 |
| Phase 2（D1-D4） | experiment tag + 映射 + 数据管理面板 + 数据字典 | **同一 participant 两次不同实验数据分别读回、不串数据**；面板可浏览管理 |
| Phase 3（D5-D8） | 脑波设备 + 分析 + 可视化 + 联合导出 | 真实设备落库、特征可算、曲线/情感地图可渲染 |
| Phase 4（D9-D10） | 流式推送 + 权限审计 | 实时曲线、平台级权限视图 |

## 10. 风险与开放问题

| 风险/问题 | 影响 | 对策 |
|---|---|---|
| 原型需求抽象与 D1/D2 并行开发冲突 | 原型可能提出新标识需求 | 9/1 会议前完成 D1/D2（低成本），原型 P4 直接验证隔离效果 |
| experiment 元数据（假设/IRB/协议快照）存哪 | 会议留「任意」 | 先由 PF 协议承载；协议快照入 BioDB 作为可选后续 |
| 真实脑波设备适配成本 | 高，依赖硬件 | 模拟通路已验证，D5 单列、不进 Phase 2 关键路径 |
| 跨实验分析的一致性 | 各实验通道/事件命名不一 | 数据字典对接（D4）先行，从原型 P1-P3 提取通道清单 |
| 不做 | 平台多租户/云托管、任意 JS 注入、自动统计结论生成 | 明确排除（`03-development.md`） |
