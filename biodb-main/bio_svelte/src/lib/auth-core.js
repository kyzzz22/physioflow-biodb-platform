export const MANAGE_SESSION_KEY = "manage_jwt";

export function decodeJwtPayload(token) {
  if (typeof token !== "string") return null;
  const parts = token.split(".");
  if (parts.length !== 3 || !parts[1]) return null;
  try {
    const normalized = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
    const binary = atob(padded);
    const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
    return JSON.parse(new TextDecoder().decode(bytes));
  } catch (error) {
    return null;
  }
}

export function tokenStatus(token, nowMs = Date.now(), safetyWindowMs = 30000) {
  const claims = decodeJwtPayload(token);
  if (!claims || typeof claims.exp !== "number") return { valid: false, reason: "invalid", claims: null };
  if (claims.exp * 1000 <= nowMs + safetyWindowMs) {
    return { valid: false, reason: "expired", claims };
  }
  if (claims.WebUI !== true) return { valid: false, reason: "invalid_role", claims };
  return { valid: true, reason: "", claims };
}

export function isProtectedManagePath(pathname, base = "/WebUI") {
  const relative = pathname.startsWith(base) ? pathname.slice(base.length) || "/" : pathname;
  return ["/user-info", "/token-list", "/participants"].some(
    (path) => relative === path || relative.startsWith(path + "/")
  );
}

export function safeNextPath(next, base = "/WebUI") {
  if (!next || typeof next !== "string") return `${base}/user-info`;
  if (!next.startsWith(`${base}/`) || next.startsWith(`${base}//`)) return `${base}/user-info`;
  return next;
}

export function apiErrorMessage(status, detail = "") {
  if (status === 401) return "ログインセッションの有効期限が切れました。再度ログインしてください。";
  if (status === 403) return "この操作を行う権限がありません。";
  if (status === 404) return "対象が見つかりませんでした。";
  if (status === 429) return "リクエストが多すぎます。しばらく待ってから再試行してください。";
  if (status >= 500) return "BioDB サービスでエラーが発生しました。しばらく待ってから再試行してください。";
  return detail || "リクエストに失敗しました。";
}
