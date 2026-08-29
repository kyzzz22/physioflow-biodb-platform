# D7 实现记录 — 分析管线

- **日期**：2026-08-29
- **仓库**：`kyzzz22/physioflow-app`（分支 `demo`，基于 D6 提交 `5a554cb`）
- **目标**：预处理（重采样/滤波/伪迹剔除）、特征（HRV/EDA/频谱）、统计/ML，消费 BioDB 读回，产出进会话包
- **BioDB 侧改动**：**无**（复用 `/sensor/data/features` 与 `/sensor/analysis/*`）

## 背景

D3 能读回数据、D6 能联合导出，但导出的仍是**原始时序**。研究者要自己写脚本才能算出心率变异性或频带功率。
D7 把「预处理 → 特征 → 统计/ML」做成 PF 内置管线，分析结果随导出包一起交付。

## 设计决策

### 1. 本地管线 + 服务端端点，两者并存
BioDB 已提供 `/sensor/data/features`（服务端特征）与 `/sensor/analysis/*`（kmeans/regression 训练预测）。
PF 侧**仍然实现完整本地管线**，因为：

- 本地会话未推送到 BioDB 时也要能分析
- 算法可离线验证、可单测
- 不把分析结果锁死在网络可用性上

两者在 e2e 中做了交叉校验（采样率一致），互为参照而非替代。

### 2. 零新增依赖
FFT（radix-2 Cooley-Tukey）、岭回归（Gauss-Jordan）、k-means、t 分布 p 值全部本地实现。
理由：PF 是前端项目，引入数值库会显著增加包体；且这些算法的正确性能被构造信号直接验证。

### 3. 缺失样本插值但不外推
导出的 CSV 里缺失留空（D6 的约定），但**分析前必须插值**——FFT 与 HRV 无法处理空洞。
折中：内部空隙线性插值，**首尾用最近观测值**（不外推生理信号），并在结果里记录 `missing` 与 `interpolatedFraction`。

### 4. 伪迹剔除用一阶差分，不用移动中位数残差
初版用「信号减移动中位数」的稳健 z 分数，测试暴露出严重问题：100 点里误剔 **39 个**正常点。
根因是移动中位数对任何弯曲信号都有系统性滞后残差，拿它当噪声尺度会把正常波动判成伪迹。
改用**一阶差分 + MAD**：脉冲在差分里是瞬态跳变，平滑信号则不是。修正后同一数据只剔除 3 个（脉冲位置及邻域），正常点原值保留。

### 5. 未知采样率时降级而非猜测
无法从时间线推出采样率时，仍产出时域统计，但**不出频谱与 HRV**，并在 `warnings` 里写明。
不填默认值——猜错的采样率会让所有频域结果静默失真。

## 实现

| 文件 | 说明 |
|---|---|
| `src/analysis/signal/preprocess.js` | 缺失填补、重采样、移动平均/中值、去趋势、伪迹剔除 |
| `src/analysis/signal/spectrum.js` | radix-2 FFT、周期图 PSD、频带功率（绝对+相对）、主频 |
| `src/analysis/signal/features.js` | 时域统计、峰值检测、RR 间期、HRV 时域/频域、EDA tonic/phasic 分解与 SCR |
| `src/analysis/signal/stats.js` | 描述统计、Pearson、Welch t 检验、Cohen's d、岭回归、k-means |
| `src/analysis/signal/pipeline.js` | 编排：通道识别 → 分析 → JSON/CSV 渲染 |
| `src/bioDBClient.js` | `fetchBioDBFeatures` / `trainBioDBModel` / `predictBioDB` / `listBioDBAnalyses` |
| `src/data/jointExport.js` | 联合导出附带 `analysis/`，并把管线警告上浮到 manifest |

### 通道识别

按通道 ID 与单位分派特征族，未识别的走通用时域统计（永远安全）：

| 族 | 触发 | 特征 |
|---|---|---|
| `cardiac` | `ecg`/`ekg`/`ppg`/`bvp`/`blood_volume` | HRV 时域（SDNN/RMSSD/pNN50/平均心率）+ 频域（VLF/LF/HF/LF-HF） |
| `eda` | `eda`/`gsr`/`electrodermal`，或单位 `uS` | tonic 水平、phasic 变异、SCR 次数与幅值 |
| `eeg` | `eeg`/`tp9`/`af7`/`af8`/`tp10`/`aux`，或单位 `uV` | 频带功率（含 EEG 五频段） |
| `generic` | 其余 | 均值/标准差/最值/RMS/分位数/主频 |

### 归档结构

