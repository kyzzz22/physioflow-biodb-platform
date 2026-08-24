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
  ja: { label: '日本語' },
  zh: { label: '中文' },
};

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
  html = html.replace(/<code>((?:\.\.?\/)?[^<]*?\.md)<\/code>/g, (m, path) => {
    const abs = join(dirname(fileRel), path);
    if (!existsSync(join(repoRoot, abs))) return m;
    return `<a href="${relLink(fileRel, abs)}">${path}</a>`;
  });
  return html;
}

function shell(title, bodyHtml, fileRel) {
  const lang = langOf(fileRel) || 'zh';
  const other = lang === 'ja' ? 'zh' : 'ja';
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
@media (prefers-color-scheme: dark){
  body{background:#0d1117;color:#e6edf3}
  .site-header{background:#010409}
  .lang-switch{background:#21262d;border-color:#30363d}
  .lang-switch a.active,.lang-switch span.active{background:#f0f6fc;color:#010409}
  .foot{border-top-color:#30363d;color:#7d8590}
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
<main class="wrap"><article class="markdown-body">${bodyHtml}</article>
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
  const html = rewriteMdLinks(md.render(text), fileRel);
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
  if (f.endsWith('.md')) renderFile(join('docs', 'ja', f));
}

// Chinese: docs/zh/README.md → zh/index.html; docs/zh/*.md → docs/zh/*.html
for (const f of readdirSync(join(repoRoot, 'docs', 'zh'))) {
  if (f.endsWith('.md')) renderFile(join('docs', 'zh', f));
}

// Reference docs (docs/sourced/) rendered in their original language only.
for (const f of readdirSync(join(repoRoot, 'docs', 'sourced'))) {
  if (f.endsWith('.md')) renderFile(join('docs', 'sourced', f));
}

console.log('Site built at', siteDir);
