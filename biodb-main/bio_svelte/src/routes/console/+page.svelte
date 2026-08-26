<script>
  import Settings from "./Settings.svelte";
  import Overview from "./Overview.svelte";
  import DataBrowse from "./DataBrowse.svelte";
  import Events from "./Events.svelte";
  import Experiments from "./Experiments.svelte";
  import Analysis from "./Analysis.svelte";
  import Export from "./Export.svelte";
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

  let active = $state("overview");
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
  <div class="tabs">
    {#each tabs as t}
      <button
        class="tab"
        class:active={active === t.id}
        onclick={() => (active = t.id)}
      >
        {t.label}
      </button>
    {/each}
  </div>

  <div class="view">
    {#if active === "overview"}
      <Overview />
    {:else if active === "browse"}
      <DataBrowse />
    {:else if active === "events"}
      <Events />
    {:else if active === "experiments"}
      <Experiments />
    {:else if active === "analysis"}
      <Analysis />
    {:else if active === "export"}
      <Export />
    {:else if active === "settings"}
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
  .tabs {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 18px;
  }
  .tab {
    background: transparent;
    border: 1px solid var(--border-color, #3a3a3a);
    color: var(--muted-color, #9aa0a6);
    padding: 6px 14px;
    border-radius: 999px;
    cursor: pointer;
    font-size: 13px;
    transition: all 0.15s;
  }
  .tab:hover {
    border-color: var(--accent-color, #4c9aff);
    color: var(--text-color, #e5e7eb);
  }
  .tab.active {
    background: var(--accent-color, #4c9aff);
    border-color: var(--accent-color, #4c9aff);
    color: #fff;
  }
  .view {
    margin-top: 4px;
  }
  .status {
    position: fixed;
    bottom: 24px;
    right: 24px;
    padding: 10px 16px;
    border-radius: 8px;
    font-size: 13px;
    max-width: 420px;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
    z-index: 100;
  }
  .status.info {
    background: var(--accent-color, #4c9aff);
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
