import assert from "node:assert/strict";
import test from "node:test";
import {
  apiErrorMessage,
  decodeJwtPayload,
  isProtectedManagePath,
  safeNextPath,
  tokenStatus,
} from "../src/lib/auth-core.js";

function jwt(payload) {
  const encode = (value) => Buffer.from(JSON.stringify(value)).toString("base64url");
  return `${encode({ alg: "none" })}.${encode(payload)}.`;
}

test("accepts an unexpired WebUI management JWT", () => {
  const token = jwt({ sub: "user-1", WebUI: true, userRole: "admin", exp: 2000 });
  assert.equal(decodeJwtPayload(token).sub, "user-1");
  assert.equal(tokenStatus(token, 1000 * 1000, 0).valid, true);
});

test("rejects expired, malformed, and non-WebUI tokens", () => {
  assert.equal(tokenStatus(jwt({ WebUI: true, exp: 999 }), 1000 * 1000, 0).reason, "expired");
  assert.equal(tokenStatus("not-a-jwt").reason, "invalid");
  assert.equal(tokenStatus(jwt({ WebUI: false, exp: 2000 }), 1000 * 1000, 0).reason, "invalid_role");
});

test("protects management pages but keeps login and console transitional access public", () => {
  assert.equal(isProtectedManagePath("/WebUI/user-info"), true);
  assert.equal(isProtectedManagePath("/WebUI/token-list"), true);
  assert.equal(isProtectedManagePath("/WebUI/participants/edit"), true);
  assert.equal(isProtectedManagePath("/WebUI/login"), false);
  assert.equal(isProtectedManagePath("/WebUI/console"), false);
});

test("next redirect stays inside the WebUI base", () => {
  assert.equal(safeNextPath("/WebUI/token-list"), "/WebUI/token-list");
  assert.equal(safeNextPath("https://evil.example"), "/WebUI/user-info");
  assert.equal(safeNextPath("//evil.example"), "/WebUI/user-info");
});

test("maps authentication and server failures to actionable messages", () => {
  assert.match(apiErrorMessage(401), /再度ログイン/);
  assert.match(apiErrorMessage(403), /権限/);
  assert.match(apiErrorMessage(503), /サービス/);
});
