import assert from "node:assert/strict";
import { afterEach, describe, it } from "node:test";

import { buildRecordsPath, createRecord, listRecords } from "./api";

const originalFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = originalFetch; });

describe("tracker API service", () => {
  it("builds encoded record filters and performs GET", async () => {
    let requestedUrl = "";
    globalThis.fetch = async (input) => {
      requestedUrl = String(input);
      return new Response(JSON.stringify({ total: 0, page: 1, limit: 100, data: [] }), { status: 200, headers: { "Content-Type": "application/json" } });
    };
    const path = buildRecordsPath({ status: "in_progress", stage: "review", search: "María Pérez" });
    assert.equal(path, "/records?status=in_progress&stage=review&search=Mar%C3%ADa+P%C3%A9rez&limit=100");
    const result = await listRecords({ search: "María Pérez" });
    assert.equal(result.total, 0);
    assert.match(requestedUrl, /search=Mar%C3%ADa\+P%C3%A9rez/);
  });

  it("serializes a typed POST body", async () => {
    let requestInit: RequestInit | undefined;
    globalThis.fetch = async (_input, init) => {
      requestInit = init;
      return new Response(JSON.stringify({ id: "new-id" }), { status: 201, headers: { "Content-Type": "application/json" } });
    };
    const input = { full_name: "Test Candidate", email: "test@example.com", phone: "+34 600 000 001", position: "Asistente", experience_years: 2 };
    const record = await createRecord(input);
    assert.equal(record.id, "new-id");
    assert.equal(requestInit?.method, "POST");
    assert.deepEqual(JSON.parse(String(requestInit?.body)), input);
  });

  it("surfaces API detail errors", async () => {
    globalThis.fetch = async () => new Response(JSON.stringify({ detail: "Email already exists" }), { status: 409, headers: { "Content-Type": "application/json" } });
    await assert.rejects(() => createRecord({ full_name: "Duplicate", email: "duplicate@example.com", phone: "1", position: "Test", experience_years: 0 }), /Email already exists/);
  });
});

