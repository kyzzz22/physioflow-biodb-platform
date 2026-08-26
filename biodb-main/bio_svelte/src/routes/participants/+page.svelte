<script>
    import ParticipantList from "./ParticipantList.svelte";
    import AddParticipant from "./AddParticipant.svelte";

    let isAddPage = $state(false)
</script>

<div class="view-controller">
    <button class="toggle-button" onclick={() => {isAddPage = !isAddPage}}>
        {#if isAddPage}
            <svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="icon"><polyline points="15 18 9 12 15 6"></polyline></svg>
            リストに戻る
        {:else}
            <svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="icon"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
            実験協力者追加
        {/if}
    </button>
</div>

<div class="component-display">
    {#if isAddPage}
        <AddParticipant></AddParticipant>
    {:else}
        <ParticipantList></ParticipantList>
    {/if}
</div>

<style>
    .view-controller {
        margin-bottom: 25px; /* ボタンと下記コンポーネント間のマージン */
        /* text-align: right; */ /* ボタンを右寄せにしたい場合など */
    }

    .toggle-button {
        background-color: var(--accent-color, #28a745);
        color: #ffffff;
        border: none;
        padding: 12px 22px; /* パディングを少し調整 */
        border-radius: 8px; /* 角丸を少し大きく */
        cursor: pointer;
        transition: background-color 0.2s ease, box-shadow 0.2s ease, transform 0.1s ease;
        font-weight: 600; /* 少し太字に */
        font-size: 1rem;
        display: inline-flex; /* アイコンとテキストを中央揃え */
        align-items: center;
        gap: 8px; /* アイコンとテキストの間隔 */
        box-shadow: 0 2px 5px rgba(0,0,0,0.15);
    }

    .toggle-button:hover {
        background-color: var(--link-hover-color, #34d399);
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }

    .toggle-button:active {
        transform: translateY(1px);
        box-shadow: 0 2px 4px rgba(0,0,0,0.15);
    }
</style>