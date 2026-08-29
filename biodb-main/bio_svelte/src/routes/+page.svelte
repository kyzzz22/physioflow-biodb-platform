<svelte:head>
  <title>BioDB 管理コンソール</title>
</svelte:head>

<div class="welcome">
  <header>
    <div class="logo">BioDB</div>
    <p class="subtitle">実験データ・ユーザ・トークンの一元管理</p>
  </header>

  <a class="card main" href="./console">
    <svg width="40" height="40" viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <ellipse cx="16" cy="8" rx="10" ry="4" stroke="var(--accent)" stroke-width="2"/>
      <path d="M6 8v16c0 2.2 4.5 4 10 4s10-1.8 10-4V8" stroke="var(--accent)" stroke-width="2" fill="none"/>
      <path d="M6 16c0 2.2 4.5 4 10 4s10-1.8 10-4" stroke="var(--accent)" stroke-width="2" fill="none"/>
    </svg>
    <div>
      <h2>データコンソール</h2>
      <p>棚卸し / データ閲覧 / イベント / 実験登録 / 分析 / エクスポート / 接続設定</p>
    </div>
    <span class="go">→</span>
  </a>

  <div class="grid">
    <a class="card" href="./user-info">
      <h3>ユーザ情報</h3>
      <p>自分のユーザ情報の確認と修正</p>
    </a>
    <a class="card" href="./token-list">
      <h3>トークンリスト</h3>
      <p>API 用の長期トークンの発行と管理</p>
    </a>
    <a class="card" href="./participants">
      <h3>実験協力者</h3>
      <p>参加者アカウントの管理</p>
    </a>
    <a class="card" href="./login">
      <h3>ログイン</h3>
      <p>Google アカウントでログイン</p>
    </a>
  </div>
</div>

<style>
  .welcome {
    max-width: var(--content-max);
    margin: 0 auto;
    padding: 20px;
  }
  header {
    margin-bottom: 24px;
  }
  .logo {
    font-size: 2rem;
    font-weight: 700;
    color: var(--accent);
    letter-spacing: 0.5px;
  }
  .subtitle {
    margin-top: 6px;
    color: var(--muted);
    font-size: 14px;
  }
  a.card {
    display: flex;
    align-items: center;
    gap: 16px;
    text-decoration: none;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 20px;
    transition: border-color 0.15s, transform 0.15s, box-shadow 0.15s;
  }
  a.card:hover {
    border-color: var(--accent-hover);
    transform: translateY(-2px);
    box-shadow: var(--shadow);
  }
  a.card h2, a.card h3 {
    color: var(--text);
    margin: 0;
  }
  a.card p {
    color: var(--muted);
    font-size: 13px;
    margin: 6px 0 0;
    line-height: 1.5;
  }
  .card.main {
    margin-bottom: 16px;
    padding: 24px;
  }
  .card.main h2 {
    color: var(--accent-hover);
  }
  .card.main .go {
    margin-left: auto;
    color: var(--muted);
    font-size: 20px;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 16px;
  }
  .grid a.card {
    display: block;
    padding: 18px 20px;
  }
</style>
