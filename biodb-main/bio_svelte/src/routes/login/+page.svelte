<script>
    import { onMount } from "svelte";
    import { goto } from "$app/navigation";
    import axios from "axios";
    import { PUBLIC_GOOGLE_CLIENT_ID } from "$env/static/public";

    async function getWebuiJwt(path, credential) {
        const res = await axios.post(
            path,
            {role: "manage"},
            {
                headers: {
                'Authorization': 'Bearer ' + credential,
                'Content-Type': 'application/json',
                },
            });
            const token = res.data.access_token;
            return token
    }

    onMount(() => {
        window.googleCallback = async function (data) {
            const credential = data.credential
            try {
                    const token = await getWebuiJwt("/auth/google/callback", credential)
                    sessionStorage.setItem("manage_jwt", token);
                    goto("./user-info")
            } catch (error) {
                console.error("Error during callback", error);
            }
        };

        const script = document.createElement('script');
        script.src = 'https://accounts.google.com/gsi/client';
        script.async = true;
        script.defer = true;
        document.head.appendChild(script);
    });
</script>

<h1>BioDB 可視化クライアント ログイン</h1>

<div id="g_id_onload"
     data-client_id={PUBLIC_GOOGLE_CLIENT_ID}
     data-context="signin"
     data-ux_mode="popup"
     data-callback="googleCallback"
     data-auto_prompt="false">
</div>

<div class="g_id_signin"
     data-type="standard"
     data-shape="rectangular"
     data-theme="filled_blue"
     data-text="signin_with"
     data-size="large"
     data-logo_alignment="left">
</div>
