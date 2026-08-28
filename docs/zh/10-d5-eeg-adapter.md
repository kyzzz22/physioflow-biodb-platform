# D5 实现记录 — 真实脑波设备 adapter（Muse EEG）

- **日期**：2026-08-28
- **仓库**：`kyzzz22/physioflow-app`（分支 `demo`，基于 D4 提交 `2a8b68c`）
- **目标**：接入真实脑波设备（InteraXon Muse）作为 device connector，让 EEG 通道与既有会话/导出/推送链路打通
- **BioDB 侧改动**：**无**

> ⚠️ **重要：本项尚未用真实硬件验证。** 协议解码依据公开的开源实现编写并用构造字节做了单元验证，但仓库开发环境中没有 Muse 设备，因此「真实设备落库」这一验收项（M2）**未完成**，需在拿到设备后按本文末尾的清单复验。

## 设计决策

### 1. 传输层与适配器分离
适配器是**纯协议逻辑**，只通过注入的 `transport` 接触平台 API：

```
connect(options) -> deviceDescriptor
getCharacteristic(uuid) -> handle
subscribe(handle, handler)     handler 收到 DataView
write(handle, bytes)
disconnect()
```

好处：协议解码可在 Node 中测试（无需无线电）；桌面端可换用原生后端。

### 2. 为什么默认实现是 Web Bluetooth，以及它在哪里不可用
PF 有三种运行形态，`navigator.bluetooth` 的可用性不同：

| 运行形态 | 命令 | Web Bluetooth |
|---|---|---|
| 浏览器开发 | `npm run dev` | ✅（Chromium 系：Chrome / Edge） |
| 托管服务 | `npm run hosted:serve` | ✅（同上，需 HTTPS 或 localhost） |
| **Tauri 桌面** | `npm run desktop:dev` | ❌ WebView2 不暴露该 API |

因此 `supportsWebBluetooth()` 在桌面端返回 `false`，适配器会抛出明确错误而不是静默失败。桌面端如需 BLE，应注入一个基于原生插件的 transport（如 `tauri-plugin-web-bluetooth-api`，底层 btleplug），**本项未引入该 Rust 依赖**——它会改变构建链路与依赖树，属于独立决策。传输层接口已为此预留。

### 3. 通知流 → 采样队列
Muse 是**推送**（BLE notification，每 46.9 ms 一包 12 点/通道），而 `DeviceConnectorSession` 的契约是**拉取**（`read(channelId)`）。适配器为每个电极维护一个**有界队列**，`read()` 弹出最旧样本。队列上限 4096（@256 Hz ≈ 16 s/通道），超出时丢弃最旧样本——采样器慢于设备时不会无限占用内存。

### 4. 时间戳重建
设备不上报时钟，只有 uint16 包序号。沿用 muse-js 的算法：由序号增量 × 包时长推导，并处理 16 位回绕。样本时间戳 = 包时间戳 + 采样点序号 × (1000/256) ms。

### 5. 明确排除 Athena 固件
Muse S Athena（Gen 3, MS_03）把所有传感器复用到单一特征 `273e0013`，采用 14-bit LSB-first 打包与未公开的 `dc001` 双次握手，与 Classic 完全不同。适配器**检测该特征并直接失败**，而不是猜测解码——避免产出看似正常实则错误的 EEG 数值。

## 实现

| 文件 | 说明 |
|---|---|
| `src/devices/museProtocol.js` | 协议常量与纯解码函数（无平台依赖） |
| `src/devices/transports/webBluetooth.js` | Web Bluetooth 传输实现 + 环境检测 |
| `src/devices/museConnector.js` | 连接器描述符 + 适配器（队列/时间戳/命令序列） |
| `src/devices/index.js` | 导出 Muse 连接器、适配器与传输层 |
| `src/GraphRuntimeRunnerPage.jsx` | 运行时按 `transport` 选择适配器（原先仅支持 `simulated`） |
| `tests/muse-connector.test.js` | 单元测试 12 例 |

### 连接器通道

| 通道 | 方向 | 类型 | 单位 | 采样率 |
|---|---|---|---|---|
| `TP9` / `AF7` / `AF8` / `TP10` | input | number | `uV` | 256 Hz |
| `marker` | output | string | — | — |

