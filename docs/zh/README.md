# PhysioFlow × BioDB 研究数据平台（中文版）

> 日本語版（デフォルト）: [`README.md`](../../README.md)

覆盖**实验全生命周期**的研究数据平台：设计 → 采集 → 存储 → 管理 → 分析 → 可视化。

**📖 在线文档（GitHub Pages）**：https://kyzzz22.github.io/physioflow-biodb-platform/

- **PhysioFlow（PF）**：实验工作流（可视化协议设计、运行、被试交互、导出可复现数据包）。
- **BioDB**：生体数据仓库（传感器时序 VictoriaMetrics、事件 MongoDB、用户/权限 PostgreSQL、JWT 认证）。
- **整合**：PF 采集的生体数据推送 BioDB，按「实验ID + 协作者ID」二段标识存储，平台统一管理、分析、可视化。

## 项目链接

| 项目 | 链接 | 说明 |
|---|---|---|
| **PhysioFlow（PF）** | https://github.com/kyzzz22/physioflow-app | 实验工作流（前端） |

> BioDB（生体数据仓库）为私有仓库，不附链接。

## 文档索引（中文版）

| 文档 | 内容 |
|---|---|
| `01-situation.md` | **现状盘点与可借鉴**：PF / BioDB 各自已有的能力（业务功能、技术架构、数据模型），可直接复用部分 |
| `02-gap.md` | **合并系统缺少的部分**：从业务/技术/数据三维度列缺口 |
| `03-development.md` | **需开发的部分**：按优先级 + 依赖关系的开发清单与路线图 |
| `04-d1-experiment-tag.md` | **D1/D2 实施计划**：BioDB `experiment` 维度 + PF 映射 |
| `05-business-analysis.md` | **平台业务分析（v2）**：背景/角色/用例/业务规则/标识体系/原型计划/验收 |
| `06-biodb-deployment-summary.md` | **BioDB 测试实例部署总结**：架构/组件/部署步骤/认证流程/运维注意/实际部署与历次功能实施与验收记录 |
| `07-d2-experiment-mapping.md` | **D2 实施记录（PF demo 分支）**：`protocol.biodb` 配置 / 设置 UI / 会话推送 / e2e 验证（D2 完成） |
| `08-d3-data-panel.md` | **D3 实施记录（PF demo 分支）**：数据管理面板（participant 选择 / 读回 / 事件 CRUD）/ e2e 验证（D3 完成） |

原始参考资料（`../sourced/`，部分为中文原文）：

| 文档 | 内容 |
|---|---|
| `../sourced/MEETING_EXPERIMENT_ID.md` | 会议纪要（日文）：实验ID + 协作者ID 二段标识 |
| `../sourced/PF_EXPERIMENT_DESIGN_ANALYSIS.md` | PF 实验设计能力分析（原始） |
| `../sourced/PF_COMPOSER_V2_GAP_ANALYSIS.md` | PF 编辑器差异分析（原始） |
| `../sourced/PF_BIODB_INTEGRATION.md` | PF×BioDB 对接方案（Phase 1-3） |
| `../sourced/PLATFORM_BUSINESS_ANALYSIS.md` | 平台总体业务分析（第一版） |

## 进度与计划（一览）

### ✅ 已完成（BioDB 侧 + PF 侧 D1~D3）

| 项目 | 状态 |
|---|---|
| **D1** `experiment` 标签维度（写入/读回/事件关联/实验注册表/联合导出/特征·ML 分析） | ✅ 端到端验收通过（[`06-biodb-deployment-summary.md`](06-biodb-deployment-summary.md)） |
| util 可视化页面（`/util/`） | ✅ |
| bio_console 中文 WebUI（`/db/`） | ✅ |
| WebUI 整合 `/WebUI/console`（日语版·深色主题） | ✅ 2026-08-27 |
| **D2** 实验/协作者映射（PF demo 分支）— `protocol.biodb` + 设置 UI + 会话推送 | ✅ 2026-08-28（[`07-d2-experiment-mapping.md`](07-d2-experiment-mapping.md)） |
| **D3** 数据管理面板（PF demo 分支）— participant 选择 / 读回 / 事件 CRUD | ✅ 2026-08-28（[`08-d3-data-panel.md`](08-d3-data-panel.md)） |

### 🚧 待开发（PF 侧 D4~D10）

| 开发项 | 优先级 | 状态 |
|---|---|---|
| D4 数据字典对接 | P1 | 待开发（下一步着手） |
| D5 脑波设备 adapter | P1 | 待开发 |
| D6 联合导出/归档 | P2 | 待开发 |
| D7 分析管线 | P2 | 待开发 |
| D8 可视化 | P2 | 待开发 |
| D9 流式推送 | P3 | 待开发 |
| D10 权限/审计 | P3 | 待开发 |

### 路线图

```
Phase 2（P0-P1）  D1 ✅ → D2 ✅ → D3 ✅ → D4 数据字典
Phase 3（P1-P2）  D5 脑波设备 → D7 分析管线 → D8 可视化 → D6 联合导出
Phase 4（P3）     D9 流式推送 → D10 权限/审计
```

详细：[`03-development.md`](03-development.md)

## 核心结论

1. **实验ID + 协作者ID 二段结构** = PF `protocolId` + participant，映射 BioDB `experiment` + `participant` tag。
2. **PF 协议 = 领域模型**，BioDB = 数据仓库，二者职责互补。
3. 下一阶段：PF 数据字典对接（D4）→ 脑波设备 adapter（D5）→ 分析/可视化（D6~D10）。
