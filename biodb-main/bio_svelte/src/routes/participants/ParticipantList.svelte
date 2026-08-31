<script>
    import { onMount } from "svelte";
    import axios from "axios";
    import EditParticipant from './EditParticipant.svelte';

    let participantLoadPromise = $state()
    let isEditModalOpen = $state(false)
    let currentParticipant = $state(null)

    function openEditModal(participant) {
        currentParticipant = participant
        isEditModalOpen = true
    }

    function handleUpdateSuccess() {
        isEditModalOpen = false
        currentParticipant = null
        participantLoadPromise = getParticipants()
    }

    function formatDate(dateString) {
        if (!dateString) return 'N/A'
        const date = new Date(dateString)
        return date.toLocaleDateString('ja-JP', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
        })
    }

    function getGenderText(sex) {
        switch (sex) {
            case 1: return '男性'
            case 2: return '女性'
            case 9: return 'その他'
            default: return '未選択'
        }
    }

    async function getParticipants() {
        const response = await axios.get('/auth/participant', {
            headers: { Authorization: `Bearer ${sessionStorage.getItem("manage_jwt")}` }
        })
        return response.data.participants
    }

    async function toggleParticipantStatus(participant) {
        const updatedStatus = !participant.is_enable
        try {
            await axios.post(`/auth/participant/${participant.id}`, {
                is_enable: updatedStatus
            }, {
                headers: { Authorization: `Bearer ${sessionStorage.getItem("manage_jwt")}` }
            })
            participantLoadPromise = getParticipants()
        } catch (err) {
            console.error("Participant status toggle failed:", err)
            alert('状態の更新に失敗しました。')
        }
    }

    onMount(() => {
        participantLoadPromise = getParticipants()
    })
</script>

<h2>実験協力者リスト</h2>

{#if participantLoadPromise}
    {#await participantLoadPromise}
        <p class="status-message loading">Now Loading...</p>
    {:then participants}
        {#if participants && participants.length > 0}
            <ul class="participant-list">
                {#each participants as participant (participant.id)}
                    <li class="participant-item">
                        <div class="participant-info">
                            <p><strong>ID:</strong> {participant.id}</p>
                            <p><strong>Email:</strong> {participant.email}</p>
                            <p><strong>名前:</strong> {participant.name || 'N/A'}</p>
                            <p><strong>性別:</strong> {getGenderText(participant.sex)}</p>
                            <p><strong>生年月日:</strong> {formatDate(participant.birth_date)}</p>
                            <p><strong>状態:</strong> <span class={participant.is_enable ? 'status-active' : 'status-inactive'}>{participant.is_enable ? '有効' : '無効'}</span></p>
                        </div>
                        <div class="participant-actions">
                            <button class="button-edit" onclick={() => openEditModal(participant)}>編集</button>
                            <button class="button-toggle" onclick={() => toggleParticipantStatus(participant)}>
                                {participant.is_enable ? '無効化' : '有効化'}
                            </button>
                        </div>
                    </li>
                {/each}
            </ul>
        {:else}
            <p class="status-message empty">登録されている実験協力者はいません</p>
        {/if}
    {:catch err}
        <p class="status-message error">セッションタイム切れ、またはエラーが発生しました。ログインし直してください。</p>
    {/await}
{/if}

{#if isEditModalOpen}
    <EditParticipant
        participant={currentParticipant}
        onClose={() => isEditModalOpen = false}
        onUpdateSuccess={handleUpdateSuccess}
    />
{/if}

<style>
    h2 {
        color: var(--accent-color, #28a745);
        margin-bottom: 24px;
        font-size: 1.8rem;
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

    .status-message.empty {
        color: var(--text-color, #e0e0e0);
        font-style: italic;
    }

    .participant-list {
        list-style: none;
        padding: 0;
        margin: 0;
    }

    .participant-item {
        background-color: var(--nav-background-color, #2c2c2c);
        border: 1px solid var(--border-color, #444);
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 20px;
        display: flex;
        flex-direction: column;
        gap: 15px;
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
        transition: box-shadow 0.3s ease, border-color 0.3s ease;
    }

    .participant-item:hover {
        box-shadow: 0 6px 12px rgba(0, 0, 0, 0.3);
        border-color: var(--accent-color, #28a745);
    }

    .participant-info p {
        margin: 0 0 10px 0;
        color: var(--text-color, #e0e0e0);
        line-height: 1.6;
        word-break: break-all;
    }

    .participant-info p:last-child {
        margin-bottom: 0;
    }

    .participant-info strong {
        color: var(--accent-color, #28a745);
        margin-right: 8px;
        font-weight: 600;
    }

    .status-active {
        color: var(--accent-color, #28a745);
        font-weight: bold;
    }

    .status-inactive {
        color: #aaa;
        font-weight: bold;
    }

    .participant-actions {
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
        margin-top: 10px;
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

    .button-edit {
        background-color: var(--accent);
    }
    .button-edit:hover {
        background-color: var(--accent-hover);
    }

    .button-toggle {
        background-color: var(--accent-color, #28a745);
    }

    @media (min-width: 600px) {
        .participant-item {
            flex-direction: row;
            justify-content: space-between;
            align-items: flex-start;
        }

        .participant-info {
            flex-grow: 1;
        }

        .participant-actions {
            margin-top: 0;
            flex-direction: column;
            align-items: flex-end;
            min-width: 120px;
        }
        .participant-actions button {
            width: 100%;
        }
        .participant-actions button:not(:last-child) {
             margin-bottom: 8px;
        }
    }
</style>
