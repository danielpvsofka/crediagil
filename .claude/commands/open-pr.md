---
description: Ejecuta tests y revisiones independientes; si no hay bloqueantes, abre el PR del issue y lo mueve a In review.
argument-hint: "<n>"
disable-model-invocation: true
---

Abre el PR del issue `#$ARGUMENTS` solo si pasan los tests y las revisiones independientes.

Usa el MCP `github`. La configuración (repositorio, owner y número del Project, estados, rama
base `main`) está en la sección "Flujo de tickets" de `CLAUDE.md`.

Sigue los pasos en orden. **Al primer fallo o bloqueo, detente sin abrir el PR** y explica el
motivo. Nunca hagas `git commit` ni `git push` sin confirmación explícita del usuario en este
momento.

## Pasos

1. **Issue y acceso**:
   - Si el argumento no es un número entero positivo, muestra `Uso: /open-pr <n>` y termina.
   - Lee el número del Project en `CLAUDE.md`; si es `PENDIENTE`, pide completarlo y termina.
   - Con `issue_read`, comprueba que el issue `n` existe y está abierto.
   - Con `projects_list` (`list_project_items`, `field_names: ["Status"]`), localiza su ítem.
     Si el acceso al Project falla (p. ej. 403), explica que el `GITHUB_PAT` debe ser un
     token classic con scopes `repo` y `project`, y termina. Si el issue no está en el Project,
     informa y termina.
2. **Rama y diff**:
   - Con `git branch --show-current`, si la rama es `main`, explica que se necesita una rama
     de trabajo y termina.
   - Obtén los archivos cambiados frente a `main`, sumando los commits de la rama y los
     cambios sin commit: `git diff --name-only main...HEAD`, `git status --porcelain`.
   - Si no hay ningún cambio, explícalo y termina.
3. **Tests**: ejecuta `uv run pytest`. Si falla, muestra el resumen del fallo y termina **sin
   invocar revisiones**.
4. **Revisión de código**:
   - Invoca el subagente `code-reviewer` con la herramienta Agent.
   - En el prompt pasa la base `main`, la lista de archivos y el diff completo:
     `git diff main...HEAD` más `git diff HEAD` si hay cambios sin commit.
5. **Revisión de cumplimiento**:
   - Si alguna ruta cambiada empieza por `src/`, invoca la skill `compliance-check` con el
     argumento `#<n>` (la base es siempre `main`).
   - Si ninguna empieza por `src/`, no la invoques y anota "compliance-check: no aplica (sin
     cambios en src/)".
6. **Veredictos**:
   - En cada respuesta, busca la primera línea que empiece por `VEREDICTO:`.
   - Si falta, o su valor no es exactamente `BLOQUEANTE` o `NO BLOQUEANTE`, cuenta como
     **BLOQUEANTE**.
   - Si alguna revisión es bloqueante, lista todos los hallazgos de cada revisor y termina.
7. **Publicar la rama**:
   - Si hay cambios sin commit o commits sin publicar (`git status -sb`), muéstralos.
   - Propón el mensaje de commit y **pide confirmación explícita** antes de `git commit` y
     `git push -u origin <rama>`.
   - Sin confirmación, termina sin abrir el PR.
8. **PR existente**: con `list_pull_requests` (`head: danielpvsofka:<rama>`, `state: open`),
   si ya existe un PR abierto para la rama, informa su enlace, no crees otro y continúa en el
   paso 10.
9. **Crear el PR** con `create_pull_request`, con `base: main`, `head: <rama>` y como título el
   del issue. Cuerpo:

   ```markdown
   Closes #<n>

   ## Resumen
   <qué cambia, a partir de spec.md>

   ## Revisión
   - Tests: ✅ `uv run pytest`
   - code-reviewer: NO BLOQUEANTE (<k> hallazgos menores)
   - compliance-check: NO BLOQUEANTE | no aplica (sin cambios en src/)

   🤖 Generated with [Claude Code](https://claude.com/claude-code)
   ```

10. **Mover a In review** el ítem con `projects_write`. Si falla, informa; el PR ya existe.
11. **Comentar en el issue** con `add_issue_comment`:
    - Localiza la feature del issue buscando `Issue: #<n>` o `issues/<n>)` en
      `specs/*/spec.md`.
    - Si no la encuentras, dilo en el comentario y resume desde el diff, sin inventar
      decisiones.

    ```markdown
    ### PR abierto: #<pr>

    **Especificado**: <historias y requisitos principales de spec.md>

    **Decidido**: <decisiones clave de research.md / plan.md>

    **Pendiente**: <tareas `- [ ]` de tasks.md> · <hallazgos menores de las revisiones>
    ```

## Informe final

Indica el enlace al PR, el estado del ítem, el veredicto de cada revisión y el enlace al
comentario.
