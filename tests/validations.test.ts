import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { sampleCandidates, sampleVacancy } from "../src/data/sampleData";
import { isValidEmail, validateCandidate, validateVacancy } from "../src/utils/validations";

describe("domain validations", () => {
  it("validates email format", () => {
    assert.equal(isValidEmail("person@example.com"), true);
    assert.equal(isValidEmail("missing-at.example.com"), false);
    assert.equal(isValidEmail("person@domain"), false);
  });

  it("collects every candidate validation error", () => {
    assert.deepEqual(validateCandidate(sampleCandidates[0]!), { valid: true, errors: [] });
    const invalid = validateCandidate({
      ...sampleCandidates[0]!,
      yearsOfExperience: 51,
      currentSalary: 0,
      expectedSalary: -1,
      skills: [],
      email: "invalid",
      phone: " ",
    });
    assert.equal(invalid.valid, false);
    assert.equal(invalid.errors.length, 6);
  });

  it("validates vacancy ranges and required skills", () => {
    assert.deepEqual(validateVacancy(sampleVacancy), { valid: true, errors: [] });
    const invalid = validateVacancy({
      ...sampleVacancy,
      requiredSkills: [],
      minYearsExperience: -1,
      maxYearsExperience: -2,
      salaryRangeMin: 5000,
      salaryRangeMax: 0,
    });
    assert.equal(invalid.valid, false);
    assert.equal(invalid.errors.length, 5);
  });
});

