/**
 * Transformaciones, scoring/matching y reportes agregados.
 * El motor de scoring es el núcleo del sistema de matching de Nexova.
 */

import {
  ENGLISH_ORDER,
  SENIORITY_ORDER,
  CANDIDATE_STATUSES,
} from "../types/models";
import type {
  Candidate,
  Vacancy,
  SelectionProcess,
  SeniorityLevel,
  CandidateStatus,
  ScoredCandidate,
} from "../types/models";

/** Redondea un número a 2 decimales. */
function roundToTwo(value: number): number {
  return Math.round(value * 100) / 100;
}

/** Conjunto de habilidades del candidato normalizadas a minúsculas. */
function toSkillSet(skills: string[]): Set<string> {
  return new Set(skills.map((skill) => skill.toLowerCase()));
}

// ----- Componentes del scoring (cada uno con su tope) -----

/** Match de habilidades — máx 40 puntos. */
function scoreSkills(candidate: Candidate, vacancy: Vacancy): number {
  const candidateSkills = toSkillSet(candidate.skills);

  // Requeridas: 40 si las tiene todas, 20 si tiene >= 50%, 0 en otro caso.
  let requiredScore = 0;
  if (vacancy.requiredSkills.length === 0) {
    requiredScore = 40;
  } else {
    const matched = vacancy.requiredSkills.filter((skill) =>
      candidateSkills.has(skill.toLowerCase())
    ).length;
    const ratio = matched / vacancy.requiredSkills.length;
    if (ratio === 1) requiredScore = 40;
    else if (ratio >= 0.5) requiredScore = 20;
  }

  // Preferidas: +10 por cada una que tenga, con tope de +20.
  const matchedPreferred = vacancy.preferredSkills.filter((skill) =>
    candidateSkills.has(skill.toLowerCase())
  ).length;
  const preferredScore = Math.min(matchedPreferred * 10, 20);

  // La categoría completa está topada en 40 (para que el total máximo sea 100).
  return Math.min(40, requiredScore + preferredScore);
}

/** Match de experiencia — máx 20 puntos. */
function scoreExperience(candidate: Candidate, vacancy: Vacancy): number {
  const exp = candidate.yearsOfExperience;
  if (exp >= vacancy.minYearsExperience && exp <= vacancy.maxYearsExperience) {
    return 20;
  }
  const distance =
    exp < vacancy.minYearsExperience
      ? vacancy.minYearsExperience - exp
      : exp - vacancy.maxYearsExperience;
  return distance <= 2 ? 10 : 0;
}

/** Match de seniority — máx 15 puntos. */
function scoreSeniority(candidate: Candidate, vacancy: Vacancy): number {
  const candidateIndex = SENIORITY_ORDER.indexOf(candidate.seniority);
  const requiredIndex = SENIORITY_ORDER.indexOf(vacancy.requiredSeniority);
  const diff = Math.abs(candidateIndex - requiredIndex);
  if (diff === 0) return 15;
  if (diff === 1) return 7;
  return 0;
}

/** Match de nivel de inglés — máx 15 puntos. */
function scoreEnglish(candidate: Candidate, vacancy: Vacancy): number {
  const candidateIndex = ENGLISH_ORDER.indexOf(candidate.englishLevel);
  const requiredIndex = ENGLISH_ORDER.indexOf(vacancy.requiredEnglishLevel);
  return candidateIndex >= requiredIndex ? 15 : 0;
}

/** Match de salario — máx 10 puntos. */
function scoreSalary(candidate: Candidate, vacancy: Vacancy): number {
  const expected = candidate.expectedSalary;
  if (expected >= vacancy.salaryRangeMin && expected <= vacancy.salaryRangeMax) {
    return 10;
  }
  if (
    expected > vacancy.salaryRangeMax &&
    expected <= vacancy.salaryRangeMax * 1.2
  ) {
    return 5;
  }
  return 0;
}

/**
 * Calcula el puntaje de match (0-100) entre un candidato y una vacante,
 * sumando los cinco componentes (habilidades, experiencia, seniority,
 * inglés y salario).
 */
