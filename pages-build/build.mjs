// Build the GitHub Pages site: render README.md + docs/**/*.md to HTML
// with GitHub's official markdown styles (github-markdown-css).
// Bilingual: ja = default (top README.md + docs/ja/), zh = docs/zh/.
import { readFileSync, writeFileSync, mkdirSync, readdirSync, existsSync } from 'node:fs';
import { join, dirname, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import MarkdownIt from 'markdown-it';

const pagesBuildDir = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(pagesBuildDir, '..');
const siteDir = join(repoRoot, '_site');

const md = new MarkdownIt({ html: true, linkify: true, typographer: true });

const lightCss = readFileSync(join(pagesBuildDir, 'node_modules/github-markdown-css/github-markdown.css'), 'utf8');
const darkCss = readFileSync(join(pagesBuildDir, 'node_modules/github-markdown-css/github-markdown-dark.css'), 'utf8');

const LANG = {
  ja: {
    label: '日本語',
    hero: {
      title: 'PhysioFlow × BioDB 研究データプラットフォーム',
      sub: '実験のライフサイクル全体をカバーする研究データプラットフォーム：設計 → 収集 → 保存 → 管理 → 分析 → 可視化。',
      badges: ['実験ID + 協力者ID 二段識別', 'JWT 認証', 'VictoriaMetrics · MongoDB · PostgreSQL'],
      read: 'ドキュメントを読む',
      github: 'GitHub リポジトリ',
      githubUrl: 'https://github.com/kyzzz22/physioflow-biodb-platform',
      cards: [
        { title: 'PhysioFlow（PF）', text: '実験ワークフロー：ビジュアルなプロトコル設計、実行、参加者インタラクション、再現可能なデータパケットのエクスポート。' },
        { title: 'BioDB', text: '生体データウェアハウス：センサ時系列 VictoriaMetrics、イベント MongoDB、ユーザー/権限 PostgreSQL。' },
        { title: '統合', text: 'PF が収集した生体データを BioDB へプッシュし、「実験ID + 協力者ID」の二段識別で保存・一元管理・分析・可視化。' },
      ],
    },
  },
  zh: {
    label: '中文',
    hero: {
      title: 'PhysioFlow × BioDB 研究数据平台',
      sub: '覆盖实验全生命周期的研究数据平台：设计 → 采集 → 存储 → 管理 → 分析 → 可视化。',
      badges: ['实验ID + 协作者ID 二段标识', 'JWT 认证', 'VictoriaMetrics · MongoDB · PostgreSQL'],
      read: '阅读文档',
      github: 'GitHub 仓库',
      githubUrl: 'https://github.com/kyzzz22/physioflow-biodb-platform',
      cards: [
        { title: 'PhysioFlow（PF）', text: '实验工作流：可视化协议设计、运行、被试交互、导出可复现数据包。' },
        { title: 'BioDB', text: '生体数据仓库：传感器时序 VictoriaMetrics、事件 MongoDB、用户/权限 PostgreSQL。' },
        { title: '平台整合', text: 'PF 采集的生体数据推送 BioDB，按「实验ID + 协作者ID」二段标识存储，统一管理、分析、可视化。' },
      ],
    },
  },
};

// heroHtml(lang): landing-page hero + feature cards (home pages only)
function heroHtml(lang) {
  const h = LANG[lang].hero;
  const badges = h.badges.map((b) => `<span>${b}</span>`).join('');
  const cards = h.cards.map((c) => `<div class="card"><h3>${c.title}</h3><p>${c.text}</p></div>`).join('');
  return `
<section class="hero">
  <div class="hero-inner">
    <h1 class="hero-title">${h.title}</h1>
    <p class="hero-sub">${h.sub}</p>
    <p class="hero-badges">${badges}</p>
    <div class="hero-actions">
      <a class="btn btn-primary" href="#readme">${h.read}</a>
      <a class="btn btn-ghost" href="${h.githubUrl}" target="_blank" rel="noopener">${h.github}</a>
    </div>
  </div>
</section>
<section class="cards">${cards}</section>`;
}

// langOf(fileRel): 'ja' | 'zh' | null (sourced docs stay in their original language)
function langOf(fileRel) {
  if (fileRel === 'README.md' || fileRel.startsWith('docs/ja/') || fileRel.includes('MEETING_EXPERIMENT_ID')) return 'ja';
  if (fileRel.startsWith('docs/zh/')) return 'zh';
  return null;
}

// counterpart(fileRel): the same doc in the other language, or null.
// ja <-> zh trees: README.md <-> docs/zh/README.md, docs/ja/X.md <-> docs/zh/X.md
function counterpart(fileRel) {
  if (fileRel === 'README.md') return 'docs/zh/README.md';
  if (fileRel === 'docs/zh/README.md') return 'README.md';
  if (fileRel.startsWith('docs/ja/')) return 'docs/zh/' + fileRel.slice('docs/ja/'.length);
  if (fileRel.startsWith('docs/zh/')) return 'docs/ja/' + fileRel.slice('docs/zh/'.length);
  return null;
}

// outPath(fileRel): site-relative output path (dir for index.html, else .html)
function outPath(fileRel) {
  if (fileRel === 'README.md') return 'index.html';
  if (fileRel === 'docs/zh/README.md') return 'zh/index.html';
  return fileRel.replace(/\.md$/, '.html');
}

function relLink(fromFile, toFile) {
  const from = dirname('/' + outPath(fromFile));
  const to = '/' + outPath(toFile);
  let r = relative(from, to);
  if (!r.startsWith('.')) r = './' + r;
  return r;
}

// homeFor(lang): output path of that language's index
const HOME = { ja: 'index.html', zh: 'zh/index.html' };

// Rewrite .md links (e.g. "docs/ja/01-situation.md#anchor") to .html so the site links resolve.
function rewriteMdLinks(html, fileRel) {
  html = html.replace(/href="([^"#]+)\.md(#[^"]*)?"/g, 'href="$1.html$2"');
  // Turn backticked file paths (`docs/ja/X.md`) into working links.
  // Protect existing <a>…</a> spans first so a backticked path inside link
  // text (e.g. [`README.md`](../../README.md)) is not wrapped a second time.
  const anchors = [];
  html = html.replace(/<a\b[^>]*>[\s\S]*?<\/a>/g, (m) => {
    anchors.push(m);
    return `\u0000${anchors.length - 1}\u0000`;
  });
  html = html.replace(/<code>((?:\.\.?\/)?[^<]*?\.md)<\/code>/g, (m, path) => {
    const abs = join(dirname(fileRel), path);
    if (!existsSync(join(repoRoot, abs))) return m;
    return `<a href="${relLink(fileRel, abs)}">${path}</a>`;
  });
  html = html.replace(/\u0000(\d+)\u0000/g, (m, i) => anchors[Number(i)]);
  return html;
}

function shell(title, bodyHtml, fileRel) {
  const lang = langOf(fileRel) || 'zh';
  const other = lang === 'ja' ? 'zh' : 'ja';
  const isHome = outPath(fileRel) === 'index.html' || outPath(fileRel) === 'zh/index.html';
  const counter = counterpart(fileRel);
  const jaUrl = lang === 'ja' ? null : (counter ? relLink(fileRel, counter) : relLink(fileRel, HOME.ja));
  const zhUrl = lang === 'zh' ? null : (counter ? relLink(fileRel, counter) : relLink(fileRel, HOME.zh));
  const headerText = lang === 'ja'
    ? 'PhysioFlow × BioDB 研究データプラットフォーム'
    : 'PhysioFlow × BioDB 研究数据平台';
  const footText = lang === 'ja'
    ? 'PhysioFlow × BioDB 研究データプラットフォーム · GitHub Pages によるレンダリング（docs/*.md → HTML）'
    : 'PhysioFlow × BioDB 研究数据平台 · 由 GitHub Pages 渲染（docs/*.md → HTML）';
  const crumb = fileRel.startsWith('docs/') ? 'docs' : null;

  return `<!doctype html>
<html lang="${lang === 'ja' ? 'ja' : 'zh-CN'}">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>${title}</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;600;700&family=Noto+Sans+SC:wght@400;500;600;700&display=swap"/>
<style>
body{margin:0;background:#ffffff;color:#1f2328;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans","Noto Sans JP","Noto Sans SC",Helvetica,Arial,sans-serif}
.site-header{background:#24292f;color:#f0f6fc;padding:12px 24px;display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.site-header a{color:#f0f6fc;text-decoration:none;font-weight:600}
.site-header a:hover{text-decoration:underline}
.site-header .crumb{color:rgba(240,246,252,.7);font-weight:400}
.lang-switch{margin-left:auto;display:inline-flex;gap:2px;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.15);border-radius:6px;padding:2px}
.lang-switch a,.lang-switch span{font-size:12px;font-weight:500;padding:3px 10px;border-radius:4px;color:rgba(240,246,252,.8)}
.lang-switch a.active,.lang-switch span.active{background:#ffffff;color:#1f2328}
.lang-switch a:not(.active):hover{background:rgba(255,255,255,.15);text-decoration:none}
.wrap{max-width:1012px;margin:0 auto;padding:24px 24px 64px}
.foot{margin-top:32px;padding-top:16px;border-top:1px solid #d0d7de;color:#59636e;font-size:12px}
.hero{background:linear-gradient(135deg,#0d1117 0%,#24292f 55%,#1f6feb 150%);color:#f0f6fc;padding:56px 24px 44px;text-align:center}
.hero-inner{max-width:1012px;margin:0 auto}
.hero-title{margin:0 0 12px;font-size:clamp(26px,4vw,40px);font-weight:700;letter-spacing:.5px;line-height:1.3}
.hero-sub{margin:0 auto 20px;max-width:720px;font-size:clamp(15px,2vw,18px);color:rgba(240,246,252,.85);line-height:1.7}
.hero-badges{display:flex;gap:8px;justify-content:center;flex-wrap:wrap;margin:0 0 26px;padding:0}
.hero-badges span{font-size:12px;padding:5px 14px;border-radius:999px;background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.22);color:#f0f6fc}
.hero-actions{display:flex;gap:12px;justify-content:center;flex-wrap:wrap}
.btn{display:inline-block;padding:10px 22px;border-radius:8px;font-weight:600;font-size:14px;text-decoration:none;transition:background .15s,transform .15s}
.btn:hover{transform:translateY(-1px)}
.btn-primary{background:#1f6feb;color:#fff}
.btn-primary:hover{background:#388bfd}
.btn-ghost{background:transparent;color:#f0f6fc;border:1px solid rgba(240,246,252,.4)}
.btn-ghost:hover{background:rgba(255,255,255,.1)}
.cards{max-width:1012px;margin:0 auto;padding:24px 24px 8px;display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px}
.card{background:#ffffff;border:1px solid #d0d7de;border-radius:10px;padding:20px 20px 16px;border-top:3px solid #1f6feb;transition:box-shadow .15s,transform .15s}
.card:hover{box-shadow:0 4px 16px rgba(31,35,40,.12);transform:translateY(-2px)}
.card h3{margin:0 0 8px;font-size:16px;color:#1f2328}
.card p{margin:0;font-size:13.5px;line-height:1.65;color:#59636e}
@media (prefers-color-scheme: dark){
  body{background:#0d1117;color:#e6edf3}
  .site-header{background:#010409}
  .lang-switch{background:#21262d;border-color:#30363d}
  .lang-switch a.active,.lang-switch span.active{background:#f0f6fc;color:#010409}
  .foot{border-top-color:#30363d;color:#7d8590}
  .hero{background:linear-gradient(135deg,#010409 0%,#0d1117 55%,#1f6feb 150%)}
  .card{background:#161b22;border-color:#30363d}
  .card h3{color:#f0f6fc}
  .card p{color:#8b949e}
  .card:hover{box-shadow:0 4px 16px rgba(0,0,0,.4)}
}
</style>
<style>${lightCss}</style>
<style>@media (prefers-color-scheme: dark){${darkCss}}</style>
</head>
<body>
<header class="site-header">
  <a href="${relLink(fileRel, HOME[lang])}">${headerText}</a>
  ${crumb ? `<span class="crumb">/ ${crumb}</span>` : ''}
  <span class="lang-switch">
    ${jaUrl ? `<a href="${jaUrl}" class="${lang === 'ja' ? 'active' : ''}">日本語</a>` : `<span class="active">日本語</span>`}
    ${zhUrl ? `<a href="${zhUrl}" class="${lang === 'zh' ? 'active' : ''}">中文</a>` : `<span class="active">中文</span>`}
  </span>
</header>
${isHome ? heroHtml(lang) : ''}
<main class="wrap"><article id="readme" class="markdown-body">${bodyHtml}</article>
<p class="foot">${footText}</p>
</main>
</body>
</html>`;
}

function firstHeading(text, fallback) {
  const m = text.match(/^#\s+(.+)$/m);
  return m ? m[1].trim() : fallback;
}

function renderFile(fileRel) {
  const abs = join(repoRoot, fileRel);
  if (!existsSync(abs)) return;
  const text = readFileSync(abs, 'utf8');
  const isHome = outPath(fileRel) === 'index.html' || outPath(fileRel) === 'zh/index.html';
  // On home pages the H1 is already shown in the hero banner.
  const body = isHome ? text.replace(/^#\s+[^\n]*\n/, '') : text;
  const html = rewriteMdLinks(md.render(body), fileRel);
  const out = join(siteDir, outPath(fileRel));
  mkdirSync(dirname(out), { recursive: true });
  writeFileSync(out, shell(firstHeading(text, fileRel), html, fileRel));
  console.log('  ', fileRel, '->', outPath(fileRel));
}

mkdirSync(siteDir, { recursive: true });
console.log('Building site...');

// Default (ja): top README.md → index.html; docs/ja/*.md → docs/ja/*.html
renderFile('README.md');
for (const f of readdirSync(join(repoRoot, 'docs', 'ja'))) {
  if (f.endsWith('.md')) renderFile('docs/ja/' + f);
}

// Chinese: docs/zh/README.md → zh/index.html; docs/zh/*.md → docs/zh/*.html
for (const f of readdirSync(join(repoRoot, 'docs', 'zh'))) {
  if (f.endsWith('.md')) renderFile('docs/zh/' + f);
}

// Reference docs (docs/sourced/) rendered in their original language only.
for (const f of readdirSync(join(repoRoot, 'docs', 'sourced'))) {
  if (f.endsWith('.md')) renderFile('docs/sourced/' + f);
}

console.log('Site built at', siteDir);
