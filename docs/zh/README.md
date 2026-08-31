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

## 在线入口（单一 origin）

BioDB 的 nginx（默认 `:5002`）以单一 origin 提供全部 UI。研究室 LAN 内任意终端可访问 `http://<主机IP>:5002/`（需放行防火墙 5002 入站）。

| 路径 | 内容 |
|---|---|
| `/` | **统一落地页**（日/中切换，默认日语）— PF Dashboard / BioDB Console 两大卡片 + 子链接 |
| `/pf/` | PhysioFlow Dashboard（构建产物同捆，浏览器本地保存） |
| `/WebUI/console` | BioDB 控制台（SvelteKit，日文·深色主题）— 库存 / 浏览 / 事件 / 实验 / 分析 / 导出 / 连接设置 |
| `/db/` | BioDB 控制台（中文版，静态版） |
| `/util/` | 可视化客户端（历史 / 实时 / 事件图表 / 情感地图） |
| `/shared/theme.css` | 统一设计 token（暗色 + 绿色主题） |

全部 UI 统一于同一套**暗色 + 绿色**设计系统（`biodb-main/webui-theme/theme.css`）。

## 文档索引（中文版）

| 文档 | 内容 |
|---|---|
| `01-situation.md` | **现状盘点与可借鉴**：PF / BioDB 各自已有的能力（业务功能、技术架构、数据模型），可直接复用部分 |
| `02-gap.md` | **合并系统缺少的部分**：从业务/技术/数据三维度列缺口 |
| `03-development.md` | **需开发的部分**：按优先级 + 依赖关系的开发清单与路线图（含 WebUI 平台侧） |
| `04-d1-experiment-tag.md` | **D1/D2 实施计划**：BioDB `experiment` 维度 + PF 映射 |
| `05-business-analysis.md` | **平台业务分析（v2）**：背景/角色/用例/业务规则/标识体系/原型计划/验收 |
| `06-biodb-deployment-summary.md` | **BioDB 测试实例部署总结**：架构/组件/部署步骤/认证流程/运维注意/历次功能实现与自动 E2E 记录 |
| `07-d2-experiment-mapping.md` | **D2 实施记录（PF demo 分支）**：`protocol.biodb` 配置 / 设置 UI / 会话推送 / e2e 验证（D2 完成） |
| `08-d3-data-panel.md` | **D3 实施记录（PF demo 分支）**：数据管理面板（participant 选择 / 读回 / 事件 CRUD）/ e2e 验证（D3 完成） |
| `09-d4-channel-dictionary.md` | **D4 实施记录（PF demo 分支）**：通道数据字典（`dataType`/`unit`/`sampleRate` 提取 → 导出附带 → 推送附加到实验）/ e2e 验证（D4 完成） |
| `10-d5-eeg-adapter.md` | **D5 实施记录（PF demo 分支）**：Muse 脑波设备 adapter（BLE 协议解码 / 传输层可注入 / 通知流转采样队列）+ 12 例单元测试（⚠️ 未做真实硬件验证） |
| `11-d6-joint-export.md` | **D6 实施记录（PF demo 分支）**：联合导出（PF 会话包 + BioDB 时序/事件/实验信封合并为单一归档）+ 7 例单测与 e2e 验证（D6 完成） |
| `12-d7-analysis-pipeline.md` | **D7 实施记录（PF demo 分支）**：分析管线（预处理/HRV·EDA·频谱特征/统计·ML，零新增依赖）+ 19 例单测与 e2e 验证（D7 完成） |
| `13-d8-visualization.md` | **D8 实施记录（PF demo 分支）**：可视化（历史多列曲线 / 实时模式 / 情感地图 / D7 特征面板，SVG + 纯几何可测试）+ 19 例单测与 e2e 验证（D8 完成） |
| `14-webui-console.md` | **WebUI 统一部署与控制台扩展**：统一入口 / 共通主题 / 控制台功能（看板·缩放·分析图表等） |

原始参考资料（`../sourced/`，部分为中文原文）：

| 文档 | 内容 |
|---|---|
| `../sourced/MEETING_EXPERIMENT_ID.md` | 会议纪要（日文）：实验ID + 协作者ID 二段标识 |
| `../sourced/PF_EXPERIMENT_DESIGN_ANALYSIS.md` | PF 实验设计能力分析（原始） |
| `../sourced/PF_COMPOSER_V2_GAP_ANALYSIS.md` | PF 编辑器差异分析（原始） |
| `../sourced/PF_BIODB_INTEGRATION.md` | PF×BioDB 对接方案（Phase 1-3） |
| `../sourced/PLATFORM_BUSINESS_ANALYSIS.md` | 平台总体业务分析（第一版） |

