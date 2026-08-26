<script>
    import axios from "axios";
    import { onMount } from "svelte";

    let loadPromise = $state();

    let uName = $state('')
    let uBirthdate = $state('')
    let uSex = $state(0) // 数値型として扱う
    let isUpdating = $state(false)
    let updateMessage = $state({ type: '', text: '' })

    async function updateUserInfo() {
        isUpdating = true
        updateMessage = { type: '', text: '' }

        try {
            await axios.post(
                '/auth/user/info',
                { name: uName, sex: Number(uSex), birthdate: uBirthdate }, // uSexをNumberに変換
                { headers: { Authorization: `Bearer ${sessionStorage.getItem("manage_jwt")}` } }
            );
            updateMessage = { type: 'success', text: 'ユーザー情報の更新に成功しました．' }
        } catch (err) {
            console.error("Update error:", err); // エラー詳細をコンソールに出力
            let errorMessage = '更新に失敗しました．';
            if (err.response && err.response.data && err.response.data.message) {
                errorMessage += ` ${err.response.data.message}`;
            } else {
                errorMessage += 'もう一度お試しください．';
            }
            updateMessage = { type: 'error', text: errorMessage }
        } finally {
            isUpdating = false
        }
    }

    async function getUserInfo() {
        const res = await axios.get('/auth/user/info', {
            headers: { Authorization: `Bearer ${sessionStorage.getItem("manage_jwt")}` }
        })
        return res.data
    }

    onMount(() => {
        const promise = getUserInfo()
        promise.then(res => {
            uName = res.name || ''; // 初期値がnullの場合を考慮
            uSex = res.sex !== undefined ? res.sex : 0; // 初期値がnull/undefinedの場合を考慮
            uBirthdate = res.birthdate || ''; // 初期値がnullの場合を考慮
        }).catch(err => {
            console.error("Failed to load user info:", err);
            // ここでユーザーへのエラー表示も検討
        })
        loadPromise = promise
    });
</script>