```
analysis/analysis.json    完整结果（含 warnings）
analysis/analysis.csv     每通道一行，扁平化特征
```

## 验证

`node e2e-d7.mjs`（凭据走环境变量）全部 PASS。用**构造的已知信号**推送 → 读回 → 分析，验证数值是否恢复真值：

```
→ 300 samples/channel at 10 Hz (ecg, eda, eeg)
✓ run local analysis pipeline
   → sample rate 10 Hz, channels: ecg, eda, eeg
      ecg (cardiac): HR=60.0 bpm, RMSSD=0.0
      eda (eda):     tonic=2.16, SCR=3
      eeg (eeg):     peak=1.99 Hz
✓ server-side /data/features
   → server: 300 points @ 10 Hz
   → sample rates agree (local 10 vs server 10)
✓ train kmeans on BioDB      → model kmeans_42_..., inertia 64.69
✓ predict with the trained model
✓ train regression on BioDB
✓ list stored analyses       → 8 analysis record(s)
✓ local ridge regression recovers a known slope   → r2 1.000000
✓ local kmeans separates two planted clusters     → 2 clusters
✓ joint export carries the analysis               → 19 files, 3 channels
```

数值对照：构造 60 bpm 心律 → 测得 60.0 bpm；构造 3 次皮肤电导反应 → 检出 3 次；构造 2 Hz 正弦 → 测得 1.99 Hz（FFT 分辨率 0.039 Hz）。
岭回归恢复已知斜率 `1.5 + 3a - 2b`，r² = 1.000000。

单元测试 `tests/analysis-pipeline.test.js` **19 例** + `tests/joint-export.test.js` 增 2 例：

- 缺失填补（内部插值/首尾保持）、重采样长度比、移动中值抗脉冲、去趋势
- **伪迹剔除只命中脉冲、不动正常点**（回归测试，锁定上述修正）
- FFT 恢复纯音频率、拒绝非 2 的幂长度
- 峰值检测与 RR 间期恢复模拟心率；规则 vs 不规则心律的 RMSSD/SDNN 分离
- EDA 分离 tonic 与 SCR 计数；通道分派命中各特征族
- Pearson / Welch t / Cohen's d；岭回归恢复系数；k-means 确定性与分簇
- 管线读取 BioDB 列式形状、估计采样率、缺失上报、未知采样率降级、通道白名单
- 联合导出携带分析并上浮警告 / 未携带时如实记录

`npm run build` 通过；全量测试 285 项中 284 通过 / 0 失败 / 1 跳过；新增文件 lint 无告警。

## 过程中发现并修正：e2e 自己的物理错误

首轮 e2e 里我把 EEG 构造成 10 Hz alpha 波，但推送采样率是 10 Hz——**超过 5 Hz 奈奎斯特极限**，必然混叠。
实测报出 `peak=0.94 Hz`（混叠产物），而我的断言容差写成 ±5 Hz，把它放过了。

已修正：改用 2 Hz（采样率可表示），断言收紧到**两个 FFT 分辨率**（0.078 Hz）。修正后测得 1.99 Hz。

教训：宽松的容差会让错误的实现通过验证，等同于没有验证。

## 已知约束

- 服务端回归示例的 r² 很低（0.008），因为 e2e 用 `ecg/eeg/eda` 三个**本就无线性关系**的通道做演示，非缺陷。
- HRV 频域用 4 Hz 插值网格（HRV 分析惯例），短窗口（<4 个 RR 间期）不出频域结果。
- 峰值检测的自适应阈值按信号幅值的固定比例取，极端幅值漂移的信号可能需要调 `sensitivity`。
- 未做自动通道标注 UI——目前靠通道 ID/单位约定识别。
- 分析为全窗口一次性计算，未做滑窗/分段。

## 依赖

- D3（读回）/ D4（通道字典）/ D6（联合导出）— 前提，均已完成
- BioDB `/sensor/data/features` 与 `/sensor/analysis/*` — 前提，已完成

## 文件清单

| 文件（PF demo 分支） | 类型 |
|---|---|
| `src/analysis/signal/preprocess.js` | 新增 |
| `src/analysis/signal/spectrum.js` | 新增 |
| `src/analysis/signal/features.js` | 新增 |
| `src/analysis/signal/stats.js` | 新增 |
| `src/analysis/signal/pipeline.js` | 新增 |
| `src/bioDBClient.js` | 修改（4 个分析端点） |
| `src/data/jointExport.js` | 修改（附带分析） |
| `tests/analysis-pipeline.test.js` | 新增（19 例） |
| `tests/joint-export.test.js` | 修改（+2 例） |
| `e2e-d7.mjs` | 新增 |
