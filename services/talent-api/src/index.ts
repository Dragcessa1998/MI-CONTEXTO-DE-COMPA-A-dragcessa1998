/**
 * Hito 5 — API central de Nexova (servicio de talento).
 *
 * Expone candidatos, vacantes, procesos de selección, scoring/ranking y reportes.
 * Toda la lógica de negocio se REUTILIZA desde el módulo del Hito 2 (`/src`) vía el
 * alias @logic; no se duplica aquí.
 *
 * Arranque:  npm run dev   (o  npm start)
 */

import express, { type Request, type Response, type NextFunction } from "express";

import {
  filterCandidatesBySeniority,
  filterCandidatesByAvailability,
} from "@logic/utils/collections";
import { findCandidateById } from "@logic/utils/search";
import {
  rankCandidatesForVacancy,
  calculateAverageSalary,
  countCandidatesByStatus,
  findTopSkills,
  calculateVacancyFillRate,
} from "@logic/utils/transformations";
import { validateCandidate, validateVacancy } from "@logic/utils/validations";
import type {
  Candidate,
  Vacancy,
  SelectionProcess,
  SeniorityLevel,
  AvailabilityStatus,
  ProcessStage,
} from "@logic/types/models";

import {
  candidates,
  vacancies,
  processes,
  nextCandidateId,
  nextVacancyId,
  nextProcessId,
} from "./store.js";
import { isMalformedJson, sendError } from "./errors.js";
import {
  corsAllowlist,
  requireTalentAccess,
  securityHeaders,
  validateTalentSecurityConfiguration,
} from "./security.js";

const app = express();
app.disable("x-powered-by");
app.use(securityHeaders);
app.use(corsAllowlist);
app.use(express.json({ limit: "100kb", strict: true }));

const PORT = Number(process.env.PORT ?? 4000);
const PROCESS_STAGES: ProcessStage[] = [
  "Screening",
  "Interview",
  "Technical test",
  "Final interview",
  "Offer",
  "Rejected",
  "Hired",
];

// Construye un Candidate a partir del cuerpo de la petición (alta/edición completa).
function buildCandidate(body: Record<string, unknown>, id: string): Candidate {
  return {
    id,
    fullName: String(body.fullName ?? ""),
    email: String(body.email ?? ""),
    phone: String(body.phone ?? ""),
    yearsOfExperience: Number(body.yearsOfExperience),
    skills: Array.isArray(body.skills) ? (body.skills as string[]) : [],
    englishLevel: body.englishLevel as Candidate["englishLevel"],
    seniority: body.seniority as SeniorityLevel,
    currentSalary: Number(body.currentSalary),
    expectedSalary: Number(body.expectedSalary),
    availability: body.availability as AvailabilityStatus,
    location: String(body.location ?? ""),
    remoteOnly: Boolean(body.remoteOnly),
    status: (body.status as Candidate["status"]) ?? "Active",
  };
}

function buildVacancy(body: Record<string, unknown>, id: string): Vacancy {
  return {
    id,
    title: String(body.title ?? ""),
    companyName: String(body.companyName ?? ""),
    requiredSkills: Array.isArray(body.requiredSkills) ? (body.requiredSkills as string[]) : [],
    preferredSkills: Array.isArray(body.preferredSkills) ? (body.preferredSkills as string[]) : [],
    minYearsExperience: Number(body.minYearsExperience),
    maxYearsExperience: Number(body.maxYearsExperience),
    requiredEnglishLevel: body.requiredEnglishLevel as Vacancy["requiredEnglishLevel"],
    requiredSeniority: body.requiredSeniority as SeniorityLevel,
    salaryRangeMin: Number(body.salaryRangeMin),
    salaryRangeMax: Number(body.salaryRangeMax),
    isRemote: Boolean(body.isRemote),
    location: String(body.location ?? ""),
    status: (body.status as Vacancy["status"]) ?? "Open",
  };
}

// ---------- Salud ----------
app.get("/health", (_req: Request, res: Response) => {
  res.json({
    status: "ok",
    candidates: candidates.length,
    vacancies: vacancies.length,
    processes: processes.length,
  });
});

// La salud es pública; todo dato o acción de talento exige un JWT manager/admin.
app.use(requireTalentAccess);

// ---------- Candidatos (CRUD completo) ----------

