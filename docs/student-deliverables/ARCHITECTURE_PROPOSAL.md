# Backend Architecture Proposal

## 1. Executive summary

This proposal defines the first backend structure for the company platform that supports the corporate site, authenticated users, operational data, inventory workflows, and future AI-assisted features. The recommendation is a **modular layered architecture organized by business domain**, implemented as a FastAPI application inside the existing company monorepo.

The structure keeps HTTP concerns, business rules, persistence, and integrations separate. It is deliberately modular without introducing distributed services too early. The company can therefore ship one deployable backend while keeping domain boundaries clear enough to split a high-load domain later.

## 2. Context and assumptions

The proposal is based on the company project built during the previous milestones. The system has a public frontend, authenticated users, operational workflows, inventory or catalog data, file-based inputs, reporting needs, and AI-assisted capabilities. The backend will serve a separate frontend through a versioned HTTP API.

These assumptions should be confirmed with the team before implementation:

- The first release is a single deployable backend with one primary relational database.
- Users have different permissions, so authentication and authorization are cross-cutting concerns.
- Inventory, suppliers, incidents, files, and AI features are separate business areas with different change rates.
- The frontend and backend are deployed independently and communicate through JSON APIs.
- Background work may be added later for file analysis, telemetry, and AI tasks; it should not block normal request handling.

## 3. Recommended architectural pattern

### Modular layered architecture

Each domain follows the same layers:

1. **API layer**: FastAPI routers, request validation, response schemas, and dependency wiring.
2. **Application layer**: use cases and orchestration. This layer coordinates a business operation without knowing HTTP details.
3. **Domain layer**: domain rules, entities, value objects, and domain-specific errors.
4. **Infrastructure layer**: database repositories, external API clients, file storage, authentication adapters, and configuration.

This is a better fit than a single global `models.py`, `routes.py`, and `services.py` because the company has several operational domains. It also avoids the operational cost of microservices while the product and traffic profile are still evolving. A serverless design would make deployment of isolated functions possible, but it would add fragmentation and integration complexity before there is evidence that independent scaling is required.

The application remains one deployable unit, but each domain owns its routes, schemas, use cases, and persistence adapters. Shared code is limited to genuinely cross-cutting concerns such as configuration, security, database session management, logging, and error handling.

## 4. Proposed repository structure

```text
backend/
├── app/
│   ├── main.py                 # FastAPI application factory and startup wiring
│   ├── core/
│   │   ├── config.py           # Environment-backed settings
│   │   ├── security.py         # Password/token helpers and auth dependencies
│   │   ├── database.py         # Engine, session and transaction boundaries
│   │   ├── errors.py           # Shared error types and exception handlers
│   │   └── logging.py          # Structured logging setup
│   ├── api/
│   │   ├── router.py           # Versioned root router
│   │   └── dependencies.py     # Shared request dependencies
│   ├── domains/
│   │   ├── auth/
│   │   │   ├── router.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   ├── models.py
│   │   │   └── repository.py
│   │   ├── users/
│   │   ├── inventory/
│   │   ├── suppliers/
│   │   ├── incidents/
│   │   ├── files/
│   │   ├── reports/
│   │   └── ai_assistant/
│   ├── integrations/
│   │   ├── storage.py           # File/object storage adapter
│   │   ├── notifications.py     # Email or messaging adapter
│   │   └── ai_provider.py       # Provider-neutral AI adapter
│   └── migrations/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── api/
├── docs/
│   └── ARCHITECTURE_PROPOSAL.md
├── .env.example
├── pyproject.toml
└── README.md
```

The domain folders are the primary ownership boundary. A domain may contain additional files as its complexity grows, but a router should not contain database queries or multi-step business rules. Repositories should not decide HTTP status codes, and schemas used for transport should not be reused as database models by convenience alone.

## 5. Domain and responsibility boundaries

| Domain | Responsibility | Example business operations |
|---|---|---|
| `auth` | Identity, sessions, roles, permissions | sign in, refresh session, authorize request |
| `users` | User profile and account lifecycle | view profile, update preferences |
| `inventory` | Items, stock state, adjustments | create item, adjust stock, query availability |
| `suppliers` | Supplier records and relationships | create supplier, list supplier items |
| `incidents` | Operational incidents and their status | open, assign, resolve incident |
| `files` | Upload metadata and processing state | register upload, request analysis |
| `reports` | Read models and reporting queries | inventory summary, incident metrics |
| `ai_assistant` | AI use cases and provider orchestration | classify file, summarize incident |

Cross-domain workflows should be explicit application services. For example, an inventory adjustment may emit an event or call a reporting projection, but the inventory domain remains the owner of stock invariants.

## 6. FastAPI router and endpoint organization

