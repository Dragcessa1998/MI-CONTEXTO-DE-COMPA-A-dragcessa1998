import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { sampleCandidates, sampleProcesses, sampleVacancy } from "../src/data/sampleData";
import {
  calculateAverageSalary,
  calculateCandidateScore,
  calculateTotalExpectedSalary,
  calculateVacancyFillRate,
  countCandidatesByStatus,
  findMaximumExpectedSalary,
  findMinimumExpectedSalary,
  findTopSkills,
  groupCandidatesBySeniority,
  rankCandidatesForVacancy,
} from "../src/utils/transformations";

describe("transformations and reports", () => {
  it("scores from 0 to 100 and ranks highest first", () => {
    const scores = sampleCandidates.map((candidate) =>
      calculateCandidateScore(candidate, sampleVacancy),
    );
    assert.ok(scores.every((score) => score >= 0 && score <= 100));
    const ranking = rankCandidatesForVacancy(sampleCandidates, sampleVacancy);
    assert.equal(ranking[0]?.candidate.id, "C-2024-0453");
    assert.ok((ranking[0]?.score ?? 0) >= (ranking[1]?.score ?? 0));
  });

  it("groups and counts every declared category", () => {
    const groups = groupCandidatesBySeniority(sampleCandidates);
    assert.equal(groups.Senior.length, 1);
    assert.equal(groups.Executive.length, 0);
    assert.deepEqual(countCandidatesByStatus(sampleCandidates), {
      Active: 3,
      "In process": 0,
      Hired: 0,
      Inactive: 0,
    });
  });

  it("calculates sums, averages, minima and maxima including empty cases", () => {
    assert.equal(calculateTotalExpectedSalary(sampleCandidates), 13500);
    assert.equal(calculateAverageSalary(sampleCandidates), 4500);
    assert.equal(findMinimumExpectedSalary(sampleCandidates), 2800);
    assert.equal(findMaximumExpectedSalary(sampleCandidates), 6500);
    assert.equal(calculateTotalExpectedSalary([]), 0);
    assert.equal(calculateAverageSalary([]), 0);
    assert.equal(findMinimumExpectedSalary([]), null);
    assert.equal(findMaximumExpectedSalary([]), null);
  });

  it("returns top skills and fill-rate reports", () => {
    const topSkills = findTopSkills(sampleCandidates, 3);
    assert.deepEqual(topSkills, [
      { skill: "TypeScript", count: 2 },
      { skill: "React", count: 2 },
      { skill: "Node.js", count: 2 },
    ]);
    assert.equal(findTopSkills(sampleCandidates, 0).length, 0);
    assert.equal(calculateVacancyFillRate(sampleProcesses), 25);
    assert.equal(calculateVacancyFillRate([]), 0);
  });
});

