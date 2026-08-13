import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { sampleCandidates } from "../src/data/sampleData";
import {
  filterCandidates,
  filterCandidatesByAvailability,
  filterCandidatesBySeniority,
  filterCandidatesBySkills,
  sortCandidatesByExperience,
  sortCandidatesByFields,
  sortCandidatesBySalary,
} from "../src/utils/collections";

describe("collection operations", () => {
  it("filters skills case-insensitively and requires every skill", () => {
    const result = filterCandidatesBySkills(sampleCandidates, ["typescript", "NODE.JS"]);
    assert.deepEqual(result.map(({ id }) => id), ["C-2024-0451", "C-2024-0453"]);
    assert.equal(filterCandidatesBySkills(sampleCandidates, ["COBOL"]).length, 0);
  });

  it("filters individual seniority and multiple availability values", () => {
    assert.deepEqual(
      filterCandidatesBySeniority(sampleCandidates, "Senior").map(({ id }) => id),
      ["C-2024-0453"],
    );
    assert.deepEqual(
      filterCandidatesByAvailability(sampleCandidates, ["Immediate", "2 weeks"]).map(
        ({ id }) => id,
      ),
      ["C-2024-0452", "C-2024-0453"],
    );
  });

  it("combines several optional business criteria", () => {
    const result = filterCandidates(sampleCandidates, {
      requiredSkills: ["typescript", "node.js"],
      seniorities: ["Semi-Senior", "Senior"],
      availability: ["1 month", "2 weeks"],
      statuses: ["Active"],
      minYearsExperience: 5,
      maxYearsExperience: 8,
      maxExpectedSalary: 7000,
      location: "valencia",
      remoteOnly: false,
    });
    assert.deepEqual(result.map(({ id }) => id), ["C-2024-0451", "C-2024-0453"]);
    assert.deepEqual(filterCandidates(sampleCandidates, {}), sampleCandidates);
  });

  it("sorts ascending and descending without mutating its input", () => {
    const originalIds = sampleCandidates.map(({ id }) => id);
    assert.deepEqual(
      sortCandidatesBySalary(sampleCandidates, "asc").map(({ expectedSalary }) => expectedSalary),
      [2800, 4200, 6500],
    );
    assert.deepEqual(
      sortCandidatesByExperience(sampleCandidates, "desc").map(
        ({ yearsOfExperience }) => yearsOfExperience,
      ),
      [8, 5, 3],
    );
    assert.deepEqual(sampleCandidates.map(({ id }) => id), originalIds);
  });

  it("uses later sort fields as tie breakers", () => {
    const tied = [
      { ...sampleCandidates[0]!, yearsOfExperience: 5, fullName: "Zoe" },
      { ...sampleCandidates[1]!, yearsOfExperience: 5, fullName: "Ana" },
      { ...sampleCandidates[2]!, yearsOfExperience: 8, fullName: "Carla" },
    ];
    const result = sortCandidatesByFields(tied, [
      { field: "yearsOfExperience", order: "desc" },
      { field: "fullName", order: "asc" },
    ]);
    assert.deepEqual(result.map(({ fullName }) => fullName), ["Carla", "Ana", "Zoe"]);
    assert.deepEqual(sortCandidatesByFields(tied, []).map(({ fullName }) => fullName), [
      "Zoe",
      "Ana",
      "Carla",
    ]);
  });
});

