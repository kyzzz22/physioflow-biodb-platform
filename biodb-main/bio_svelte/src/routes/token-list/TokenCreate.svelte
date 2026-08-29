<script>
    import axios from "axios";

    let scopeAll = $state(true)
    let expirationDays = $state(30)
    let description = $state("")

    // createTokenPromise は未使用のためコメントアウトまたは削除を検討
    // let createTokenPromise = $state() 
    let createTokenTask = $state({isCreating: false, token: "", type: ""})
    let popupVisible = $state(false)

    async function createToken() {
        createTokenTask.isCreating = true
        createTokenTask.type = "" // 以前の結果をクリア
        try {
            const res = await axios.post('/auth/token',
                {
                    scopes: [scopeAll ? "all" : ""], // "all"以外は空文字で良いか確認
                    expiration_days: parseInt(expirationDays, 10), // 数値型で送信
                    description: description
                },
                {headers: { Authorization: `Bearer ${sessionStorage.getItem("manage_jwt")}`}}
            )
            if (res.data && res.data.token) { // レスポンスデータの存在確認
                createTokenTask.token = res.data.token
                createTokenTask.type = "success"
                popupVisible = true
            } else {
                // トークンがレスポンスに含まれない場合のエラー処理
                createTokenTask.type = "error";
                console.error("Token not found in response:", res);
            }
        }
        catch(err) { // エラーオブジェクトをキャッチして詳細を確認できるようにする
            createTokenTask.type = "error"
            console.error("Token creation failed:", err);
        }
        finally {
            createTokenTask.isCreating = false
        }
        // res.data.token を返す必要性は要確認 (関数の呼び出し元で使っているか)
        // return res.data.token 
    }
</script>

<h2>トークン作成</h2>

