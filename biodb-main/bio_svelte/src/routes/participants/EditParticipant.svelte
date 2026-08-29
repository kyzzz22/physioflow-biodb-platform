<script>
    import axios from 'axios';

    let { participant, onUpdateSuccess, onClose } = $props();

    // Create a local copy for editing to avoid directly mutating the prop
    let editableParticipant = $state({ ...participant });

    let updateTask = $state({
        isUpdating: false,
        message: '',
        isError: false
    });

    async function handleSubmit(event) {
        event.preventDefault();
        updateTask.isUpdating = true;
        updateTask.message = '';
        updateTask.isError = false;

        const updateData = {
            name: editableParticipant.name,
            sex: parseInt(editableParticipant.sex, 10),
            birthdate: editableParticipant.birthdate,
        };

        try {
            await axios.post(`/auth/participant/${participant.id}`, updateData, {
                headers: { Authorization: `Bearer ${sessionStorage.getItem("manage_jwt")}` }
            });
            updateTask.isUpdating = false;
            onUpdateSuccess(); // Call prop
        } catch (err) {
            console.error("Failed to update participant:", err);
            updateTask.isUpdating = false;
            updateTask.isError = true;
            updateTask.message = '更新に失敗しました。コンソールを確認してください。';
        }
    }

    function handleKeydown(event) {
        if (event.key === 'Escape') {
            onClose();
        }
    }
</script>

<svelte:window on:keydown={handleKeydown} />

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="popup-overlay" onclick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
    <div class="popup" role="dialog" aria-modal="true" aria-labelledby="dialog-title">
        <h3 id="dialog-title">実験協力者情報の編集</h3>
        <form onsubmit={handleSubmit}>
            <div class="form-group">
                <label for="name">名前:</label>
                <input id="name" type="text" bind:value={editableParticipant.name} required>
            </div>
            <div class="form-group">
                <label for="sex">性別:</label>
                <select id="sex" bind:value={editableParticipant.sex}>
                    <option value={0}>未選択</option>
                    <option value={1}>男性</option>
                    <option value={2}>女性</option>
                    <option value={9}>その他</option>
                </select>
            </div>
            <div class="form-group">
                <label for="birthdate">誕生日:</label>
                <input id="birthdate" type="date" bind:value={editableParticipant.birthdate} required>
            </div>

            {#if updateTask.message}
                <p class="status-message {updateTask.isError ? 'error' : ''}">{updateTask.message}</p>
            {/if}

            <div class="popup-actions">
                <button type="button" class="button-close" onclick={onClose} disabled={updateTask.isUpdating}>キャンセル</button>
                <button type="submit" class="button-save" disabled={updateTask.isUpdating}>
                    {#if updateTask.isUpdating}
                        <span class="spinner"></span> 保存中...
                    {:else}
                        保存
                    {/if}
                </button>
            </div>
        </form>
    </div>
</div>

<style>
    .popup-overlay {
        position: fixed; top: 0; left: 0; width: 100%; height: 100%;
        background: rgba(0, 0, 0, 0.75);
        display: flex; justify-content: center; align-items: center;
        z-index: 1000; backdrop-filter: blur(4px);
        padding: 15px;
    }
    .popup {
        background: var(--nav-background-color, #2c2c2c);
        color: var(--text-color, #e0e0e0);
        padding: 25px 30px;
        border-radius: 10px;
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.6);
        width: 100%;
        max-width: 550px;
        border: 1px solid var(--border-color, #444);
    }
    .popup h3 {
        color: var(--accent-color, #28a745);
        margin-top: 0; margin-bottom: 25px;
        font-size: 1.6rem; text-align: center;
    }
    .form-group {
        display: flex; flex-direction: column;
        gap: 8px; margin-bottom: 20px;
    }
    label {
        font-weight: 600; color: var(--text-color, #e0e0e0);
    }
    input, select {
        padding: 12px 15px; border-radius: 6px;
        border: 1px solid var(--border-color, #444);
        background-color: var(--background-color, #1a1a1a);
        color: var(--text-color, #e0e0e0);
        font-family: inherit; font-size: 1rem;
        transition: border-color 0.2s ease, box-shadow 0.2s ease;
    }
    input:focus, select:focus {
        outline: none; border-color: var(--accent-color, #28a745);
        box-shadow: 0 0 5px var(--accent-color, #28a745);
    }
    .popup-actions {
        display: flex; gap: 15px;
        justify-content: flex-end; margin-top: 25px;
    }
    .popup-actions button {
        border: none; padding: 10px 20px; border-radius: 6px;
        cursor: pointer; transition: background-color 0.2s ease;
        font-weight: 500;
        display: flex; align-items: center; gap: 8px;
    }
    .button-close { background-color: var(--border-color, #6c757d); color: white; }
    .button-close:hover:not(:disabled) { background-color: #5a6268; }
    .button-save { background-color: var(--accent-color, #28a745); color: white; }
    .button-save:hover:not(:disabled) { background-color: var(--link-hover-color, #34d399); }
    button:disabled { background-color: #555; color: #aaa; cursor: not-allowed; }

    .spinner {
        width: 1em; height: 1em; border: 2px solid currentColor;
        border-right-color: transparent; border-radius: 50%;
        animation: spinner-anim 0.8s linear infinite; display: inline-block;
    }
    @keyframes spinner-anim { to { transform: rotate(360deg); } }
    
    .status-message {
        text-align: center;
        padding: 10px;
        margin-top: 15px;
        border-radius: 6px;
        font-size: 0.95rem;
    }
    .status-message.error {
        color: var(--danger);
        background-color: var(--danger-tint);
        border: 1px solid rgba(248, 113, 113, 0.35);
    }
</style>