// GET /candidates?seniority=Senior&availability=Immediate,2 weeks
app.get("/candidates", (req: Request, res: Response) => {
  let result: Candidate[] = candidates;

  const seniority = req.query.seniority as string | undefined;
  if (seniority) {
    result = filterCandidatesBySeniority(result, seniority as SeniorityLevel);
  }

  const availability = req.query.availability as string | undefined;
  if (availability) {
    const statuses = availability.split(",").map((value) => value.trim()) as AvailabilityStatus[];
    result = filterCandidatesByAvailability(result, statuses);
  }

  res.json({ total: result.length, data: result });
});

// GET /candidates/:id  (búsqueda lineal del Hito 2)
app.get("/candidates/:id", (req: Request, res: Response) => {
  const candidate = findCandidateById(candidates, req.params.id);
  if (!candidate) return sendError(res, 404, "CANDIDATE_NOT_FOUND", "No encontramos esa candidatura.");
  res.json(candidate);
});

// POST /candidates  (validación de negocio del Hito 2)
app.post("/candidates", (req: Request, res: Response) => {
  const candidate = buildCandidate(req.body ?? {}, nextCandidateId());
  const validation = validateCandidate(candidate);
  if (!validation.valid) return sendError(res, 400, "VALIDATION_ERROR", "Revisa los datos del candidato.", validation.errors);
  candidates.push(candidate);
  res.status(201).json(candidate);
});

// PUT /candidates/:id  (reemplazo completo)
app.put("/candidates/:id", (req: Request, res: Response) => {
  const index = candidates.findIndex((item) => item.id === req.params.id);
  if (index === -1) return sendError(res, 404, "CANDIDATE_NOT_FOUND", "No encontramos esa candidatura.");
  const candidate = buildCandidate(req.body ?? {}, req.params.id);
  const validation = validateCandidate(candidate);
  if (!validation.valid) return sendError(res, 400, "VALIDATION_ERROR", "Revisa los datos del candidato.", validation.errors);
  candidates[index] = candidate;
  res.json(candidate);
});

// PATCH /candidates/:id  (actualización parcial)
app.patch("/candidates/:id", (req: Request, res: Response) => {
  const index = candidates.findIndex((item) => item.id === req.params.id);
  if (index === -1) return sendError(res, 404, "CANDIDATE_NOT_FOUND", "No encontramos esa candidatura.");
  const merged: Candidate = { ...candidates[index]!, ...(req.body ?? {}), id: req.params.id };
  const validation = validateCandidate(merged);
  if (!validation.valid) return sendError(res, 400, "VALIDATION_ERROR", "Revisa los datos del candidato.", validation.errors);
  candidates[index] = merged;
  res.json(merged);
});

// DELETE /candidates/:id
app.delete("/candidates/:id", (req: Request, res: Response) => {
  const index = candidates.findIndex((item) => item.id === req.params.id);
  if (index === -1) return sendError(res, 404, "CANDIDATE_NOT_FOUND", "No encontramos esa candidatura.");
  candidates.splice(index, 1);
  res.status(204).end();
});

// ---------- Vacantes ----------

app.get("/vacancies", (_req: Request, res: Response) => {
  res.json({ total: vacancies.length, data: vacancies });
});

app.get("/vacancies/:id", (req: Request, res: Response) => {
  const vacancy = vacancies.find((item) => item.id === req.params.id);
  if (!vacancy) return sendError(res, 404, "VACANCY_NOT_FOUND", "No encontramos esa vacante.");
  res.json(vacancy);
});

app.post("/vacancies", (req: Request, res: Response) => {
  const vacancy = buildVacancy(req.body ?? {}, nextVacancyId());
  const validation = validateVacancy(vacancy);
  if (!validation.valid) return sendError(res, 400, "VALIDATION_ERROR", "Revisa los datos de la vacante.", validation.errors);
  vacancies.push(vacancy);
  res.status(201).json(vacancy);
});

app.delete("/vacancies/:id", (req: Request, res: Response) => {
  const index = vacancies.findIndex((item) => item.id === req.params.id);
  if (index === -1) return sendError(res, 404, "VACANCY_NOT_FOUND", "No encontramos esa vacante.");
  vacancies.splice(index, 1);
  res.status(204).end();
});

