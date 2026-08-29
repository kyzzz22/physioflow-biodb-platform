import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

const API_TARGET = 'http://localhost:5002';

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		proxy: {
			// dev 模式下 API 走 vite 代理到 nginx（与生产同源路径一致）
			'/auth': API_TARGET,
			'/sensor': API_TARGET,
			'/event': API_TARGET,
			'/experiment': API_TARGET
		}
	}
});
