<script>
  import {
    consoleState,
    loadExperiments,
    showDict,
    createExperiment,
    deleteExperiment,
    status,
  } from "$lib/console-state.svelte.js";

  let list = $state([]);
  let dictId = $state("");
  let dictObj = $state(null);
  let loading = $state(false);

  let name = $state("");
  let eid = $state("");
  let label = $state("");
  let desc = $state("");
  let dictInput = $state("");

  async function doLoad() {
    if (!consoleState.cfg.user_id || !consoleState.cfg.token) {
      status("先に「接続設定」で user_id / 長期トークンを設定してください", "err");
      return;
    }
    loading = true;
    try {
      list = await loadExperiments();
      status(`実験一覧を読み込みました（${list.length} 件）`, "ok");
    } catch (e) {
      status("実験一覧の読み込み失敗: " + e.message, "err");
    } finally {
      loading = false;
    }
  }

  async function doShowDict(id) {
    try {
      const data = await showDict(id);
      dictId = id;
      dictObj = data.dictionary || {};
    } catch (e) {
      status("データ辞書の読み込み失敗: " + e.message, "err");
    }
  }

  async function doCreate() {
    if (!name.trim()) {
      status("name を入力してください", "err");
      return;
    }
    const body = { name: name.trim() };
    if (eid.trim()) body.experiment_id = eid.trim();
    if (label.trim()) body.label = label.trim();
    if (desc.trim()) body.description = desc.trim();
    if (dictInput.trim()) {
      try {
        body.dictionary = JSON.parse(dictInput.trim());
      } catch (e) {
        status("データ辞書が有効な JSON ではありません", "err");
        return;
      }
    }
    try {
      const data = await createExperiment(body);
      status(`実験を作成しました: ${data.experiment?.experiment_id || name.trim()}`, "ok");
      name = "";
      eid = "";
      label = "";
      desc = "";
      dictInput = "";
      doLoad();
    } catch (e) {
      status("実験作成失敗: " + e.message, "err");
    }
  }

  async function doDelete(id) {
    if (!id || !confirm("この実験登録を削除しますか？関連する時系列データには影響しません。")) return;
    try {
      await deleteExperiment(id);
      status("実験を削除しました", "ok");
      doLoad();
    } catch (e) {
      status("削除失敗: " + e.message, "err");
    }
  }
</script>

<div class="card">
  <h3>実験登録</h3>
  <div class="row" style="margin:10px 0">
    <button onclick={doLoad} disabled={loading}>{loading ? "読み込み中…" : "一覧を読み込み"}</button>
  </div>

  {#if list.length}
    <div class="card sub">
      <h4>実験一覧（{list.length}）</h4>
      <table>
        <thead>
          <tr>
            <th>experiment_id</th>
            <th>name</th>
            <th>label</th>
            <th>説明</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {#each list as e}
            <tr>
              <td>{e.experiment_id || "—"}</td>
              <td>{e.name || "—"}</td>
              <td>{e.label || "—"}</td>
              <td>{e.description || "—"}</td>
              <td>
                <a class="link" onclick={() => doShowDict(e.experiment_id || e.id)}>辞書</a>
                <a class="link danger" onclick={() => doDelete(e.experiment_id || e.id)}>削除</a>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {:else if !loading}
    <p class="hint">登録はまだありません。「一覧を読み込み」を押してください。</p>
  {/if}

  {#if dictObj}
    <div class="card sub">
      <h4>データ辞書 · {dictId}</h4>
      <pre>{JSON.stringify(dictObj, null, 2)}</pre>
    </div>
  {/if}
</div>

<div class="card">
  <h3>新規実験登録</h3>
  <div class="grid">
    <div class="field">
      <label>name（必須）</label>
      <input bind:value={name} placeholder="実験名" />
    </div>
    <div class="field">
      <label>experiment_id（任意、省略時は自動生成）</label>
      <input bind:value={eid} placeholder="UUID" />
    </div>
    <div class="field">
      <label>label（任意）</label>
      <input bind:value={label} />
    </div>
    <div class="field">
      <label>説明（任意）</label>
      <input bind:value={desc} />
    </div>
    <div class="field wide">
      <label>データ辞書（任意、JSON）</label>
      <textarea bind:value={dictInput} rows="4" placeholder={'{"eda": {"unit": "uS"}}'}></textarea>
    </div>
  </div>
  <div class="row" style="margin:10px 0">
    <button onclick={doCreate}>作成</button>
  </div>
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
  .link {
    color: var(--accent-color, #4c9aff);
    cursor: pointer;
    margin-right: 8px;
  }
  .link.danger {
    color: var(--danger, #f87171);
  }
  textarea {
    background: var(--input-bg, #1e1e1e);
    color: var(--text-color, #e5e7eb);
    border: 1px solid var(--border-color, #3a3a3a);
    border-radius: 6px;
    padding: 8px;
    font-family: monospace;
    font-size: 12px;
    resize: vertical;
  }
  pre {
    background: var(--input-bg, #1e1e1e);
    border: 1px solid var(--border-color, #3a3a3a);
    border-radius: 6px;
    padding: 10px;
    overflow: auto;
    font-size: 12px;
    max-height: 320px;
  }
</style>