The root application includes a versioned router. Each domain exposes its own `router.py`; the root router only composes them.

```text
/api/v1/auth
/api/v1/users
/api/v1/inventory
/api/v1/suppliers
/api/v1/incidents
/api/v1/files
/api/v1/reports
/api/v1/ai
```

Representative route groups:

- `POST /api/v1/auth/login`, `POST /api/v1/auth/refresh`, `POST /api/v1/auth/logout`
- `GET /api/v1/users/me`, `PATCH /api/v1/users/me`
- `GET /api/v1/inventory/items`, `POST /api/v1/inventory/items`, `PATCH /api/v1/inventory/items/{item_id}`
- `GET /api/v1/suppliers`, `POST /api/v1/suppliers`
- `GET /api/v1/incidents`, `POST /api/v1/incidents`, `PATCH /api/v1/incidents/{incident_id}/status`
- `POST /api/v1/files`, `GET /api/v1/files/{file_id}`
- `GET /api/v1/reports/inventory`, `GET /api/v1/reports/incidents`
- `POST /api/v1/ai/file-analysis`, `POST /api/v1/ai/incident-summary`

Routes are grouped by the resource or business capability they expose, not by HTTP verb. Each router depends on an application service through FastAPI dependency injection. Authentication dependencies are applied at the router or endpoint boundary according to the required permission.

## 7. Frontend and backend as separate systems

The frontend consumes the backend through the versioned API contract. The frontend should receive the API base URL from an environment variable such as `PUBLIC_API_BASE_URL`; it must not hardcode deployment-specific URLs. The backend should keep secrets, database credentials, signing keys, and provider tokens in environment-backed configuration.

The backend must configure CORS with an explicit allow-list for known frontend origins. Credentials should only be enabled when the chosen authentication mechanism requires them, and wildcard origins must not be used with credentials. Development and production origins should be separate settings.

The frontend should handle loading, validation, and presentation. The backend remains responsible for authorization, domain validation, transaction boundaries, and consistent error responses. A shared API contract or generated client may be added later, but the two applications should remain deployable independently.

## 8. Configuration, persistence, and background work

Configuration is loaded once through a typed settings object. `.env.example` documents required variable names without containing real secrets. Database sessions are request-scoped, and write operations use explicit transaction boundaries.

Long-running work such as file analysis, report generation, telemetry processing, or AI calls should move to a background worker when it would exceed normal request latency. The HTTP endpoint should return a durable job or resource status instead of holding a request open indefinitely. This can initially be implemented behind an application interface so the first deployment does not commit the team to a particular queue technology.

## 9. Risks and points of attention

1. **A shared dumping ground**: If every domain writes to a global `services.py` or `utils.py`, ownership becomes unclear and changes create hidden coupling. New code should stay inside the owning domain unless it is demonstrably cross-cutting.
2. **Business rules in routers**: If routers perform database queries and decisions directly, the same rule will be duplicated across endpoints and become difficult to test. Routers should validate transport data and delegate to application services.
3. **Uncontrolled database coupling**: Letting one domain modify another domain's tables directly can break invariants. Cross-domain operations should use an application service or an explicit interface.
4. **Frontend trust**: CORS and client-side checks do not provide authorization. Every protected operation must enforce permissions on the backend.
5. **Synchronous AI and file work**: Calling slow providers inside ordinary request handlers can exhaust workers. These operations need timeouts, retries, observability, and a path to asynchronous execution.
6. **Environment drift**: Hardcoded URLs or secrets make local, staging, and production behavior diverge. Configuration must be explicit and environment-specific.

## 10. Research that informed the proposal

The structure follows the conventions described in the official FastAPI documentation: applications can be split into multiple files, routers can be grouped and included in a main application, and dependencies provide reusable request-scoped wiring.

- FastAPI — Bigger Applications / Multiple Files: https://fastapi.tiangolo.com/tutorial/bigger-applications/
- FastAPI — APIRouter: https://fastapi.tiangolo.com/reference/apirouter/
- FastAPI — Dependencies: https://fastapi.tiangolo.com/tutorial/dependencies/
- FastAPI — CORS: https://fastapi.tiangolo.com/tutorial/cors/
- FastAPI — Settings and environment variables: https://fastapi.tiangolo.com/advanced/settings/

These conventions directly influence the proposed `api/`, domain routers, dependency modules, and environment-backed configuration. The proposal keeps the frontend and backend separate at deployment time while using a clear, versioned API boundary between them.

## 11. Decision record

The team should approve this structure before implementing endpoints. The first implementation milestone should establish the application factory, settings, database session, API version router, authentication boundary, and one complete domain vertical slice. Once that slice is reviewed, the remaining domains can follow the same pattern without creating a large unvalidated framework upfront.
