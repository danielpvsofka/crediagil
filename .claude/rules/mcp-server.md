---
paths:
  - "src/**/mcp/**"
  - "src/**/mcp_server/**"
---

# Reglas para el servidor MCP del agente

- Las herramientas MCP exponen datos y acciones; las reglas de negocio deterministas
  (identidad verificada, umbrales de preaprobación) se hacen cumplir en hooks del Claude Agent
  SDK, no dentro de la herramienta ni en su descripción (Principio II).
- Ninguna credencial en código ni en configuración versionada: se leen del entorno.
- Todo dato devuelto o registrado indica su documento de origen y el fragmento del que se
  extrajo (Principio VI). Un campo ausente en la fuente se devuelve nulo, nunca estimado
  (Principio V).
- Las descripciones de herramientas son en español y explican cuándo usarlas y cuándo escalar.
