import assert from "node:assert/strict";
import test from "node:test";

import { errorPayload, isMalformedJson } from "./errors.js";

test("errorPayload exposes only the explicit public contract", () => {
  const secret = "postgres://admin:password@internal/database";
  const payload = errorPayload(
    "INTERNAL_ERROR",
    "No pudimos completar la operación. Inténtalo de nuevo.",
  );

  assert.equal(payload.error.code, "INTERNAL_ERROR");
  assert.equal(JSON.stringify(payload).includes(secret), false);
  assert.equal("details" in payload.error, false);
});

test("validation details are included only when explicitly supplied", () => {
  assert.deepEqual(errorPayload("VALIDATION_ERROR", "Revisa los datos.", ["Email inválido"]), {
    error: {
      code: "VALIDATION_ERROR",
      message: "Revisa los datos.",
      details: ["Email inválido"],
    },
  });
});

test("malformed JSON errors are classified without serializing their message", () => {
  const malformed = Object.assign(new SyntaxError("Unexpected token with secret"), { body: "{" });
  assert.equal(isMalformedJson(malformed), true);
  assert.equal(isMalformedJson(new Error("ordinary failure")), false);
});