## 进度与计划（一览）

### ✅ 原型功能已实现

> 下列项目均已完成代码实现，并保留了标注日期的自动测试／E2E 执行记录；主要流程的人工操作确认、真实数据综合确认和实机确认仍需另行进行。

| 项目 | 状态 |
|---|---|
| **D1** `experiment` 标签维度（写入/读回/事件关联/实验注册表/联合导出/特征·ML 分析） | ✅ 已实现、有自动 E2E 执行记录（[`06-biodb-deployment-summary.md`](06-biodb-deployment-summary.md)） |
| util 可视化页面（`/util/`） | ✅ |
| bio_console 中文 WebUI（`/db/`） | ✅ |
| WebUI 整合 `/WebUI/console`（日语版） | ✅ 2026-08-27 |
| **D2** 实验/协作者映射（PF demo 分支）— `protocol.biodb` + 设置 UI + 会话推送 | ✅ 2026-08-28（[`07-d2-experiment-mapping.md`](07-d2-experiment-mapping.md)） |
| **D3** 数据管理面板（PF demo 分支）— participant 选择 / 读回 / 事件 CRUD | ✅ 2026-08-28（[`08-d3-data-panel.md`](08-d3-data-panel.md)） |
| **D4** 通道数据字典对接（PF demo 分支）— 通道清单提取 / 导出附带 / 推送附加到实验 | ✅ 2026-08-28（[`09-d4-channel-dictionary.md`](09-d4-channel-dictionary.md)） |
| **D6** 联合导出/归档（PF demo 分支）— PF 会话包 + BioDB 时序/事件/实验合并为单一归档 | ✅ 2026-08-29（[`11-d6-joint-export.md`](11-d6-joint-export.md)） |
| **D7** 分析管线（PF demo 分支）— 预处理 / HRV·EDA·频谱特征 / 统计·ML，零新增依赖，分析结果随导出交付 | ✅ 2026-08-29（[`12-d7-analysis-pipeline.md`](12-d7-analysis-pipeline.md)） |
| **D8** 可视化（PF demo 分支）— 历史多列曲线 / 实时窗口 / 情感地图 / D7 特征面板 | ✅ 2026-08-29（[`13-d8-visualization.md`](13-d8-visualization.md)） |
| **WebUI 统一入口** — 落地页（日/中）/ `/pf/` 同捆 / `/shared` 主题分发 | ✅ 2026-08-30（[`14-webui-console.md`](14-webui-console.md)） |
| **统一设计系统** — 全 UI 暗色 + 绿色统一（token 集中、图表色统一） | ✅ 2026-08-30 |
| **控制台功能扩展** — 库存看板 / 浏览缩放·CSV / 分析图表 / 事件批量删除 / 字典编辑 | ✅ 2026-08-30 |

### 🚧 待开发（PF 侧 D9~D10）

| 开发项 | 优先级 | 状态 |
|---|---|---|
| D5 脑波设备 adapter（Muse） | P1 | ⚠️ 代码完成、**实机未验证**（需 Muse 设备） |
| D9 流式推送 | P3 | 待开发 |
| D10 权限/审计 | P3 | 待开发 |

### 路线图

```
Phase 2（P0-P1）  D1 ✅ → D2 ✅ → D3 ✅ → D4 ✅ 数据字典
Phase 3（P1-P2）  D5 ⚠️ 脑波设备（实机验证待定）→ D7 ✅ 分析管线 → D8 ✅ 可视化 → D6 ✅ 联合导出
Phase 4（P3）     D9 流式推送 → D10 权限/审计
```

详细：[`03-development.md`](03-development.md)

## 核心结论

1. **实验ID + 协作者ID 二段结构** = PF `protocolId` + participant，映射 BioDB `experiment` + `participant` tag。这是整个平台的标识基础。
2. **PF 协议 = 领域模型**，BioDB = 数据仓库，二者职责互补：PF 负责设计·采集·体验，BioDB 负责保存·管理·分析·可视化。
3. **全部 UI 统一于单一 nginx 入口**：`/`（日/中落地页）→ PF `/pf/`、BioDB `/WebUI/console`，共用一套暗色 + 绿色设计系统（`webui-theme/theme.css`，经 `/shared/` 分发）。
4. **开发状态**：D1~D4、D6~D8（PF 侧）与 WebUI 整合、控制台扩展均已完成原型实现，并有自动测试／E2E 执行记录；最新环境全链路复验、浏览器人工操作和真实数据综合确认尚未完成。
5. **未完成项目**：D5 真机联调（代码已完成）→ D9 流式推送 → D10 权限/审计；WebUI 还需完成 LAN HTTPS 与人工操作确认。
