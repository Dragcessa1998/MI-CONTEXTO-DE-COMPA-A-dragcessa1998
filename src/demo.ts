/**
 * Demo ejecutable de la capa de lógica del Hito 2.
 * Ejecuta:  npx tsx src/demo.ts   (o  npm run demo)
 *
 * Ejercita las funciones de colecciones, búsqueda, scoring/matching,
 * agregaciones y validaciones con los datos de ejemplo del CONTEXT.md.
 */

import {
  filterCandidatesBySkills,
  filterCandidatesBySeniority,
  filterCandidatesByAvailability,
  sortCandidatesBySalary,
  sortCandidatesByExperience,
  filterCandidates,
  sortCandidatesByFields,
} from "./utils/collections";
import {
  findCandidateById,
  findCandidateByEmail,
  binarySearchCandidateBySalary,
} from "./utils/search";
import {
  calculateCandidateScore,
  rankCandidatesForVacancy,
  groupCandidatesBySeniority,
  countCandidatesByStatus,
  calculateAverageSalary,
  calculateTotalExpectedSalary,
  findMinimumExpectedSalary,
  findMaximumExpectedSalary,
  findTopSkills,
  calculateVacancyFillRate,
} from "./utils/transformations";
import {
  validateCandidate,
  validateVacancy,
  isValidEmail,
} from "./utils/validations";
import {
  sampleCandidates,
  sampleVacancy,
  sampleProcesses,
} from "./data/sampleData";

function section(title: string): void {
  console.log("\n" + "=".repeat(60) + "\n" + title + "\n" + "=".repeat(60));
}

const names = (list: { fullName: string }[]): string =>
  list.map((c) => c.fullName).join(", ") || "(ninguno)";

section("1. COLECCIONES — filtrado y ordenamiento");

console.log(
  "Con TypeScript + React + Node.js:",
  names(filterCandidatesBySkills(sampleCandidates, ["TypeScript", "React", "Node.js"]))
);
console.log(
  "Seniority = Senior:",
  names(filterCandidatesBySeniority(sampleCandidates, "Senior"))
);
console.log(
  "Disponibilidad Immediate o 2 weeks:",
  names(filterCandidatesByAvailability(sampleCandidates, ["Immediate", "2 weeks"]))
);
console.log(
  "Por salario esperado (asc):",
  sortCandidatesBySalary(sampleCandidates, "asc").map((c) => c.expectedSalary)
);
console.log(
  "Por experiencia (desc):",
  sortCandidatesByExperience(sampleCandidates, "desc").map((c) => c.yearsOfExperience)
);
console.log(
  "Filtro combinado (senior + Valencia + hasta 7000):",
  names(
    filterCandidates(sampleCandidates, {
      seniorities: ["Senior"],
      location: "Valencia",
      maxExpectedSalary: 7000,
    }),
  ),
);
console.log(
  "Orden multi-campo (experiencia desc, nombre asc):",
  sortCandidatesByFields(sampleCandidates, [
    { field: "yearsOfExperience", order: "desc" },
    { field: "fullName", order: "asc" },
  ]).map((candidate) => candidate.fullName),
);

section("2. BÚSQUEDA — lineal y binaria");

console.log("Por ID C-2024-0452:", findCandidateById(sampleCandidates, "C-2024-0452")?.fullName ?? "null");
console.log(
  "Por email (case-insensitive) MARIA.GONZALEZ@EMAIL.COM:",
  findCandidateByEmail(sampleCandidates, "MARIA.GONZALEZ@EMAIL.COM")?.fullName ?? "null"
);
const sortedBySalary = sortCandidatesBySalary(sampleCandidates, "asc");
console.log(
  "Salarios ordenados:",
  sortedBySalary.map((c) => c.expectedSalary)
);
console.log("Búsqueda binaria salario 4200 → índice:", binarySearchCandidateBySalary(sortedBySalary, 4200));
console.log("Búsqueda binaria salario 9999 → índice:", binarySearchCandidateBySalary(sortedBySalary, 9999));

section("3. SCORING Y MATCHING contra la vacante");

console.log(`Vacante: ${sampleVacancy.title} (${sampleVacancy.companyName})`);
for (const candidate of sampleCandidates) {
  console.log(`  ${candidate.fullName}: ${calculateCandidateScore(candidate, sampleVacancy)} pts`);
}
console.log("\nRanking (mejor primero):");
for (const { candidate, score } of rankCandidatesForVacancy(sampleCandidates, sampleVacancy)) {
  console.log(`  ${score} pts — ${candidate.fullName}`);
}

section("4. AGREGACIONES Y REPORTES");

const bySeniority = groupCandidatesBySeniority(sampleCandidates);
console.log("Agrupados por seniority:");
for (const level of Object.keys(bySeniority) as Array<keyof typeof bySeniority>) {
  console.log(`  ${level}: ${names(bySeniority[level])}`);
}
console.log("Conteo por estado:", countCandidatesByStatus(sampleCandidates));
console.log("Salario esperado promedio:", calculateAverageSalary(sampleCandidates));
console.log("Suma de salarios esperados:", calculateTotalExpectedSalary(sampleCandidates));
console.log("Salario esperado mínimo:", findMinimumExpectedSalary(sampleCandidates));
console.log("Salario esperado máximo:", findMaximumExpectedSalary(sampleCandidates));
console.log("Top 3 habilidades:", findTopSkills(sampleCandidates, 3));
console.log("Tasa de cobertura (fill rate):", calculateVacancyFillRate(sampleProcesses) + "%");

section("5. VALIDACIONES");

console.log("isValidEmail('a@b.com'):", isValidEmail("a@b.com"));
console.log("isValidEmail('mal-email'):", isValidEmail("mal-email"));
console.log("validateCandidate (válido):", validateCandidate(sampleCandidates[0]!));
console.log(
  "validateCandidate (inválido):",
  validateCandidate({
    ...sampleCandidates[0]!,
    yearsOfExperience: -3,
    expectedSalary: 0,
    skills: [],
    email: "sin-arroba",
  })
);
console.log("validateVacancy (válida):", validateVacancy(sampleVacancy));
console.log(
  "validateVacancy (inválida):",
  validateVacancy({ ...sampleVacancy, requiredSkills: [], salaryRangeMax: 1000, salaryRangeMin: 5000 })
);

console.log("\n✅ Demo finalizada sin errores.\n");
