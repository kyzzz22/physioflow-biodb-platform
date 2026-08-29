#!/usr/bin/env node
/**
 * PhysioFlow 构建 + 暂存脚本
 * - 在 PF 仓库（默认 E:\physioflow-app，可用 argv[2] / PF_REPO 覆盖）执行 npm run build
 * - 将 dist/ 拷贝到本仓库 pf-build/（nginx Dockerfile 的 COPY 源）
 *
 * 用法：node nginx/build-pf.cjs [PF仓库路径]
 */
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const here = __dirname; // .../biodb-main/nginx
const dest = path.join(here, '..', 'pf-build');
const pfRepo =
  process.argv[2] ||
  process.env.PF_REPO ||
  path.resolve(here, '..', '..', '..', 'physioflow-app');

if (!fs.existsSync(path.join(pfRepo, 'package.json'))) {
  console.error(`[build-pf] PF 仓库未找到: ${pfRepo}`);
  console.error('用法: node nginx/build-pf.cjs <physioflow-app 路径> 或设置 PF_REPO 环境变量');
  process.exit(1);
}

console.log(`[build-pf] 构建 PF: ${pfRepo}`);
const run = spawnSync('npm', ['run', 'build'], {
  cwd: pfRepo,
  stdio: 'inherit',
  shell: process.platform === 'win32',
});
if (run.status !== 0) {
  console.error('[build-pf] npm run build 失败');
  process.exit(run.status || 1);
}

const dist = path.join(pfRepo, 'dist');
if (!fs.existsSync(path.join(dist, 'index.html'))) {
  console.error(`[build-pf] PF 构建产物缺失 index.html: ${dist}`);
  process.exit(1);
}

fs.rmSync(dest, { recursive: true, force: true });
fs.cpSync(dist, dest, { recursive: true });

if (!fs.existsSync(path.join(dest, 'index.html'))) {
  console.error(`[build-pf] 暂存失败: ${dest}/index.html 不存在`);
  process.exit(1);
}

console.log(`[build-pf] 已暂存到 ${dest}`);
