import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { sampleCandidates } from "../src/data/sampleData";
import { sortCandidatesBySalary } from "../src/utils/collections";
import {
  binarySearchCandidateBySalary,
  findCandidateByEmail,
  findCandidateById,
} from "../src/utils/search";

describe("search operations", () => {
  it("performs linear searches and handles absent elements", () => {
    assert.equal(findCandidateById(sampleCandidates, "C-2024-0452")?.fullName, "Juan Pérez");
    assert.equal(findCandidateById(sampleCandidates, "missing"), null);
    assert.equal(
      findCandidateByEmail(sampleCandidates, "MARIA.GONZALEZ@EMAIL.COM")?.id,
      "C-2024-0451",
    );
    assert.equal(findCandidateByEmail([], "nobody@example.com"), null);
  });

  it("performs binary search on salary-sorted arrays", () => {
    const sorted = sortCandidatesBySalary(sampleCandidates, "asc");
    const index = binarySearchCandidateBySalary(sorted, 4200);
    assert.equal(sorted[index]?.id, "C-2024-0451");
    assert.equal(binarySearchCandidateBySalary(sorted, 9999), -1);
    assert.equal(binarySearchCandidateBySalary([], 4200), -1);
  });
});

