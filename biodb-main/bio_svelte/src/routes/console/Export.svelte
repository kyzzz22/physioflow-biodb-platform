<script>
  import {
    consoleState,
    getReadJwt,
    exportData,
    saveContext,
    status,
    cell,
  } from "$lib/console-state.svelte.js";
  import { resolveConsoleContext } from "$lib/console-context.js";

  let summary = $state(null);
  let busy = $state(false);

  async function doExport() {
    const ctx = resolveConsoleContext(consoleState.context, consoleState.cfg.participant_id);
    if (ctx.error) {
      status(ctx.error, "err");
      return;
    }
    const { participant: p, experiment: e, start: s, end: en, rows } = ctx;
    if (!rows.length) {
      status("チャンネルを 1 つ以上入力してください", "err");
      return;
    }
    saveContext();
    busy = true;
    summary = null;
    consoleState.exportResult = null;
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
      summary = null;
      consoleState.exportResult = null;
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
    a.download = `biodb_export_${consoleState.context.experiment.trim() || "all"}_${consoleState.context.participant.trim() || "p"}_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  }
</script>

<div class="card">
  <h3>エクスポート</h3>
  <p class="hint">時系列データ + イベント + 実験メタデータを JSON で一括ダウンロードします。</p>
  <div class="grid single">
    <div class="field">
      <label for="export-channels">チャンネル（カンマ区切り）</label>
      <input id="export-channels" bind:value={consoleState.context.channels} onchange={saveContext} placeholder="例: eda, ppg" />
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
  .grid.single { grid-template-columns: 1fr; }
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
