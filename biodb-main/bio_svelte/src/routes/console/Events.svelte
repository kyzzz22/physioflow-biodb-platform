<script>
  import {
    consoleState,
    getEvents,
    getEventJwt,
    api,
    toUtc,
    fmtLocal,
    status,
  } from "$lib/console-state.svelte.js";

  let listExp = $state("");
  let listPid = $state("");
  let listStart = $state("");
  let listEnd = $state("");
  let events = $state([]);

  let newType = $state("");
  let newStart = $state("");
  let newEnd = $state("");
  let newExp = $state("");
  let newDesc = $state("");

  function nowMinus(n) {
    const d = new Date(Date.now() - n * 86400000);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}T${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  }

  async function doLoad() {
    const exp = listExp.trim();
    const pid = listPid.trim() || consoleState.cfg.participant_id;
    const start = toUtc(listStart) || new Date(Date.now() - 86400000).toISOString();
    const end = toUtc(listEnd) || new Date().toISOString();
    if (!pid) {
      status("participant_id を入力してください", "err");
      return;
    }
    try {
      events = await getEvents(pid, start, end, exp || undefined);
      status(`イベントを読み込みました（${events.length} 件）`, "ok");
    } catch (e) {
      status("イベント読み込み失敗: " + e.message, "err");
    }
  }

  async function doCreate() {
    const pid = listPid.trim() || consoleState.cfg.participant_id;
    const evType = newType.trim();
    const start = toUtc(newStart);
    const exp = newExp.trim();
    if (!pid || !evType || !start) {
      status("participant_id、イベント種別、開始時刻を入力してください", "err");
      return;
    }
    try {
      const endIso = toUtc(newEnd);
      const startMs = new Date(start).getTime();
      const endMs = endIso ? new Date(endIso).getTime() : startMs + 1000;
      const endEff = new Date(endMs).toISOString();
      const j = await getEventJwt(
        pid,
        new Date(startMs - 1000).toISOString(),
        new Date(endMs + 1000).toISOString(),
        exp || undefined
      );
      const body = { user_id: pid, start_time: start, event: evType, end_time: endEff };
      if (exp) body.experiment_id = exp;
      if (newDesc.trim()) body.description = newDesc.trim();
      await api("POST", "/event/events", body, j);
      status("イベントを作成しました", "ok");
      newType = "";
      newStart = "";
      newEnd = "";
      newExp = "";
      newDesc = "";
      doLoad();
    } catch (e) {
      status("イベント作成失敗: " + e.message, "err");
    }
  }

  async function doDelete(id) {
    const pid = listPid.trim() || consoleState.cfg.participant_id;
    if (!id || !confirm("このイベントを削除しますか？")) return;
    try {
      const j = await getEventJwt(pid, "2020-01-01T00:00:00Z", "2035-01-01T00:00:00Z");
      await api("DELETE", "/event/events/" + id, null, j);
      status("イベントを削除しました", "ok");
      doLoad();
    } catch (e) {
      status("削除失敗: " + e.message, "err");
    }
  }

  // 種別フィルタ + 一括削除
  let typeFilter = $state("all");
  let selectedIds = $state({});

  const filteredEvents = $derived(
    events.filter(
      (e) => typeFilter === "all" || (e.event || e.type || e.name || "marker") === typeFilter
    )
  );

  function toggleAll() {
    const all = filteredEvents.map((e) => e.event_id || e.id);
    const on = all.length && all.every((id) => selectedIds[id]);
    const next = {};
    if (!on) all.forEach((id) => (next[id] = true));
    selectedIds = next;
  }

  async function doBulkDelete() {
    const ids = Object.keys(selectedIds).filter((id) => selectedIds[id]);
    const pid = listPid.trim() || consoleState.cfg.participant_id;
    if (!ids.length) {
      status("削除するイベントを選択してください", "err");
      return;
    }
    if (!confirm(`選択した ${ids.length} 件のイベントを削除しますか？`)) return;
    try {
      const j = await getEventJwt(pid, "2020-01-01T00:00:00Z", "2035-01-01T00:00:00Z");
      for (const id of ids) {
        await api("DELETE", "/event/events/" + id, null, j);
      }
      status(`${ids.length} 件のイベントを削除しました`, "ok");
      selectedIds = {};
      doLoad();
    } catch (e) {
      status("一括削除失敗: " + e.message, "err");
    }
  }
