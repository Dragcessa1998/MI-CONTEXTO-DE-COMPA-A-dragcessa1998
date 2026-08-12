# Propuesta de arquitectura backend de Nexova

## 1. Contexto y decisión

Nexova es una consultora B2B de 120 personas, con operación en Valencia y Miami, y un equipo técnico de seis personas. Su plataforma debe sostener procesos estrechamente relacionados: selección de candidatos, proveedores, soporte, incidentes, telemetría, reporting y agentes de IA. Hoy el monorepo ya contiene tres frontends Next.js, lógica de negocio compartida en TypeScript, una API de talento Express y una API FastAPI para proveedores.

Propongo un **monolito modular FastAPI organizado por dominios y con capas internas**. Cada dominio mantiene su router, contratos Pydantic, reglas de negocio y acceso a datos, pero todos se despliegan inicialmente como una única aplicación.

Esta decisión responde a la realidad de Nexova:

- Un equipo de seis personas puede operar y observar un despliegue backend mejor que varios servicios independientes.
- Autenticación, incidentes, reporting y agentes comparten identidades y datos; mantenerlos juntos reduce fallos de consistencia y coordinación distribuida.
- Los límites de dominio permiten extraer un módulo como servicio separado en el futuro si aparecen necesidades medibles de escala, aislamiento o despliegue independiente.
- El monorepo existente ya favorece cambios coordinados entre `uis/`, `services/`, `packages/shared/` y la lógica de negocio.

No propongo MVC como estructura principal porque Nexova expone una API, no vistas renderizadas por el backend. Tampoco propongo microservicios o serverless ahora: añadirían despliegues, contratos remotos, observabilidad y gestión de fallos distribuidos antes de que exista una necesidad operativa demostrada.

## 2. Estado actual y evolución

El backend está dividido actualmente entre:

- `services/api`: FastAPI, Pydantic y TinyDB para el directorio de proveedores.
- `services/talent-api`: Express y TypeScript para candidatos, vacantes, procesos y reportes.
- `src/`: lógica TypeScript de scoring y matching, reutilizada por las aplicaciones que la necesitan.

La evolución debe ser incremental. `services/api` se convierte en la aplicación FastAPI principal y recibe los nuevos dominios. `services/talent-api` continúa funcionando durante la transición; no se duplican sus reglas en Python hasta decidir formalmente si se mantiene como servicio especializado o se migra un caso de uso completo. Mientras convivan, sus contratos HTTP son la frontera y cada dato tiene un único propietario.

## 3. Estructura propuesta

```text
services/api/
├── app/
│   ├── __init__.py
│   ├── main.py                 # crea FastAPI, middleware y routers
│   ├── core/
│   │   ├── config.py           # configuración tipada desde entorno
│   │   ├── security.py         # JWT, hashing y dependencias de autorización
│   │   └── errors.py           # traducción uniforme de errores a HTTP
│   ├── db/
│   │   ├── database.py         # conexión y ciclo de vida
│   │   └── migrations/         # evolución del esquema relacional
│   └── domains/
│       ├── suppliers/
│       ├── identity/
│       ├── talent/
│       ├── incidents/
│       ├── telemetry/
│       ├── reporting/
│       ├── support/
│       └── rfp/
│           ├── router.py       # entrada/salida HTTP
│           ├── schemas.py      # modelos Pydantic de API
│           ├── service.py      # reglas y casos de uso
│           ├── repository.py   # acceso a persistencia
│           └── models.py       # modelos persistidos, cuando apliquen
├── tests/
│   ├── conftest.py
│   ├── unit/
│   └── integration/
├── pyproject.toml
└── .env.example
```

El criterio principal es el **dominio de negocio**, no el tipo técnico global. Así, los archivos de proveedores permanecen juntos y no se mezclan con incidentes o autenticación. Dentro de cada dominio:

1. `router.py` conoce HTTP y delega.
2. `schemas.py` valida los contratos de entrada y salida.
3. `service.py` contiene reglas de negocio y orquesta casos de uso.
4. `repository.py` encapsula TinyDB o PostgreSQL.
5. `models.py` describe la representación persistida sin contaminar el contrato público.

