"use strict";

// Interfaz de chat (spec 008). Solo muestra y opera: no aplica reglas de negocio.
// Todo texto —del solicitante, de documentos o del modelo— entra con textContent, nunca como
// marcado (FR-024).

const hilo = document.getElementById("hilo");
const formulario = document.getElementById("formulario");
const campoMensaje = document.getElementById("mensaje");
const botonEnviar = document.getElementById("enviar");
const botonNueva = document.getElementById("nueva-conversacion");
const indicador = document.getElementById("estado-agente");
const campoAdjuntar = document.getElementById("adjuntar");
const listaAdjuntos = document.getElementById("adjuntos");
const errorAdjuntos = document.getElementById("error-adjuntos");
const selectorCasos = document.getElementById("casos");
const descripcionCaso = document.getElementById("descripcion-caso");
const campoFalla = document.getElementById("falla");
const fallaActiva = document.getElementById("falla-activa");
const errorFalla = document.getElementById("error-falla");
const botonReiniciar = document.getElementById("reiniciar");
const avisoSistema = document.getElementById("aviso-sistema");

// Valores por defecto; el servidor es la autoridad y los límites reales se leen de /api/estado.
let limites = { max_adjuntos: 5, max_bytes_adjunto: 102400, extensiones: [".txt", ".md"] };

const FALLA_MAXIMA = 20;

let ocupado = false;
let adjuntosElegidos = []; // objetos File
let casos = []; // catálogo servido por GET /api/casos
let sinClave = false; // sin clave de la API no se puede enviar

function nodo(etiqueta, clase, texto) {
  const elemento = document.createElement(etiqueta);
  if (clase) elemento.className = clase;
  if (texto !== undefined) elemento.textContent = texto;
  return elemento;
}

function agregar(elemento) {
  const vacio = hilo.querySelector(".vacio");
  if (vacio) vacio.remove();
  hilo.appendChild(elemento);
  hilo.scrollTop = hilo.scrollHeight;
}

function mostrarHiloVacio() {
  hilo.replaceChildren(nodo("p", "vacio", "Escribe un mensaje para empezar la conversación."));
}

function burbuja(clase, quien, texto, adjuntos) {
  const caja = nodo("div", `mensaje ${clase}`);
  caja.appendChild(nodo("span", "quien", quien));
  caja.appendChild(nodo("span", "texto", texto));
  if (adjuntos && adjuntos.length > 0) {
    caja.appendChild(nodo("span", "adjuntos-enviados", `Adjuntos: ${adjuntos.join(", ")}`));
  }
  agregar(caja);
  return caja;
}

function fijarOcupado(valor) {
  ocupado = valor;
  campoMensaje.disabled = valor;
  campoAdjuntar.disabled = valor;
  botonEnviar.disabled = valor || sinClave;
  botonNueva.disabled = valor;
  botonReiniciar.disabled = valor;
  selectorCasos.disabled = valor;
  campoFalla.disabled = valor;
  indicador.hidden = !valor;
}

// ---------------------------------------------------------------- adjuntos

function formatearTamano(bytes) {
  return bytes < 1024 ? `${bytes} B` : `${(bytes / 1024).toFixed(1)} KiB`;
}

function mostrarErrorAdjuntos(mensajes) {
  errorAdjuntos.replaceChildren();
  mensajes.forEach((mensaje) => errorAdjuntos.appendChild(nodo("span", "linea", mensaje)));
  errorAdjuntos.hidden = mensajes.length === 0;
}

function pintarAdjuntos() {
  listaAdjuntos.replaceChildren();
  adjuntosElegidos.forEach((archivo, indice) => {
    const ficha = nodo("li", "ficha");
    ficha.appendChild(nodo("span", "nombre", `${archivo.name} (${formatearTamano(archivo.size)})`));
    const quitar = nodo("button", "quitar", "Quitar");
    quitar.type = "button";
    quitar.setAttribute("aria-label", `Quitar ${archivo.name}`);
    quitar.addEventListener("click", () => {
      adjuntosElegidos.splice(indice, 1);
      mostrarErrorAdjuntos([]);
      pintarAdjuntos();
    });
    ficha.appendChild(quitar);
    listaAdjuntos.appendChild(ficha);
  });
}

