# D8 实现记录 — 可视化

- **日期**：2026-08-29
- **仓库**：`kyzzz22/physioflow-app`（分支 `demo`，基于 D7 提交 `b1e2267`）
- **目标**：历史多列曲线、实时模式、情感地图，消费 D3 读回与 D7 分析结果
- **BioDB 侧改动**：**无**

## 背景

D3 能读回数据、D7 能算出特征，但读回面板只有一张单通道简图，D7 的结果更是只能看 JSON。
D8 补上呈现层：多通道叠加曲线、实时窗口、情感地图，以及 D7 特征的图形化。

## 设计决策

### 1. 几何计算与渲染分离
所有坐标映射、降采样、刻度、路径生成都在 `chartGeometry.js` 里做成**纯函数**，组件只负责把它返回的东西画出来。
好处与 D7 一致：**图表数学可在 Node 里单测**，不需要 DOM。这是本次能验证「路径无 NaN」「标记落在绘图区内」的前提。

### 2. SVG 而非 Canvas
既有的 `analysis/charts.js` 用 Canvas 2D（柱状图/散点图）。D8 新增部分改用 SVG：

- 路径是字符串，可断言、可快照
- 浏览器原生缩放，高分屏不失真
- 事件标记、悬停圆点可直接挂 DOM 事件

Canvas 的既有图表保持不动（它们工作正常，重写无收益）。

### 3. min/max 降采样，而不是抽稀或平均
256 Hz 下五分钟 EEG 是 76,800 点，塞进约 600 像素——全画既慢又误导。
按像素分桶、**每桶保留 min 与 max**，保留视觉包络（尖峰不会被平均掉），这正是眼睛实际读取的信息。

### 4. 缺失处断线，不画成零
`seriesPath` 遇到 null 会断开子路径（生成新的 `M` 命令），而不是连成一条掉到零点的线。
D6 已确立「缺失留空不填零」的约定，可视化必须遵守——画成零会让数据缺失伪装成测到零。

### 5. 实时模式用 rAF 节流，数据源由调用方注入
256 Hz 下「每个样本渲染一次」会饿死主线程，所以用 `requestAnimationFrame` 逐帧拉取。
D9（流式推送）尚未完成，设备运行时不会把数据推给这个面板，因此 `sampleSource` 设计成**由调用方注入**；
没有数据源时组件仍能渲染传入的 `samples`（可用于回放录制会话）。

## 实现

| 文件 | 说明 |
|---|---|
| `src/analysis/chartGeometry.js` | 纯几何：min/max 降采样、坐标映射与逆映射、nice 刻度、路径/面积路径、事件标记吸附、情感坐标 |
| `src/analysis/MultiChannelChart.jsx` | 历史多列曲线：多通道叠加、事件标记、悬停读数、拖拽缩放 |
| `src/analysis/LiveChart.jsx` | 实时窗口：滑动缓冲、rAF 拉取、暂停/继续 |
| `src/analysis/FeaturePanel.jsx` | D7 结果可视化：指标块、频带堆叠条、HRV、EDA |
| `src/analysis/AffectMap.jsx` | 情感地图：效价-唤醒环格、象限着色与计数、轨迹连线 |
| `src/DataPanel.jsx` | 接入四个视图（单通道 / 全部通道 / 特征 / 情感地图） |
| `src/questionnaire.css` | D8 样式（含深色模式） |

### 视图切换

D3 的数据面板新增四视图，默认「全部通道」：

| 视图 | 数据源 |
|---|---|
| Single series | 单通道（D3 既有简图） |
| All channels | BioDB 读回 + 事件列表叠加 |
| Features | D7 管线对当前窗口的分析结果 |
| Affect map | 事件中的效价/唤醒（若研究记录了它们） |

## 验证

`node e2e-d8.mjs`（凭据走环境变量）全部 PASS。用**真实读回数据**（推送 → 读回，含 VictoriaMetrics 可见性重试）而非 mock：

