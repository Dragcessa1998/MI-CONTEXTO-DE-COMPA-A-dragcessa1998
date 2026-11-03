# AGENTS.md — Protocolo de trabajo para agentes de código

Este archivo define cómo opera **cualquier agente de código** (Claude Code, Cursor,
Windsurf…) en el monorepo de Nexova. Es de lectura obligatoria. Si una instrucción
del usuario contradice este protocolo, **detente y pregunta** antes de actuar.

---

## 1. Lectura obligatoria al inicio de cada sesión

Antes de tocar nada, lee y carga en contexto, en este orden:

0. `BRIEFING.md` — briefing oficial de Nexova (00-general-contexts): identidad, restricciones y hoja de ruta.
1. `memory-bank/projectbrief.md` — qué es Nexova y qué problema resolvemos (negocio).
2. `memory-bank/techContext.md` — stack, estructura del monorepo y decisiones de arquitectura.
3. `memory-bank/progress.md` — estado actual y próximos pasos.
4. `CONTEXT.md` — contexto específico del hito en curso.
5. Las reglas activas de `.agents/rules/` y las skills de `.agents/skills/`.

> El banco de memoria es la **fuente de verdad** del proyecto. Si algo en el código
> contradice el banco de memoria, asúmelo como señal de deriva y verifícalo.

---

## 2. Flujo obligatorio antes de cada commit

Ejecuta estos pasos **en orden**. Ningún commit sin completarlos:

1. **Revisar contexto.** Confirma que el cambio cumple `CONTEXT.md` y las reglas de `.agents/rules/` (nombres de campos, etiquetas de dominio, ubicación del código).
2. **Verificar tipos y build.** En la app/paquete afectado: `npm run build` y/o `tsc --noEmit` sin errores. Si hay app interactiva, comprobar que arranca (`npm run dev`/`next start`) sin errores de runtime.
3. **No duplicar.** Asegúrate de que la lógica compartida se **importa** desde su fuente única (`/src`, `packages/shared`) y no se ha copiado.
4. **Actualizar el banco de memoria.** Refleja en `memory-bank/progress.md` (y en `techContext.md` si hubo decisión de arquitectura) lo completado, decidido o pendiente.
5. **Higiene y entrega.** Verifica que **no** se commitea ningún `.env*.local` ni secreto; usa mensajes de commit descriptivos; trabaja en una **rama de hito** y entrega por **Pull Request** hacia `main`.

---

## 3. Zonas protegidas — NO modificar sin confirmación explícita del desarrollador

- `BRIEFING.md`, `CONTEXT.md` y `company-choice.md` — definen la empresa y el hito; son decisiones del estudiante.
- `memory-bank/projectbrief.md` — verdad de negocio; cambiarla altera el contrato del proyecto.
- Cualquier `*/.env`, `*/.env.local` o archivo con secretos.
- Lockfiles (`package-lock.json`) salvo cuando el cambio sea, precisamente, de dependencias.
- Código de hitos ya entregados en otras apps de `uis/` o `services/` que no sea el objeto de la tarea actual.

Ante la duda sobre si algo entra aquí: **pregunta primero**.

---

## 4. Dónde va cada cosa

| Tipo de código | Ubicación |
| --- | --- |
| Web pública | `uis/website` |
| App interna / dashboards | `uis/backoffice` |
| Lógica de negocio compartida (TS) | `/src` (fuente única, se importa) |
| APIs / workers backend | `/services` |
| Tipos/utilidades compartidas | `packages/shared` |
| Config de agentes (reglas/skills) | `.agents/` |

Consulta `memory-bank/techContext.md` para el detalle de la estructura.
