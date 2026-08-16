# Nexova Talent API (Hito 5 — Backend)

API central de Nexova para el dominio de talento: **candidatos, vacantes, scoring y
reportes**. Implementada con **Express + TypeScript** en `/services`. **Reutiliza** toda
la lógica de negocio del Hito 2 (`/src`) vía el alias `@logic` — no la duplica.

## Ejecutar

```bash
cd services/talent-api
npm install
npm run dev        # http://localhost:4000  (recarga en caliente)
# o: npm start
npm run typecheck  # tsc --noEmit
npm test
```

`JWT_SECRET` debe coincidir con FastAPI. Excepto `/health`, toda ruta exige un
Bearer firmado con `iss=nexova-platform`, `aud=nexova-internal`, expiración y rol
`manager` o `admin`. Un usuario de soporte (`user`) recibe 403. Copia
`.env.example` sólo para desarrollo y nunca guardes el secreto real en Git.

## Endpoints

La allowlist CORS sólo refleja orígenes configurados. En Compose, el backoffice
usa el proxy same-origin `/talent-api` y el servicio no publica un puerto al host.

| Método | Ruta | Descripción | Lógica del Hito 2 |
| --- | --- | --- | --- |
| GET | `/health` | Estado y conteos | — |
| GET | `/candidates?seniority=&availability=` | Lista/filtra candidatos | `filterCandidatesBySeniority`, `filterCandidatesByAvailability` |
| GET | `/candidates/:id` | Candidato por ID | `findCandidateById` (búsqueda lineal) |
| POST | `/candidates` | Alta de candidato (valida) | `validateCandidate` |
| PUT | `/candidates/:id` | Reemplazo completo (valida) | `validateCandidate` |
| PATCH | `/candidates/:id` | Actualización parcial (valida) | `validateCandidate` |
| DELETE | `/candidates/:id` | Baja de candidato | — |
| GET | `/vacancies` · `/vacancies/:id` | Vacantes | — |
| POST | `/vacancies` | Alta de vacante (valida) | `validateVacancy` |
| DELETE | `/vacancies/:id` | Baja de vacante | — |
| GET | `/vacancies/:id/ranking` | **Ranking de candidatos** | `rankCandidatesForVacancy` (scoring 0-100) |
| GET · POST | `/processes` | Procesos de selección | — |
| PATCH | `/processes/:id` | Avanzar etapa / actualizar score o notas (valida `stage`) | — |
| GET | `/reports/summary` | Salario medio, conteo por estado, top skills | `calculateAverageSalary`, `countCandidatesByStatus`, `findTopSkills` |
| GET | `/reports/fill-rate` | % de procesos terminados en "Hired" | `calculateVacancyFillRate` |

### Ejemplos

```bash
curl localhost:4000/health
curl -H "Authorization: Bearer $TOKEN" "localhost:4000/candidates?seniority=Senior"
curl -H "Authorization: Bearer $TOKEN" localhost:4000/vacancies/V-2024-0892/ranking
curl -H "Authorization: Bearer $TOKEN" localhost:4000/reports/summary
curl -X POST localhost:4000/candidates -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"fullName":"Ana Ruiz","email":"ana@mail.com","phone":"+34600000000","yearsOfExperience":4,"skills":["TypeScript"],"englishLevel":"B2","seniority":"Semi-Senior","currentSalary":3000,"expectedSalary":3500,"availability":"1 month","location":"Valencia","remoteOnly":false,"status":"Active"}'
```

## Integración sin duplicar

`tsconfig.json` define `"@logic/*": ["../../src/*"]`, de modo que la API importa la
lógica de negocio desde su fuente única en el monorepo:

```ts
import { rankCandidatesForVacancy } from "@logic/utils/transformations";
```

El almacenamiento es **en memoria** (sembrado con los datos del Hito 2); se sustituirá
por una base de datos en un hito posterior.