{#if loadPromise}
    {#await loadPromise}
        <p class="status-message loading">ユーザー情報を読み込んでいます...</p>
    {:then res}
        <div class="user-info-container">
            <h2>ユーザー情報</h2>
            <form class="user-info-form" onsubmit={updateUserInfo}>
                <div class="form-group">
                    <label for="email">メールアドレス：</label>
                    <input id="email" type="email" readonly value={res.email}>
                </div>

                <div class="form-group">
                    <label for="id">ユーザID：</label>
                    <input id="id" type="text" readonly value={res.id}>
                </div>

                <div class="form-group">
                    <label for="name">名前：</label>
                    <input id="name" type="text" bind:value={uName} required placeholder="例：山田 太郎">
                </div>

                <div class="form-group">
                    <label for="sex">性別：</label>
                    <select id="sex" bind:value={uSex}>
                        <option value={0}>未選択</option>
                        <option value={1}>男性</option>
                        <option value={2}>女性</option>
                        <option value={9}>その他</option>
                    </select>
                </div>

                <div class="form-group">
                    <label for="birthdate">生年月日：</label>
                    <input id="birthdate" type="date" bind:value={uBirthdate}>
                </div>

                <button type="submit" class="submit-button" disabled={isUpdating}>
                    {#if isUpdating}
                        <span class="spinner"></span> 更新中...
                    {:else}
                        <svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="icon"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path><polyline points="17 21 17 13 7 13 7 21"></polyline><polyline points="7 3 7 8 15 8"></polyline></svg>
                        情報を更新
                    {/if}
                </button>
            </form>

            {#if updateMessage.text}
                <p class="status-message {updateMessage.type}">{updateMessage.text}</p>
            {/if}
        </div>
    {:catch err}
        <p class="status-message error">ユーザー情報の読み込みに失敗しました．セッションが切れている可能性があります．再度ログインしてください．</p>
    {/await}
{/if}

<style>
    .user-info-container {
        max-width: 700px; /* コンテナ全体の最大幅 */
        margin: 25px auto;
        padding: 20px;
        /* background-color: var(--background-color, #1a1a1a); */ /* 背景はメインエリアに依存 */
    }

    h2 {
        color: var(--accent-color, #28a745);
        margin-bottom: 24px;
        font-size: 1.8rem;
        padding-bottom: 12px;
        border-bottom: 2px solid var(--accent-color, #28a745);
        text-align: center; /* 中央揃え */
    }

    .user-info-form {
        display: flex;
        flex-direction: column;
        gap: 22px; /* 項目間の隙間 */
        padding: 25px; /* フォーム内のパディング */
        background-color: var(--nav-background-color, #2c2c2c);
        border-radius: 10px;
        border: 1px solid var(--border-color, #444);
        box-shadow: 0 6px 15px rgba(0,0,0,0.25);
    }

    .form-group {
        display: flex;
        flex-direction: column;
        gap: 8px;
    }

    label {
        font-weight: 600;
        color: var(--text-color, #e0e0e0);
        font-size: 1rem;
        margin-bottom: 2px; /* 既存のmargin-topを吸収し、少し下に隙間 */
    }

    input[type="email"],
    input[type="text"],
    input[type="date"],
    select {
        width: 100%;
        padding: 12px 15px;
        border-radius: 6px;
        border: 1px solid var(--border-color, #444);
        background-color: var(--background-color, #1a1a1a);
        color: var(--text-color, #e0e0e0);
        font-family: inherit;
        font-size: 1rem;
        box-sizing: border-box;
        transition: border-color 0.2s ease, box-shadow 0.2s ease;
    }

    input:read-only {
        background-color: var(--border-color, #3a3a3a);
        color: #a0a0a0; /* 少し濃いめのグレー */
        cursor: not-allowed;
        border-color: var(--border-color, #444); /* ボーダー色も統一 */
    }
    input:read-only:focus {
        box-shadow: none; /* readonlyはフォーカス時のハイライト不要 */
    }

    input:not(:read-only):focus,
    select:focus,
    input[type="date"]:focus {
        outline: none;
        border-color: var(--accent-color, #28a745);
        box-shadow: 0 0 0 3px rgba(var(--accent-color-rgb, 40, 167, 69), 0.25); /* var(--accent-color-rgb) が定義されている前提 */
        /* もし未定義なら: box-shadow: 0 0 5px var(--accent-color, #28a745); */
    }
    
    input[type="date"]::-webkit-calendar-picker-indicator {
        filter: invert(0.8) brightness(0.9); /* アイコンの色を調整 */
        cursor: pointer;
    }
    input[type="date"] { /* placeholderのスタイル */
        color-scheme: dark; /* カレンダーピッカーのUIをダークテーマに合わせる試み */
    }
    input[type="date"]:required:invalid::-webkit-datetime-edit {
        color: transparent; /* 日付未入力時に"yyyy/mm/dd"などが表示されないようにするChrome対策 */
    }
    input[type="date"]:required:invalid {
        color: var(--text-color, #e0e0e0); /* プレースホルダーテキストの色 (Firefoxなど) */
    }
    input[type="date"]:required:invalid:focus::-webkit-datetime-edit {
        color: var(--text-color, #e0e0e0); /* フォーカス時に再表示 */
    }


    select {
        appearance: none;
        background-image: url('data:image/svg+xml;charset=US-ASCII,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%22292.4%22%20height%3D%22292.4%22%3E%3Cpath%20fill%3D%22%23e0e0e0%22%20d%3D%22M287%2069.4a17.6%2017.6%200%200%200-13-5.4H18.4c-5%200-9.3%201.8-12.9%205.4A17.6%2017.6%200%200%200%200%2082.2c0%205%201.8%209.3%205.4%2012.9l128%20127.9c3.6%203.6%207.8%205.4%2012.8%205.4s9.2-1.8%2012.8-5.4L287%2095c3.5-3.5%205.4-7.8%205.4-12.8%200-5-1.9-9.4-5.4-13z%22%2F%3E%3C%2Fsvg%3E');
        background-repeat: no-repeat;
        background-position: right 15px center;
        background-size: 12px 12px;
        padding-right: 40px;
    }

    .submit-button {
        width: 100%;
        padding: 12px 20px;
        background-color: var(--accent-color, #28a745);
        color: #ffffff;
        border: none;
        border-radius: 6px;
        cursor: pointer;
        font-weight: 600;
        font-size: 1.05rem;
        transition: background-color 0.2s ease, opacity 0.2s ease, transform 0.1s ease;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        margin-top: 10px; /* 最後の要素との間に少しマージン */
        box-shadow: 0 2px 5px rgba(0,0,0,0.15);
    }
    .submit-button:hover:not(:disabled) {
        background-color: var(--link-hover-color, #34d399);
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
    .submit-button:active:not(:disabled) {
        transform: translateY(1px);
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
    }
    @keyframes spinner-anim {
        to { transform: rotate(360deg); }
    }

    .status-message {
        margin-top: 25px; /* フォームや他のメッセージとの間隔を確保 */
        padding: 15px 20px;
        border-radius: 6px;
        text-align: center;
        font-weight: 500;
        font-size: 1rem;
        /* max-width は user-info-form と合わせるか、コンテナに依存 */
    }
    .status-message.loading {
        color: var(--text-color, #e0e0e0);
        /* background-color: rgba(var(--accent-color-rgb, 40, 167, 69), 0.1); */
        /* border: 1px solid var(--accent-color, #28a745); */
    }
    .status-message.success {
        color: #155724; /* 既存の色を優先 */
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
    }
    .status-message.error {
        color: #721c24; /* 既存の色を優先 */
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
    }

</style>