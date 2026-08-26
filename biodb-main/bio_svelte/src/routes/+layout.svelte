<script>
    let { children } = $props()
</script>

<div class="all">
    <nav>
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
    :root {
        --background-color: #1a1a1a; /* よりソフトな黒 */
        --text-color: #e0e0e0;
        --accent-color: #28a745; /* 鮮やかでモダンな濃い緑 */
        --nav-background-color: #2c2c2c;
        --link-hover-color: #34d399; /* アクセントカラーの明るい版 */
        --border-color: #444;
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
        outline: none; /* フォーカスリングを削除（キーボード操作用に別途考慮が必要な場合あり） */
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