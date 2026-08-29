<script>
  import { onMount } from "svelte";
  import { consoleState, discover, loadExperiments, fmtUTC, status } from "$lib/console-state.svelte.js";

  let loading = $state(false);
  let expCount = $state(0);
  let autoRun = $state(false);

  async function runDiscover() {
    if (!consoleState.cfg.user_id || !consoleState.cfg.token) {
      status("先に「接続設定」で user_id / 長期トークンを設定してください", "err");
      return;
    }
    loading = true;
    try {
      const cards = await discover();
      try {
        const exps = await loadExperiments();
        expCount = exps.length;
      } catch (e) {
        expCount = 0;
      }
      status(`棚卸し完了：${cards.length} 件の実験`, "ok");
    } catch (e) {
      status("棚卸し失敗: " + e.message, "err");
    } finally {
      loading = false;
      autoRun = false;
    }
  }

  onMount(() => {
    if (consoleState.cfg.user_id && consoleState.cfg.token) {
      autoRun = true;
      runDiscover();
    }
  });

  function openInBrowse(card) {
    consoleState.browseSeed = {
      exp: card.experiment === "（無ラベル）" ? "" : card.experiment,
      pid: card.participant,
      ts: Date.now(),
    };
    status("実験をデータ閲覧に反映しました。タブを切り替えて「読み取り」を実行してください", "info");
  }

  const cards = $derived(consoleState.overviewCards);
  const stats = $derived.by(() => {
    const participants = new Set(cards.map((c) => c.participant).filter(Boolean));
    let points = 0;
    let t0 = null;
    let t1 = null;
    for (const c of cards) {
      points += c.points || 0;
      if (c.t0 && (!t0 || c.t0 < t0)) t0 = c.t0;
      if (c.t1 && (!t1 || c.t1 > t1)) t1 = c.t1;
    }
    return { participants: participants.size, points, t0, t1 };
  });
  const recent = $derived(
    [...cards].sort((a, b) => (b.t1 || "").localeCompare(a.t1 || "")).slice(0, 5)
  );
</script>

<div class="card">
  <h3>データ棚卸し（直近 7 日）</h3>
  <p class="hint">参加者一覧を取得し、各参加者の直近 7 日分データを読み取って実験ごとに集計します。</p>
  <div class="row" style="margin: 10px 0">
    <button onclick={runDiscover} disabled={loading || autoRun}>
      {loading ? "棚卸し中…" : "棚卸し実行"}
    </button>
  </div>

  {#if loading}
    <p class="hint">棚卸し中…（参加者一覧 + 各参加者 7 日分データ）</p>
  {/if}

  {#if cards.length}
    <div class="stat-grid">
      <div class="stat-card">
        <div class="stat-num">{expCount}</div>
        <div class="stat-label">実験登録数</div>
      </div>
      <div class="stat-card">
        <div class="stat-num">{stats.participants}</div>
        <div class="stat-label">参加者数</div>
      </div>
      <div class="stat-card">
        <div class="stat-num">{stats.points.toLocaleString()}</div>
        <div class="stat-label">総データ点数</div>
      </div>
      <div class="stat-card">
        <div class="stat-num stat-small">{stats.t0 ? fmtUTC(stats.t0).slice(0, 16) : "—"}</div>
        <div class="stat-label">〜 {stats.t1 ? fmtUTC(stats.t1).slice(0, 16) : "—"}</div>
      </div>
    </div>

    {#if recent.length}
      <h3 style="margin-top: 18px">最近の活動</h3>
      <div class="recent">
        {#each recent as card}
          <div class="recent-item" onclick={() => openInBrowse(card)}>
            <span class="recent-exp">{card.experiment}</span>
            <span class="recent-meta">{card.participant} · {fmtUTC(card.t1).slice(0, 16)}</span>
            <span class="chip">{card.points.toLocaleString()} pts</span>
          </div>
        {/each}
      </div>
    {/if}

    <h3 style="margin-top: 18px">実験一覧（クリックでデータ閲覧へ）</h3>
    <div class="cards">
      {#each cards as card}
        <div class="exp-card" onclick={() => openInBrowse(card)}>
          <div class="exp-title">{card.experiment}</div>
          <div class="exp-meta">
            participant: {card.participant}<br />
            データ: {card.t0 ? `${fmtUTC(card.t0)} 〜 ${fmtUTC(card.t1)}` : "—"}<br />
            合計点数: {card.points}
          </div>
          <div class="exp-chips">
            {#each card.channels as ch}
              <span class="chip">{ch}</span>
            {/each}
          </div>
        </div>
      {/each}
    </div>
    <p class="hint" style="margin-top:8px">カードをクリックするとデータ閲覧タブに反映されます。</p>
  {:else if !loading}
    <p class="hint">データはまだありません。「棚卸し実行」を押してください。</p>
  {/if}
</div>

<style>
  .row {
    display: flex;
    gap: 8px;
    align-items: center;
  }
  .hint {
    font-size: 12px;
    color: var(--muted-color, #9aa0a6);
  }
  .stat-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 12px;
    margin: 14px 0 4px;
  }
  .stat-card {
    background: var(--card-bg, #262626);
    border: 1px solid var(--border-color, #3a3a3a);
    border-radius: 10px;
    padding: 14px 16px;
  }
  .stat-num {
    font-size: 1.6rem;
    font-weight: 700;
    color: var(--accent-hover);
    line-height: 1.2;
  }
  .stat-num.stat-small {
    font-size: 1rem;
    color: var(--text-color, #e0e0e0);
  }
  .stat-label {
    margin-top: 4px;
    font-size: 12px;
    color: var(--muted-color, #9aa0a6);
  }
  .recent {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-top: 8px;
  }
  .recent-item {
    display: flex;
    align-items: center;
    gap: 12px;
    background: var(--card-bg, #262626);
    border: 1px solid var(--border-color, #3a3a3a);
    border-radius: 8px;
    padding: 8px 12px;
    cursor: pointer;
    transition: border-color 0.15s;
  }
  .recent-item:hover {
    border-color: var(--accent-color);
  }
  .recent-exp {
    font-weight: 600;
    flex: 1;
  }
  .recent-meta {
    font-size: 12px;
    color: var(--muted-color, #9aa0a6);
  }
  .cards {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 12px;
    margin-top: 12px;
  }
  .exp-card {
    background: var(--card-bg, #262626);
    border: 1px solid var(--border-color, #3a3a3a);
    border-radius: 10px;
    padding: 12px;
    cursor: pointer;
    transition: border-color 0.15s;
  }
  .exp-card:hover {
    border-color: var(--accent-color);
  }
  .exp-title {
    font-weight: 700;
    margin-bottom: 6px;
  }
  .exp-meta {
    font-size: 12px;
    color: var(--muted-color, #9aa0a6);
    line-height: 1.5;
  }
  .exp-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 8px;
  }
  .chip {
    background: var(--accent-tint);
    color: var(--accent-hover);
    border: 1px solid var(--accent-tint-strong);
    border-radius: var(--radius-pill);
    padding: 2px 10px;
    font-size: 12px;
  }
</style>
