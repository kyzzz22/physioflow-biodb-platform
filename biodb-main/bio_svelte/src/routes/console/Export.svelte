<script>
  import {
    consoleState,
    getReadJwt,
    exportData,
    toUtc,
    toLocalInput,
    status,
    cell,
  } from "$lib/console-state.svelte.js";

  let pid = $state("");
  let exp = $state("");
  let start = $state("");
  let end = $state("");
  let channels = $state("eda, ppg");
  let summary = $state(null);
  let busy = $state(false);

  function defaults() {
    const dEnd = new Date();
    const dStart = new Date(dEnd.getTime() - 3600000);
    start = toLocalInput(dStart);
    end = toLocalInput(dEnd);
  }

  defaults();

  async function doExport() {
    const p = pid.trim() || consoleState.cfg.participant_id;
    const e = exp.trim();
    const s = toUtc(start) || new Date(Date.now() - 3600000).toISOString();
    const en = toUtc(end) || new Date().toISOString();
    const rows = channels
      .split(",")
      .map((x) => x.trim())
      .filter(Boolean);
    if (!p || !rows.length) {
      status("participant_id とチャンネルを入力してください", "err");
      return;
    }
    busy = true;
    try {
      const j = await getReadJwt(p, s, en, e || undefined);
      const res = await exportData(j, {
        rows,
        start_time: s,
        end_time: en,
        experiment_id: e || undefined,
      });
      consoleState.exportResult = res;
      const sensor = res.sensor || {};
      const n = Object.keys(sensor).reduce((acc, k) => acc + (sensor[k] || []).length, 0);
      summary = {
        channels: Object.keys(sensor).join(", ") || "—",
        points: n,
        events: (res.events || []).length,
        experiment: res.experiment ? JSON.stringify(res.experiment) : "なし",
      };
      status("エクスポートが完了しました", "ok");
    } catch (err) {
      status("エクスポート失敗: " + err.message, "err");
    } finally {
      busy = false;
    }
  }

  function doDownload() {
    const res = consoleState.exportResult;
    if (!res) return;
    const blob = new Blob([JSON.stringify(res, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `biodb_export_${exp.trim() || "all"}_${pid.trim() || "p"}_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  }
</script>

<div class="card">
  <h3>エクスポート</h3>
  <p class="hint">時系列データ + イベント + 実験メタデータを JSON で一括ダウンロードします。</p>
  <div class="grid">
    <div class="field">
      <label for="export-experiment">実験（任意）</label>
      <input id="export-experiment" bind:value={exp} placeholder="登録済み実験 ID" />
    </div>
    <div class="field">
      <label for="export-participant">participant_id</label>
      <input id="export-participant" bind:value={pid} placeholder="21 文字の参加者 ID" />
    </div>
    <div class="field">
      <label for="export-start">開始</label>
      <input id="export-start" type="datetime-local" bind:value={start} />
    </div>
    <div class="field">
      <label for="export-end">終了</label>
      <input id="export-end" type="datetime-local" bind:value={end} />
    </div>
    <div class="field wide">
      <label for="export-channels">チャンネル（カンマ区切り）</label>
      <input id="export-channels" bind:value={channels} placeholder="例: eda, ppg" />
    </div>
  </div>
  <div class="row" style="margin:10px 0">
    <button onclick={doExport} disabled={busy}>{busy ? "エクスポート中…" : "エクスポート実行"}</button>
    <button class="secondary" onclick={doDownload} disabled={!summary}>JSON ダウンロード</button>
  </div>

  {#if summary}
    <div class="card sub">
      <h4>エクスポート摘要</h4>
      <table>
        <thead>
          <tr>
            <th>時系列チャンネル</th>
            <th>総点数</th>
            <th>イベント</th>
            <th>実験メタデータ</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>{summary.channels}</td>
            <td>{summary.points}</td>
            <td>{summary.events}</td>
            <td>{summary.experiment}</td>
          </tr>
        </tbody>
      </table>
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
    background: var(--accent-tint);
  }
</style>
