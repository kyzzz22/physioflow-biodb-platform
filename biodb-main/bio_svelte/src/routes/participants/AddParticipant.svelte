<script>
    import axios from "axios";

    let participantData = $state({
        email: "",
        name: "",
        sex: 0,
        birthdate: ""
    })
    let createTask = $state({
        isCreating: false,
        taskSuccess: false,
        message: "" // To hold success or error message
    })

    async function createParticipant() {
        createTask.isCreating = true
        createTask.message = ""
        try {
            const res = await axios.post("/auth/participant",
                participantData,
                {headers: { Authorization: `Bearer ${sessionStorage.getItem("manage_jwt")}`}}
            )
            createTask = {isCreating: false, taskSuccess: true, message: "実験協力者の追加に成功しました。"}
        }
        catch(err) {
            createTask = {isCreating: false, taskSuccess: false, message: "実験協力者の追加に失敗しました。コンソールを確認してください。"}
            console.error("Participant creation failed:", err);
        }
    }
</script>

<h2>実験協力者追加画面</h2>

<form class="participant-creation-form" onsubmit={createParticipant}>
    <div class="form-group">
        <label for="email">Email: </label>
        <input id="email" type="email" bind:value={participantData.email} required>
    </div>

    <div class="form-group">
        <label for="name">名前: </label>
        <input id="name" type="text" bind:value={participantData.name} required>
    </div>

    <div class="form-group">
        <label for="sex">性別: </label>
        <select id="sex" bind:value={participantData.sex}>
            <option value={0}>未選択</option>
            <option value={1}>男性</option>
            <option value={2}>女性</option>
            <option value={9}>その他</option>
        </select>
    </div>

    <div class="form-group">
        <label for="birthdate">誕生日: </label>
        <input id="birthdate" type="date" bind:value={participantData.birthdate} required>
    </div>

    <button type="submit" class="submit-button" disabled={createTask.isCreating}>
        {#if createTask.isCreating}
            <span class="spinner"></span> 追加中...
        {:else}
            実験協力者追加
        {/if}
    </button>
</form>

{#if !createTask.isCreating && createTask.message}
    <p class="status-message {createTask.taskSuccess ? 'success' : 'error'}">
        {createTask.message}
    </p>
{/if}


<style>
    h2 {
        color: var(--accent-color, #28a745);
        margin-bottom: 24px;
        font-size: 1.8rem;
        padding-bottom: 12px;
        border-bottom: 2px solid var(--accent-color, #28a745);
    }

    .participant-creation-form {
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

    input[type="text"],
    input[type="email"],
    input[type="date"],
    select {
        padding: 12px 15px;
        border-radius: 6px;
        border: 1px solid var(--border-color, #444);
        background-color: var(--background-color, #1a1a1a);
        color: var(--text-color, #e0e0e0);
        font-family: inherit;
        font-size: 1rem;
        transition: border-color 0.2s ease, box-shadow 0.2s ease;
    }

    input[type="text"]:focus,
    input[type="email"]:focus,
    input[type="date"]:focus,
    select:focus {
        outline: none;
        border-color: var(--accent-color, #28a745);
        box-shadow: 0 0 5px var(--accent-color, #28a745);
    }
    
    select {
        -webkit-appearance: none;
        -moz-appearance: none;
        appearance: none;
        background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%236b7280' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e");
        background-position: right 0.5rem center;
        background-repeat: no-repeat;
        background-size: 1.5em 1.5em;
        padding-right: 2.5rem;
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
        background-color: var(--link-hover-color, #34d399);
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

    @media (max-width: 600px) {
        .participant-creation-form {
            padding: 20px;
        }
    }
</style>