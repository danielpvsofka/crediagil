---
name: ticket
description: Toma un issue del Project (el siguiente en Todo o el indicado), lo mueve a In progress y genera su spec con Spec Kit.
argument-hint: "[n|siguiente]"
disable-model-invocation: true
---

Toma un ticket del Project de GitHub y arranca su ciclo Spec Kit. Argumento: `$ARGUMENTS`.

Usa el MCP `github`. La configuración (repositorio, owner y número del Project, estados) está
en la sección "Flujo de tickets" de `CLAUDE.md`. No crees ramas ni hagas commit.

Regla general: si un paso falla antes del paso 5, informa el motivo y **no cambies nada** en
GitHub ni en `specs/`.

## Pasos

1. **Argumento**:
   - Vacío o `siguiente` significa "siguiente".
   - Un número entero positivo es el issue `n`.
   - Cualquier otra cosa: muestra `Uso: /ticket [n|siguiente]` y termina.
2. **Configuración y acceso**:
   - Lee owner y número del Project en `CLAUDE.md`. Si el número es `PENDIENTE`, pide
     completarlo y termina.
   - Llama a `projects_list` con `list_project_fields` y luego `list_project_items`, con
     `field_names: ["Status"]`. Pagina si hace falta.
   - Si cualquiera de las dos falla (p. ej. 403), explica que el `GITHUB_PAT` debe
     ser un token classic con scopes `repo` y `project`, y termina.
3. **Elegir el ítem**:
   - "siguiente": toma el primer ítem con `Status = Todo` en el orden devuelto. Si no hay
     ninguno, responde "No hay trabajo pendiente en Todo" y termina.
   - `n`: busca el ítem del issue `n` de este repositorio. Si no está en el Project, o el
     issue está cerrado o no existe (compruébalo con `issue_read`), informa el motivo y
     termina.
4. **Spec existente**:
   - Busca `Issue: #n` o `issues/n)` en `specs/*/spec.md`.
   - Si ya existe, indica la ruta y termina sin crear otra.
   - Si el ítem ya está en `In progress`, avisa que no se mueve de nuevo.
5. **Mover a In progress** con `projects_write`, antes de generar la spec. Si falla, informa y
   termina.
6. **Generar la spec**:
   - Lee título y cuerpo completos con `issue_read`.
   - Invoca la skill `speckit-specify` con este texto como descripción:

     ```text
     <título>

     <cuerpo completo, sin recortar>

     Issue: #<n>
     ```

   - Sigue su flujo completo, incluida la lista de verificación.
   - Si falla: informa el error, deja el ítem en `In progress` y **no** comentes en el issue.
7. **Comentar en el issue** con `add_issue_comment`:

   ```markdown
   ### Spec generada con `/ticket`

   **Spec**: `specs/NNN-nombre/spec.md`

   **Historias de usuario**
   - US1 (P1): <título>
   - …

   **Requisitos principales**: FR-001 <resumen>, FR-002 <resumen>, …

   Siguiente paso: `/speckit-plan`.
   ```

   Usa solo lo que está en la spec generada. Si el comentario falla, informa que la spec existe
   pero el comentario no se publicó.

## Informe final

Indica el issue, el estado del ítem, la ruta de la spec, el enlace al comentario y el
siguiente paso (`/speckit-plan`).
