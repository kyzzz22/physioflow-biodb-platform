<script>
  import Settings from "./Settings.svelte";
  import Overview from "./Overview.svelte";
  import DataBrowse from "./DataBrowse.svelte";
  import Events from "./Events.svelte";
  import Experiments from "./Experiments.svelte";
  import Analysis from "./Analysis.svelte";
  import Export from "./Export.svelte";
  import ContextBar from "./ContextBar.svelte";
  import { consoleState } from "$lib/console-state.svelte.js";

  const tabs = [
    { id: "overview", label: "棚卸し" },
    { id: "browse", label: "データ閲覧" },
    { id: "events", label: "イベント" },
    { id: "experiments", label: "実験登録" },
    { id: "analysis", label: "分析" },
    { id: "export", label: "エクスポート" },
    { id: "settings", label: "接続設定" },
  ];

  let statusVisible = $state(false);

  $effect(() => {
    if (consoleState.status) {
      statusVisible = true;
      const t = setTimeout(() => (statusVisible = false), 6000);
      return () => clearTimeout(t);
    }
  });
</script>

<svelte:head>
  <title>BioDB コンソール</title>
</svelte:head>

<div class="console">
  <h1 class="page-title">BioDB コンソール</h1>

  <div class="tabs">
    {#each tabs as t}
      <button
        class="tab"
        class:active={consoleState.activeTab === t.id}
        onclick={() => (consoleState.activeTab = t.id)}
      >
        {t.label}
      </button>
    {/each}
  </div>

  {#if consoleState.activeTab !== "settings" && consoleState.activeTab !== "overview"}
    <ContextBar />
  {/if}

  <div class="view">
    {#if consoleState.activeTab === "overview"}
      <Overview />
    {:else if consoleState.activeTab === "browse"}
      <DataBrowse />
    {:else if consoleState.activeTab === "events"}
      <Events />
    {:else if consoleState.activeTab === "experiments"}
      <Experiments />
    {:else if consoleState.activeTab === "analysis"}
      <Analysis />
    {:else if consoleState.activeTab === "export"}
      <Export />
    {:else if consoleState.activeTab === "settings"}
      <Settings />
    {/if}
  </div>

  {#if statusVisible}
    <div class="status {consoleState.statusType}">
      {consoleState.status}
    </div>
  {/if}
</div>

<style>
  .console {
    max-width: 1100px;
    margin: 0 auto;
    padding: 20px;
  }
  .page-title {
    margin: 0 0 14px;
    font-size: 1.4rem;
  }
  /* 矩形 tab — /db/ と統一 */
  .tabs {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-bottom: 18px;
    padding: 8px 12px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
  }
  .tab {
    background: transparent;
    border: 1px solid transparent;
    color: var(--muted);
    padding: 6px 16px;
    border-radius: var(--radius-sm);
    cursor: pointer;
    font-size: 13px;
  }
  .tab:hover {
    background: var(--surface-2);
    color: var(--text);
    border-color: var(--border);
  }
  .tab.active {
    background: var(--accent);
    border-color: var(--accent);
    color: #fff;
  }
  .view {
    margin-top: 4px;
  }
  .status {
    position: fixed;
    bottom: 16px;
    left: 50%;
    transform: translateX(-50%);
    padding: 10px 16px;
    border-radius: 8px;
    font-size: 13px;
    max-width: 420px;
    box-shadow: var(--shadow);
    z-index: 100;
  }
  .status.info {
    background: var(--accent-color);
    color: #fff;
  }
  .status.ok {
    background: #16a34a;
    color: #fff;
  }
  .status.err {
    background: #dc2626;
    color: #fff;
  }
</style>
