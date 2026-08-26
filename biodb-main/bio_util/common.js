/**
 * BioDB util 可视化共享逻辑
 * - 长期 token → sensor_read JWT 获取
 * - sensor 数据读回
 * - Canvas 曲线绘图工具
 * 所有 API 均经 nginx 同源代理（/auth、/sensor）。
 */
"use strict";

const Util = {
  apiBase: "", // 同源经 nginx 代理

  /** 从 localStorage 读取/保存配置 */
  loadConfig() {
    try {
      return JSON.parse(localStorage.getItem("biodb_util_config") || "{}");
    } catch (e) {
      return {};
    }
  },
  saveConfig(cfg) {
    localStorage.setItem("biodb_util_config", JSON.stringify(cfg));
  },

  /**
   * 渲染共享凭据/时间窗表单（注入到 #config-form 容器）。
   * 表单字段：user_id / token / participant_id / experiment_id(可选) / start / end / channels
   * 返回一个 getter 函数，读取当前表单值。
   */
  renderConfigForm(extraFields = "") {
    const cfg = this.loadConfig();
    const container = document.getElementById("config-form");
    if (!container) return () => ({});

    const val = (k, def) => (cfg[k] !== undefined && cfg[k] !== "" ? cfg[k] : def);

    container.innerHTML = `
      <div class="grid">
        <div class="field">
          <label>user_id（长期 token 用户名）</label>
          <input id="cfg-user_id" value="${val("user_id", "")}" placeholder="WebUI token-list 中的 user_id">
        </div>
        <div class="field">
          <label>长期 token</label>
          <input id="cfg-token" type="password" value="${val("token", "")}" placeholder="43~44 位字符">
        </div>
        <div class="field">
          <label>participant_id</label>
          <input id="cfg-participant_id" value="${val("participant_id", "")}" placeholder="21 位参与者 ID">
        </div>
        <div class="field">
          <label>experiment_id（可选）</label>
          <input id="cfg-experiment_id" value="${val("experiment_id", "")}" placeholder="实验注册表 ID">
        </div>
        <div class="field">
          <label>开始时间</label>
          <input id="cfg-start" type="datetime-local" value="${val("start", "")}">
        </div>
        <div class="field">
          <label>结束时间</label>
          <input id="cfg-end" type="datetime-local" value="${val("end", "")}">
        </div>
        <div class="field" style="grid-column: span 2;">
          <label>通道（逗号分隔的传感器字段名）</label>
          <input id="cfg-channels" value="${val("channels", "")}" placeholder="例如: eda, hr, eeg_alpha">
        </div>
        ${extraFields}
      </div>
      <div class="row" style="margin-top: 12px;">
        <button id="cfg-save">保存配置</button>
        <button id="cfg-clear" class="secondary">清空</button>
      </div>
    `;

    document.getElementById("cfg-save").addEventListener("click", () => {
      const form = this.collectConfigForm();
      this.saveConfig(form);
      this.showStatus("配置已保存到 localStorage", "info");
    });
    document.getElementById("cfg-clear").addEventListener("click", () => {
      localStorage.removeItem("biodb_util_config");
      location.reload();
    });

    return () => this.collectConfigForm();
  },

  /** 读取当前表单值 */
  collectConfigForm() {
    const g = (id) => {
      const el = document.getElementById(id);
      return el ? el.value.trim() : "";
    };
    return {
      user_id: g("cfg-user_id"),
      token: g("cfg-token"),
      participant_id: g("cfg-participant_id"),
      experiment_id: g("cfg-experiment_id"),
      start: g("cfg-start"),
      end: g("cfg-end"),
      channels: g("cfg-channels"),
    };
  },

  showStatus(msg, type = "info") {
    let el = document.getElementById("status");
    if (!el) {
      el = document.createElement("div");
      el.id = "status";
      el.className = "status";
      document.body.appendChild(el);
    }
    el.className = "status " + type;
    el.textContent = msg;
  },

  /** 获取 sensor_read JWT（长期 token 换取） */
  async getReadJwt({ user_id, token, participant_id, start_time, end_time, experiment_id }) {
    const body = {
      user_id,
      token,
      participant_id,
      start_time,
      end_time,
    };
    if (experiment_id) body.experiment_id = experiment_id;
    const resp = await fetch(`${this.apiBase}/auth/jwt/sensors/readjwt`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await resp.json();
    if (!resp.ok || !data.jwt) {
      throw new Error(data.message || `JWT 获取失败 (HTTP ${resp.status})`);
    }
    return data.jwt;
  },

  /** 读回传感器数据（统一信封：compression/format/data base64） */
  async readData(jwt, { rows, start_time, end_time, chunk_seconds }) {
    const payload = {
      compression: "none",
      format: "json",
      rows,
      start_time,
      end_time,
    };
    if (chunk_seconds) payload.chunk_seconds = chunk_seconds;
    const resp = await fetch(`${this.apiBase}/sensor/data/read`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + jwt,
      },
      body: JSON.stringify(payload),
    });
    const data = await resp.json();
    if (!resp.ok) {
      throw new Error(data.detail || `读回失败 (HTTP ${resp.status})`);
    }
    // data 形如 {compression, format, data: base64(json)}
    const jsonStr = atob(data.data);
    return JSON.parse(jsonStr);
  },

  /** 联合导出（时序+事件+实验元数据） */
  async exportData(jwt, { rows, start_time, end_time, experiment_id, include_events, include_experiment }) {
    const payload = {
      compression: "none",
      format: "json",
      rows,
      start_time,
      end_time,
      include_events: include_events !== false,
      include_experiment: include_experiment !== false,
    };
    if (experiment_id) payload.experiment_id = experiment_id;
    const resp = await fetch(`${this.apiBase}/sensor/data/export`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + jwt,
      },
      body: JSON.stringify(payload),
    });
    const data = await resp.json();
    if (!resp.ok) {
      throw new Error(data.detail || `导出失败 (HTTP ${resp.status})`);
    }
    return data;
  },

  /** 特征统计 */
  async features(jwt, { rows, start_time, end_time }) {
    const payload = { compression: "none", format: "json", rows, start_time, end_time };
    const resp = await fetch(`${this.apiBase}/sensor/data/features`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: "Bearer " + jwt },
      body: JSON.stringify(payload),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || `特征统计失败 (HTTP ${resp.status})`);
    return data.features;
  },

  /**
   * 在 canvas 上绘制多通道时间序列曲线。
   * @param {HTMLCanvasElement} canvas
   * @param {object} result  {time: [...], [channel]: [...]}
   * @param {object} opts {channels: [names], colors: {}, height, title}
   */
  drawSeries(canvas, result, opts = {}) {
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.parentElement ? canvas.parentElement.getBoundingClientRect() : { width: 800 };
    const width = opts.width || Math.max(rect.width - 24, 400);
    const height = opts.height || 300;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = width + "px";
    canvas.style.height = height + "px";
    const ctx = canvas.getContext("2d");
    ctx.scale(dpr, dpr);

    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = "#fafafa";
    ctx.fillRect(0, 0, width, height);

    const timeStrs = result.time || [];
    const channels = opts.channels || Object.keys(result).filter((k) => k !== "time");
    if (!timeStrs.length || !channels.length) {
      ctx.fillStyle = "#888";
      ctx.font = "14px sans-serif";
      ctx.fillText("（无数据）", 16, height / 2);
      return;
    }

    const margin = { top: 16, right: 16, bottom: 28, left: 56 };
    const plotW = width - margin.left - margin.right;
    const plotH = height - margin.top - margin.bottom;

    // X 轴：时间
    const t0 = new Date(timeStrs[0]).getTime();
    const t1 = new Date(timeStrs[timeStrs.length - 1]).getTime();
    const xOf = (t) => margin.left + ((t - t0) / (t1 - t0 || 1)) * plotW;

    // Y 轴范围（按通道分别归一化，重叠绘制便于观察）
    ctx.strokeStyle = "#ddd";
    ctx.beginPath();
    for (let i = 0; i <= 4; i++) {
      const y = margin.top + (i / 4) * plotH;
      ctx.moveTo(margin.left, y);
      ctx.lineTo(width - margin.right, y);
    }
    ctx.stroke();

    // X 轴刻度（5 个时间标签）
    ctx.fillStyle = "#666";
    ctx.font = "11px sans-serif";
    ctx.textAlign = "center";
    for (let i = 0; i <= 4; i++) {
      const t = t0 + ((t1 - t0) / 4) * i;
      const d = new Date(t);
      const label = `${d.getHours()}:${String(d.getMinutes()).padStart(2, "0")}:${String(d.getSeconds()).padStart(2, "0")}`;
      ctx.fillText(label, xOf(t), height - 8);
    }

    // 每条通道一条子带
    const bandH = plotH / channels.length;
    const colors = opts.colors || {};
    const palette = ["#2563eb", "#dc2626", "#16a34a", "#d97706", "#7c3aed", "#0891b2", "#db2777", "#65a30d"];

    channels.forEach((ch, ci) => {
      const values = result[ch] || [];
      if (!values.length) return;
      const nums = values.map((v) => (v === null || v === undefined ? NaN : Number(v)));
      const finite = nums.filter((v) => !isNaN(v));
      if (!finite.length) return;
      const vMin = Math.min(...finite);
      const vMax = Math.max(...finite);
      const vSpan = vMax - vMin || 1;

      const bandTop = margin.top + ci * bandH;
      const color = colors[ch] || palette[ci % palette.length];

      ctx.strokeStyle = color;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      nums.forEach((v, i) => {
        const x = xOf(new Date(timeStrs[i]).getTime());
        const y = isNaN(v) ? null : bandTop + bandH / 2 - ((v - vMin) / vSpan - 0.5) * bandH * 0.9;
        if (y === null) return;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();

      // 通道名 + 数值范围
      ctx.fillStyle = color;
      ctx.font = "bold 12px sans-serif";
      ctx.textAlign = "left";
      ctx.fillText(ch, margin.left + 4, bandTop + 14);
      ctx.font = "10px sans-serif";
      ctx.fillStyle = "#888";
      ctx.fillText(
        `min=${vMin.toFixed(2)}  max=${vMax.toFixed(2)}  n=${values.length}`,
        margin.left + 4,
        bandTop + bandH - 6
      );
    });

    if (opts.title) {
      ctx.fillStyle = "#333";
      ctx.font = "bold 13px sans-serif";
      ctx.textAlign = "left";
      ctx.fillText(opts.title, 8, 12);
    }
  },

  /**
   * 绘制多通道时序曲线并叠加事件标记（垂直虚线 + 标签）。
   * 事件字段兼容：time/start_time、type、name、experiment_id、detail/data。
   */
  drawSeriesWithEvents(canvas, result, events, opts = {}) {
    this.drawSeries(canvas, result, opts);
    if (!events || !events.length) return;
    const timeStrs = result.time || [];
    if (!timeStrs.length) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.parentElement ? canvas.parentElement.getBoundingClientRect() : { width: 800 };
    const width = opts.width || Math.max(rect.width - 24, 400);
    const height = opts.height || 300;
    const ctx = canvas.getContext("2d");
    // drawSeries 已 scale(dpr) 并设置了 canvas 尺寸，此处仅叠加绘制，不再重复 scale

    const margin = { top: 16, right: 16, bottom: 28, left: 56 };
    const plotW = width - margin.left - margin.right;
    const plotH = height - margin.top - margin.bottom;
    const t0 = new Date(timeStrs[0]).getTime();
    const t1 = new Date(timeStrs[timeStrs.length - 1]).getTime();
    const xOf = (t) => margin.left + ((t - t0) / (t1 - t0 || 1)) * plotW;

    const eventColors = {
      start: "#16a34a",
      end: "#dc2626",
      marker: "#d97706",
      note: "#7c3aed",
    };

    events.forEach((ev) => {
      const evTime = ev.time || ev.start_time;
      if (!evTime) return;
      const t = new Date(evTime).getTime();
      if (t < t0 || t > t1) return;
      const x = xOf(t);
      const type = String(ev.type || "marker").toLowerCase();
      const color = eventColors[type] || eventColors.marker;

      ctx.strokeStyle = color;
      ctx.setLineDash([4, 4]);
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(x, margin.top);
      ctx.lineTo(x, height - margin.bottom);
      ctx.stroke();
      ctx.setLineDash([]);

      // 标签
      const label = ev.name || ev.type || "event";
      ctx.fillStyle = color;
      ctx.font = "bold 11px sans-serif";
      ctx.textAlign = "left";
      const labelX = x + 4 < width - margin.right - 60 ? x + 4 : x - 60;
      ctx.fillText(label, Math.max(labelX, margin.left), margin.top + 12);
      if (ev.detail) {
        ctx.font = "10px sans-serif";
        ctx.fillStyle = "#6b7280";
        const detailStr = typeof ev.detail === "string" ? ev.detail : JSON.stringify(ev.detail);
        ctx.fillText(String(detailStr).slice(0, 30), Math.max(labelX, margin.left), margin.top + 26);
      }
    });
  },

  /** 通用：解析时间输入为 ISO8601 */
  parseTimeInput(value) {
    if (!value) return null;
    const dt = new Date(value);
    if (isNaN(dt.getTime())) return null;
    return dt.toISOString();
  },
};

window.Util = Util;
