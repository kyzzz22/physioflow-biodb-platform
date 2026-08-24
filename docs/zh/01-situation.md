# 现状盘点与可借鉴（已有能力清单）

两个项目的现状盘点，分「可借鉴/直接复用」与「需改造」两类。按业务功能、技术架构、数据模型三维度。

## 1. PhysioFlow（PF）— 实验工作流

### 业务功能（可借鉴/直接复用）

| 能力 | 说明 | 复用方式 |
|---|---|---|
| 可视化协议设计 | 节点图（13+ 节点类型）、拖拽连线、分组、子流程、撤销/重做、画布交互（pan/zoom/多选/搜索/自动布局/流快照/小地图） | 直接复用（前端设计端） |
| PPT 式界面编辑器 | 参与者界面所见即所得编辑（元素库拖拽、属性面板、全屏节点编辑） | 直接复用 |
| 问卷设计器 | 9 题型 / 11 预设 / 条件跳过 / 确定性随机 / 逐题限时 / 计分输出 / CSV | 直接复用 |
| 认知任务运行器 | Stroop / Go/No-Go 真试次（RT/正确率/漏报/误报） | 直接复用 |
| 任务模板 | Emotion（SAM）/ Stroop / Go-No-Go | 直接复用（原型先行） |
| 确定性运行时 | 注入时钟/ID、暂停/恢复/重试/跳过、快照恢复、事件回放 | 直接复用（运行端） |
| 导出 | graph 数据包（events/responses/device_events JSONL+CSV）、BIDS v1.8.0、数据字典 | 直接复用（分析输入） |

### 技术架构（可借鉴）

| 能力 | 说明 |
|---|---|
| 单一事实来源（Protocol Graph） | 协议 schema + 不可变命令 + 冻结 hash，可复现 |
| 组件注册表 | 声明式组件（editorFields/ports/runtime.kind），可扩展 |
| Hosted 服务层 | 部署/launch token/bootstrap/HTTP API（架构参考，可对 BioDB 做适配） |
| 纯函数核心 | 大部分逻辑纯函数 + 严格测试门禁（208+ 测试） |
| 浏览器原生 | 压缩/Base64/流均浏览器能力 |

### 数据模型（可借鉴）

| 模型 | 说明 |
|---|---|
| 协议 schema | protocolId（= 实验ID）、节点/边/分组/变量/问卷/设备连接器 |
| 运行时事件 envelope | protocolId/sequence/时间三时钟/节点/组件 |
| 设备事件 envelope | connector/device/时间/采样（Phase 1 已采集） |
| 数据契约 v2 | events/responses/device_events JSONL+CSV + 数据字典 |

### 需改造（对整合）

| 项 | 说明 |
|---|---|
| 实验ID 显式化 | `protocolId` 是实验ID，但需映射到 BioDB `experiment` tag / 语义名 |
| BioDB 客户端 | Phase 1 已实现 `src/biodb/`（推送、JWT、容器） |

## 2. BioDB — 生体数据仓库

### 业务功能（可借鉴）

| 能力 | 说明 | 复用方式 |
|---|---|---|
| 传感器数据入库 | `/sensor/data/write`（容器：format/compression/data），VictoriaMetrics 时序 | 直接复用（存储端） |
| 数据读取 | `/sensor/data/read`（rows/时间窗），读回列主序 | 直接复用（分析取数） |
| 事件管理 | `/event/events` CRUD（协作者/实验者双视角） | 直接复用（管理端） |
| 用户/权限 | PostgreSQL + 长期 token → JWT（scope/时间窗） | 直接复用（认证） |
| WebUI/可视化客户端 | 用户/协作者/长期 token 管理 UI；util 实时/历史曲线、情感地图 | 部分可移植（Phase 3） |

### 技术架构（可借鉴）

| 能力 | 说明 |
|---|---|
| 三 DB 分层 | 时序（VictoriaMetrics）/ 半结构化（MongoDB）/ 结构化（PostgreSQL） |
| nginx 反代 + 多 API 服务 | `/auth` `/sensor` `/event` 独立服务，docker compose 一键部署 |
| JWT 认证模型 | 长期 token → 短命用途 JWT（sensor_read/write/event，时间窗 claim） |
| CORS 全开 | 浏览器可直接跨域（Phase 1 已验证，无代理） |

### 数据模型（可借鉴）

| 模型 | 说明 |
|---|---|
| 时序系列 | `biodb_<column>`，tag `participant` + `experimenter`，时间戳纳秒 |
| 事件 | Mongo `user_id`（=协作者）/ `created_by`（=实验者）/ 时间 / details |
| 标识 | 用户/协作者 21 位 ID（nanoid） |

### 需改造（对整合）

| 项 | 说明 |
|---|---|
| **experiment tag 维度** | 时序缺「实验」维度（会议核心问题）——`p_victoria_metrics.py` 的 `tag_columns` 加 `experiment` |
| 条件/实验元数据 | 实验条件（刺激集等）目前无结构化存储（决定用 PF 协议承载） |
| 分析/ML/可视化 | BioDB 无分析管线、无完整可视化（Phase 3 在 PF 侧或新模块做） |

## 3. 已整合部分（Phase 1，可借鉴）

| 能力 | 说明 |
|---|---|
| `src/biodb/` | PF→BioDB 推送（容器编解码、BioDbClient、JWT 缓存/刷新、pushSession） |
| `src/runtime/deviceRuntime.js` | 设备采样器（drift-corrected，按 sampleRateHz） |
| 运行时设备采集 | `device_events` 采集 + 本地导出（jsonl/csv）+ 完成屏 BioDB 导出按钮 |
| `protocol.biodb` | 协议内实验配置（enabled/participantId） |
