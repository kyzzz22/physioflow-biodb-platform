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
  let featsData = $state(null); // {total_points, sample_rate_hz, columns}
  let qualityData = $state(null); // {total_points, columns}
  let busy = $state(false);
  let showQuality = $state(false);

  const BAND_COLORS = ["#60a5fa", "#a78bfa", "#34d399", "#fbbf24", "#f87171"];
  const BANDS = ["delta", "theta", "alpha", "beta", "gamma"];

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
        featsData = feats;
        qualityData = null;
        showQuality = false;
        resultHtml = renderTable(feats);
      } else {
        const data = await api(
          "POST",
          "/sensor/data/quality",
          { compression: "none", format: "json", rows, start_time: s, end_time: en },
          j
        );
        const q = data.columns ? data : data.data || data;
        qualityData = q;
        featsData = null;
        showQuality = true;
        resultHtml = renderTable(q);
      }
      status(kind === "features" ? "特徴統計が完了しました" : "品質チェックが完了しました", "ok");
    } catch (err) {
      status((kind === "features" ? "特徴統計失敗: " : "品質チェック失敗: ") + err.message, "err");
    } finally {
      busy = false;
    }
  }

  // 频带堆叠条:channel → 各频带占比(0-1)
  function bandRows(cols) {
    return Object.entries(cols || {}).map(([ch, c]) => {
      const br = c.band_energy_ratio || {};
      const total = BANDS.reduce((a, b) => a + (Number(br[b]) || 0), 0);
      return {
        ch,
        bands: BANDS.map((b) => ({ name: b, value: total ? (Number(br[b]) || 0) / total : 0 })),
        dominantFreq: c.dominant_freq_hz,
        dominantPower: c.dominant_power,
      };
    });
  }

  // 时域指标条:mean/std/rms 每通道内相对比例
  function metricRows(cols) {
    return Object.entries(cols || {}).map(([ch, c]) => {
      const m = ["mean", "std", "rms"];
      const vals = m.map((k) => Number(c[k]) || 0);
      const max = Math.max(...vals, 1e-12);
      return {
        ch,
        items: m.map((k, i) => ({
          name: k,
          value: Number(c[k]) || 0,
          pct: (vals[i] / max) * 100,
        })),
      };
    });
  }

  function qualityRows(cols) {
    return Object.entries(cols || {}).map(([ch, c]) => ({
      ch,
      completeness: c.completeness,
      missingRate: c.estimated_missing_rate,
      maxGap: c.max_gap_seconds,
      intervalMedian: c.interval_ms && c.interval_ms.median,
      points: c.points,
    }));
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
          .filter(([k]) => k !== "columns")
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

  {#if featsData && featsData.columns}
    <div class="card sub">
      <h4>周波数バンドエネルギー比（{featsData.sample_rate_hz} Hz / {featsData.total_points} pts）</h4>
      {#each bandRows(featsData.columns) as r}
        <div class="band-row">
          <span class="band-ch">{r.ch}</span>
          <div class="band-bar">
            {#each r.bands as b, i}
              <div
                class="band-seg"
                style={`width:${(b.value * 100).toFixed(1)}%;background:${BAND_COLORS[i]}`}
                title={`${b.name}: ${(b.value * 100).toFixed(1)}%`}
              ></div>
            {/each}
          </div>
          {#if r.dominantFreq !== undefined && r.dominantFreq !== null}
            <span class="chip">
              支配 {Number(r.dominantFreq).toFixed(2)} Hz
              {#if r.dominantPower !== undefined && r.dominantPower !== null}
                (pwr {Number(r.dominantPower).toExponential(1)})
              {/if}
            </span>
          {/if}
        </div>
      {/each}
      <div class="legend">
        {#each BANDS as b, i}
          <span class="lg"><i style="background:{BAND_COLORS[i]}"></i>{b}</span>
        {/each}
      </div>
    </div>

    <div class="card sub">
      <h4>時域指標（mean / std / rms 相対値）</h4>
      {#each metricRows(featsData.columns) as r}
        <div class="metric-row">
          <span class="band-ch">{r.ch}</span>
          {#each r.items as it}
            <div class="metric-item">
              <span class="metric-label">{it.name}</span>
              <div class="metric-bar-wrap">
                <div class="metric-bar" style={`width:${it.pct.toFixed(1)}%`}></div>
              </div>
              <span class="metric-val">{Number(it.value).toFixed(3)}</span>
            </div>
          {/each}
        </div>
      {/each}
    </div>
  {/if}

  {#if showQuality && qualityData && qualityData.columns}
    <div class="card sub">
      <h4>データ品質（completeness / 欠損率）</h4>
      {#each qualityRows(qualityData.columns) as r}
        <div class="band-row">
          <span class="band-ch">{r.ch}</span>
          <div class="metric-bar-wrap q">
            <div
              class="metric-bar"
              style={`width:${Math.min(100, (r.completeness || 0) * 100).toFixed(1)}%`}
            ></div>
          </div>
          <span class="chip">
            完全性 {(r.completeness * 100).toFixed(1)}% · 欠損 {(r.missingRate * 100).toFixed(1)}%
            {#if r.maxGap !== undefined}
              · maxGap {r.maxGap}s
            {/if}
          </span>
        </div>
      {/each}
    </div>
  {/if}

  {#if resultHtml}
    <!-- 詳細テーブル -->
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
  h4 {
    margin: 0 0 10px;
    font-size: 14px;
  }
  .band-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 8px;
  }
  .band-ch {
    min-width: 90px;
    font-size: 12px;
    font-weight: 600;
    color: var(--text-color, #e0e0e0);
  }
  .band-bar {
    flex: 1;
    display: flex;
    height: 14px;
    border-radius: 4px;
    overflow: hidden;
    background: var(--input-bg, #1e1e1e);
    border: 1px solid var(--border-color, #3a3a3a);
  }
  .band-seg {
    height: 100%;
  }
  .legend {
    display: flex;
    gap: 12px;
    margin-top: 4px;
    font-size: 11px;
    color: var(--muted-color, #9aa0a6);
  }
  .lg i {
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 2px;
    margin-right: 4px;
  }
  .metric-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 8px;
    flex-wrap: wrap;
  }
  .metric-item {
    display: flex;
    align-items: center;
    gap: 6px;
    flex: 1;
    min-width: 180px;
  }
  .metric-label {
    font-size: 11px;
    color: var(--muted-color, #9aa0a6);
    min-width: 30px;
  }
  .metric-bar-wrap {
    flex: 1;
    height: 10px;
    border-radius: 4px;
    background: var(--input-bg, #1e1e1e);
    border: 1px solid var(--border-color, #3a3a3a);
    overflow: hidden;
  }
  .metric-bar-wrap.q {
    flex: 1;
  }
  .metric-bar {
    height: 100%;
    background: var(--accent-color);
    border-radius: 4px;
  }
  .metric-val {
    font-size: 11px;
    color: var(--muted-color, #9aa0a6);
    min-width: 60px;
    text-align: right;
  }
  .chip {
    font-size: 11px;
    padding: 2px 10px;
    border-radius: var(--radius-pill);
    background: var(--accent-tint);
    color: var(--accent-hover);
    border: 1px solid var(--accent-tint-strong);
    white-space: nowrap;
  }
  :global(.card.sub pre) {
    max-height: 420px;
  }
</style>
