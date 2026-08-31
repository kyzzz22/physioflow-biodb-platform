<script>
    import { onMount } from "svelte";
    import { apiRequest } from "$lib/api-client.js";

    let tokenPromise = $state()
    let actionMessage = $state({ type: "", text: "" })
    
    function formatDate(dateString){
        const date = new Date(dateString)
        return date.toLocaleString('ja-JP', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            timeZoneName: 'short'
        })
    }

    async function fetchToken() {
        const response = await apiRequest('/auth/token')
        return response.tokens
    }

    async function deleteToken(tokenId) {
        actionMessage = { type: "", text: "" }
        try {
            await apiRequest(`/auth/token/${tokenId}`, { method: "DELETE" })
            actionMessage = { type: "success", text: "トークンを削除しました。" }
        }
        catch(err) {
            actionMessage = { type: "error", text: err.message }
        }
        tokenPromise = fetchToken()
    }

    async function toggleActiveToken(tokenId) {
        actionMessage = { type: "", text: "" }
        const tokens = await tokenPromise
        const token = tokens.find((t) => t.token_id === tokenId)
        if (!token) return; // トークンが見つからない場合は何もしない
        const updatedStatus = !(token.is_active)
        try {
            await apiRequest(`/auth/token/${tokenId}`, {
                method: "POST",
                body: { is_active: updatedStatus },
            })
            actionMessage = { type: "success", text: "トークンの状態を更新しました。" }
        }
        catch(err) {
            actionMessage = { type: "error", text: err.message }
        }
        tokenPromise = fetchToken()
    }

    onMount(() => {
        tokenPromise = fetchToken()
    })
</script>

<h2>トークンリスト</h2>

{#if actionMessage.text}
    <p class="status-message {actionMessage.type}">{actionMessage.text}</p>
{/if}

{#if tokenPromise}
    {#await tokenPromise}
        <p class="status-message loading">Now Loading...</p>
    {:then tokens}
        {#if tokens && tokens.length > 0}
            <ul class="token-list">
                {#each tokens as token (token.token_id)}
                    <li class="token-item">
                        <div class="token-info">
                            <p><strong>ID：</strong> {token.token_id}</p>
                            <p><strong>説明：</strong> {token.description || 'なし'}</p>
                            <p><strong>作成日：</strong> {formatDate(token.created_at)}</p>
                            <p><strong>有効期限：</strong> {formatDate(token.expired_at)}</p>
                            <p><strong>状態：</strong> <span class={token.is_active ? 'status-active' : 'status-inactive'}>{token.is_active ? 'アクティブ' : '非アクティブ'}</span></p>
                            <p><strong>スコープ：</strong> {token.scopes.join(', ')}</p>
                        </div>
                        <div class="token-actions">
                            <button class="button-toggle" onclick={() => {toggleActiveToken(token.token_id)}}>
                                {token.is_active ? '非アクティブ化' : 'アクティブ化'}
                            </button>
                            <button class="button-delete" onclick={() => {deleteToken(token.token_id)}}>削除</button>
                        </div>
                    </li>
                {/each}
            </ul>
        {:else}
            <p class="status-message empty">利用可能なトークンはありません</p>
        {/if}
    {:catch error}
        <p class="status-message error">セッションタイム切れ，またはエラーが発生しました．ログインし直してください．</p>
    {/await}
{/if}

<style>
    /* このSvelteコンポーネント固有のスタイル */
    /* :global() を使って親のCSS変数を参照することもできるが、通常は不要 */

    h2 {
        color: var(--accent-color, #28a745); /* フォールバックカラーを指定 */
        margin-bottom: 24px;
        font-size: 1.8rem; /* emからremに変更 */
        padding-bottom: 12px;
        border-bottom: 2px solid var(--accent-color, #28a745);
    }

    .status-message {
        text-align: center;
        padding: 25px;
        margin-top: 25px;
        border-radius: 6px;
        font-size: 1.1rem;
    }

    .status-message.loading {
        color: var(--text-color, #e0e0e0);
    }

    .status-message.error {
        background-color: var(--danger-tint);
        color: var(--danger);
        border: 1px solid rgba(248, 113, 113, 0.35);
    }
    .status-message.success {
        color: var(--ok-text);
        background: var(--accent-tint);
        border: 1px solid var(--accent-tint-strong);
    }

    .status-message.empty {
        color: var(--text-color, #e0e0e0);
        font-style: italic;
    }

    .token-list {
        list-style: none;
        padding: 0;
        margin: 0;
    }

    .token-item {
        background-color: var(--nav-background-color, #2c2c2c);
        border: 1px solid var(--border-color, #444);
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 20px;
        display: flex; /* 情報とアクションボタンを横並びにする */
        flex-direction: column; /* デフォルトは縦積み */
        gap: 15px; /* 要素間の隙間 */
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
        transition: box-shadow 0.3s ease;
    }

    .token-item:hover {
        box-shadow: 0 6px 12px rgba(0, 0, 0, 0.3);
    }

    .token-info p {
        margin: 0 0 10px 0;
        color: var(--text-color, #e0e0e0);
        line-height: 1.6;
    }

    .token-info p:last-child {
        margin-bottom: 0;
    }

    .token-info strong {
        color: var(--accent-color, #28a745);
        margin-right: 8px;
        font-weight: 600;
    }

    .status-active {
        color: var(--accent-color, #28a745);
        font-weight: bold;
    }

    .status-inactive {
        color: #aaa; /* 非アクティブ状態の色を少し抑えめに */
        font-weight: bold;
    }

    .token-actions {
        display: flex;
        gap: 10px; /* ボタン間の隙間 */
        flex-wrap: wrap; /* ボタンがはみ出たら折り返す */
        margin-top: 10px; /* 情報エリアとの間に少しマージン */
    }

    button {
        color: #ffffff;
        border: none;
        padding: 10px 18px;
        border-radius: 5px;
        cursor: pointer;
        transition: background-color 0.2s ease, transform 0.1s ease;
        font-weight: 500;
        font-size: 0.95rem;
    }

    button:hover {
        opacity: 0.85;
    }

    button:active {
        transform: translateY(1px);
    }

    .button-toggle {
        background-color: var(--accent-color, #28a745);
    }

    .button-delete {
        background-color: var(--danger-bg); /* 削除ボタンは赤系 */
    }
    .button-delete:hover {
        background-color: var(--danger);
    }

    /* レスポンシブ調整: カード内で情報とアクションが横並びになるように */
    @media (min-width: 600px) {
        .token-item {
            flex-direction: row; /* 幅が600px以上なら情報とアクションを横並び */
            justify-content: space-between; /* 両端に配置 */
            align-items: flex-start; /* 上揃え */
        }

        .token-info {
            flex-grow: 1;
        }

        .token-actions {
            margin-top: 0; /* 横並び時は上のマージン不要 */
            flex-direction: column; /* ボタンを縦に積む場合 */
            align-items: flex-end; /* 右寄せ */
            min-width: 150px; /* アクションエリアの最小幅 */
        }
        .token-actions button {
            width: 100%; /* ボタンの幅をアクションエリアに合わせる */
        }
        .token-actions button:not(:last-child) {
             margin-bottom: 8px; /* 縦積みボタン間のマージン */
        }
    }

</style>
