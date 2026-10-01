/* ==========================================================================
   Bildumargi · cliente de la API y utilidades de formato
   ========================================================================== */

class ErrorAPI extends Error {
  constructor(mensaje, datos, estado) {
    super(mensaje);
    this.datos = datos;
    this.estado = estado;
  }
}

/* ==========================================================================
   Modo demostración y grabación
   --------------------------------------------------------------------------
   La demo es Bildumargi SIN servidor: una carpeta que se abre con doble clic
   en el navegador, para equipos donde no se puede ejecutar ningún programa.
   Funciona así:
     1. En la aplicación real se activa la GRABACIÓN (?grabar_demo=1). Cada
        respuesta del servidor se guarda con una clave (método + ruta + filtros).
     2. `crear_demo.py` mete esa grabación en la carpeta de la demo como
        js/demo-datos.js (window.BILDUMARGI_DEMO_DATOS).
     3. En la demo, `pedir()` contesta con lo grabado en vez de ir al servidor.
   ========================================================================== */
const MODO_DEMO = typeof window !== "undefined" && Boolean(window.BILDUMARGI_DEMO_DATOS);
const GRABANDO = typeof window !== "undefined" && !MODO_DEMO
  && (/[?&]grabar_demo=1\b/.test(location.search) || sessionStorage.getItem("bildumargi.grabar") === "1");
if (GRABANDO) { try { sessionStorage.setItem("bildumargi.grabar", "1"); } catch { /* sin almacenamiento */ } }
const GRABACION = {};
let PETICIONES_EN_CURSO = 0;

/** Clave estable de una petición: el token de sesión no importa (cambia en
    cada análisis) y los parámetros se ordenan para que el orden no cuente. */
function claveDemo(ruta, opciones = {}) {
  const metodo = (opciones.method || "GET").toUpperCase();
  const u = new URL(ruta, "http://demo.local");
  const camino = u.pathname.replace(/^\/api\/sesion\/[^/]+/, "/api/sesion/S");
  const pares = [...u.searchParams].filter(([k]) => k !== "v").sort((a, b) =>
    a[0].localeCompare(b[0]) || String(a[1]).localeCompare(String(b[1])));
  const q = pares.map(([k, v]) => `${k}=${v}`).join("&");
  return `${metodo} ${camino}${q ? `?${q}` : ""}`;
}

/** Respuesta grabada para esa petición, probando si hace falta sin los
    parámetros que solo cambian la página o el orden de una tabla. */
function respuestaDemo(ruta, opciones) {
  const datos = window.BILDUMARGI_DEMO_DATOS;
  const clave = claveDemo(ruta, opciones);
  if (clave in datos) return datos[clave];
  // Otra página de una tabla que no se grabó: se enseña la primera
  const primeraPagina = clave.replace(/([?&]pagina=)\d+/, "$11");
  if (primeraPagina in datos) return datos[primeraPagina];
  const metodo = (opciones.method || "GET").toUpperCase();
  // Lo que en la aplicación real guardaría algo, en la demo se da por hecho.
  if (metodo !== "GET") return { ok: true, demo: true };
  return undefined;
}

async function pedir(ruta, opciones = {}) {
  if (MODO_DEMO) {
    const metodo = (opciones.method || "GET").toUpperCase();
    // Una pausa breve al «analizar», para que se vea que algo ocurre
    await new Promise((r) => setTimeout(r, metodo === "GET" ? 60 : 900));
    const cuerpo = respuestaDemo(ruta, opciones);
    if (cuerpo === undefined) throw new ErrorAPI(t("demo_no_grabado"), null, 404);
    return JSON.parse(JSON.stringify(cuerpo));
  }
  PETICIONES_EN_CURSO++;
  try {
    const cuerpo = await pedirServidor(ruta, opciones);
    if (GRABANDO) {
      GRABACION[claveDemo(ruta, opciones)] = cuerpo;
      if (typeof actualizarPanelGrabacion === "function") actualizarPanelGrabacion();
    }
    return cuerpo;
  } finally {
    PETICIONES_EN_CURSO--;
  }
}

async function pedirServidor(ruta, opciones = {}) {
  let respuesta;
  try {
    respuesta = await fetch(ruta, opciones);
  } catch (e) {
    throw new ErrorAPI(t("error_generico"), null, 0);
  }
  let cuerpo = null;
  try {
    cuerpo = await respuesta.json();
  } catch (e) {
    cuerpo = null;
  }
  if (!respuesta.ok) {
    if (cuerpo && cuerpo.detail === "sesion_caducada") {
      throw new ErrorAPI(t("sesion_caducada"), cuerpo, respuesta.status);
    }
    const mensaje = (cuerpo && (cuerpo.detail || (cuerpo.errores || []).join(" "))) || t("error_generico");
    throw new ErrorAPI(mensaje, cuerpo, respuesta.status);
  }
  return cuerpo;
}

function parametros(objeto) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(objeto)) {
    if (v === null || v === undefined || v === "") continue;
    p.append(k, v);
  }
  const cadena = p.toString();
  return cadena ? `?${cadena}` : "";
}

