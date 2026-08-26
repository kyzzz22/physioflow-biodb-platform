/**
 * BioDB Console — Canvas 曲线绘图工具（Svelte 迁移版）
 * drawSeries / drawSeriesWithEvents
 */

/**
 * 在 canvas 上绘制多通道时间序列曲线。
 * @param {HTMLCanvasElement} canvas
 * @param {object} result  {time: [...], [channel]: [...]}
 * @param {object} opts {channels: [names], colors: {}, height, title}
 */
export function drawSeries(canvas, result, opts = {}) {
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
  ctx.fillStyle = "#1e1e1e";
  ctx.fillRect(0, 0, width, height);

  const timeStrs = result.time || [];
  const channels = opts.channels || Object.keys(result).filter((k) => k !== "time");
  if (!timeStrs.length || !channels.length) {
    ctx.fillStyle = "#888";
    ctx.font = "14px sans-serif";
    ctx.fillText("（データなし）", 16, height / 2);
    return;
  }

  const margin = { top: 16, right: 16, bottom: 28, left: 56 };
  const plotW = width - margin.left - margin.right;
  const plotH = height - margin.top - margin.bottom;

  // X 轴：时间
  const t0 = new Date(timeStrs[0]).getTime();
  const t1 = new Date(timeStrs[timeStrs.length - 1]).getTime();
  const xOf = (t) => margin.left + ((t - t0) / (t1 - t0 || 1)) * plotW;

  // 网格
  ctx.strokeStyle = "#333";
  ctx.beginPath();
  for (let i = 0; i <= 4; i++) {
    const y = margin.top + (i / 4) * plotH;
    ctx.moveTo(margin.left, y);
    ctx.lineTo(width - margin.right, y);
  }
  ctx.stroke();

  // X 轴刻度
  ctx.fillStyle = "#999";
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
  const palette = ["#3b82f6", "#ef4444", "#22c55e", "#f59e0b", "#a78bfa", "#06b6d4", "#ec4899", "#84cc16"];

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
    ctx.fillStyle = "#aaa";
    ctx.fillText(
      `min=${vMin.toFixed(2)}  max=${vMax.toFixed(2)}  n=${values.length}`,
      margin.left + 4,
      bandTop + bandH - 6
    );
  });

  if (opts.title) {
    ctx.fillStyle = "#ccc";
    ctx.font = "bold 13px sans-serif";
    ctx.textAlign = "left";
    ctx.fillText(opts.title, 8, 12);
  }
}

/**
 * 绘制多通道时序曲线并叠加事件标记（垂直虚线 + 标签）。
 * 事件字段兼容：time/start_time、type、name、experiment_id、detail/data。
 */
export function drawSeriesWithEvents(canvas, result, events, opts = {}) {
  drawSeries(canvas, result, opts);
  if (!events || !events.length) return;
  const timeStrs = result.time || [];
  if (!timeStrs.length) return;

  const rect = canvas.parentElement ? canvas.parentElement.getBoundingClientRect() : { width: 800 };
  const width = opts.width || Math.max(rect.width - 24, 400);
  const height = opts.height || 300;
  const ctx = canvas.getContext("2d");

  const margin = { top: 16, right: 16, bottom: 28, left: 56 };
  const plotW = width - margin.left - margin.right;
  const plotH = height - margin.top - margin.bottom;
  const t0 = new Date(timeStrs[0]).getTime();
  const t1 = new Date(timeStrs[timeStrs.length - 1]).getTime();
  const xOf = (t) => margin.left + ((t - t0) / (t1 - t0 || 1)) * plotW;

  const eventColors = {
    start: "#22c55e",
    end: "#ef4444",
    marker: "#f59e0b",
    note: "#a78bfa",
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
      ctx.fillStyle = "#9ca3af";
      const detailStr = typeof ev.detail === "string" ? ev.detail : JSON.stringify(ev.detail);
      ctx.fillText(String(detailStr).slice(0, 30), Math.max(labelX, margin.left), margin.top + 26);
    }
  });
}
