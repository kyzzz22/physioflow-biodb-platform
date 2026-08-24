// Build the GitHub Pages site: render README.md + docs/*.md to HTML
// with GitHub's official markdown styles (github-markdown-css).
import { readFileSync, writeFileSync, mkdirSync, readdirSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import MarkdownIt from 'markdown-it';

const pagesBuildDir = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(pagesBuildDir, '..');
const siteDir = join(repoRoot, '_site');

const md = new MarkdownIt({ html: true, linkify: true, typographer: true });

const lightCss = readFileSync(join(pagesBuildDir, 'node_modules/github-markdown-css/github-markdown.css'), 'utf8');
const darkCss = readFileSync(join(pagesBuildDir, 'node_modules/github-markdown-css/github-markdown-dark.css'), 'utf8');

// Rewrite .md links (e.g. "docs/01-situation.md#anchor") to .html so the site links resolve.
function rewriteMdLinks(html) {
  return html.replace(/href="([^"#]+)\.md(#[^"]*)?"/g, 'href="$1.html$2"');
}

function shell(title, bodyHtml, rootLink, crumb) {
  return `<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>${title}</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;600;700&display=swap"/>
<style>
body{margin:0;background:#ffffff;color:#1f2328;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans","Noto Sans SC",Helvetica,Arial,sans-serif}
.site-header{background:#24292f;color:#f0f6fc;padding:12px 24px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.site-header a{color:#f0f6fc;text-decoration:none;font-weight:600}
.site-header a:hover{text-decoration:underline}
.site-header .crumb{color:rgba(240,246,252,.7);font-weight:400}
.wrap{max-width:1012px;margin:0 auto;padding:24px 24px 64px}
.foot{margin-top:32px;padding-top:16px;border-top:1px solid #d0d7de;color:#59636e;font-size:12px}
@media (prefers-color-scheme: dark){
  body{background:#0d1117;color:#e6edf3}
  .site-header{background:#010409}
  .foot{border-top-color:#30363d;color:#7d8590}
}
</style>
<style>${lightCss}</style>
<style>@media (prefers-color-scheme: dark){${darkCss}}</style>
</head>
<body>
<header class="site-header">
  <a href="${rootLink}">physioflow-biodb-platform</a>
  ${crumb ? `<span class="crumb">/ ${crumb}</span>` : ''}
</header>
<main class="wrap"><article class="markdown-body">${bodyHtml}</article>
<p class="foot">PhysioFlow × BioDB 研究数据平台 · 由 GitHub Pages 渲染（docs/*.md → HTML）</p>
</main>
</body>
</html>`;
}

function firstHeading(text, fallback) {
  const m = text.match(/^#\s+(.+)$/m);
  return m ? m[1].trim() : fallback;
}

mkdirSync(join(siteDir, 'docs'), { recursive: true });

// README.md → index.html
{
  const text = readFileSync(join(repoRoot, 'README.md'), 'utf8');
  const html = rewriteMdLinks(md.render(text));
  writeFileSync(join(siteDir, 'index.html'), shell('PhysioFlow × BioDB 研究数据平台', html, './', null));
}

// docs/*.md → docs/*.html (including sourced/)
for (const file of readdirSync(join(repoRoot, 'docs'))) {
  if (!file.endsWith('.md')) continue;
  const text = readFileSync(join(repoRoot, 'docs', file), 'utf8');
  const html = rewriteMdLinks(md.render(text));
  const outName = file.replace(/\.md$/, '.html');
  writeFileSync(join(siteDir, 'docs', outName), shell(firstHeading(text, file), html, '../', 'docs'));
}

console.log('Site built at', siteDir);