`core/` sólo contiene capacidades realmente transversales. `packages/shared/` conserva contratos compartidos entre aplicaciones, pero no debe convertirse en un contenedor de reglas de todos los dominios.

## 4. Aplicación FastAPI, routers y endpoints

La documentación oficial de FastAPI recomienda dividir aplicaciones grandes en paquetes y módulos, declarar operaciones relacionadas con `APIRouter` e incluir los routers en la aplicación principal. El prefijo, las etiquetas, dependencias y respuestas comunes pueden definirse una sola vez por router, evitando duplicación.

`app/main.py` debe limitarse a crear la aplicación, configurar middleware, registrar manejadores de errores e incluir routers. No debe contener reglas de negocio ni consultas a la base de datos.

| Dominio | Router y rutas | Responsabilidad |
| --- | --- | --- |
| Sistema | `GET /health` | Salud básica de la aplicación |
| Proveedores | `/suppliers`, `/suppliers/{id}` y acciones de tarifa/estado | Directorio oficial de Patricia Solís |
| Identidad | `/auth/login`, `/auth/me`, `/users`, `/profiles/me` | Sesión, usuarios, perfiles y roles |
| Talento | `/candidates`, `/vacancies`, `/processes`, `/reports` | Selección, scoring y pipeline de candidatos |
| Incidentes | `/api/incidents`, `/api/incidents/{id}`, `/api/incidents/summary` | Soporte externalizado y cumplimiento de SLA |
| Telemetría | `/telemetry/events`, `/telemetry/report` | Captura y análisis operativo |
| Reporting | `/reporting/*` | KPIs materializados para backoffice y dirección |
| Soporte | `POST /agent/query` | Adaptador HTTP del agente RAG/LangGraph |
| RFP | `/rfp/tickets` y `/rfp/tickets/{id}` | Ingesta y seguimiento del workflow de propuestas |

Las dependencias de autenticación se aplican al router completo cuando todas sus operaciones comparten la misma política; las comprobaciones de propietario o rol permanecen en la operación o servicio correspondiente. Los códigos y modelos de respuesta se declaran explícitamente para que OpenAPI sea un contrato útil para los frontends.

Los paths exigidos por actividades del programa se mantienen estables. Si Nexova necesita versionado público, se añadirá en una migración coordinada (`/api/v1`) y no como cambio silencioso.

## 5. Persistencia y límites

TinyDB es suficiente para el alcance inicial del directorio de proveedores, pero no debe extenderse a autenticación concurrente, telemetría, incidentes o workflows. Esos dominios requieren PostgreSQL por integridad, consultas, concurrencia y migraciones.

Cada dominio accede a sus tablas mediante su repositorio. Un dominio no consulta directamente las tablas internas de otro: solicita el caso de uso a su servicio o consume un contrato explícito. Las transacciones que afectan a varios registros se resuelven en la capa de servicio.

La lógica TypeScript de scoring existente en `/src` conserva un único propietario mientras `services/talent-api` la ejecute. Si se migra a Python, debe hacerse como una migración completa con pruebas de paridad; copiar parcialmente el algoritmo produciría dos resultados distintos para una misma candidatura.

## 6. Configuración y entorno

La configuración se centraliza en `app/core/config.py` mediante una clase tipada de settings. URL de base de datos, secreto y expiración JWT, orígenes CORS, endpoints externos y nivel de logging proceden del entorno. Pydantic Settings permite leer variables de entorno en una configuración tipada y sobreescribirlas de forma controlada en pruebas.

- `.env.example` documenta nombres y valores no sensibles.
- `.env` y `.env.local` no se versionan.
- No existen secretos por defecto válidos en producción.
- La aplicación falla al arrancar si falta una configuración obligatoria.
- Los frontends sólo reciben variables `NEXT_PUBLIC_*` que puedan ser públicas; tokens, claves y DSN permanecen en el servidor.

## 7. Convivencia con los frontends

`uis/website` y `uis/backoffice` siguen siendo aplicaciones Next.js independientes. Se comunican con el backend únicamente mediante HTTP y contratos JSON; no importan modelos Python ni acceden a la base de datos.

En desarrollo, las URLs se configuran por entorno (`NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SUPPLIERS_API_URL`) y FastAPI admite explícitamente los orígenes locales necesarios. En producción se prefieren dominios conocidos o un proxy bajo el mismo origen.