// Comprobación previa solo como ayuda: el servidor decide (FR-008).
function motivoDeRechazo(archivo, yaElegidos) {
  const nombre = archivo.name;
  const minuscula = nombre.toLowerCase();
  if (!limites.extensiones.some((extension) => minuscula.endsWith(extension))) {
    return `"${nombre}" no se puede adjuntar: solo se admiten archivos ${limites.extensiones.join(" y ")}.`;
  }
  if (archivo.size === 0) return `"${nombre}" está vacío.`;
  if (archivo.size > limites.max_bytes_adjunto) {
    return `"${nombre}" supera el tamaño máximo de ${Math.floor(limites.max_bytes_adjunto / 1024)} KiB.`;
  }
  if (yaElegidos >= limites.max_adjuntos) {
    return `Solo se pueden adjuntar ${limites.max_adjuntos} archivos por mensaje; "${nombre}" no se añadió.`;
  }
  return null;
}

campoAdjuntar.addEventListener("change", () => {
  const rechazos = [];
  Array.from(campoAdjuntar.files).forEach((archivo) => {
    const motivo = motivoDeRechazo(archivo, adjuntosElegidos.length);
    if (motivo) rechazos.push(motivo);
    else adjuntosElegidos.push(archivo);
  });
  campoAdjuntar.value = ""; // permite volver a elegir el mismo archivo
  mostrarErrorAdjuntos(rechazos);
  pintarAdjuntos();
});

function aBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  const bloque = 0x8000;
  let binario = "";
  for (let i = 0; i < bytes.length; i += bloque) {
    binario += String.fromCharCode(...bytes.subarray(i, i + bloque));
  }
  return btoa(binario);
}

async function adjuntosParaEnviar(archivos) {
  return Promise.all(
    archivos.map(async (archivo) => ({
      nombre: archivo.name,
      contenido_b64: aBase64(await archivo.arrayBuffer()),
    })),
  );
}

// ---------------------------------------------------------------- API

async function llamar(ruta, cuerpo) {
  let respuesta;
  try {
    respuesta = await fetch(ruta, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cuerpo),
    });
  } catch {
    throw new Error("No se pudo conectar con la interfaz. ¿Sigue en marcha?");
  }
  let datos = null;
  try {
    datos = await respuesta.json();
  } catch {
    // Sin cuerpo JSON: se informa solo el estado HTTP.
  }
  if (!respuesta.ok) {
    const error = datos && datos.error;
    throw new Error(error ? error.mensaje : `Error ${respuesta.status} del servidor.`);
  }
  return datos;
}

// ---------------------------------------------------------------- avisos

// Un icono distinto por tipo: los avisos no dependen solo del color (FR-013). El rótulo viene de
// la API (una sola tabla en Python).
const ICONOS = {
  credito_preaprobado: "✔",
  informacion_solicitada: "?",
  escalamiento: "↗",
  bloqueo_regla: "⛔",
};

function pesos(valor) {
  return typeof valor === "number" ? `$${valor.toLocaleString("es-CO")}` : String(valor);
}

function tasaMensual(valor) {
  const numero = Number(valor);
  if (Number.isNaN(numero)) return String(valor);
  return `${(numero * 100).toLocaleString("es-CO", { maximumFractionDigits: 2 })} % mensual`;
}

