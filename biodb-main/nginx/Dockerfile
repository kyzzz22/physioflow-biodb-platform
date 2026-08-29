FROM node:22-alpine AS webui-build

WORKDIR /app

COPY bio_svelte/package.json bio_svelte/package-lock.json ./
RUN npm ci

COPY bio_svelte/ ./

ARG PUBLIC_GOOGLE_CLIENT_ID
ENV PUBLIC_GOOGLE_CLIENT_ID=$PUBLIC_GOOGLE_CLIENT_ID

RUN npm run build

FROM nginx:1.27-alpine

COPY nginx/nginx.conf /etc/nginx/nginx.conf
COPY --from=webui-build /app/build /usr/share/nginx/html/WebUI
COPY bio_util/ /usr/share/nginx/html/util/
COPY bio_console/ /usr/share/nginx/html/db/
# PhysioFlow Dashboard（相対パスビルド済み SPA）+ 統合ランディングページ
COPY pf-build/ /usr/share/nginx/html/pf/
COPY nginx/landing/index.html /usr/share/nginx/html/index.html
# 統合テーマトークン（/db/, /util/ 共通）
COPY webui-theme/theme.css /usr/share/nginx/html/shared/theme.css
