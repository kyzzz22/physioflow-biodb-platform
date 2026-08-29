<script>
    let { children } = $props()
    import "$lib/global.css";
</script>

<div class="all">
    <nav>
        <div class="brand">BioDB</div>
        <a href="./login">login</a>
        <a href="./user-info">ユーザ情報</a>
        <a href="./token-list">トークンリスト</a>
        <a href="./participants">実験協力者</a>
        <a href="./console">コンソール</a>
    </nav>

    <div class="main">
        {@render children()}
    </div>
</div>


<style>
    /* 統一テーマ token — webui-theme/theme.css と同期する（dev モードでは nginx が無いため内聯） */
    :root {
        /* --- Surfaces --- */
        --bg: #1a1a1a;
        --surface: #2c2c2c;
        --surface-2: #262626;
        --input-bg: #1e1e1e;
        --border: #444;
        --border-strong: #5a5a5a;

        /* --- Text --- */
        --text: #e0e0e0;
        --text-strong: #ffffff;
        --muted: #9aa0a6;

        /* --- Accent (green) --- */
        --accent: #28a745;
        --accent-hover: #34d399;
        --accent-rgb: 40, 167, 69;
        --accent-tint: rgba(40, 167, 69, 0.12);
        --accent-tint-strong: rgba(40, 167, 69, 0.22);

        /* --- Status --- */
        --ok: #16a34a;
        --ok-text: #4ade80;
        --danger: #f87171;
        --danger-bg: #dc2626;
        --danger-tint: rgba(248, 113, 113, 0.12);
        --warning: #fbbf24;

        /* --- Focus / selection / scrollbar --- */
        --focus-ring: 0 0 0 3px rgba(40, 167, 69, 0.35);
        --selection-bg: rgba(40, 167, 69, 0.35);

        /* --- Radii --- */
        --radius-sm: 6px;
        --radius: 8px;
        --radius-lg: 10px;
        --radius-pill: 999px;

        /* --- Shadows --- */
        --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.25);
        --shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
        --shadow-lg: 0 8px 25px rgba(0, 0, 0, 0.6);

        /* --- Fonts --- */
        --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", "Hiragino Sans",
                     "Noto Sans JP", "Microsoft YaHei", sans-serif;
        --font-mono: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;

        /* --- Layout --- */
        --content-max: 1100px;
        --pad-page: 24px;
        --pad-card: 16px;

        /* --- Chart palette (keep in sync with webui-theme/theme.css --chart-*) --- */
        --chart-1: #60a5fa;
        --chart-2: #f87171;
        --chart-3: #34d399;
        --chart-4: #fbbf24;
        --chart-5: #a78bfa;
        --chart-6: #22d3ee;
        --chart-7: #f472b6;
        --chart-8: #a3e635;
        --event-start: #34d399;
        --event-end: #f87171;
        --event-marker: #fbbf24;
        --event-note: #a78bfa;

        /* --- Svelte aliases (既存コンポーネントの var() を解決) --- */
        --background-color: var(--bg);
        --text-color: var(--text);
        --accent-color: var(--accent);
        --accent-color-rgb: var(--accent-rgb);
        --nav-background-color: var(--surface);
        --link-hover-color: var(--accent-hover);
        --border-color: var(--border);
        --muted-color: var(--muted);
        --card-bg: var(--surface-2);
    }

    :global(html) {
        background: var(--background-color);
    }

    :global(body) {
        background: var(--background-color);
        color: var(--text-color);
        font-family: var(--font-sans);
        line-height: 1.6;
    }

    .all {
        display: flex;
        min-height: 100vh; /* 画面全体の高さを使用 */
    }

    nav {
        background-color: var(--nav-background-color);
        width: 250px; /* ナビゲーションの幅を少し広めに */
        padding: 20px;
        border-right: 1px solid var(--border-color);
        display: flex;
        flex-direction: column; /* リンクを縦に並べる */
        transition: width 0.3s ease; /* スムーズな幅変更アニメーション */
    }

    .brand {
        font-weight: 700;
        font-size: 1.1rem;
        color: var(--accent-color);
        padding: 4px 15px 14px;
        letter-spacing: 0.5px;
    }

    nav a {
        color: var(--text-color);
        text-decoration: none;
        padding: 12px 15px; /* パディングを調整してクリックしやすく */
        margin-bottom: 8px; /* リンク間の余白 */
        border-radius: 6px; /* 角を丸く */
        transition: background-color 0.2s ease, color 0.2s ease; /* スムーズなホバーエフェクト */
        font-weight: 500; /* 少し太字に */
    }

    nav a:hover,
    nav a:focus { /* フォーカス時もスタイルを適用 */
        background-color: var(--accent-color);
        color: #ffffff; /* ホバー時のテキスト色を白に */
    }

    .main {
        flex-grow: 1; /* 残りのスペースをすべて使用 */
        padding: 30px; /* メインコンテンツのパディングを増加 */
        overflow-y: auto; /* コンテンツが多い場合にスクロール可能に */
    }

    /* レスポンシブ対応 */
    @media (max-width: 768px) {
        .all {
            flex-direction: column; /* 画面が小さい場合は縦並び */
        }

        nav {
            width: 100%; /* ナビゲーションを全幅に */
            border-right: none;
            border-bottom: 1px solid var(--border-color);
            padding: 15px; /* パディングを調整 */
            flex-direction: row; /* リンクを横並びに */
            justify-content: space-around; /* リンクを均等配置 */
            overflow-x: auto; /* リンクが多い場合に横スクロール */
        }

        .brand {
            padding: 4px 15px;
        }

        nav a {
            margin-bottom: 0;
            margin-right: 10px; /* 横並び時のリンク間余白 */
            white-space: nowrap; /* リンクテキストが改行されないように */
        }

        nav a:last-child {
            margin-right: 0;
        }

        .main {
            padding: 20px; /* モバイル時のパディング調整 */
        }
    }

    @media (max-width: 480px) {
        nav {
            padding: 10px;
            flex-wrap: wrap; /* さらに小さい画面ではリンクを折り返す */
            justify-content: center;
        }

        nav a {
            margin: 5px; /* 折り返し時のマージン調整 */
        }
    }
</style>
