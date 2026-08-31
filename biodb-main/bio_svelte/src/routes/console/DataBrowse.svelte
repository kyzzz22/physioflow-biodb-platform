<script>
  import { onMount } from "svelte";
  import {
    consoleState,
    getReadJwt,
    getEvents,
    readData,
    toUtc,
    fmtLocal,
    fmtUTC,
    toLocalInput,
    status,
  } from "$lib/console-state.svelte.js";
  import { drawSeriesWithEvents } from "$lib/console-draw.js";

  let exp = $state("");
  let pid = $state("");
  let start = $state("");
  let end = $state("");
  let channels = $state("eda, ppg");
  let summaryRows = $state([]);
  let eventNote = $state("");
  let timezoneHint = $state("");
  let canvasEl = $state(undefined);
  let lastResult = $state(null);
  let lastEvents = $state([]);
  let channelToggles = $state({});
  let dragStartX = $state(null);
  let dragCurX = $state(null);
  let dragging = $state(false);

  const CHART_MARGIN = { top: 16, right: 16, bottom: 28, left: 56 };

  onMount(() => {
    setDefaults();
  });

  // 概览卡片点击 → 填入实验与 participant
  $effect(() => {
    const seed = consoleState.browseSeed;
    if (seed.ts) {
      exp = seed.exp;
      pid = seed.pid;
    }
  });

  function setDefaults() {
    const dEnd = new Date();
    const dStart = new Date(dEnd.getTime() - 3600000);
    start = toLocalInput(dStart);
    end = toLocalInput(dEnd);
    timezoneHint = `保存は UTC。現在の窓: ${fmtUTC(dStart.toISOString())} 〜 ${fmtUTC(dEnd.toISOString())}`;
  }

  async function doLoad() {
    const e = exp.trim();
    const p = pid.trim();
    const s = toUtc(start);
    const en = toUtc(end);
    const rows = channels
      .split(",")
      .map((x) => x.trim())
      .filter(Boolean);
    if (!p || !s || !en) {
      status("participant_id と時間窓を入力してください", "err");
      return;
    }
    status("読み取り中…", "info");
    try {
      const j = await getReadJwt(p, s, en, e || undefined);
      const res = await readData(j, { rows, start_time: s, end_time: en });
      let events = [];
      try {
        events = await getEvents(p, s, en, e || undefined);
      } catch (err) {
        /* 事件读取失败不阻塞曲线绘制 */
      }
      lastResult = res;
      lastEvents = events;
      channelToggles = Object.fromEntries(
        Object.keys(res).filter((k) => k !== "time").map((k) => [k, true])
      );
      drawChart();
      // 摘要（mean / std / 欠損率 を追加）
      const times = res.time || [];
      summaryRows = Object.entries(res)
        .filter(([k]) => k !== "time" && (res[k] || []).length)
        .map(([k, arr]) => {
          const nums = arr.filter((v) => v !== null && v !== undefined);
          const span =
            times.length >= 2 ? (new Date(times[times.length - 1]) - new Date(times[0])) / 1000 : 0;
          const mean = nums.length ? nums.reduce((a, b) => a + b, 0) / nums.length : NaN;
          const std = nums.length > 1
            ? Math.sqrt(nums.reduce((a, b) => a + (b - mean) ** 2, 0) / nums.length)
            : NaN;
          const missing = arr.length - nums.length;
          return {
            k,
            n: arr.length,
            min: nums.length ? Math.min(...nums).toFixed(2) : "—",
            max: nums.length ? Math.max(...nums).toFixed(2) : "—",
            mean: isNaN(mean) ? "—" : mean.toFixed(2),
            std: isNaN(std) ? "—" : std.toFixed(2),
            missing,
            missingRate: arr.length ? ((missing / arr.length) * 100).toFixed(1) : "0.0",
            hz: span ? (arr.length / span).toFixed(1) : "—",
          };
        });
      eventNote = events.length
        ? `イベント ${events.length} 件: ${events.map((x) => x.name || x.event || x.type).join(", ")}`
        : "イベントなし";
      status("読み取り完了", "ok");
    } catch (e) {
      status("読み取り失敗: " + e.message, "err");
    }
  }

  function drawChart() {
    if (!canvasEl || !lastResult) return;
    const shown = Object.keys(channelToggles).filter((k) => channelToggles[k]);
    drawSeriesWithEvents(canvasEl, lastResult, lastEvents, {
      channels: shown.length ? shown : undefined,
      title: `${exp.trim() || "全実験"} · ${pid.trim()}`,
      window: zoomWindow() || undefined,
    });
  }

  function zoomWindow() {
    // 拖拽选择中实时预览用
    if (!dragStartX || dragCurX === null || !lastResult) return null;
    const t0 = new Date(lastResult.time[0]).getTime();
    const t1 = new Date(lastResult.time[lastResult.time.length - 1]).getTime();
    const width = canvasEl ? canvasEl.clientWidth : 0;
    if (!width) return null;
    const plotW = width - CHART_MARGIN.left - CHART_MARGIN.right;
    const x0 = Math.min(dragStartX, dragCurX);
    const x1 = Math.max(dragStartX, dragCurX);
    const w0 = new Date(t0 + ((x0 - CHART_MARGIN.left) / plotW) * (t1 - t0));
    const w1 = new Date(t0 + ((x1 - CHART_MARGIN.left) / plotW) * (t1 - t0));
    return { start: w0.toISOString(), end: w1.toISOString() };
  }

  // canvas 拖拽选择区间 → 回填表单并重新读取
  function onMouseDown(e) {
    const rect = canvasEl.getBoundingClientRect();
    dragStartX = e.clientX - rect.left;
    dragCurX = dragStartX;
    dragging = true;
  }
  function onMouseMove(e) {
    if (!dragging) return;
    const rect = canvasEl.getBoundingClientRect();
    dragCurX = e.clientX - rect.left;
    drawChart();
  }
  function onMouseUp() {
    if (!dragging) return;
    dragging = false;
    const win = zoomWindow();
    dragStartX = null;
    dragCurX = null;
    if (!win) {
      drawChart();
      return;
    }
    const s = new Date(win.start);
    const en = new Date(win.end);
    if (en - s < 1000) {
      status("選択範囲が短すぎます", "err");
      drawChart();
      return;
    }
    // 回填表单（ローカル時間）→ 再読み込み
    start = toLocalInput(s);
    end = toLocalInput(en);
    status(`ズーム窓: ${fmtUTC(win.start)} 〜 ${fmtUTC(win.end)}`, "info");
    doLoad();
  }

  function zoomReset() {
    setDefaults();
    doLoad();
  }

  function downloadCsv() {
    if (!lastResult) return;
    const rows = lastResult;
    const keys = Object.keys(rows).filter((k) => k !== "time" && (rows[k] || []).length);
    const header = ["time", ...keys];
    const lines = [header.join(",")];
    const n = (rows.time || []).length;
    for (let i = 0; i < n; i++) {
      const line = [rows.time[i]];
      for (const k of keys) line.push(rows[k][i] ?? "");
      lines.push(line.join(","));
    }
    const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `biodb_read_${pid.trim() || "all"}_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }
</script>

<div class="card">
  <h3>データ閲覧</h3>
  <div class="grid">
    <div class="field">
      <label for="browse-experiment">実験（experiment_id、任意）</label>
      <input id="browse-experiment" bind:value={exp} placeholder="登録済み実験 ID" />
    </div>
    <div class="field">
      <label for="browse-participant">participant_id</label>
      <input id="browse-participant" bind:value={pid} placeholder="21 文字の参加者 ID" />
    </div>
    <div class="field">
      <label for="browse-start">開始</label>
      <input id="browse-start" type="datetime-local" bind:value={start} />
    </div>
    <div class="field">
      <label for="browse-end">終了</label>
      <input id="browse-end" type="datetime-local" bind:value={end} />
    </div>
    <div class="field wide">
      <label for="browse-channels">チャンネル（カンマ区切りのセンサー項目）</label>
      <input id="browse-channels" bind:value={channels} placeholder="例: eda, ppg, eeg_alpha" />
    </div>
  </div>
  <p class="hint">{timezoneHint}</p>
  <div class="row" style="margin:10px 0">
    <button onclick={doLoad}>読み取り</button>
    <button class="secondary" onclick={setDefaults}>現在時刻に設定</button>
    {#if lastResult}
      <button class="secondary" onclick={zoomReset}>ズーム解除</button>
      <button class="secondary" onclick={downloadCsv}>CSV ダウンロード</button>
    {/if}
  </div>

  {#if lastResult}
    <div class="channels">
      {#each Object.keys(channelToggles) as ch}
        <label class="chk">
          <input
            type="checkbox"
            checked={channelToggles[ch]}
            onchange={() => {
              channelToggles[ch] = !channelToggles[ch];
              drawChart();
            }}
          />
          {ch}
        </label>
      {/each}
    </div>
  {/if}

  <div class="chart-wrap" style="position:relative">
    <canvas
      bind:this={canvasEl}
      style="width:100%;cursor:crosshair"
      onmousedown={onMouseDown}
      onmousemove={onMouseMove}
      onmouseup={onMouseUp}
      onmouseleave={onMouseUp}
    ></canvas>
    {#if dragging && dragStartX !== null && dragCurX !== null}
      <div
        class="sel"
        style={`left:${Math.min(dragStartX, dragCurX)}px;width:${Math.abs(dragCurX - dragStartX)}px`}
      ></div>
    {/if}
  </div>
  <p class="hint">曲線をドラッグして範囲選択 → ズーム再読み込み。チェックボックスで表示チャンネル切替。</p>

  {#if summaryRows.length}
    <div class="card sub">
      <h4>摘要（ローカル {fmtLocal(toUtc(start))} 〜 {fmtLocal(toUtc(end))} / UTC {fmtUTC(toUtc(start))} 〜 {fmtUTC(toUtc(end))}）</h4>
      <table>
        <thead>
          <tr>
            <th>チャンネル</th>
            <th>点数</th>
            <th>欠損</th>
            <th>欠損率</th>
            <th>min</th>
            <th>max</th>
            <th>mean</th>
            <th>std</th>
            <th>サンプリング</th>
          </tr>
        </thead>
        <tbody>
          {#each summaryRows as r}
            <tr>
              <td>{r.k}</td>
              <td>{r.n}</td>
              <td>{r.missing}</td>
              <td>{r.missingRate}%</td>
              <td>{r.min}</td>
              <td>{r.max}</td>
              <td>{r.mean}</td>
              <td>{r.std}</td>
              <td>{r.hz} Hz</td>
            </tr>
          {/each}
        </tbody>
      </table>
      <p class="hint">{eventNote}</p>
    </div>
  {/if}
</div>

<style>
  .grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }
  .field {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .field.wide {
    grid-column: span 2;
  }
  .field label {
    font-size: 13px;
    color: var(--muted-color, #9aa0a6);
  }
  .row {
    display: flex;
    gap: 8px;
    align-items: center;
  }
  .hint {
    font-size: 12px;
    color: var(--muted-color, #9aa0a6);
  }
  .channels {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin: 8px 0;
  }
  .chk {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 12px;
    color: var(--muted-color, #9aa0a6);
    cursor: pointer;
  }
  .sel {
    position: absolute;
    top: 0;
    bottom: 0;
    background: rgba(40, 167, 69, 0.25);
    border: 1px solid var(--accent-color);
    pointer-events: none;
  }
  .card.sub {
    margin-top: 14px;
    padding: 12px;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }
  th,
  td {
    border: 1px solid var(--border-color, #3a3a3a);
    padding: 6px 10px;
    text-align: left;
  }
  th {
    background: var(--accent-tint);
  }
</style>
