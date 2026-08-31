<script>
  import { consoleState, saveCfg, hasCreds, getReadJwt, status } from "$lib/console-state.svelte.js";

  let user = $state(consoleState.cfg.user_id || "");
  let token = $state(consoleState.cfg.token || "");
  let pid = $state(consoleState.cfg.participant_id || "");
  let result = $state("");

  function doSave() {
    consoleState.cfg.user_id = user.trim();
    consoleState.cfg.token = token.trim();
    consoleState.cfg.participant_id = pid.trim();
    saveCfg();
    status("設定を保存しました", "ok");
  }

  async function doTest() {
    result = "接続テスト中…";
    if (!user.trim() || !token.trim() || !pid.trim()) {
      result = "user_id / token / participant_id をすべて入力してください";
      return;
    }
    try {
      const j = await getReadJwt(
        pid.trim(),
        new Date(Date.now() - 60000).toISOString(),
        new Date().toISOString()
      );
      if (j) result = "接続成功（read JWT 取得OK）";
    } catch (e) {
      result = "接続失敗: " + e.message;
    }
  }
</script>

<div class="card">
  <h3>接続設定</h3>
  <p class="hint">長期トークンの user_id / token / participant_id を設定します。設定はブラウザの localStorage に保存されます。</p>

  <div class="grid">
    <div class="field">
      <label for="settings-user">user_id（長期トークン所有者）</label>
      <input id="settings-user" bind:value={user} placeholder="WebUI トークン一覧の user_id" />
    </div>
    <div class="field">
      <label for="settings-token">長期トークン</label>
      <input id="settings-token" bind:value={token} type="password" placeholder="43〜44 文字" />
    </div>
    <div class="field">
      <label for="settings-participant">participant_id</label>
      <input id="settings-participant" bind:value={pid} placeholder="21 文字の参加者 ID" />
    </div>
  </div>

  <div class="row" style="margin-top:12px">
    <button onclick={doSave}>設定を保存</button>
    <button class="secondary" onclick={doTest}>接続テスト</button>
  </div>
  {#if result}
    <p class="hint" style="margin-top:8px">{result}</p>
  {/if}
  {#if hasCreds()}
    <p class="hint" style="color:var(--ok)">設定済み: {consoleState.cfg.user_id}</p>
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
</style>