CORS usa una lista cerrada por entorno. No se combina `allow_credentials=True` con un origen comodín: la documentación de FastAPI advierte que el comodín no permite los intercambios que usan credenciales. Métodos y cabeceras permitidos se limitan a los que consume la interfaz.

Los contratos se comprueban con pruebas de integración del backend y clientes tipados en el frontend. Un cambio incompatible exige coordinación o una nueva versión del endpoint.

## 8. Decisiones operativas

- **Validación:** Pydantic valida límites de confianza; la capa de servicio aplica invariantes del negocio.
- **Errores:** excepciones de dominio se traducen en un único lugar a respuestas 400/403/404/409; errores inesperados producen 500 sin stack trace ni secretos.
- **Observabilidad:** cada petición recibe un identificador de correlación y logs estructurados; nunca se registran tokens ni PII completa.
- **Pruebas:** unidades para servicios y validadores; integración para repositorios, auth y rutas; smoke test de `/health`.
- **Dependencias:** sólo se añaden cuando la biblioteca estándar o una dependencia ya instalada no resuelven el caso.
- **Migraciones:** los cambios de PostgreSQL se versionan y se ejecutan antes del despliegue de código que los requiere.

## 9. Riesgos y puntos de atención

1. **Dos backends con reglas duplicadas.** Si Express y FastAPI implementan scoring o procesos por separado, Nexova obtendrá respuestas contradictorias. Mitigación: propietario único por capacidad, contratos HTTP y migraciones completas con pruebas de paridad.
2. **Monolito sin límites reales.** Importaciones directas entre repositorios o tablas convertirían la estructura en carpetas decorativas. Mitigación: servicios de dominio como frontera, revisión de dependencias y pruebas por módulo.
3. **TinyDB fuera de su alcance.** Usarlo para telemetría, autenticación o jobs produciría carreras y consultas frágiles. Mitigación: PostgreSQL para esos dominios y migraciones versionadas.
4. **CORS o configuración permisivos.** Un comodín, secreto de desarrollo o variable pública puede exponer sesiones y datos. Mitigación: settings validados al inicio, allowlist por entorno y revisión de `.env.example`/`.gitignore`.
5. **Contratos frontend/backend desalineados.** Cambiar nombres, estados o respuestas sin coordinación rompe el backoffice. Mitigación: modelos de respuesta explícitos, OpenAPI, clientes tipados y pruebas de integración.

## 10. Criterios para separar un servicio en el futuro

Un dominio sólo se extrae del monolito si existe evidencia de al menos una de estas necesidades: escala muy distinta, aislamiento de seguridad, despliegue independiente frecuente, dependencia tecnológica incompatible o equipo propietario autónomo. La extracción conserva el contrato del módulo y añade observabilidad, reintentos e idempotencia antes de introducir una llamada remota.

## 11. Fuentes técnicas consultadas

- FastAPI, [Bigger Applications — Multiple Files](https://fastapi.tiangolo.com/tutorial/bigger-applications/): paquetes, módulos, `APIRouter`, prefijos y dependencias compartidas.
- FastAPI, [CORS (Cross-Origin Resource Sharing)](https://fastapi.tiangolo.com/tutorial/cors/): orígenes explícitos, credenciales y middleware.
- FastAPI, [Settings and Environment Variables](https://fastapi.tiangolo.com/advanced/settings/): configuración tipada y reutilizable.
- Pydantic, [Settings Management](https://docs.pydantic.dev/latest/concepts/pydantic_settings/): carga y validación de configuración desde variables de entorno.
- Next.js, [Environment Variables](https://nextjs.org/docs/app/guides/environment-variables): separación entre variables del servidor y variables públicas del navegador.

## 12. Resumen

Nexova debe avanzar con un monolito modular FastAPI, organizado por dominios y con capas pequeñas dentro de cada uno. Esta estructura mantiene bajo el coste operativo actual, respeta el monorepo y ofrece límites claros para autenticación, proveedores, incidentes, telemetría y agentes. La API Express existente se mantiene como transición con propiedad explícita de datos; sólo se migra o separa un dominio cuando una necesidad medida lo justifique.