const API = {
  config: () => pedir("/api/config"),
  analizar: (formData) => pedir("/api/analizar", { method: "POST", body: formData }),
  idiomas: (s, q) => pedir(`/api/sesion/${s}/idiomas${parametros(q)}`),
  buscar: (s, q) => pedir(`/api/sesion/${s}/buscar${parametros(q)}`),
  ficha: (s, id) => pedir(`/api/sesion/${s}/ficha/${id}`),
  fichaRed: (id) => pedir(`/api/ficha-red/${encodeURIComponent(id)}`),
  recGenerales: (s, q) => pedir(`/api/sesion/${s}/recomendaciones/generales${parametros(q)}`),
  recPanel: (s, q) => pedir(`/api/sesion/${s}/recomendaciones/panel${parametros(q)}`),
  valoraciones: (s, id) => pedir(`/api/sesion/${s}/valoraciones/${encodeURIComponent(id)}`),
  guardarValoracion: (s, id, cuerpo) => pedir(`/api/sesion/${s}/valoraciones/${encodeURIComponent(id)}`,
    { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cuerpo) }),
  entrar: (biblioteca, clave) => pedir("/api/entrar",
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ biblioteca, clave }) }),
  adminEntrar: (clave) => pedir("/api/admin/entrar",
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ clave }) }),
  adminGuardar: (token, cuerpo) => pedir("/api/admin/configuracion",
    { method: "PUT", headers: { "Content-Type": "application/json", "X-Admin": token || "" }, body: JSON.stringify(cuerpo) }),
  adminDilve: (token) => pedir("/api/admin/dilve", { headers: { "X-Admin": token || "" } }),
  adminDilveCredenciales: (token, usuario, clave) => pedir("/api/admin/dilve/credenciales",
    { method: "POST", headers: { "Content-Type": "application/json", "X-Admin": token || "" },
      body: JSON.stringify({ usuario, clave }) }),
  adminDilveAccion: (token, accion) => pedir(`/api/admin/dilve/${accion}`,
    { method: "POST", headers: { "X-Admin": token || "" } }),
  sugerenciasAutores: (s, recalcular, filtros) => pedir(
    `/api/sesion/${s}/sugerencias/autores${parametros({ recalcular: recalcular || "", ...(filtros || {}) })}`),
  sugerenciasNovedades: (s, q) => pedir(`/api/sesion/${s}/sugerencias/novedades${parametros(q)}`),
  thema: (ui) => pedir(`/api/thema${parametros({ ui })}`),
  evaluacionAfinidad: (s, corte) => pedir(`/api/sesion/${s}/sugerencias/evaluacion${parametros({ corte: corte || "" })}`),
  historial: (s) => pedir(`/api/sesion/${s}/historial`),
  abrirCarga: (s, id) => pedir(`/api/sesion/${s}/historial/${encodeURIComponent(id)}/abrir`, { method: "POST" }),
  borrarCarga: (s, id) => pedir(`/api/sesion/${s}/historial/${encodeURIComponent(id)}`, { method: "DELETE" }),
  preferencias: (s) => pedir(`/api/sesion/${s}/preferencias`),
  signaturas: (s) => pedir(`/api/sesion/${s}/signaturas`),
  guardarSignaturas: (s, reglas) => pedir(`/api/sesion/${s}/signaturas`,
    { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ reglas }) }),
  guardarPreferencias: (s, cuerpo) => pedir(`/api/sesion/${s}/preferencias`,
    { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cuerpo) }),
  red: (s, q) => pedir(`/api/sesion/${s}/red${parametros(q)}`),
  responder: (s, cuerpo) => pedir(`/api/sesion/${s}/respuestas`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cuerpo) }),
  borrarRespuesta: (s, id) => pedir(`/api/sesion/${s}/respuestas/${encodeURIComponent(id)}`, { method: "DELETE" }),
  borrarValoracion: (s, id) => pedir(`/api/sesion/${s}/valoraciones/${encodeURIComponent(id)}`,
    { method: "DELETE" }),
};

/* ---------- Formato ------------------------------------------------------- */
// Castellano, euskera, catalán y gallego escriben los números igual (punto de
// miles, coma decimal); se usa es-ES para los cuatro porque los datos «eu» de
// algunos navegadores agrupan a la inglesa («3,447») y parten los años. El
// inglés va al revés (10,112 · 32.9%): en-GB.
const localeNum = () => (IDIOMA === "en" ? "en-GB" : "es-ES");

// Un decimal con los separadores del idioma: 1,28 o 1.28.
const numeroDecimal = (n, d = 2) => Number(n).toLocaleString(localeNum(),
  { minimumFractionDigits: d, maximumFractionDigits: d });

const miles = (n) => (n === null || n === undefined || n === ""
  ? "—" : Number(n).toLocaleString(localeNum()));

const pct = (n) => (n === null || n === undefined ? "—"
  : `${Number(n).toLocaleString(localeNum(), { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`);

const decimal = (n, d = 2) => (n === null || n === undefined ? t("sin_dato")
  : Number(n).toLocaleString(localeNum(), { minimumFractionDigits: d, maximumFractionDigits: d }));

function escapar(texto) {
  const div = document.createElement("div");
  div.textContent = texto === null || texto === undefined ? "" : String(texto);
  return div.innerHTML;
}

/* ---------- Descarga de CSV ----------------------------------------------- */
function descargarCSV(nombre, cabeceras, filas) {
  const escapaCampo = (v) => {
    const s = v === null || v === undefined ? "" : String(v);
    return /[";\n]/.test(s) ? `"${s.replaceAll('"', '""')}"` : s;
  };
  const lineas = [cabeceras.map(escapaCampo).join(";")];
  for (const fila of filas) lineas.push(fila.map(escapaCampo).join(";"));
  // BOM para que Excel abra bien los acentos al doble clic.
  const blob = new Blob(["\ufeff" + lineas.join("\r\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nombre;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
