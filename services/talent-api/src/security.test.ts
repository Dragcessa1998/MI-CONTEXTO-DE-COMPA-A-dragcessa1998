import { createHmac } from "node:crypto";
import type { AddressInfo } from "node:net";
import { after, before, test } from "node:test";
import assert from "node:assert/strict";

import app from "./index.js";
import { verifyTalentToken } from "./security.js";


const SECRET = "test-secret-that-is-longer-than-thirty-two-characters";
let baseUrl = "";
let server: ReturnType<typeof app.listen>;

function token(role: string, expiration = Math.floor(Date.now() / 1000) + 300): string {
  const header = Buffer.from(JSON.stringify({ alg: "HS256", typ: "JWT" })).toString("base64url");
  const payload = Buffer.from(JSON.stringify({
    sub: "42",
    role,
    iss: "nexova-platform",
    aud: "nexova-internal",
    exp: expiration,
  })).toString("base64url");
  const signature = createHmac("sha256", SECRET).update(`${header}.${payload}`).digest("base64url");
  return `${header}.${payload}.${signature}`;
}

before(async () => {
  process.env.JWT_SECRET = SECRET;
  server = app.listen(0);
  await new Promise<void>((resolve) => server.once("listening", resolve));
  const address = server.address() as AddressInfo;
  baseUrl = `http://127.0.0.1:${address.port}`;
});

after(async () => {
  await new Promise<void>((resolve, reject) => {
    server.close((error) => error ? reject(error) : resolve());
  });
});

test("JWT manager válido conserva identidad y rol", () => {
  assert.deepEqual(verifyTalentToken(token("manager"), SECRET, ["manager", "admin"]), {
    userId: "42",
    role: "manager",
  });
});

test("API de candidatos rechaza anónimo y rol de soporte", async () => {
  const anonymous = await fetch(`${baseUrl}/candidates`);
  const expired = await fetch(`${baseUrl}/candidates`, {
    headers: { Authorization: `Bearer ${token("manager", 1)}` },
  });
  const support = await fetch(`${baseUrl}/candidates`, {
    headers: { Authorization: `Bearer ${token("user")}` },
  });
  const manager = await fetch(`${baseUrl}/candidates`, {
    headers: { Authorization: `Bearer ${token("manager")}` },
  });

  assert.equal(anonymous.status, 401);
  assert.equal(anonymous.headers.get("www-authenticate"), "Bearer");
  assert.equal(expired.status, 401);
  assert.equal(support.status, 403);
  assert.equal(manager.status, 200);
});

test("CORS niega orígenes desconocidos y expone cabeceras defensivas", async () => {
  const denied = await fetch(`${baseUrl}/health`, {
    method: "OPTIONS",
    headers: {
      Origin: "https://attacker.example",
      "Access-Control-Request-Method": "GET",
    },
  });
  const health = await fetch(`${baseUrl}/health`);

  assert.equal(denied.status, 403);
  assert.equal(denied.headers.get("access-control-allow-origin"), null);
  assert.equal(health.headers.get("x-content-type-options"), "nosniff");
  assert.equal(health.headers.get("x-powered-by"), null);
  assert.equal(health.headers.get("content-security-policy"), "default-src 'none'; frame-ancestors 'none'");
});
