<script>
  import {
    consoleState,
    getReadJwt,
    features,
    api,
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
  let resultHtml = $state("");
  let busy = $state(false);

  function defaults() {
    const dEnd = new Date();
    const dStart = new Date(dEnd.getTime() - 3600000);
    start = toLocalInput(dStart);
    end = toLocalInput(dEnd);
  }

  defaults();

  async function run(kind) {
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
      if (kind === "features") {
        const feats = await features(j, { rows, start_time: s, end_time: en });
        resultHtml = renderTable(feats);
      } else {
        const data = await api(
          "POST",
          "/sensor/data/quality",
          { compression: "none", format: "json", rows, start_time: s, end_time: en },
          j
        );
        resultHtml = `<pre>${escapeHtml(JSON.stringify(data, null, 2))}</pre>`;
      }
      status(kind === "features" ? "特徴統計が完了しました" : "品質チェックが完了しました", "ok");
    } catch (err) {
      status((kind === "features" ? "特徴統計失敗: " : "品質チェック失敗: ") + err.message, "err");
    } finally {
      busy = false;
    }
  }

  function renderTable(obj) {
    if (Array.isArray(obj)) {
      if (!obj.length) return "<p class='hint'>データなし</p>";
      const cols = Object.keys(obj[0] || {});
      let h = "<table><thead><tr>" + cols.map((c) => `<th>${escapeHtml(c)}</th>`).join("") + "</tr></thead><tbody>";
      h += obj
        .map(
          (r) =>
            "<tr>" + cols.map((c) => `<td>${escapeHtml(cell(r[c]))}</td>`).join("") + "</tr>"
        )
        .join("");
      return h + "</tbody></table>";
    }
    if (obj && typeof obj === "object") {
      return (
        "<table>" +
        Object.entries(obj)
          .map(([k, v]) => `<tr><th>${escapeHtml(k)}</th><td>${escapeHtml(cell(v))}</td></tr>`)
          .join("") +
        "</table>"
      );
    }
    return `<p>${escapeHtml(cell(obj))}</p>`;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }
</script>

<div class="card">
  <h3>分析（特徴統計 / 品質チェック）</h3>
  <div class="grid">
    <div class="field">
      <label>実験（任意）</label>
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
      <label>チャンネル（カンマ区切り）</label>
      <input bind:value={channels} placeholder="例: eda, ppg" />
    </div>
  </div>
  <div class="row" style="margin:10px 0">
    <button onclick={() => run("features")} disabled={busy}>特徴統計</button>
    <button class="secondary" onclick={() => run("quality")} disabled={busy}>品質チェック</button>
  </div>

  {#if resultHtml}
    <!-- 渲染分析结果（表格/JSON） -->
    <div class="card sub">{@html resultHtml}</div>
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
  .card.sub {
    margin-top: 14px;
    padding: 12px;
  }
  :global(.card.sub table) {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }
  :global(.card.sub th),
  :global(.card.sub td) {
    border: 1px solid var(--border-color, #3a3a3a);
    padding: 6px 10px;
    text-align: left;
  }
  :global(.card.sub th) {
    background: rgba(76, 154, 255, 0.1);
  }
  :global(.card.sub pre) {
    background: var(--input-bg, #1e1e1e);
    padding: 10px;
    border-radius: 6px;
    overflow: auto;
    font-size: 12px;
    max-height: 420px;
  }
</style>