function lineasDeAviso(aviso, turno) {
  const c = aviso.contenido || {};
  switch (aviso.tipo) {
    case "credito_preaprobado":
      return [
        `Monto: ${pesos(c.monto)}`,
        `Plazo: ${c.plazo_meses} meses`,
        `Cuota mensual: ${pesos(c.cuota)}`,
        `Tasa: ${tasaMensual(c.tasa_mensual)}`,
      ];
    case "informacion_solicitada":
      return [`Datos que se piden: ${(c.datos || []).join(", ")}`, `Motivo: ${c.motivo}`];
    case "escalamiento":
      return [
        `Referencia: ${c.id_escalamiento}`,
        `Causa: ${String(c.causa || "").replaceAll("_", " ")}`,
      ];
    case "bloqueo_regla": {
      const negacion = (turno.negaciones || []).find(
        (n) => n.herramienta === c.herramienta && n.codigo === c.codigo,
      );
      const lineas = [`Se intentó: ${c.herramienta}`, `Código: ${c.codigo}`, `Motivo: ${c.mensaje}`];
      if (negacion && negacion.accion) lineas.push(`Qué hacer: ${negacion.accion}`);
      return lineas;
    }
    default:
      return Object.entries(c).map(([clave, valor]) => `${clave}: ${JSON.stringify(valor)}`);
  }
}

function tarjetaDeAviso(aviso, turno) {
  const tarjeta = nodo("div", `aviso ${aviso.tipo}`);
  tarjeta.setAttribute("role", "note");
  const encabezado = nodo("div", "aviso-encabezado");
  const icono = nodo("span", "aviso-icono", ICONOS[aviso.tipo] || "•");
  icono.setAttribute("aria-hidden", "true");
  encabezado.appendChild(icono);
  encabezado.appendChild(nodo("strong", "aviso-rotulo", aviso.rotulo));
  tarjeta.appendChild(encabezado);
  lineasDeAviso(aviso, turno).forEach((linea) => tarjeta.appendChild(nodo("div", "aviso-linea", linea)));
  return tarjeta;
}

// Solo los avisos que trae el resultado del turno: nunca se deducen del texto de la respuesta.
function pintarAvisos(turno) {
  (turno.avisos || []).forEach((aviso) => agregar(tarjetaDeAviso(aviso, turno)));
}

// ---------------------------------------------------------------- detalle técnico

function comoTexto(valor) {
  if (valor === null || valor === undefined) return "(sin datos)";
  return typeof valor === "string" ? valor : JSON.stringify(valor, null, 2);
}

function bloqueDeDato(titulo, valor) {
  const bloque = nodo("div", "dato");
  bloque.appendChild(nodo("div", "dato-titulo", titulo));
  bloque.appendChild(nodo("pre", "dato-valor", comoTexto(valor)));
  return bloque;
}

function eventoDeTraza(evento, indice) {
  const clases = ["evento"];
  if (evento.de_subagente) clases.push("subagente");
  if (evento.es_error) clases.push("fallida");
  const fila = nodo("li", clases.join(" "));
  const encabezado = nodo("div", "evento-encabezado");
  encabezado.appendChild(nodo("strong", "evento-nombre", `${indice + 1}. ${evento.nombre}`));
  if (evento.tipo === "delegacion") encabezado.appendChild(nodo("span", "etiqueta", "delegación"));
  if (evento.de_subagente) encabezado.appendChild(nodo("span", "etiqueta", "subagente"));
  if (evento.es_error) encabezado.appendChild(nodo("span", "etiqueta error", "falló"));
  fila.appendChild(encabezado);
  fila.appendChild(bloqueDeDato("Entrada", evento.entrada));
  fila.appendChild(bloqueDeDato("Salida", evento.salida));
  return fila;
}

