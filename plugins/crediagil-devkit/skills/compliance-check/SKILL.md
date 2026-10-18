---
name: compliance-check
description: Revisión de cumplimiento de la constitución sobre los cambios en src/ de la rama actual frente a main, en contexto aislado con el subagente compliance-reviewer. Úsala cuando el diff toca lógica de negocio.
context: fork
agent: crediagil-devkit:compliance-reviewer
argument-hint: "[issue o nota para el revisor]"
allowed-tools: Read, Grep, Glob, Bash(git diff:*), Bash(git ls-files:*)
---

Revisa el cumplimiento de la constitución (`.specify/memory/constitution.md`) del siguiente
diff de lógica de negocio (`src/`) de la rama actual frente a `main`.

Contexto del solicitante: $ARGUMENTS

## Diff de `src/` (commits de la rama)

```diff
!`git diff main...HEAD -- src/`
```

## Cambios de `src/` aún sin commit

```diff
!`git diff HEAD -- src/`
```

## Archivos nuevos de `src/` que git aún no sigue

No aparecen en los diffs de arriba: léelos completos con Read.

```text
!`git ls-files --others --exclude-standard -- src/`
```

## Instrucciones

- Si ambos diffs y la lista de archivos nuevos están vacíos, responde exactamente:

  ```text
  VEREDICTO: NO BLOQUEANTE

  HALLAZGOS:
  - [menor] — sin cambios de lógica de negocio en src/.
  ```

- En otro caso, sigue tu procedimiento de revisión contra los principios I–VII y responde
  solo con el formato `VEREDICTO:` / `HALLAZGOS:`.
