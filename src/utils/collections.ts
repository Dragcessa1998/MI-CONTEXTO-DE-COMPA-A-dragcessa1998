/**
 * Operaciones de colecciones sobre candidatos: filtrado y ordenamiento.
 * Todas las funciones son puras y no mutan los arrays recibidos.
 */

import type {
  Candidate,
  SeniorityLevel,
  AvailabilityStatus,
  CandidateStatus,
} from "../types/models";

export interface CandidateFilters {
  requiredSkills?: readonly string[];
  seniorities?: readonly SeniorityLevel[];
  availability?: readonly AvailabilityStatus[];
  statuses?: readonly CandidateStatus[];
  minYearsExperience?: number;
  maxYearsExperience?: number;
  maxExpectedSalary?: number;
  location?: string;
  remoteOnly?: boolean;
}

export type CandidateSortField =
  | "fullName"
  | "yearsOfExperience"
  | "expectedSalary";

export interface CandidateSortCriterion {
  field: CandidateSortField;
  order: "asc" | "desc";
}

/**
 * Combina opcionalmente habilidades, seniority, disponibilidad, estado,
 * experiencia, salario, ubicación y modalidad remota en un solo filtro puro.
 */
export function filterCandidates(
  candidates: readonly Candidate[],
  filters: CandidateFilters,
): Candidate[] {
  const normalizedLocation = filters.location?.trim().toLowerCase();
  const normalizedSkills = filters.requiredSkills?.map((skill) =>
    skill.toLowerCase(),
  );

  return candidates.filter((candidate) => {
    const skills = new Set(candidate.skills.map((skill) => skill.toLowerCase()));
    return (
      (normalizedSkills === undefined ||
        normalizedSkills.every((skill) => skills.has(skill))) &&
      (filters.seniorities === undefined ||
        filters.seniorities.includes(candidate.seniority)) &&
      (filters.availability === undefined ||
        filters.availability.includes(candidate.availability)) &&
      (filters.statuses === undefined || filters.statuses.includes(candidate.status)) &&
      (filters.minYearsExperience === undefined ||
        candidate.yearsOfExperience >= filters.minYearsExperience) &&
      (filters.maxYearsExperience === undefined ||
        candidate.yearsOfExperience <= filters.maxYearsExperience) &&
      (filters.maxExpectedSalary === undefined ||
        candidate.expectedSalary <= filters.maxExpectedSalary) &&
      (normalizedLocation === undefined ||
        candidate.location.toLowerCase().includes(normalizedLocation)) &&
      (filters.remoteOnly === undefined || candidate.remoteOnly === filters.remoteOnly)
    );
  });
}

function compareCandidates(
  left: Candidate,
  right: Candidate,
  field: CandidateSortField,
): number {
  if (field === "fullName") {
    return left.fullName.localeCompare(right.fullName, "es");
  }
  return left[field] - right[field];
}

/** Ordena por uno o varios campos, respetando la prioridad indicada. */
export function sortCandidatesByFields(
  candidates: readonly Candidate[],
  criteria: readonly CandidateSortCriterion[],
): Candidate[] {
  return [...candidates].sort((left, right) => {
    for (const criterion of criteria) {
      const result = compareCandidates(left, right, criterion.field);
      if (result !== 0) return criterion.order === "asc" ? result : -result;
    }
    return 0;
  });
}

/**
 * Devuelve los candidatos que poseen TODAS las habilidades requeridas.
 * El matching es case-insensitive. Si no se requiere ninguna habilidad,
 * devuelve todos los candidatos.
 */
export function filterCandidatesBySkills(
  candidates: Candidate[],
  requiredSkills: string[]
): Candidate[] {
  if (requiredSkills.length === 0) return [...candidates];

  const normalizedRequired = requiredSkills.map((skill) => skill.toLowerCase());

  return candidates.filter((candidate) => {
    const candidateSkills = new Set(
      candidate.skills.map((skill) => skill.toLowerCase())
    );
    return normalizedRequired.every((skill) => candidateSkills.has(skill));
  });
}

/** Devuelve los candidatos con el nivel de seniority indicado. */
export function filterCandidatesBySeniority(
  candidates: Candidate[],
  seniority: SeniorityLevel
): Candidate[] {
  return candidates.filter((candidate) => candidate.seniority === seniority);
}

/**
 * Devuelve los candidatos cuya disponibilidad coincide con cualquiera de los
 * estados proporcionados.
 */
export function filterCandidatesByAvailability(
  candidates: Candidate[],
  availability: AvailabilityStatus[]
): Candidate[] {
  return candidates.filter((candidate) =>
    availability.includes(candidate.availability)
  );
}

/**
 * Devuelve una copia de los candidatos ordenada por salario esperado.
 * No muta el array original.
 */
export function sortCandidatesBySalary(
  candidates: Candidate[],
  order: "asc" | "desc"
): Candidate[] {
  return sortCandidatesByFields(candidates, [{ field: "expectedSalary", order }]);
}

/**
 * Devuelve una copia de los candidatos ordenada por años de experiencia.
 * No muta el array original.
 */
export function sortCandidatesByExperience(
  candidates: Candidate[],
  order: "asc" | "desc"
): Candidate[] {
  return sortCandidatesByFields(candidates, [{ field: "yearsOfExperience", order }]);
}