export function calculateCandidateScore(
  candidate: Candidate,
  vacancy: Vacancy
): number {
  const total =
    scoreSkills(candidate, vacancy) +
    scoreExperience(candidate, vacancy) +
    scoreSeniority(candidate, vacancy) +
    scoreEnglish(candidate, vacancy) +
    scoreSalary(candidate, vacancy);

  // Garantiza el rango 0-100.
  return Math.max(0, Math.min(100, total));
}

/**
 * Puntúa todos los candidatos contra una vacante y los devuelve ordenados
 * por puntaje (más alto primero). No muta el array original.
 */
export function rankCandidatesForVacancy(
  candidates: Candidate[],
  vacancy: Vacancy
): ScoredCandidate[] {
  return candidates
    .map((candidate) => ({
      candidate,
      score: calculateCandidateScore(candidate, vacancy),
    }))
    .sort((a, b) => b.score - a.score);
}

/** Agrupa los candidatos por nivel de seniority. */
export function groupCandidatesBySeniority(
  candidates: Candidate[]
): Record<SeniorityLevel, Candidate[]> {
  const groups = {} as Record<SeniorityLevel, Candidate[]>;
  for (const level of SENIORITY_ORDER) {
    groups[level] = [];
  }
  for (const candidate of candidates) {
    groups[candidate.seniority].push(candidate);
  }
  return groups;
}

/** Cuenta cuántos candidatos hay en cada estado. */
export function countCandidatesByStatus(
  candidates: Candidate[]
): Record<CandidateStatus, number> {
  const counts = {} as Record<CandidateStatus, number>;
  for (const status of CANDIDATE_STATUSES) {
    counts[status] = 0;
  }
  for (const candidate of candidates) {
    counts[candidate.status] += 1;
  }
  return counts;
}

/**
 * Calcula el salario esperado promedio de todos los candidatos,
 * redondeado a 2 decimales. Devuelve 0 si la lista está vacía.
 */
export function calculateAverageSalary(candidates: Candidate[]): number {
  if (candidates.length === 0) return 0;
  const total = candidates.reduce(
    (sum, candidate) => sum + candidate.expectedSalary,
    0
  );
  return roundToTwo(total / candidates.length);
}

/** Suma de salarios esperados; para una colección vacía devuelve 0. */
export function calculateTotalExpectedSalary(candidates: Candidate[]): number {
  return candidates.reduce((total, candidate) => total + candidate.expectedSalary, 0);
}

/** Menor salario esperado; devuelve null si no hay candidatos. */
export function findMinimumExpectedSalary(candidates: Candidate[]): number | null {
  if (candidates.length === 0) return null;
  return Math.min(...candidates.map((candidate) => candidate.expectedSalary));
}

/** Mayor salario esperado; devuelve null si no hay candidatos. */
export function findMaximumExpectedSalary(candidates: Candidate[]): number | null {
  if (candidates.length === 0) return null;
  return Math.max(...candidates.map((candidate) => candidate.expectedSalary));
}

/**
 * Devuelve las N habilidades más comunes entre todos los candidatos,
 * ordenadas por frecuencia (más alta primero). El conteo es case-insensitive
 * pero conserva la primera grafía encontrada para mostrarla.
 */
export function findTopSkills(
  candidates: Candidate[],
  topN: number
): Array<{ skill: string; count: number }> {
  if (topN <= 0) return [];

  const counts = new Map<string, { skill: string; count: number }>();
  for (const candidate of candidates) {
    for (const skill of candidate.skills) {
      const key = skill.toLowerCase();
      const entry = counts.get(key);
      if (entry) entry.count += 1;
      else counts.set(key, { skill, count: 1 });
    }
  }

  return Array.from(counts.values())
    .sort((a, b) => b.count - a.count)
    .slice(0, topN);
}

/**
 * Calcula el porcentaje de procesos de selección que terminaron en "Hired".
 * Devuelve un número entre 0 y 100, redondeado a 2 decimales (0 si no hay datos).
 */
export function calculateVacancyFillRate(
  processes: SelectionProcess[]
): number {
  if (processes.length === 0) return 0;
  const hired = processes.filter((process) => process.stage === "Hired").length;
  return roundToTwo((hired / processes.length) * 100);
}