// Cerrado por defecto: no estorba la lectura (FR-014). Nunca se le pone `open`.
function pintarDetalle(turno) {
  const traza = turno.traza || [];
  const detalle = nodo("details", "detalle");
  const resumen = nodo("summary", "", `Detalle técnico (${traza.length} llamadas)`);
  detalle.appendChild(resumen);

  if (traza.length === 0) {
    detalle.appendChild(nodo("p", "sin-llamadas", "Sin llamadas a herramientas."));
  } else {
    const lista = nodo("ol", "traza");
    traza.forEach((evento, indice) => lista.appendChild(eventoDeTraza(evento, indice)));
    detalle.appendChild(lista);
  }

  const pie = nodo("div", "pie-detalle");
  pie.appendChild(nodo("div", "", `Razón de parada: ${turno.razon_parada ?? "(desconocida)"}`));
  pie.appendChild(nodo("div", "", `Estado del turno: ${turno.parada}`));
  if (typeof turno.costo_usd === "number") {
    pie.appendChild(nodo("div", "", `Coste: ${turno.costo_usd.toFixed(4)} USD`));
  }
  detalle.appendChild(pie);
  agregar(detalle);
}

function pintarTurno(turno) {
  if (turno.error) {
    burbuja("error", "Error", turno.error);
  } else {
    burbuja("agente", "Agente", turno.respuesta);
  }
  pintarAvisos(turno);
  pintarDetalle(turno);
}

async function enviar() {
  if (ocupado || sinClave) return;
  const mensaje = campoMensaje.value;
  if (!mensaje.trim()) return;

  const archivos = adjuntosElegidos.slice();
  const caja = burbuja(
    "solicitante",
    "Tú",
    mensaje,
    archivos.map((archivo) => archivo.name),
  );
  campoMensaje.value = "";
  adjuntosElegidos = [];
  mostrarErrorAdjuntos([]);
  pintarAdjuntos();
  fijarOcupado(true);
  try {
    const adjuntos = await adjuntosParaEnviar(archivos);
    pintarTurno(await llamar("/api/turnos", { mensaje, adjuntos }));
  } catch (error) {
    // El turno no se realizó: se devuelve el mensaje y los adjuntos para no perder lo escrito.
    caja.remove();
    campoMensaje.value = mensaje;
    adjuntosElegidos = archivos;
    pintarAdjuntos();
    burbuja("error", "Error", error.message);
  } finally {
    fijarOcupado(false);
    campoMensaje.focus();
  }
}

// ---------------------------------------------------------------- operación de la demostración

function mostrarFalla(llamadas) {
  fallaActiva.hidden = !(llamadas > 0);
  fallaActiva.textContent =
    llamadas > 0 ? `Simulación activa: las próximas ${llamadas} llamadas al core fallarán.` : "";
  campoFalla.value = String(llamadas);
}

function mostrarErrorFalla(mensaje) {
  errorFalla.textContent = mensaje || "";
  errorFalla.hidden = !mensaje;
}

// Comprobación previa solo como ayuda: el servidor valida (FR-019).
function llamadasDeFalla() {
  const texto = campoFalla.value.trim();
  const numero = Number(texto);
  if (texto === "" || !Number.isInteger(numero) || numero < 0 || numero > FALLA_MAXIMA) {
    mostrarErrorFalla(`Indica un número entero de 0 a ${FALLA_MAXIMA}.`);
    return null;
  }
  mostrarErrorFalla("");
  return numero;
}

function limpiarConversacion() {
  adjuntosElegidos = [];
  mostrarErrorAdjuntos([]);
  pintarAdjuntos();
  mostrarHiloVacio();
}

async function nuevaConversacion() {
  if (ocupado) return;
  const llamadas = llamadasDeFalla();
  if (llamadas === null) return;
  fijarOcupado(true);
  try {
    const datos = await llamar("/api/conversaciones", { falla_llamadas: llamadas });
    limpiarConversacion();
    mostrarFalla(datos.falla_llamadas);
  } catch (error) {
    burbuja("error", "Error", error.message);
  } finally {
    fijarOcupado(false);
    campoMensaje.focus();
  }
}

// ---------------------------------------------------------------- arranque

