import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { filterRecords } from "./filters";
import type { TrackerRecord } from "../types/tracker";

const base: TrackerRecord = {
  id: "1",
  full_name: "María González",
  email: "maria@example.com",
  phone: "+34 600 000 000",
  position: "Asistente de Dirección",
  linkedin_url: null,
  cv_url: null,
  status: "received",
  stage: "pending",
  experience_years: 4,
  notes_count: 0,
  applied_at: "2026-08-01T10:00:00Z",
  updated_at: "2026-08-01T10:00:00Z",
};

const records: TrackerRecord[] = [
  base,
  { ...base, id: "2", full_name: "Carlos Ruiz", email: "carlos@example.com", status: "in_progress", stage: "technical_interview" },
];

describe("candidate filters", () => {
  it("combines status, stage and case-insensitive name/email search", () => {
    assert.deepEqual(filterRecords(records, { status: "in_progress", stage: "technical_interview", search: "CARLOS" }).map(({ id }) => id), ["2"]);
    assert.deepEqual(filterRecords(records, { search: "maria@" }).map(({ id }) => id), ["1"]);
    assert.equal(filterRecords(records, { status: "selected" }).length, 0);
  });

  it("returns a copy for empty filters", () => {
    const result = filterRecords(records, {});
    assert.deepEqual(result, records);
    assert.notEqual(result, records);
  });
});

