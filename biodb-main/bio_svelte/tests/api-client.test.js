import assert from "node:assert/strict";
import test from "node:test";

globalThis.$state = (value) => value;
const stored = new Map();
globalThis.sessionStorage = {
  getItem: (key) => stored.get(key) || null,
  setItem: (key, value) => stored.set(key, value),
  removeItem: (key) => stored.delete(key),
};
globalThis.window = new EventTarget();
globalThis.CustomEvent = class CustomEvent extends Event {};

const { apiRequest, ApiError } = await import("../src/lib/api-client.js");
const { authState, setManageSession } = await import("../src/lib/auth-state.svelte.js");

function jwt(payload) {
  const encode = (value) => Buffer.from(JSON.stringify(value)).toString("base64url");
  return `${encode({ alg: "none" })}.${encode(payload)}.signature`;
}

test("authenticated requests attach the shared management JWT", async () => {
  const token = jwt({ sub: "user-1", WebUI: true, userRole: "admin", exp: 4102444800 });
  setManageSession(token);
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (path, options) => {
    assert.equal(path, "/auth/user/info");
    assert.equal(options.headers.Authorization, `Bearer ${token}`);
    return new Response(JSON.stringify({ id: "user-1" }), { status: 200 });
  };
  try {
    assert.equal((await apiRequest("/auth/user/info")).id, "user-1");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("401 clears the shared session and returns an actionable error", async () => {
  const token = jwt({ sub: "user-1", WebUI: true, userRole: "admin", exp: 4102444800 });
  setManageSession(token);
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({ message: "expired" }), { status: 401 });
  try {
    await assert.rejects(apiRequest("/auth/token"), (error) => {
      assert.equal(error instanceof ApiError, true);
      assert.equal(error.status, 401);
      assert.match(error.message, /再度ログイン/);
      return true;
    });
    assert.equal(authState.token, "");
    assert.equal(sessionStorage.getItem("manage_jwt"), null);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