function mostrarAvisoSistema(mensaje, accion) {
  avisoSistema.replaceChildren(nodo("p", "", mensaje));
  if (accion) {
    const boton = nodo("button", "", accion.texto);
    boton.type = "button";
    boton.addEventListener("click", accion.alPulsar);
    avisoSistema.appendChild(boton);
  }
  avisoSistema.hidden = false;
}

// Nunca se muestra el valor de la clave: la API solo dice si está o no configurada (FR-021).
async function iniciar() {
  let estado;
  try {
    const respuesta = await fetch("/api/estado");
    estado = await respuesta.json();
  } catch {
    mostrarAvisoSistema("No se pudo consultar el estado de la interfaz. ¿Sigue en marcha?");
    return;
  }

  if (estado.limites) limites = estado.limites;
  if (estado.falla_simulada) mostrarFalla(estado.falla_simulada.llamadas);

  if (!estado.clave_configurada) {
    sinClave = true;
    botonEnviar.disabled = true;
    mostrarAvisoSistema(
      "Falta la clave de la API. Define la variable ANTHROPIC_API_KEY en tu entorno o en el " +
        "archivo local ignorado por git y vuelve a arrancar la interfaz. No se muestra ningún valor.",
    );
  } else if (!estado.estado_core_legible) {
    mostrarAvisoSistema(
      "No se puede leer el estado guardado del core. Puedes reiniciar los datos para empezar de cero.",
      { texto: "Reiniciar datos", alPulsar: reiniciarDatos },
    );
  }
}

function poblarCasos() {
  casos.forEach((caso) => {
    const opcion = document.createElement("option");
    opcion.value = caso.id;
    opcion.textContent = caso.nombre;
    selectorCasos.appendChild(opcion);
  });
}

async function cargarCasos() {
  try {
    const respuesta = await fetch("/api/casos");
    casos = (await respuesta.json()).casos || [];
  } catch {
    casos = [];
  }
  poblarCasos();
}

// Elegir un caso rellena el mensaje y los adjuntos; no envía nada.
function cargarCaso() {
  const caso = casos.find((c) => c.id === selectorCasos.value);
  descripcionCaso.textContent = caso ? caso.descripcion : "";
  if (!caso) return;
  campoMensaje.value = caso.mensaje;
  adjuntosElegidos = caso.adjuntos.map(
    (adjunto) => new File([adjunto.texto], adjunto.nombre, { type: "text/plain" }),
  );
  mostrarErrorAdjuntos([]);
  pintarAdjuntos();
  if (caso.falla_sugerida > 0) campoFalla.value = String(caso.falla_sugerida);
  campoMensaje.focus();
}

async function reiniciarDatos() {
  if (ocupado) return;
  const confirmado = window.confirm(
    "Esto borra las solicitudes, los escalamientos y las verificaciones guardados y empieza " +
      "una conversación nueva. ¿Continuar?",
  );
  if (!confirmado) return;
  fijarOcupado(true);
  try {
    await llamar("/api/datos/reiniciar", { confirmar: true });
    limpiarConversacion();
    mostrarFalla(0);
    hilo.appendChild(nodo("p", "nota", "Datos reiniciados: el core volvió al estado inicial."));
  } catch (error) {
    burbuja("error", "Error", error.message);
  } finally {
    fijarOcupado(false);
    campoMensaje.focus();
  }
}

formulario.addEventListener("submit", (evento) => {
  evento.preventDefault();
  enviar();
});

campoMensaje.addEventListener("keydown", (evento) => {
  if (evento.key === "Enter" && !evento.shiftKey && !evento.isComposing) {
    evento.preventDefault();
    enviar();
  }
});

botonNueva.addEventListener("click", nuevaConversacion);
botonReiniciar.addEventListener("click", reiniciarDatos);
selectorCasos.addEventListener("change", cargarCaso);

mostrarHiloVacio();
cargarCasos();
iniciar();