// GET /vacancies/:id/ranking  (motor de scoring del Hito 2)
app.get("/vacancies/:id/ranking", (req: Request, res: Response) => {
  const vacancy = vacancies.find((item) => item.id === req.params.id);
  if (!vacancy) return sendError(res, 404, "VACANCY_NOT_FOUND", "No encontramos esa vacante.");

  const ranking = rankCandidatesForVacancy(candidates, vacancy).map((entry) => ({
    candidateId: entry.candidate.id,
    fullName: entry.candidate.fullName,
    seniority: entry.candidate.seniority,
    score: entry.score,
  }));

  res.json({ vacancyId: vacancy.id, title: vacancy.title, ranking });
});

// ---------- Procesos de selección ----------

app.get("/processes", (_req: Request, res: Response) => {
  res.json({ total: processes.length, data: processes });
});

app.post("/processes", (req: Request, res: Response) => {
  const body = req.body ?? {};
  const errors: string[] = [];

  if (!findCandidateById(candidates, String(body.candidateId ?? ""))) {
    errors.push("candidateId no corresponde a ningún candidato");
  }
  if (!vacancies.find((item) => item.id === body.vacancyId)) {
    errors.push("vacancyId no corresponde a ninguna vacante");
  }
  if (!PROCESS_STAGES.includes(body.stage as ProcessStage)) {
    errors.push("stage no es una etapa válida");
  }
  if (errors.length > 0) return sendError(res, 400, "VALIDATION_ERROR", "Revisa los datos del proceso.", errors);

  const now = new Date();
  const process: SelectionProcess = {
    id: nextProcessId(),
    candidateId: String(body.candidateId),
    vacancyId: String(body.vacancyId),
    stage: body.stage as ProcessStage,
    score: Number(body.score ?? 0),
    notes: String(body.notes ?? ""),
    createdAt: now,
    updatedAt: now,
  };
  processes.push(process);
  res.status(201).json(process);
});

// PATCH /processes/:id  (avanzar etapa / actualizar score o notas)
app.patch("/processes/:id", (req: Request, res: Response) => {
  const index = processes.findIndex((item) => item.id === req.params.id);
  if (index === -1) return sendError(res, 404, "PROCESS_NOT_FOUND", "No encontramos ese proceso.");

  const body = req.body ?? {};
  if (body.stage !== undefined && !PROCESS_STAGES.includes(body.stage as ProcessStage)) {
    return sendError(res, 400, "VALIDATION_ERROR", "Revisa la etapa del proceso.", ["La etapa seleccionada no es válida."]);
  }

  const current = processes[index]!;
  const updated: SelectionProcess = {
    ...current,
    stage: (body.stage as ProcessStage) ?? current.stage,
    score: body.score !== undefined ? Number(body.score) : current.score,
    notes: body.notes !== undefined ? String(body.notes) : current.notes,
    updatedAt: new Date(),
  };
  processes[index] = updated;
  res.json(updated);
});

// ---------- Reportes ----------

app.get("/reports/summary", (_req: Request, res: Response) => {
  res.json({
    totalCandidates: candidates.length,
    averageExpectedSalary: calculateAverageSalary(candidates),
    byStatus: countCandidatesByStatus(candidates),
    topSkills: findTopSkills(candidates, 5),
  });
});

// GET /reports/fill-rate  (porcentaje de procesos terminados en "Hired")
app.get("/reports/fill-rate", (_req: Request, res: Response) => {
  res.json({
    totalProcesses: processes.length,
    fillRatePercent: calculateVacancyFillRate(processes),
  });
});

// ---------- 404 y manejo de errores ----------
app.use((_req: Request, res: Response) => {
  sendError(res, 404, "ROUTE_NOT_FOUND", "La ruta solicitada no existe.");
});

app.use((err: unknown, _req: Request, res: Response, _next: NextFunction) => {
  if (isMalformedJson(err)) {
    sendError(res, 400, "INVALID_JSON", "El cuerpo de la petición no contiene JSON válido.");
    return;
  }
  // El detalle se conserva únicamente en el proceso/observabilidad; nunca se
  // serializa porque puede contener rutas, credenciales o datos personales.
  sendError(res, 500, "INTERNAL_ERROR", "No pudimos completar la operación. Inténtalo de nuevo.");
});

if (process.env.NODE_ENV !== "test") {
  validateTalentSecurityConfiguration();
  app.listen(PORT, () => {
    console.log(`Nexova Talent API escuchando en http://localhost:${PORT}`);
  });
}

export default app;