</script>

<div class="card">
  <h3>イベント一覧</h3>
  <div class="grid">
    <div class="field">
      <label>実験（任意）</label>
      <input bind:value={listExp} placeholder="登録済み実験 ID" />
    </div>
    <div class="field">
      <label>participant_id</label>
      <input bind:value={listPid} placeholder="21 文字の参加者 ID" />
    </div>
    <div class="field">
      <label>開始</label>
      <input type="datetime-local" bind:value={listStart} placeholder={nowMinus(1)} />
    </div>
    <div class="field">
      <label>終了</label>
      <input type="datetime-local" bind:value={listEnd} />
    </div>
  </div>
  <div class="row" style="margin:10px 0">
    <button onclick={doLoad}>読み込み</button>
    <select bind:value={typeFilter} style="padding:6px 10px;background:var(--input-bg);color:var(--text);border:1px solid var(--border);border-radius:6px">
      <option value="all">全種別</option>
      <option value="start">start</option>
      <option value="end">end</option>
      <option value="marker">marker</option>
      <option value="note">note</option>
    </select>
    {#if events.length}
      <button class="secondary" onclick={toggleAll}>
        {#if filteredEvents.length && filteredEvents.every((e) => selectedIds[e.event_id || e.id])}全解除{:else}全選択{/if}
      </button>
      <button class="danger" onclick={doBulkDelete}>選択を削除</button>
    {/if}
  </div>

  {#if filteredEvents.length}
    <div class="card sub">
      <h4>イベント一覧（{filteredEvents.length}/{events.length}）</h4>
      <table>
        <thead>
          <tr>
            <th style="width:32px">
              <input
                type="checkbox"
                checked={filteredEvents.length && filteredEvents.every((e) => selectedIds[e.event_id || e.id])}
                onchange={toggleAll}
              />
            </th>
            <th>種別</th>
            <th>実験</th>
            <th>開始（ローカル）</th>
            <th>終了（ローカル）</th>
            <th>説明</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {#each filteredEvents as e}
            <tr>
              <td>
                <input
                  type="checkbox"
                  checked={!!selectedIds[e.event_id || e.id]}
                  onchange={() => {
                    const id = e.event_id || e.id;
                    selectedIds[id] = !selectedIds[id];
                  }}
                />
              </td>
              <td>{e.name || e.event || e.type}</td>
              <td>{e.experiment_id || "—"}</td>
              <td>{fmtLocal(e.start_time || e.time)}</td>
              <td>{fmtLocal(e.end_time)}</td>
              <td>{e.description || e.detail || "—"}</td>
              <td><a class="link danger" onclick={() => doDelete(e.event_id || e.id)}>削除</a></td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {:else if events.length}
    <p class="hint" style="margin-top:8px">この種別のイベントはありません。</p>
  {/if}
</div>

<div class="card">
  <h3>新規イベント作成</h3>
  <div class="grid">
    <div class="field">
      <label>イベント種別</label>
      <input bind:value={newType} placeholder="例: start / marker / note" />
    </div>
    <div class="field">
      <label>実験（任意）</label>
      <input bind:value={newExp} placeholder="登録済み実験 ID" />
    </div>
    <div class="field">
      <label>開始時刻</label>
      <input type="datetime-local" bind:value={newStart} />
    </div>
    <div class="field">
      <label>終了時刻（任意、省略時 +1 秒）</label>
      <input type="datetime-local" bind:value={newEnd} />
    </div>
    <div class="field wide">
      <label>説明（任意）</label>
      <input bind:value={newDesc} />
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
    background: var(--accent-tint);
  }
  .link.danger {
    color: var(--danger, #f87171);
    cursor: pointer;
  }
</style>