<form class="token-creation-form" onsubmit={createToken}>
    <div class="form-group">
        <label for="scopeAll">スコープ(ALL)：</label>
        <div class="checkbox-wrapper">
            <input type="checkbox" id="scopeAll" bind:checked={scopeAll} disabled>
            <span>(現在は"all"固定です)</span>
        </div>
    </div>

    <div class="form-group">
        <label for="expiration">有効期限(日数)：{expirationDays}日</label>
        <input id="expiration" type="range" min={1} max={365} bind:value={expirationDays}>
    </div>

    <div class="form-group">
        <label for="description">説明(オプション)：</label>
        <textarea id="description" placeholder="例：開発環境用APIキー" bind:value={description}></textarea>
    </div>

    <button type="submit" class="submit-button" disabled={createTokenTask.isCreating}>
        {#if createTokenTask.isCreating}
            <span class="spinner"></span> トークン作成中...
        {:else}
            トークン作成
        {/if}
    </button>
</form>

{#if !createTokenTask.isCreating}
    {#if createTokenTask.type === "success"}
        <p class="status-message success">トークン作成成功</p>
    {:else if createTokenTask.type === "error"}
        <p class="status-message error">トークン作成失敗．コンソールを確認するか，時間を置いて再試行してください．</p>
    {/if}
{/if}


{#if popupVisible}
    <div class="popup-overlay">
        <div class="popup">
            <h3>トークンが作成されました！</h3>
            <p>以下のトークンを安全な場所にコピーして保管してください。この画面を閉じると再表示できません。</p>
            <div class="token-display-wrapper">
                <input type="text" readonly value={createTokenTask.token} class="token-output-field"/>
                <div class="popup-actions">
                    <button class="button-copy" onclick={() => {navigator.clipboard.writeText(createTokenTask.token)}}>コピー</button>
                    <button class="button-close" onclick={() => {popupVisible = false}}>閉じる</button>
                </div>
            </div>
        </div>
    </div>
{/if}


<style>

    h2 {
        color: var(--accent-color, #28a745);
        margin-bottom: 24px;
        font-size: 1.8rem;
        padding-bottom: 12px;
        border-bottom: 2px solid var(--accent-color, #28a745);
    }

    .token-creation-form {
        display: flex;
        flex-direction: column;
        gap: 25px; /* 項目間の隙間 */
        max-width: 650px; /* フォームの最大幅 */
        margin: 20px auto; /* 上下にも少しマージン */
        padding: 30px;
        background-color: var(--nav-background-color, #2c2c2c);
        border-radius: 10px; /* 角丸を少し大きく */
        border: 1px solid var(--border-color, #444);
        box-shadow: 0 6px 15px rgba(0,0,0,0.25);
    }

    .form-group {
        display: flex;
        flex-direction: column;
        gap: 8px; /* ラベルと入力要素の間の隙間 */
    }

    label {
        font-weight: 600; /* 少し太字に */
        color: var(--text-color, #e0e0e0);
        font-size: 1rem;
    }

    .checkbox-wrapper {
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .checkbox-wrapper span {
        font-size: 0.85rem;
        color: #aaa; /* 説明文の色を少し薄く */
    }

    input[type="checkbox"] {
        accent-color: var(--accent-color, #28a745);
        width: 18px; /* サイズ調整 */
        height: 18px;
        cursor: pointer; /* disabled時はCSSで not-allowed が優先される */
    }
    input[type="checkbox"]:disabled {
        opacity: 0.6;
        cursor: not-allowed;
    }

    input[type="range"] {
        width: 100%;
        accent-color: var(--accent-color, #28a745);
        cursor: pointer;
        background: transparent; /* デフォルトの背景を透明に */
        margin-top: 5px;
    }
    input[type="range"]::-webkit-slider-runnable-track {
        width: 100%;
        height: 10px;
        cursor: pointer;
        background: var(--border-color, #555); /* トラックの背景色 */
        border-radius: 5px;
    }
    input[type="range"]::-webkit-slider-thumb {
        -webkit-appearance: none;
        appearance: none;
        width: 22px;
        height: 22px;
        background: var(--accent-color, #28a745);
        border-radius: 50%;
        cursor: pointer;
        margin-top: -6px; /* トラックの中央に配置 */
        border: 2px solid var(--nav-background-color, #2c2c2c); /* つまみに枠線 */
    }
    input[type="range"]::-moz-range-track {
        width: 100%;
        height: 10px;
        cursor: pointer;
        background: var(--border-color, #555);
        border-radius: 5px;
    }
    input[type="range"]::-moz-range-thumb {
        width: 18px; /* Webkitより少し小さめ */
        height: 18px;
        background: var(--accent-color, #28a745);
        border-radius: 50%;
        cursor: pointer;
        border: 2px solid var(--nav-background-color, #2c2c2c);
    }


    textarea {
        min-height: 100px; /* 最小高さを設定 */
        padding: 12px 15px;
        border-radius: 6px;
        border: 1px solid var(--border-color, #444);
        background-color: var(--background-color, #1a1a1a);
        color: var(--text-color, #e0e0e0);
        font-family: inherit;
        font-size: 1rem;
        resize: vertical;
        transition: border-color 0.2s ease, box-shadow 0.2s ease;
    }
    textarea:focus {
        outline: none;
        border-color: var(--accent-color, #28a745);
        /* box-shadow: 0 0 0 3px rgba(var(--accent-color-rgb, 40, 167, 69), 0.25); */
        /* --accent-color-rgb を定義していれば上記を使用。なければ以下のような単純なものに */
        box-shadow: 0 0 5px var(--accent-color, #28a745);
    }

    .submit-button {
        background-color: var(--accent-color, #28a745);
        color: #ffffff;
        border: none;
        padding: 12px 20px;
        border-radius: 6px;
        cursor: pointer;
        transition: background-color 0.2s ease, opacity 0.2s ease;
        font-weight: 600;
        font-size: 1.05rem;
        margin-top: 10px;
        display: flex; /* スピナーとテキストを中央揃え */
        align-items: center;
        justify-content: center;
        gap: 8px; /* スピナーとテキストの間 */
    }
    .submit-button:hover:not(:disabled) {
        background-color: var(--link-hover-color, #34d399); /* --link-hover-color は前回定義 */
    }
    .submit-button:disabled {
        background-color: #555;
        color: #aaa;
        cursor: not-allowed;
        opacity: 0.8;
    }

    .spinner {
        width: 1em;
        height: 1em;
        border: 2px solid currentColor;
        border-right-color: transparent;
        border-radius: 50%;
        animation: spinner-anim 0.8s linear infinite;
        display: inline-block;
    }
    @keyframes spinner-anim {
        to { transform: rotate(360deg); }
    }


    .status-message {
        margin-top: 20px;
        padding: 15px 20px;
        border-radius: 6px;
        text-align: center;
        font-weight: 500;
        font-size: 1rem;
        max-width: 650px;
        margin-left: auto;
        margin-right: auto;
    }
    .status-message.success {
        color: var(--accent-hover);
        background-color: var(--accent-tint);
        border: 1px solid var(--accent-tint-strong);
    }
    .status-message.error {
        color: var(--danger);
        background-color: var(--danger-tint);
        border: 1px solid rgba(248, 113, 113, 0.35);
    }


    .popup-overlay {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.75); /* 少し濃く */
        display: flex;
        justify-content: center;
        align-items: center;
        z-index: 1000;
        backdrop-filter: blur(4px); /* ぼかしを少し強く */
        padding: 15px; /* スマホ用に左右にパディング */
    }

    .popup {
        background: var(--nav-background-color, #2c2c2c);
        color: var(--text-color, #e0e0e0);
        padding: 25px 30px;
        border-radius: 10px;
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.6); /* 影を強調 */
        text-align: left; /* ポップアップ内は左揃えを基本に */
        width: 100%;
        max-width: 550px;
        border: 1px solid var(--border-color, #444);
    }

    .popup h3 {
        color: var(--accent-color, #28a745);
        margin-top: 0;
        margin-bottom: 15px;
        font-size: 1.6rem;
        text-align: center; /* 見出しは中央揃え */
    }

    .popup p {
        margin-bottom: 20px; /* 説明文のマージン */
        font-size: 1rem;
        line-height: 1.7;
    }

    .token-display-wrapper {
        margin-top: 15px;
    }
    
    .token-output-field {
        width: 100%;
        padding: 12px;
        font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace;
        background-color: var(--background-color, #1a1a1a);
        color: var(--text-color, #e0e0e0);
        border: 1px solid var(--border-color, #444);
        border-radius: 6px;
        margin-bottom: 15px;
        box-sizing: border-box; /* パディングとボーダーを幅に含める */
        font-size: 0.95rem;
        word-break: break-all;
    }
    .token-output-field:focus {
        outline: none;
        border-color: var(--accent-color, #28a745);
    }

    .popup-actions {
        display: flex;
        gap: 15px;
        justify-content: flex-end; /* ボタンを右寄せに */
        margin-top: 20px;
    }

    .popup-actions button {
        color: #ffffff;
        border: none;
        padding: 10px 20px;
        border-radius: 6px;
        cursor: pointer;
        transition: background-color 0.2s ease, opacity 0.2s ease;
        font-weight: 500;
        font-size: 0.95rem;
    }
    .popup-actions button:hover {
        opacity: 0.85;
    }

    .button-copy {
        background-color: var(--accent-color, #28a745);
    }
    .button-close {
        background-color: var(--border-color, #6c757d); /* グレー系の色 */
    }
    .button-close:hover {
        background-color: #5a6268;
    }

    /* レスポンシブ対応 */
    @media (max-width: 600px) {
        .token-creation-form {
            padding: 20px;
        }
        .popup {
            padding: 20px;
        }
        .popup h3 {
            font-size: 1.4rem;
        }
        .popup p {
            font-size: 0.95rem;
        }
        .popup-actions {
            flex-direction: column; /* スマホではボタンを縦積みに */
            gap: 10px;
        }
        .popup-actions button {
            width: 100%; /* ボタン幅を100%に */
        }
    }

</style>