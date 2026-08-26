<script>
  import { consoleState, discover, fmtUTC, status } from "$lib/console-state.svelte.js";

  let loading = $state(false);

  async function runDiscover() {
    if (!consoleState.cfg.user_id || !consoleState.cfg.token) {
      status("先に「接続設定」で user_id / 長期トークンを設定してください", "err");
      return;
    }
    loading = true;
    try {
      const cards = await discover();
      status(`棚卸し完了：${cards.length} 件の実験`, "ok");
    } catch (e) {
      status("棚卸し失敗: " + e.message, "err");
    } finally {
      loading = false;
    }
  }

  function openInBrowse(card) {
    consoleState.browseSeed = {
      exp: card.experiment === "（無ラベル）" ? "" : card.experiment,
      pid: card.participant,
      ts: Date.now(),
    };
    status("実験をデータ閲覧に反映しました。タブを切り替えて「読み取り」を実行してください", "info");
  }
</script>

<div class="card">
  <h3>データ棚卸し（直近 7 日）</h3>
  <p class="hint">参加者一覧を取得し、各参加者の直近 7 日分データを読み取って実験ごとに集計します。</p>
  <div class="row" style="margin: 10px 0">
    <button onclick={runDiscover} disabled={loading}>
      {loading ? "棚卸し中…" : "棚卸し実行"}
    </button>
  </div>

  {#if loading}
    <p class="hint">棚卸し中…（参加者一覧 + 各参加者 7 日分データ）</p>
  {/if}

  {#if consoleState.overviewCards.length}
    <div class="cards">
      {#each consoleState.overviewCards as card}
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
    border-color: var(--accent-color, #4c9aff);
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
    background: rgba(76, 154, 255, 0.15);
    color: var(--accent-color, #4c9aff);
    border-radius: 999px;
    padding: 2px 10px;
    font-size: 12px;
  }
</style>
