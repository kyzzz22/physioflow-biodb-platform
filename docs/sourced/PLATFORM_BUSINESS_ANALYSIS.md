# PF × BioDB 整合平台 — 总体业务分析

Date: 2026-08-23
Related: `PF_BIODB_INTEGRATION.md`, `EXPERIMENT_DESIGN_ANALYSIS.md`, `MEETING_2026-08-23_EXPERIMENT_ID.md`

## 1. 项目定位与愿景

**PhysioFlow（PF）× BioDB 整合平台**是一个覆盖**实验全生命周期**的研究数据平台：

```
设计 → 采集 → 存储 → 管理 → 分析 → 可视化
```

- **PF** 提供前端「实验工作流」：可视化设计协议（节点图）、运行实验（被试交互、认知任务、问卷）、导出可复现数据包。
- **BioDB** 提供后端「生体数据仓库」：传感器时序（VictoriaMetrics）、事件（MongoDB）、用户/权限（PostgreSQL）。
- 整合后：PF 采集的生体数据 → 推送 BioDB → 按「实验ID + 协作者ID」二段标识存储 → 平台统一管理、分析、可视化。

**愿景**：让研究室的生体实验「一次采集、处处可复用」——实验定义、原始数据、分析结果在同一平台闭环，可复现、可共享、可跨实验分析。

## 2. 目标用户与角色

| 角色 | 主要活动 | 关注点 |
|---|---|---|
| **实验设计者（研究者）** | 用 PF 设计协议（刺激/问卷/条件/认知任务）、配置设备、冻结版本 | 设计快、可复现、被试体验 |
| **实验操作员** | 运行会话、监控采集、处理设备故障 | 流程顺、故障可恢复、数据不丢 |
| **被计测者（協力者）** | 作为被试完成实验 | 界面友好、不被打断 |
| **数据分析人员** | 从 BioDB 取数、预处理、统计/ML、可视化 | 数据完整、标识清晰、可追溯 |
| **管理员** | 用户/权限/长期 token/数据保留 | 安全、合规、可控 |

## 3. 核心业务流程（端到端）

```
1. 设计：研究者用 PF 可视化搭协议（Emotion/Stroop/Go-No-Go 模板或空白）
   └ 配置设备连接器（如 EEG）→ 冻结协议（不可变版本，含 configHash）
2. 运行：操作员创建会话 → 被计测者参与
   ├ PF 运行时：节点执行 + 被试交互（界面/问卷/认知任务）
   └ 设备采集：device sampler 按 sampleRateHz 读传感器 → device_events
3. 存储：会话完成 → 推送到 BioDB
   ├ 传感器时序 → VictoriaMetrics（tag: experiment + participant + experimenter）
   └ 事件/标记 → MongoDB（event + details）
4. 管理（Phase 2/3）：按实验/协作者浏览数据、管理事件、数据字典、检索导出
5. 分析（Phase 3）：预处理/统计/ML，消费 BioDB 读回
6. 可视化（Phase 3）：实时/历史曲线、情感地图
```

## 4. 功能域分解

### 4.1 实验设计（PF 现有）
可视化节点图、13+ 节点类型、PPT 式界面编辑器、问卷设计器、认知任务、按类型默认模板、任务模板（Emotion/Stroop/Go-No-Go）、变量/条件/循环/随机、全屏编辑、画布交互。

### 4.2 实验运行（PF 现有）
确定性运行时、暂停/恢复/重试/跳过、快照恢复、实时预览、被试界面渲染、认知任务试次运行器、注意力检查、设备采集（Phase 1）。

### 4.3 数据存储与标识（BioDB + 对接）
- **传感器时序**：VictoriaMetrics，`experiment` + `participant` + `experimenter` 三 tag（**会议要求的二段结构**）。
- **事件**：MongoDB，experiment/participant/时间/详情。
- **元数据**：实验条件/协议 = PF protocol（结构化），可选 snapshot 存 BioDB。
- **标识体系**：实验ID（`protocolId` 或语义名）→ 协作者ID（participant）→ 数据。

### 4.4 数据管理（Phase 2/3 roadmap）
研究项目管理、数据字典（`graphDataDictionary` + channel 清单）、按实验/协作者浏览、检索、导出（复用导出格式）。

### 4.5 数据分析（Phase 3 roadmap）
预处理（重采样/滤波）、特征（HRV/EDA/频谱）、伪迹剔除、统计/ML 管线（消费 BioDB 读回，对写入方无关）。

### 4.6 可视化（Phase 3 roadmap）
历史多列曲线、实时模式（流式推送后）、情感地图（BioDB util 部分移植）。

## 5. 业务价值与痛点

| 痛点 | 平台价值 |
|---|---|
| 生体数据分散、格式不一、难以复用 | 统一 API 入库（BioDB），带实验/协作者标识 |
| 实验不可复现（条件/设备/流程丢失） | PF 协议冻结（含 configHash）+ 数据字典，完整复现 |
| 无法跨实验/跨协作者对比 | `experiment`+`participant` 标识 → 横断分析 |
| 脑波等设备数据未整合 | device connector 框架 + BioDB 时序存储 |
| 分析/可视化要手动导出到别处 | 平台内闭环（分析/可视化模块） |
| 权限/数据安全 | BioDB 用户/权限 + JWT + 数据保留策略 |

## 6. 与会议需求对齐

| 会议决定 | 平台落地 |
|---|---|
| 实验ID导入 | BioDB 加 `experiment` tag（Phase 1 后一行扩展） |
| 二段识别结构 | `experiment` + `participant`，对应 PF `protocolId` + session participant |
| 原型先行（5 模式） | PF 3 模板 + 空白协议即可产出 |
| 领域逻辑优先 | PF 协议 = 领域模型，DB 后置 |
| 条件信息管理 | PF 协议（非 Excel） |
| 脑波整合 | device connector → 时序入库 |
| 时间戳精度 | BioDB 纳秒级（已超需求） |

## 7. 分阶段路线图

| 阶段 | 内容 | 状态 |
|---|---|---|
| **Phase 0** | PF 现有能力（设计/运行/导出/问卷/认知任务/编辑体验） | ✅ 已完成 |
| **Phase 1** | PF 运行时采集 → BioDB 推送（simulated 验证、experiment tag） | ✅ 已实施（推送链路）；experiment tag 待扩展 |
| **Phase 2** | PF BioDB 浏览/管理面板（数据/事件/配置） | roadmap |
| **Phase 3** | 研究/数据管理、分析/ML、可视化、流式推送 | roadmap |

## 8. 成功指标

- 研究者 5 分钟内用模板搭一个可运行实验（原型先行）
- 一个会话完成后，数据自动/一键入库 BioDB，带实验+协作者标识，读回一致
- 脑波设备接入后，实时/批量数据落库可复现
- 数据分析人员能从 BioDB 直接取到带标识的完整数据，无需手动拼接
- 权限/审计/数据保留满足研究室合规

## 9. 关键架构原则

1. **PF 协议 = 领域模型**（DB 设计后置，符合会议）
2. **BioDB = 数据仓库**（时序/事件/元数据，不承载应用逻辑）
3. **标识先行**：任何数据入库都带 `experiment`+`participant`+时间
4. **浏览器原生**：压缩/Base64/流均浏览器能力，不引后端代理（Phase 1）
5. **增量落地**：Phase 每阶段独立可交付，不阻塞
