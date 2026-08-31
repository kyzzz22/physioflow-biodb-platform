<script>
    import { onMount } from "svelte";
    import { goto } from "$app/navigation";
    import { page } from "$app/state";
    import { base } from "$app/paths";
    import { PUBLIC_GOOGLE_CLIENT_ID } from "$env/static/public";
    import { apiRequest } from "$lib/api-client.js";
    import { safeNextPath } from "$lib/auth-core.js";
    import { hasManageSession, setManageSession } from "$lib/auth-state.svelte.js";

    let state = $state("loading");
    let message = $state("Google ログインを準備しています…");
    let buttonEl = $state();

    function loadGoogleIdentity() {
        if (window.google?.accounts?.id) return Promise.resolve();
        return new Promise((resolve, reject) => {
            const existing = document.getElementById("google-identity-script");
            if (existing) existing.remove();
            const script = document.createElement("script");
            script.id = "google-identity-script";
            script.src = "https://accounts.google.com/gsi/client";
            script.async = true;
            script.defer = true;
            script.onload = resolve;
            script.onerror = () => {
                script.remove();
                reject(new Error("Google Identity Services の読込みに失敗しました。"));
            };
            document.head.appendChild(script);
        });
    }

    async function handleCredential(data) {
        if (!data?.credential) {
            state = "error";
            message = "Google から認証情報を取得できませんでした。もう一度お試しください。";
            return;
        }
        state = "processing";
        message = "BioDB セッションを作成しています…";
        try {
            const result = await apiRequest("/auth/google/callback", {
                method: "POST",
                auth: false,
                body: { role: "manage" },
                headers: { Authorization: `Bearer ${data.credential}` },
            });
            setManageSession(result.access_token);
            state = "success";
            message = "ログインしました。移動しています…";
            await goto(safeNextPath(page.url.searchParams.get("next"), base), { replaceState: true });
        } catch (error) {
            state = "error";
            message = error.message || "ログインに失敗しました。";
        }
    }

    async function initializeGoogle() {
        state = "loading";
        message = "Google ログインを準備しています…";
        try {
            await loadGoogleIdentity();
            if (!buttonEl || !window.google?.accounts?.id) throw new Error("Google Identity Services を読み込めませんでした。");
            window.google.accounts.id.initialize({
                client_id: PUBLIC_GOOGLE_CLIENT_ID,
                callback: handleCredential,
                ux_mode: "popup",
            });
            buttonEl.replaceChildren();
            window.google.accounts.id.renderButton(buttonEl, {
                type: "standard",
                shape: "rectangular",
                theme: "filled_blue",
                text: "signin_with",
                size: "large",
                logo_alignment: "left",
                width: 280,
            });
            state = "ready";
            message = "Google アカウントでログインしてください。";
        } catch (error) {
            state = "error";
            message = "Google ログインを読み込めませんでした。ネットワークを確認して再試行してください。";
        }
    }

    onMount(() => {
        if (hasManageSession()) {
            goto(safeNextPath(page.url.searchParams.get("next"), base), { replaceState: true });
            return;
        }
        initializeGoogle();
    });
</script>

<svelte:head><title>ログイン | BioDB</title></svelte:head>

<div class="login-card">
    <div class="mark">BioDB</div>
    <h1>管理 WebUI にログイン</h1>
    <p class="intro">ユーザ、実験協力者、API トークンを管理するための短期セッションを作成します。</p>
    <div class="google-button" class:hidden={state === "loading" || state === "processing"} bind:this={buttonEl}></div>
    <p class="status" class:error={state === "error"} class:success={state === "success"} aria-live="polite">
        {message}
    </p>
    {#if state === "loading" || state === "processing"}
        <div class="spinner" aria-label="処理中"></div>
    {:else if state === "error"}
        <button type="button" class="secondary" onclick={initializeGoogle}>再試行</button>
    {/if}
    <p class="security">管理 JWT はこのブラウザタブの sessionStorage にのみ保存され、10 分で失効します。</p>
</div>

<style>
    .login-card { max-width: 460px; margin: 8vh auto; padding: 32px; text-align: center; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-lg); box-shadow: var(--shadow); }
    .mark { color: var(--accent-hover); font-weight: 800; letter-spacing: .08em; }
    h1 { margin: 8px 0; font-size: 1.55rem; }
    .intro, .security { color: var(--muted); font-size: 13px; }
    .google-button { display: flex; justify-content: center; min-height: 44px; margin: 24px 0 12px; }
    .google-button.hidden { visibility: hidden; }
    .status { min-height: 24px; font-size: 13px; }
    .status.error { color: var(--danger); }
    .status.success { color: var(--ok-text); }
    .security { margin-top: 24px; padding-top: 16px; border-top: 1px solid var(--border); }
    .spinner { width: 22px; height: 22px; margin: 12px auto; border: 2px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin .8s linear infinite; }
    @keyframes spin { to { transform: rotate(360deg); } }
</style>