单位写成 `uV` 而非 µV，避免非 ASCII 字符在 JSON/CSV 中的编码差异。`includeAux` 选项可追加 `AUX` 电极。

### 协议要点（Classic 固件）

- 服务 UUID：`0xfe8d`
- EEG 特征：`273e0003`（TP9）/ `0004`（AF7）/ `0005`（AF8）/ `0006`（TP10）/ `0007`（AUX），命名空间 `-4c4d-454d-96be-f03bac821358`
- EEG 通知布局：**uint16 包序号（大端）+ 18 字节载荷**；载荷为 12 个 12-bit 大端打包样本（每 3 字节 2 个样本）
- 微伏换算：`uV = 0.48828125 * (raw - 0x800)`（12-bit ADC，中心 2048）
- 控制命令为长度前缀帧：`[len, ...ASCII, '\n']`；启动序列 `h` → `p21`（纯 EEG，含 AUX 时 `p20`）→ `s` → `d`
- 已实现但未接入采样器的解码：PPG（24-bit，64 Hz）、加速度/陀螺仪（52 Hz，3 点/包）、遥测（电量/电压/温度）

**来源**：解码与常量对照 muse-js（`urish/muse-js`，MIT）的实现与 muse-rs 的协议常量，两者对 12-bit ADC 中心值（2048）与标度（0.48828125 µV/LSB）的描述一致。

## 验证

`tests/muse-connector.test.js`（12 例，全部通过）：

- 12-bit 打包/解包往返（构造字节，覆盖 `0x000`/`0x800`/`0xfff` 边界）
- 微伏换算围绕 `0x800` 中点
- EEG 通知的序号与样本数
- 遥测 / 加速度 / 陀螺仪解码与标度
- 控制命令帧编解码（`d` → `[0x02, 0x64, 0x0a]`）
- 连接器定义通过 `validateDeviceConnector`
- 通知样本经 `read()` 按序取出；队列空时报错
- 启动命令序列为 `['h','p21','s','d']`
- 检测到 Athena 特征时拒绝连接
- marker 本地记录（设备无硬件 marker 输入）
- 队列有界（上限 8 时只保留 8 个）
- **D5→D4 联动**：安装 Muse 连接器后，`channelDataDictionary()` 正确产出 4 个 EEG 通道（`uV` / 256 Hz），`dictionaryPayload()` 可直接推送到 BioDB

`npm run build` 通过；全量测试 257 项中 256 通过 / 0 失败 / 1 跳过。新增文件的 lint 无告警（`bioDBClient.js` 的 `btoa`/`Buffer` 报错为 D2/D3 既有问题，未改动）。

## 拿到设备后的待办（未完成）

1. 用 Chromium 浏览器打开参与者运行页，在协议中安装 Muse 连接器并运行，确认能扫描并连接。
2. 比对解码量级：静息闭眼时 `AF7`/`AF8` 应见 ~10 Hz α 节律，幅值应在数十 µV 量级；若整体偏移 ~725 µV 说明中点处理有误。
3. 确认 4 通道无串扰（各电极独立队列）。
4. 走通一次完整会话：采集 → 导出（`channel_dictionary.json` 含 4 个 `uV` 通道）→ 推送 BioDB（字典写入实验）。
5. 桌面端如需 BLE，评估引入原生插件 transport。

## 已知约束

- 未做真实硬件验证（见开头警示）。
- 桌面端（Tauri）暂不可用，需浏览器形态或注入原生 transport。
- 不支持 Athena（Gen 3）固件。
- `read()` 在队列为空时抛错；采样器以 256 Hz 驱动，与设备产出速率匹配，但启动后首包到达前会有短暂报错。
- marker 仅本地记录，未写入设备。

## 文件清单

| 文件（PF demo 分支） | 类型 |
|---|---|
| `src/devices/museProtocol.js` | 新增 |
| `src/devices/transports/webBluetooth.js` | 新增 |
| `src/devices/museConnector.js` | 新增 |
| `src/devices/index.js` | 修改（导出） |
| `src/GraphRuntimeRunnerPage.jsx` | 修改（按 transport 选择适配器） |
| `tests/muse-connector.test.js` | 新增（12 例） |
