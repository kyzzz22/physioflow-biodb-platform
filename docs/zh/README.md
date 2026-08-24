# PhysioFlow × BioDB 研究数据平台（中文版）

> 日本語版（デフォルト）: [`README.md`](../../README.md)

覆盖**实验全生命周期**的研究数据平台：设计 → 采集 → 存储 → 管理 → 分析 → 可视化。

**📖 在线文档（GitHub Pages）**：https://kyzzz22.github.io/physioflow-biodb-platform/

- **PhysioFlow（PF）**：实验工作流（可视化协议设计、运行、被试交互、导出可复现数据包）。
- **BioDB**：生体数据仓库（传感器时序 VictoriaMetrics、事件 MongoDB、用户/权限 PostgreSQL、JWT 认证）。
- **整合**：PF 采集的生体数据推送 BioDB，按「实验ID + 协作者ID」二段标识存储，平台统一管理、分析、可视化。

## 文档索引（中文版）

| 文档 | 内容 |
|---|---|
| `01-situation.md` | **现状盘点与可借鉴**：PF / BioDB 各自已有的能力（业务功能、技术架构、数据模型），可直接复用部分 |
| `02-gap.md` | **合并系统缺少的部分**：从业务/技术/数据三维度列缺口 |
| `03-development.md` | **需开发的部分**：按优先级 + 依赖关系的开发清单与路线图 |
| `04-d1-experiment-tag.md` | **D1/D2 实施计划**：BioDB `experiment` 维度 + PF 映射 |
| `05-business-analysis.md` | **平台业务分析（v2）**：背景/角色/用例/业务规则/标识体系/原型计划/验收 |

原始参考资料（`../sourced/`，部分为中文原文）：

| 文档 | 内容 |
|---|---|
| `../sourced/MEETING_EXPERIMENT_ID.md` | 会议纪要（日文）：实验ID + 协作者ID 二段标识 |
| `../sourced/PF_EXPERIMENT_DESIGN_ANALYSIS.md` | PF 实验设计能力分析（原始） |
| `../sourced/PF_COMPOSER_V2_GAP_ANALYSIS.md` | PF 编辑器差异分析（原始） |
| `../sourced/PF_BIODB_INTEGRATION.md` | PF×BioDB 对接方案（Phase 1-3） |
| `../sourced/PLATFORM_BUSINESS_ANALYSIS.md` | 平台总体业务分析（第一版） |

## 核心结论

1. **实验ID + 协作者ID 二段结构** = PF `protocolId` + participant，映射 BioDB `experiment` + `participant` tag。
2. **PF 协议 = 领域模型**，BioDB = 数据仓库，二者职责互补。
3. 下一阶段：BioDB 加 `experiment` tag 维度 → PF BioDB 数据管理面板 → 分析/可视化。
