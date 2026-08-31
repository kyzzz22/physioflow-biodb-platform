import { apiErrorMessage } from "./auth-core.js";
import { authState, clearManageSession, hasManageSession } from "./auth-state.svelte.js";

export class ApiError extends Error {
  constructor(message, status = 0, detail = "") {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function responseBody(response) {
  const text = await response.text();
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch (error) {
    return { message: text };
  }
}

export async function apiRequest(path, options = {}) {
  const { method = "GET", body, auth = true, headers: inputHeaders = {} } = options;
  const headers = { Accept: "application/json", ...inputHeaders };

  if (auth) {
    if (!hasManageSession()) {
      clearManageSession("expired");
      if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent("biodb:unauthorized"));
      throw new ApiError(apiErrorMessage(401), 401);
    }
    headers.Authorization = `Bearer ${authState.token}`;
  }
  if (body !== undefined) headers["Content-Type"] = "application/json";

  let response;
  try {
    response = await fetch(path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (error) {
    throw new ApiError("BioDB に接続できません。ネットワークとサービス状態を確認してください。", 0);
  }

  const data = await responseBody(response);
  if (!response.ok) {
    const detail = data.message || data.detail || data.error || "";
    if (response.status === 401) {
      clearManageSession("expired");
      if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent("biodb:unauthorized"));
    }
    throw new ApiError(apiErrorMessage(response.status, detail), response.status, detail);
  }
  return data;
}