```
→ 200 samples/channel at 10 Hz (eeg, eda, ecg)
✓ read session back
✓ geometry: every channel produces a finite SVG path
✓ geometry: decimation bounds the point count
✓ geometry: event markers land inside the plot
✓ render: MultiChannelChart emits an SVG with one path per channel
✓ D7 pipeline over the read-back window
✓ render: FeaturePanel shows the analysed channels
✓ render: AffectMap plots valence/arousal points
✓ render: empty inputs degrade to a message, not a crash
✓ data panel exposes the D8 views
```

组件经 Vite SSR 加载器渲染为静态标记（Node 无法直接加载 `.jsx`），断言 SVG 元素数量、事件标签存在、且**渲染结果不含 NaN/Infinity**。

单元测试 `tests/visualization.test.js` **19 例**：

- 降采样保留尖峰包络、输出索引单调、小序列原样通过
- 极值忽略 null；**平序列给出对称带**而非零高度图
- 坐标映射末端贴合右边界、逆映射往返一致
- nice 刻度取整步长、退化范围回退
- **数据空洞断开路径**（断言出现两个 `M` 命令）且不含 NaN
- 事件标记吸附到最近样本、窗口外事件被丢弃
- 情感坐标 SAM 1..9 → -1..1 换算；象限命名符合环格约定
- **D7 结果承载 FeaturePanel 读取的全部字段**（防重命名回归）

`npm run build` 通过；全量测试 304 项中 303 通过 / 0 失败 / 1 跳过；新增文件 lint 无告警。

## 过程中发现并修正的两个真实缺陷

**1. 时区 bug（轴标签随查看者位置变化）**

`formatAxisTime` 用了 `getHours()` 等**本地时区**方法。BioDB 存的是 UTC，于是同一条记录在北京显示 `19:20:30`、在伦敦显示 `11:20:30`——跨地区团队的截图与导出无法对齐。
已改用 `getUTCHours()` 等 UTC 方法，并在注释里写明原因。测试名即 `locale-independent`。

**2. 归一化语义与注释不符（会让小量纲通道被压扁）**

`normalizeSeries` 的注释写「每个通道保持自己的尺度」，实现却用了**全局 extent**。这并非小事：EDA 是 2 µS 量级、EEG 是数十 µV，全局归一化会把量纲小的通道压成一条直线。
已改为**每通道独立归一化**，并加了针对性回归测试（断言 EDA 与 EEG 各自仍占满全高）。

两处都是测试逼出来的——先写断言、再看实现是否配得上注释，是这个流程的价值所在。

## 已知约束

- **实时模式尚未接真实设备流**：数据源需调用方注入，D9 完成后才能直连设备运行时。
- 情感地图依赖事件中记录 valence/arousal；研究未采集时该视图为空（组件有空状态提示，非缺陷）。
- 多通道叠加时各通道独立缩放，幅值**不可跨通道比较**（UI 通过图例标注单位提示，但未做显式警示条）。
- 拖拽缩放为一次性框选，不支持平移与多级缩放栈（仅可 Reset）。
- 未做大规模数据（>10 万点）的性能基准，仅有降采样预算保护。

## 依赖

- D3（读回与事件）/ D7（分析结果）— 前提，均已完成
- D9（流式推送）— 实时模式的完整形态需它；当前可回放录制数据

## 文件清单

| 文件（PF demo 分支） | 类型 |
|---|---|
| `src/analysis/chartGeometry.js` | 新增 |
| `src/analysis/MultiChannelChart.jsx` | 新增 |
| `src/analysis/LiveChart.jsx` | 新增 |
| `src/analysis/FeaturePanel.jsx` | 新增 |
| `src/analysis/AffectMap.jsx` | 新增 |
| `src/DataPanel.jsx` | 修改（四视图接入） |
| `src/questionnaire.css` | 修改（D8 样式） |
| `tests/visualization.test.js` | 新增（19 例） |
| `e2e-d8.mjs` | 新增 |
