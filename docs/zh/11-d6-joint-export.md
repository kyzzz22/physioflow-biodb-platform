# D6 实现记录 — 联合导出 / 归档

- **日期**：2026-08-29
- **仓库**：`kyzzz22/physioflow-app`（分支 `demo`，基于 D5 提交 `4238414`）
- **目标**：把 PF 会话包（协议 + 事件 + 设备事件）与 BioDB 导出信封（时序 + 事件 + 实验元数据）合并为单一归档包
- **BioDB 侧改动**：**无**（复用 `POST /sensor/data/export`）

## 背景

D2/D3 打通了写入与读回，但采集端（PF）与数据平台（BioDB）的导出仍是**两个独立产物**：
PF 导出的是协议与行为事件，BioDB 导出的是生理时序。做分析时需要在两个包之间手工对齐参与者与时间窗。
D6 把两者合并为一个自包含归档。

## 设计决策

### 1. PF 腿优先，BioDB 腿尽力而为
PF 会话包是**采集现场的第一手记录**，即使 BioDB 不可达（网络故障、凭据缺失、实验未注册）也必须能导出。
因此：BioDB 腿失败时归档**照常生成**，只在 `joint_manifest.json` 里记录失败原因。绝不让网络问题阻断现场数据的导出。

### 2. PF 文件保持在顶层
合并包的 PF 部分**原样放在根目录**（`events.csv`、`channel_dictionary.json`、`export_manifest.json` …），
BioDB 部分统一放在 `biodb/` 下。既有分析脚本无需改路径就能继续工作。

### 3. 缺失样本留空，不填零
BioDB 返回的是列式数据 `{ time: [...], channel: [...] }`，缺失位置为 `null`。
转 CSV 时保留空单元格——填 0 会让「数据缺失」伪装成「测到 0」，这在生理信号里是完全不同的含义。

### 4. 优先用连接器声明的通道，回退到事件载荷
导出时向 BioDB 请求的通道列表优先取 D4 的 `channelDataDictionary(protocol).inputChannels`
（连接器声明的权威清单）；协议里没有连接器时，才从设备事件载荷里推断数值型键。

### 5. 时间窗以 BioDB 为权威
PF 与 BioDB 的 `started_at` / `sensorStart` 都记录在 manifest 里，但**时序窗口以 BioDB 实际返回为准**——
因为那是服务端真正接受的数据范围。

## 实现

| 文件 | 说明 |
|---|---|
| `src/data/jointExport.js` | 合并逻辑（新增） |
| `src/bioDBClient.js` | 新增 `exportBioDBData()`（三条腿一次调用） |
| `src/SessionManager.jsx` | 「Joint export (BioDB)」按钮与状态提示 |
| `tests/joint-export.test.js` | 单元测试 7 例 |
| `e2e-d6.mjs` | 端到端验证 |

### 归档结构

```
joint_manifest.json           来源、时间窗、各腿状态与条数、警告
joint_data_dictionary.json    新增字段的说明
<PF 会话文件>                  顶层，原样保留
biodb/sensor_data.csv         BioDB 时序（列式摊平为行）
biodb/sensor_data.json        BioDB 原始返回载荷
biodb/events.json             窗口内事件
biodb/experiment.json         实验注册元数据（含 D4 通道字典）
```

## 验证

`node e2e-d6.mjs`（凭据通过环境变量注入）全部 PASS：

```
→ channels: signal
✓ admin JWT / experiment list      → experiment: 595a3982-...
✓ push device samples to BioDB     → 20 rows pushed
✓ attach channel dictionary
… waiting for VictoriaMetrics visibility (attempt 2/3)
✓ export BioDB envelope (sensor/events/experiment)
  → sensor: 20 points, columns signal
  → events: 0, experiment: 595a3982-...
✓ build joint export package       → 17 files; sensor CSV 20 rows, header "time,signal"
✓ PF-only archive when the BioDB leg fails
```

单元测试 7 例：列式摊平（缺失留空）、空载荷只出表头、通道来源与回退、双腿合并的来源记录、
BioDB 腿失败仍归档 PF、空/无实验时的显式警告、联合数据字典。

`npm run build` 通过；全量测试 264 项中 263 通过 / 0 失败 / 1 跳过；新增文件 lint 无告警。

## 过程中发现：VictoriaMetrics 的写入可见性延迟

首次 e2e 推送 20 点后立即导出，返回 **0 点**；几分钟后手工重跑诊断脚本却读到 20 点。
对照实验确认接口本身正常（无过滤 40 点 / 带实验过滤 20 点），真正原因是
**写入到可查询存在约 6 秒延迟**（e2e 需重试到第 3 次）。

影响与处理：

- **e2e**：加入重试等待（最多 6 次、间隔 3 秒），不对最终一致的读做即时断言。
- **产品**：这是真实的用户场景——推送完立刻导出会拿到空数据。因此 manifest 警告与 UI 提示
  都明确写出「若刚推送，请稍等几秒再导出」，而不是含糊地报「没有数据」。

> 附带确认：`export` 与 `read` 走的是**不同代码路径**（export 走分块 `victoria_metrics_export_and_format_data`，
> read 走非分块查询）。两者在本次验证中结果一致。

## 已知约束

- 归档为**单次快照**，不做增量；重复导出会重复包含全部数据。
- 多实验共用同名通道时，BioDB 返回的列名带 `@<experiment_id>` 后缀，摊平后列名即含该后缀。
- `events` 腿依赖 BioDB 事件库；本次 e2e 窗口内无事件（只推了样本），故为 0——属预期，非缺陷。
- 未实现自动重试的用户界面（当前靠提示引导手动重导）。
- 归档未按参与者/实验做目录分层（当前由下载文件名区分）。

## 依赖

- D2（写入链路）/ D3（读回）/ D4（通道字典）— 前提，均已完成
- BioDB `/sensor/data/export` — 前提，已完成

## 文件清单

| 文件（PF demo 分支） | 类型 |
|---|---|
| `src/data/jointExport.js` | 新增 |
| `src/bioDBClient.js` | 修改（`exportBioDBData`） |
| `src/SessionManager.jsx` | 修改（联合导出入口） |
| `tests/joint-export.test.js` | 新增（7 例） |
| `e2e-d6.mjs` | 新增 |
