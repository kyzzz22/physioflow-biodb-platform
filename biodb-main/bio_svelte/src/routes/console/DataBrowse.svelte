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
      if (canvasEl) {
        drawSeriesWithEvents(canvasEl, res, events, {
          channels: Object.keys(res).filter((k) => k !== "time" && (res[k] || []).length),
          title: `${e || "全実験"} · ${p}`,
        });
      }
      // 摘要
      const times = res.time || [];
      const rowsOut = Object.entries(res)
        .filter(([k]) => k !== "time" && (res[k] || []).length)
        .map(([k, arr]) => {
          const nums = arr.filter((v) => v !== null && v !== undefined);
          const span =
            times.length >= 2 ? (new Date(times[times.length - 1]) - new Date(times[0])) / 1000 : 0;
          return {
            k,
            n: arr.length,
            min: nums.length ? Math.min(...nums).toFixed(2) : "—",
            max: nums.length ? Math.max(...nums).toFixed(2) : "—",
            hz: span ? (arr.length / span).toFixed(1) : "—",
          };
        });
      summaryRows = rowsOut;
      eventNote = events.length
        ? `イベント ${events.length} 件: ${events.map((x) => x.name || x.event || x.type).join(", ")}`
        : "イベントなし";
      status("読み取り完了", "ok");
    } catch (e) {
      status("読み取り失敗: " + e.message, "err");
    }
  }
</script>

<div class="card">
  <h3>データ閲覧</h3>
  <div class="grid">
    <div class="field">
      <label>実験（experiment_id、任意）</label>
      <input bind:value={exp} placeholder="登録済み実験 ID" />
    </div>
    <div class="field">
      <label>participant_id</label>
      <input bind:value={pid} placeholder="21 文字の参加者 ID" />
    </div>
    <div class="field">
      <label>開始</label>
      <input type="datetime-local" bind:value={start} />
    </div>
    <div class="field">
      <label>終了</label>
      <input type="datetime-local" bind:value={end} />
    </div>
    <div class="field wide">
      <label>チャンネル（カンマ区切りのセンサー項目）</label>
      <input bind:value={channels} placeholder="例: eda, ppg, eeg_alpha" />
    </div>
  </div>
  <p class="hint">{timezoneHint}</p>
  <div class="row" style="margin:10px 0">
    <button onclick={doLoad}>読み取り</button>
    <button class="secondary" onclick={setDefaults}>現在時刻に設定</button>
  </div>

  <canvas bind:this={canvasEl} style="width:100%"></canvas>

  {#if summaryRows.length}
    <div class="card sub">
      <h4>摘要（ローカル {fmtLocal(toUtc(start))} 〜 {fmtLocal(toUtc(end))} / UTC {fmtUTC(toUtc(start))} 〜 {fmtUTC(toUtc(end))}）</h4>
      <table>
        <thead>
          <tr>
            <th>チャンネル</th>
            <th>点数</th>
            <th>min</th>
            <th>max</th>
            <th>サンプリング</th>
          </tr>
        </thead>
        <tbody>
          {#each summaryRows as r}
            <tr>
              <td>{r.k}</td>
              <td>{r.n}</td>
              <td>{r.min}</td>
              <td>{r.max}</td>
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
    background: rgba(76, 154, 255, 0.1);
  }
</style>
