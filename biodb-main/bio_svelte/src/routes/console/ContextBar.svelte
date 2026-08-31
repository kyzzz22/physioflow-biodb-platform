<script>
  import {
    consoleState,
    fmtUTC,
    saveContext,
    setContextWindow,
    toUtc,
  } from "$lib/console-state.svelte.js";

  const experimentOptions = $derived.by(() => {
    const values = new Set();
    for (const item of consoleState.experimentsCache) {
      const value = item.experiment_id || item.id || item.name;
      if (value) values.add(value);
    }
    for (const item of consoleState.overviewCards) {
      if (item.experiment && item.experiment !== "（無ラベル）") values.add(item.experiment);
    }
    return [...values].sort();
  });

  const participantOptions = $derived.by(() => {
    const values = new Set();
    if (consoleState.cfg.participant_id) values.add(consoleState.cfg.participant_id);
    for (const item of consoleState.overviewCards) {
      if (item.participant) values.add(item.participant);
    }
    return [...values].sort();
  });

  const utcWindow = $derived.by(() => {
    try {
      return `${fmtUTC(toUtc(consoleState.context.start))} 〜 ${fmtUTC(toUtc(consoleState.context.end))}`;
    } catch (e) {
      return "日時を確認してください";
    }
  });
</script>

<section class="context-bar" aria-labelledby="context-title">
  <div class="context-head">
    <div>
      <h2 id="context-title">現在のデータ範囲</h2>
      <p>ここで選んだ条件を、閲覧・イベント・分析・エクスポートで共有します。</p>
    </div>
    <div class="presets" aria-label="時間範囲プリセット">
      <button type="button" class="secondary" onclick={() => setContextWindow(3600000)}>直近 1 時間</button>
      <button type="button" class="secondary" onclick={() => setContextWindow(86400000)}>直近 24 時間</button>
      <button type="button" class="secondary" onclick={() => setContextWindow(7 * 86400000)}>直近 7 日</button>
    </div>
  </div>

  <div class="context-grid">
    <div class="field">
      <label for="context-experiment">実験</label>
      <input
        id="context-experiment"
        list="context-experiments"
        bind:value={consoleState.context.experiment}
        onchange={saveContext}
        placeholder="全実験（未指定）"
      />
      <datalist id="context-experiments">
        {#each experimentOptions as value}<option value={value}></option>{/each}
      </datalist>
    </div>
    <div class="field">
      <label for="context-participant">協力者 ID</label>
      <input
        id="context-participant"
        list="context-participants"
        bind:value={consoleState.context.participant}
        onchange={saveContext}
        placeholder="participant_id"
      />
      <datalist id="context-participants">
        {#each participantOptions as value}<option value={value}></option>{/each}
      </datalist>
    </div>
    <div class="field">
      <label for="context-start">開始（ローカル）</label>
      <input id="context-start" type="datetime-local" bind:value={consoleState.context.start} onchange={saveContext} />
    </div>
    <div class="field">
      <label for="context-end">終了（ローカル）</label>
      <input id="context-end" type="datetime-local" bind:value={consoleState.context.end} onchange={saveContext} />
    </div>
  </div>
  <p class="utc">UTC: {utcWindow}</p>
</section>

<style>
  .context-bar {
    margin-bottom: 14px;
    padding: 14px;
    border: 1px solid var(--accent-tint-strong);
    border-radius: var(--radius);
    background: linear-gradient(135deg, var(--surface), var(--accent-tint));
  }
  .context-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 12px;
  }
  h2 { margin: 0; font-size: 14px; }
  p { margin: 3px 0 0; color: var(--muted); font-size: 12px; }
  .presets { display: flex; flex-wrap: wrap; gap: 6px; }
  .presets button { padding: 5px 9px; font-size: 12px; }
  .context-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 10px;
  }
  .field { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
  label { color: var(--muted); font-size: 12px; }
  .utc { margin-top: 8px; }
  @media (max-width: 800px) {
    .context-head { flex-direction: column; }
    .context-grid { grid-template-columns: 1fr 1fr; }
  }
  @media (max-width: 520px) {
    .context-grid { grid-template-columns: 1fr; }
  }
</style>
