import { MANAGE_SESSION_KEY, tokenStatus } from "./auth-core.js";

export const authState = $state({
  initialized: false,
  token: "",
  claims: null,
  reason: "",
});

export function initializeAuth() {
  if (typeof window === "undefined") return false;
  const token = sessionStorage.getItem(MANAGE_SESSION_KEY) || "";
  const result = tokenStatus(token);
  if (result.valid) {
    authState.token = token;
    authState.claims = result.claims;
    authState.reason = "";
  } else {
    sessionStorage.removeItem(MANAGE_SESSION_KEY);
    authState.token = "";
    authState.claims = null;
    authState.reason = token ? result.reason : "";
  }
  authState.initialized = true;
  return result.valid;
}

export function setManageSession(token) {
  const result = tokenStatus(token);
  if (!result.valid) throw new Error("有効な WebUI 管理セッションを取得できませんでした。");
  sessionStorage.setItem(MANAGE_SESSION_KEY, token);
  authState.token = token;
  authState.claims = result.claims;
  authState.reason = "";
  authState.initialized = true;
}

export function clearManageSession(reason = "") {
  if (typeof window !== "undefined") sessionStorage.removeItem(MANAGE_SESSION_KEY);
  authState.token = "";
  authState.claims = null;
  authState.reason = reason;
  authState.initialized = true;
}

export function hasManageSession() {
  return !!authState.token && tokenStatus(authState.token).valid;
}
