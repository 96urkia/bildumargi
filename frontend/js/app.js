/* ==========================================================================
   Bildumargi · lógica de la interfaz
   ========================================================================== */

const HUECOS = [
  { clave: "topografico", etiqueta: "hueco_topo", texto: "paso_topo_desc",
    obligatorio: true, video: "videos/topografico.mp4" },
  { clave: "catalogo", etiqueta: "hueco_catalogo", texto: "paso_catalogo_desc",
    multiple: true, video: "videos/catalogo.mp4" },
  { clave: "no_prestados", etiqueta: "hueco_nunca", texto: "paso_nunca_desc",
    video: "videos/no_prestados.mp4" },
  { clave: "mas_prestados", etiqueta: "hueco_mas2", texto: "paso_mas2_desc",
    video: "videos/mas_prestados.mp4" },
];

const estado = {
  config: null,
  sesion: null,
  biblioteca: null,
  metricas: null,
  filtros: { idiomas: [], localizaciones: [] },
  hayIdiomas: false,
  vista: "diagnostico",
  menuPlegado: false,
  pasoCarga: 0,            // paso del asistente de carga
  omitidos: new Set(),     // ficheros opcionales que se han omitido
  preferencias: null,   // se rellena al arrancar (navegador) y al cargar los listados (servidor)
  ficheros: {},
  // Memoria de los controles de cada vista, para que no se reinicien al ir
  // y volver entre secciones.
  controles: {
    diagnostico: { texto: "", idioma: "__TODOS__", loc: "__TODAS__", publico: "todo" },
    secciones: { publico: "todo", idioma: "__TODOS__", loc: "__TODAS__", texto: "",
                 categoria: "", anio: "", prestamos: "todos", pagina: 1 },
    red: { filtro: "todo" },
    compras: { fuente: "presencia", personalizadas: false, ocultar_propios: true, anio_minimo: null, idioma: "__TODOS__", seccion: "", campo: "titulo", texto: "",
               excluir_fondo: true, solo_bibliografico: true },
  },
};

const $ = (sel) => document.querySelector(sel);
const crear = (etiqueta, clase, texto) => {
  const n = document.createElement(etiqueta);
  if (clase) n.className = clase;
  if (texto !== undefined) n.textContent = texto;
  return n;
};

/* ---------- Traducción de la plantilla ------------------------------------ */
function traducirPlantilla() {
  document.querySelectorAll("[data-t]").forEach((nodo) => {
    nodo.textContent = t(nodo.dataset.t);
  });
}

/* ---------- Avisos --------------------------------------------------------- */
function aviso(tipo, texto, lista) {
  const div = crear("div", `aviso ${tipo}`);
  div.appendChild(document.createTextNode(texto));
  if (lista && lista.length) {
    const ul = crear("ul");
    lista.forEach((x) => ul.appendChild(crear("li", null, x)));
    div.appendChild(ul);
  }
  return div;
}

function cargando(contenedor) {
  contenedor.innerHTML = "";
  const div = crear("div", "cargando");
  div.appendChild(crear("span", "giro"));
  div.appendChild(crear("span", null, t("cargando")));
  contenedor.appendChild(div);
}

/* ==========================================================================
   Asistente de carga de ficheros
   Un fichero por pantalla: el topográfico (obligatorio) y después catálogo,
   no prestados y más prestados, que se pueden omitir. Cada paso dice qué se
   pierde si se omite. Al final, un resumen con todo lo cargado y el botón de
   análisis. Se puede volver a cualquier paso ya visitado.
   ========================================================================== */
const CONSECUENCIA_OMITIR = {
  catalogo: "omitir_catalogo", no_prestados: "omitir_nunca", mas_prestados: "omitir_mas2",
};

const ICONO_SUBIR = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"
  stroke-linejoin="round" aria-hidden="true"><path d="M12 16V4"/><path d="m7 9 5-5 5 5"/><path d="M20 16v3a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1v-3"/></svg>`;

function pasosAsistente() {
  return [...HUECOS.map((hueco) => ({ tipo: "fichero", hueco })), { tipo: "resumen" }];
}

function estadoHueco(hueco) {
  if (estado.ficheros[hueco.clave] && estado.ficheros[hueco.clave].length) return "hecho";
  if (estado.omitidos.has(hueco.clave)) return "omitido";
  return "pendiente";
}

// Se puede ir a un paso si todos los anteriores están resueltos (con fichero
// u omitidos). Así nadie llega al análisis sin el topográfico.
function pasoAlcanzable(indice) {
  return HUECOS.slice(0, indice).every((h) => estadoHueco(h) !== "pendiente");
}

function irAPaso(indice) {
  estado.pasoCarga = indice;
  pintarPasos();
  const titulo = document.querySelector("#pasos .tarjeta-paso h2");
  if (titulo) titulo.focus({ preventScroll: true });
}

function pintarPasos() {
  const contenedor = $("#pasos");
  if (!contenedor) return;
  contenedor.innerHTML = "";
  const pasos = pasosAsistente();
  if (!(estado.pasoCarga >= 0 && estado.pasoCarga < pasos.length)) estado.pasoCarga = 0;

  // Barra de progreso: cada paso con su estado; los alcanzables se pueden pulsar
  const progreso = crear("ol", "progreso-asistente");
  pasos.forEach((p, i) => {
    const li = crear("li");
    const situacion = p.tipo === "resumen" ? "final" : estadoHueco(p.hueco);
    const b = crear("button", `paso-progreso ${situacion}${i === estado.pasoCarga ? " actual" : ""}`);
    b.type = "button";
    b.disabled = !pasoAlcanzable(Math.min(i, HUECOS.length));
    if (i === estado.pasoCarga) b.setAttribute("aria-current", "step");
    const marca = situacion === "hecho" ? "✓" : situacion === "omitido" ? "–" : String(i + 1);
    b.append(crear("span", "numero-paso", marca),
             crear("span", "nombre-paso", p.tipo === "resumen" ? t("paso_analizar") : t(p.hueco.etiqueta)));
    b.addEventListener("click", () => irAPaso(i));
    li.appendChild(b);
    progreso.appendChild(li);
  });
  contenedor.appendChild(progreso);

  const tarjeta = crear("section", "tarjeta-paso");
  const paso = pasos[estado.pasoCarga];
  if (paso.tipo === "fichero") pintarPasoFichero(tarjeta, paso.hueco, estado.pasoCarga, HUECOS.length);
  else pintarResumenCarga(tarjeta);
  contenedor.appendChild(tarjeta);
}

function tamanoLegible(bytes) {
  return bytes >= 1048576 ? `${decimal(bytes / 1048576, 1)} MB` : `${miles(Math.max(1, Math.round(bytes / 1024)))} KB`;
}

function pintarPasoFichero(tarjeta, hueco, indice, total) {
  const ficheros = estado.ficheros[hueco.clave] || [];

  const cabeza = crear("div", "cabeza-paso");
  cabeza.append(crear("span", "contador-paso", t("paso_n_de", { a: indice + 1, b: total })),
                crear("span", hueco.obligatorio ? "etiqueta-req" : "etiqueta-opt",
                      hueco.obligatorio ? t("obligatorio") : t("opcional")));
  tarjeta.appendChild(cabeza);
  const h2 = crear("h2", null, t(hueco.etiqueta));
  h2.tabIndex = -1;
  tarjeta.appendChild(h2);
  tarjeta.appendChild(crear("p", "paso-texto", t(hueco.texto)));
  if (!hueco.obligatorio) {
    const consecuencia = crear("p", "consecuencia-omitir");
    consecuencia.append(crear("strong", null, `${t("si_omites")} `), document.createTextNode(t(CONSECUENCIA_OMITIR[hueco.clave])));
    tarjeta.appendChild(consecuencia);
  }

  // Zona para soltar o elegir el fichero
  const entrada = crear("input");
  entrada.type = "file";
  entrada.accept = ".txt,text/plain";
  entrada.id = `fichero-${hueco.clave}`;
  if (hueco.multiple) entrada.multiple = true;
  const zona = crear("div", `zona-soltar${ficheros.length ? " con-fichero" : ""}`);
  const icono = crear("span", "icono-subir");
  icono.innerHTML = ICONO_SUBIR;
  const elegir = crear("button", "boton secundario", t(hueco.multiple ? "elegir_ficheros" : "elegir_fichero"));
  elegir.type = "button";
  elegir.addEventListener("click", () => entrada.click());
  const texto = crear("span", "texto-soltar", t(hueco.multiple ? "soltar_aqui_varios" : "soltar_aqui"));
  zona.append(icono, texto, crear("span", "o-soltar", t("o")), elegir, entrada);
  tarjeta.appendChild(zona);

  const asignar = (lista) => {
    const nuevos = Array.from(lista || []).filter(Boolean);
    if (!nuevos.length) return;
    // En el catálogo se suman (AbsysNet a veces lo parte en varios); en el
    // resto, el nuevo sustituye al anterior.
    estado.ficheros[hueco.clave] = hueco.multiple ? [...ficheros, ...nuevos] : [nuevos[0]];
    estado.omitidos.delete(hueco.clave);
    pintarPasos();
    const siguiente = document.querySelector("#pasos .accion-siguiente");
    if (siguiente) siguiente.focus();
  };
  entrada.addEventListener("change", () => asignar(entrada.files));
  zona.addEventListener("dragover", (e) => { e.preventDefault(); zona.classList.add("arrastre"); });
  zona.addEventListener("dragleave", () => zona.classList.remove("arrastre"));
  zona.addEventListener("drop", (e) => { e.preventDefault(); zona.classList.remove("arrastre"); asignar(e.dataTransfer.files); });

  if (ficheros.length) {
    const lista = crear("ul", "ficheros-elegidos");
    ficheros.forEach((f, i) => {
      const li = crear("li");
      li.append(crear("span", "marca-fichero", "✓"), crear("span", "nombre-fichero", f.name),
                crear("span", "tamano-fichero", tamanoLegible(f.size)));
      const quitar = crear("button", "enlace-discreto", t("quitar"));
      quitar.type = "button";
      quitar.setAttribute("aria-label", `${t("quitar")}: ${f.name}`);
      quitar.addEventListener("click", () => {
        const resto = ficheros.filter((_, j) => j !== i);
        if (resto.length) estado.ficheros[hueco.clave] = resto; else delete estado.ficheros[hueco.clave];
        pintarPasos();
      });
      li.appendChild(quitar);
      lista.appendChild(li);
    });
    tarjeta.appendChild(lista);
  }

  if (hueco.video) {
    const video = crear("button", "enlace-video", t("ver_video"));
    video.type = "button";
    video.addEventListener("click", () => abrirVideo(hueco));
    tarjeta.appendChild(video);
  }

  // Navegación
  const pie = crear("div", "pie-paso");
  if (indice > 0) {
    const anterior = crear("button", "boton secundario", `← ${t("anterior")}`);
    anterior.type = "button";
    anterior.addEventListener("click", () => irAPaso(indice - 1));
    pie.appendChild(anterior);
  }
  const derecha = crear("div", "derecha-pie");
  if (!hueco.obligatorio && !ficheros.length) {
    const omitir = crear("button", "boton secundario", t("omitir"));
    omitir.type = "button";
    omitir.addEventListener("click", () => { estado.omitidos.add(hueco.clave); irAPaso(indice + 1); });
    derecha.appendChild(omitir);
  }
  const siguiente = crear("button", "boton accion-siguiente", `${t("siguiente")} →`);
  siguiente.type = "button";
  siguiente.disabled = !ficheros.length;
  if (!ficheros.length) siguiente.title = hueco.obligatorio ? t("falta_obligatorio") : t("elige_u_omite");
  siguiente.addEventListener("click", () => irAPaso(indice + 1));
  derecha.appendChild(siguiente);
  pie.appendChild(derecha);
  tarjeta.appendChild(pie);
}

function pintarResumenCarga(tarjeta) {
  const cabeza = crear("div", "cabeza-paso");
  cabeza.appendChild(crear("span", "contador-paso", t("paso_final")));
  tarjeta.appendChild(cabeza);
  const h2 = crear("h2", null, t("resumen_carga"));
  h2.tabIndex = -1;
  tarjeta.appendChild(h2);
  tarjeta.appendChild(crear("p", "paso-texto", t("resumen_carga_texto")));

  const lista = crear("ul", "resumen-carga");
  HUECOS.forEach((hueco, i) => {
    const situacion = estadoHueco(hueco);
    const li = crear("li", situacion);
    li.appendChild(crear("span", "marca-resumen", situacion === "hecho" ? "✓" : "–"));
    const cuerpo = crear("div", "cuerpo-resumen");
    cuerpo.appendChild(crear("strong", null, t(hueco.etiqueta)));
    if (situacion === "hecho") {
      const ficheros = estado.ficheros[hueco.clave];
      cuerpo.appendChild(crear("span", "detalle-resumen", ficheros.map((f) => f.name).join(", ")));
    } else {
      cuerpo.appendChild(crear("span", "detalle-resumen", `${t("omitido")} · ${t(CONSECUENCIA_OMITIR[hueco.clave] || "falta_obligatorio")}`));
    }
    li.appendChild(cuerpo);
    const cambiar = crear("button", "enlace-discreto", t("cambiar"));
    cambiar.type = "button";
    cambiar.addEventListener("click", () => irAPaso(i));
    li.appendChild(cambiar);
    lista.appendChild(li);
  });
  tarjeta.appendChild(lista);

  if (estadoHueco(HUECOS.find((h) => h.clave === "no_prestados")) !== "hecho") {
    tarjeta.appendChild(aviso("atencion", t("aviso_sin_nunca")));
  }

  const pie = crear("div", "pie-paso");
  const anterior = crear("button", "boton secundario", `← ${t("anterior")}`);
  anterior.type = "button";
  anterior.addEventListener("click", () => irAPaso(HUECOS.length - 1));
  const analizarBoton = crear("button", "boton grande", t("analizar"));
  analizarBoton.type = "button";
  analizarBoton.id = "btn-analizar";
  analizarBoton.addEventListener("click", analizar);
  const derecha = crear("div", "derecha-pie");
  derecha.appendChild(analizarBoton);
  pie.append(anterior, derecha);
  tarjeta.appendChild(pie);
  actualizarBotonAnalizar();
}

function actualizarBotonAnalizar() {
  const boton = $("#btn-analizar");
  if (boton) boton.disabled = !estado.ficheros.topografico;
}

function abrirVideo(hueco) {
  const contenedor = crear("div");
  const video = crear("video");
  video.src = hueco.video;
  video.controls = true;
  video.autoplay = true;
  video.addEventListener("error", () => {
    contenedor.innerHTML = "";
    contenedor.appendChild(aviso("atencion", t("video_no_disponible")));
  });
  contenedor.appendChild(video);
  abrirModal(t(hueco.etiqueta), contenedor);
}


async function analizar() {
  const boton = $("#btn-analizar");
  boton.disabled = true;
  boton.textContent = t("analizando");
  $("#avisos-carga").innerHTML = "";

  const datos = new FormData();
  for (const hueco of HUECOS) {
    const ficheros = estado.ficheros[hueco.clave] || [];
    for (const f of ficheros) datos.append(hueco.clave, f);
  }

  try {
    const resultado = await API.analizar(datos);
    await entrarEnAnalisis(resultado);
  } catch (e) {
    const errores = (e.datos && e.datos.errores) || [e.message];
    $("#avisos-carga").appendChild(aviso("error", "", errores));
    $("#avisos-carga").scrollIntoView({ block: "center" });
  } finally {
    boton.textContent = t("analizar");
    actualizarBotonAnalizar();
  }
}

// Deja la aplicación lista con un análisis: lo usan la subida de ficheros y
// la reapertura de una carga guardada (pestaña Seguimiento).
async function entrarEnAnalisis(resultado, reapertura = null) {
  if (!MODO_DEMO && estado.sesion && estado.sesion !== resultado.sesion) fetch(`/api/sesion/${estado.sesion}`, { method: "DELETE" });
  estado.sesion = resultado.sesion;
  estado.carga = resultado.carga || null;
  estado.biblioteca = resultado.biblioteca;
  estado.metricas = resultado.metricas;
  estado.filtros = resultado.filtros;
  estado.hayIdiomas = resultado.hay_idiomas;

  $("#bienvenida").classList.add("oculto");
  $("#analisis").classList.remove("oculto");
  window.scrollTo({ top: 0 });

  pintarIdentidad(resultado);
  pintarMetricas(estado.metricas);
  await cargarPreferenciasBiblioteca();
  pintarNavegador();

  const avisos = $("#avisos-globales");
  avisos.innerHTML = "";
  // Al reabrir una carga anterior, que quede claro qué fecha se está viendo
  if (reapertura && reapertura.anterior) avisos.appendChild(aviso("info", t("seg_viendo_anterior", { f: fechaCorta(reapertura.fecha) })));
  if (resultado.modo_reducido) avisos.appendChild(aviso("atencion", t("modo_reducido")));
  if (resultado.sin_no_prestados) avisos.appendChild(aviso("atencion", t("aviso_sin_nunca")));
  if (resultado.avisos && resultado.avisos.length) avisos.appendChild(aviso("info", "", resultado.avisos));
  await mostrarVista(vistaInicial());
}

function pintarIdentidad(resultado) {
  estado.identidad = resultado;   // para volver a rotularla si cambia el idioma
  $("#pastilla-biblioteca").classList.remove("oculto");
  $("#nombre-biblioteca").textContent = resultado.biblioteca;
  $("#titulo-biblioteca").textContent = resultado.biblioteca;
  const m = resultado.metricas;
  const partes = [];
  if (m.poblacion) partes.push(`${miles(m.poblacion)} ${t("habitantes")}`);
  partes.push(m.superficie ? `${miles(m.superficie)} ${t("superficie")}` : t("sin_superficie"));
  partes.push(`${t("sucursal")} ${resultado.sucursal}`);
  $("#datos-biblioteca").textContent = partes.join("  \u00b7  ");
}

/* --- Piezas del panel ------------------------------------------------------ */
function tarjetaKPI(rotulo, valor, acento, pie) {
  const caja = crear("div", "kpi");
  caja.style.setProperty("--acento", acento);
  caja.appendChild(crear("span", "rotulo", rotulo));
  caja.appendChild(crear("div", "valor", valor));
  if (pie) caja.appendChild(crear("div", "pie-kpi", pie));
  return caja;
}

function panel(titulo, subtitulo, acciones) {
  // El subtítulo es opcional: si en su lugar llega un nodo o una lista, se
  // entiende que son las acciones de la cabecera.
  if (subtitulo && typeof subtitulo !== "string") { acciones = subtitulo; subtitulo = null; }
  const seccion = crear("section", "panel");
  const cabecera = crear("header");
  const texto = crear("div");
  texto.appendChild(crear("h2", null, titulo));
  if (subtitulo) texto.appendChild(crear("div", "subtitulo", subtitulo));
  cabecera.appendChild(texto);
  if (acciones) {
    const caja = crear("div", "acciones");
    (Array.isArray(acciones) ? acciones : [acciones]).forEach((a) => { if (a) caja.appendChild(a); });
    cabecera.appendChild(caja);
  }
  seccion.appendChild(cabecera);
  return seccion;
}

function pintarMetricas(m) { estado.metricas = m; }

/* --- Acceso con clave -------------------------------------------------------
   Para volver al último análisis guardado sin subir otra vez los ficheros. La
   biblioteca escribe su nombre y la clave que le da el administrador (columna
   Clave de bibliotecas.xlsx). Solo aparece si la red lo tiene disponible. */
function pintarAccesoClave() {
  const hueco = $("#acceso-clave");
  if (!hueco) return;
  const previo = {
    biblioteca: (hueco.querySelector("#acceso-biblioteca") || {}).value || "",
    clave: (hueco.querySelector("#acceso-clave-campo") || {}).value || "",
  };
  hueco.innerHTML = "";
  const disponible = Boolean(!MODO_DEMO && estado.config && estado.config.acceso_clave);
  hueco.classList.toggle("oculto", !disponible);
  const entrada = document.querySelector("#bienvenida .entrada");
  if (entrada) entrada.classList.toggle("con-acceso", disponible);
  if (!disponible) return;

  const formulario = crear("form", "tarjeta-acceso");
  formulario.noValidate = true;
  formulario.appendChild(crear("h2", null, t("acceso_titulo")));
  formulario.appendChild(crear("p", "paso-texto", t("acceso_texto")));
  const campo = (etiqueta, id, tipo, marcador, autocompletar, valor) => {
    const l = crear("label", "campo");
    l.appendChild(crear("span", "rotulo-campo", etiqueta));
    const i = crear("input");
    i.id = id; i.type = tipo; i.value = valor; i.autocomplete = autocompletar;
    if (marcador) i.placeholder = marcador;
    l.appendChild(i);
    formulario.appendChild(l);
    return i;
  };
  const biblioteca = campo(t("acceso_biblioteca"), "acceso-biblioteca", "text", t("acceso_ejemplo"), "username", previo.biblioteca);
  const clave = campo(t("acceso_clave"), "acceso-clave-campo", "password", "", "current-password", previo.clave);
  const boton = crear("button", "boton", t("acceso_entrar"));
  boton.type = "submit";
  formulario.appendChild(boton);
  const mensajes = crear("div", "mensajes-acceso");
  formulario.appendChild(mensajes);
  formulario.appendChild(crear("p", "nota-pie", t("acceso_olvido")));
  formulario.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    mensajes.innerHTML = "";
    if (!biblioteca.value.trim() || !clave.value) {
      mensajes.appendChild(aviso("atencion", t("acceso_faltan")));
      return;
    }
    boton.disabled = true;
    boton.textContent = t("acceso_entrando");
    try {
      const resultado = await API.entrar(biblioteca.value.trim(), clave.value);
      clave.value = "";
      await entrarEnAnalisis(resultado);
      if (resultado.fecha_carga) {
        $("#avisos-globales").prepend(aviso("info", t("acceso_viendo", { f: fechaCorta(resultado.fecha_carga) })));
      }
    } catch (e) {
      // El servidor responde con claves de texto (acceso_incorrecto…); si no
      // es una de ellas (errores de análisis), se enseña tal cual
      const texto = t(e.message);
      mensajes.appendChild(aviso("error", texto !== e.message ? texto : e.message));
    } finally {
      boton.disabled = false;
      boton.textContent = t("acceso_entrar");
    }
  });
  hueco.appendChild(formulario);
}

function reiniciar() {
  if (!MODO_DEMO && estado.sesion) fetch(`/api/sesion/${estado.sesion}`, { method: "DELETE" });
  estado.sesion = null;
  estado.ficheros = {};
  estado.omitidos = new Set();
  estado.pasoCarga = 0;
  $("#bienvenida").classList.remove("oculto");
  $("#analisis").classList.add("oculto");
  $("#avisos-globales").innerHTML = "";
  $("#avisos-carga").innerHTML = "";
  window.scrollTo({ top: 0 });
  pintarPasos();
  pintarAccesoClave();
  actualizarBotonAnalizar();
  pintarAvisosDeArranque();
}

/* ==========================================================================
   Navegación
   ========================================================================== */
function seccionesPosibles() {
  const secciones = [
    { clave: "diagnostico", etiqueta: "nav_diagnostico" },
    { clave: "secciones", etiqueta: "nav_secciones" },
    // La sección entera desaparece si no hay base de datos de la red: sin el
    // catálogo colectivo no hay nada que recomendar.
    { clave: "compras", etiqueta: "nav_compras", requiere: estado.config.recomendaciones_activas },
    { clave: "red", etiqueta: "nav_red",
      requiere: Boolean(estado.config.recomendaciones_activas && estado.config.valoraciones
                        && estado.config.valoraciones.activo) },
    // El seguimiento necesita que la red guarde el historial de cargas.
    { clave: "seguimiento", etiqueta: "nav_seguimiento", requiere: Boolean(configRed().historial) },
  ];
  const activas = configRed().pestanas_activas;
  return secciones.map((s) => {
    const tecnica = s.requiere === undefined || Boolean(s.requiere);
    const porRed = !activas || activas.includes(s.clave);
    // motivo: por qué no se puede usar (lo enseña la configuración)
    return { ...s, disponible: tecnica && porRed,
             motivo: !porRed ? "config_desactivada_red" : !tecnica ? "config_no_disponible" : null };
  });
}

// Configuración de la red (la decide la administración). Sin ella, todo activo.
function configRed() {
  return (estado.config && estado.config.red) || {};
}

// Pestañas que se ven: las disponibles menos las que la biblioteca ha
// ocultado. Si ocultara todas, se muestran igualmente las disponibles.
function seccionesDisponibles() {
  const disponibles = seccionesPosibles().filter((s) => s.disponible);
  const ocultas = (estado.preferencias && estado.preferencias.pestanas_ocultas) || [];
  const visibles = disponibles.filter((s) => !ocultas.includes(s.clave));
  return visibles.length ? visibles : disponibles;
}

// Menú lateral. «Sugerencias de compra» despliega sus fuentes como submenú:
// al elegir una, el panel de arriba (indicadores, matriz y oferta) no cambia;
// solo cambia la lista de abajo.
function pintarNavegador() {
  const nav = $("#navegador");
  nav.innerHTML = "";
  const lista = crear("ul", "menu-lateral");
  for (const seccion of seccionesDisponibles()) {
    const item = crear("li");
    const actual = estado.vista === seccion.clave;
    const boton = crear("button", actual ? "activo" : "", t(seccion.etiqueta));
    boton.type = "button";
    if (actual) boton.setAttribute("aria-current", "page");
    boton.addEventListener("click", () => mostrarVista(seccion.clave));
    item.appendChild(boton);
    if (seccion.clave === "compras" && actual) {
      const fuentes = fuentesCompra();
      if (fuentes.length > 1) {
        const sub = crear("ul", "submenu");
        fuentes.forEach((f) => {
          const li = crear("li");
          const b = crear("button", estado.controles.compras.fuente === f.clave ? "activo" : "", t(f.etiqueta));
          b.type = "button";
          b.addEventListener("click", () => {
            estado.controles.compras.fuente = f.clave;
            mostrarVista("compras");
          });
          li.appendChild(b);
          sub.appendChild(li);
        });
        item.appendChild(sub);
      }
    }
    lista.appendChild(item);
  }
  nav.appendChild(lista);
  const plegar = crear("button", "plegar-menu", estado.menuPlegado ? "»" : "«");
  plegar.type = "button";
  plegar.title = t("menu_plegar");
  plegar.setAttribute("aria-label", t("menu_plegar"));
  plegar.addEventListener("click", () => {
    estado.menuPlegado = !estado.menuPlegado;
    document.body.classList.toggle("menu-plegado", estado.menuPlegado);
    try { localStorage.setItem("bildumargi.menu", estado.menuPlegado ? "1" : "0"); } catch { /* sin almacenamiento */ }
    pintarNavegador();
  });
  nav.appendChild(plegar);
}

async function mostrarVista(clave) {
  if (!seccionesDisponibles().some((s) => s.clave === clave)) clave = vistaInicial();
  estado.vista = clave;
  pintarNavegador();
  soltarMedidores();
  // Secciones es un panel de una sola pantalla: el documento deja de crecer
  // y la vista se ajusta al alto de la ventana (ver .modo-panel en el CSS).
  document.body.classList.toggle("modo-panel", ["diagnostico", "secciones", "compras", "red", "seguimiento"].includes(clave));
  const vista = $("#vista");
  cargando(vista);
  try {
    const pintores = {
      diagnostico: vistaDiagnostico, secciones: vistaSecciones, compras: vistaCompras, red: vistaRed,
      seguimiento: vistaSeguimiento,
    };
    await (pintores[clave] || vistaDiagnostico)(vista);
  } catch (e) {
    vista.innerHTML = "";
    vista.appendChild(aviso("error", e.message));
    if (e.estado === 404) {
      const boton = crear("button", "boton secundario", t("cambiar_ficheros"));
      boton.addEventListener("click", reiniciar);
      vista.appendChild(boton);
    }
  }
}

/* ---------- Controles comunes --------------------------------------------- */
function selector(etiqueta, opciones, valor, alCambiar, clase = "") {
  const campo = crear("div", `campo ${clase}`);
  const id = `sel-${Math.random().toString(36).slice(2, 8)}`;
  const label = crear("label", null, etiqueta);
  label.htmlFor = id;
  const select = crear("select");
  select.id = id;
  let grupo = null;
  for (const op of opciones) {
    if (op.grupo !== undefined) {      // separador: agrupa las opciones siguientes
      grupo = crear("optgroup");
      grupo.label = op.grupo;
      select.appendChild(grupo);
      continue;
    }
    const nodo = crear("option", null, op.etiqueta);
    nodo.value = op.valor;
    if (String(op.valor) === String(valor)) nodo.selected = true;
    (grupo || select).appendChild(nodo);
  }
  select.addEventListener("change", () => alCambiar(select.value));
  campo.append(label, select);
  return campo;
}

function entradaTexto(etiqueta, valor, marcador, alConfirmar, clase = "") {
  const campo = crear("div", `campo ${clase}`);
  const label = crear("label", null, etiqueta);
  const input = crear("input");
  input.type = "text";
  input.value = valor || "";
  input.placeholder = marcador || "";
  // Enter y «change» llegan los dos al pulsar Intro: solo se confirma si el
  // texto ha cambiado desde la última vez, para no pedir dos veces lo mismo.
  let confirmado = input.value;
  const confirmar = () => {
    if (input.value === confirmado) return;
    confirmado = input.value;
    alConfirmar(input.value);
  };
  input.addEventListener("change", confirmar);
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") confirmar(); });
  campo.append(label, input);
  return campo;
}

/* --- Buscador de signaturas con memoria de las últimas búsquedas ---------
   Las búsquedas que un bibliotecario repite («*(460*», «32*, I 32*») se
   ofrecen como sugerencias. Se guardan solo en este navegador.
   ------------------------------------------------------------------------ */
const CLAVE_BUSQUEDAS = "bildumargi.busquedas_signatura";

function busquedasRecientes() {
  try { return JSON.parse(localStorage.getItem(CLAVE_BUSQUEDAS)) || []; } catch { return []; }
}

function recordarBusqueda(texto) {
  const limpio = String(texto || "").trim();
  if (!limpio) return;
  const lista = [limpio, ...busquedasRecientes().filter((b) => b !== limpio)].slice(0, 10);
  try { localStorage.setItem(CLAVE_BUSQUEDAS, JSON.stringify(lista)); } catch { /* sin almacenamiento */ }
}

function campoSignatura(valor, alConfirmar, clase = "busqueda") {
  const campo = entradaTexto(t("buscar_signatura"), valor, t("placeholder_signatura"),
    (v) => { recordarBusqueda(v); alConfirmar(v.trim()); }, clase);
  const input = campo.querySelector("input");
  input.title = t("ayuda_signatura");
  input.setAttribute("aria-description", t("ayuda_signatura"));
  input.spellcheck = false;
  input.autocomplete = "off";
  const lista = crear("datalist");
  lista.id = `sugerencias-signatura-${Math.random().toString(36).slice(2, 7)}`;
  busquedasRecientes().forEach((b) => { const o = crear("option"); o.value = b; lista.appendChild(o); });
  input.setAttribute("list", lista.id);
  campo.appendChild(lista);
  return campo;
}

function entradaNumero(etiqueta, valor, alCambiar, opciones = {}) {
  const campo = crear("div", `campo ${opciones.clase || "estrecho"}`);
  const label = crear("label", null, etiqueta);
  const input = crear("input");
  input.type = "number";
  input.value = valor ?? "";
  if (opciones.min !== undefined) input.min = opciones.min;
  if (opciones.max !== undefined) input.max = opciones.max;
  if (opciones.paso) input.step = opciones.paso;
  input.addEventListener("change", () => alCambiar(input.value));
  campo.append(label, input);
  return campo;
}

function casilla(etiqueta, valor, alCambiar) {
  const label = crear("label", "casilla");
  const input = crear("input");
  input.type = "checkbox";
  input.checked = !!valor;
  input.addEventListener("change", () => alCambiar(input.checked));
  label.append(input, document.createTextNode(etiqueta));
  return label;
}

function opcionesIdioma() {
  return [{ valor: "__TODOS__", etiqueta: t("todos_idiomas") }]
    .concat(estado.filtros.idiomas.map((i) => ({ valor: i, etiqueta: traducirEtiqueta(i) })));
}

function opcionesLoc() {
  return [{ valor: "__TODAS__", etiqueta: t("todas") }]
    .concat(estado.filtros.localizaciones.map((l) => ({ valor: l, etiqueta: traducirEtiqueta(l) })));
}

/* ==========================================================================
   Vista: diagnóstico
   Radiografía de la colección en una pantalla: cinco indicadores con
   referencia, peso y uso relativo por sección, años de edición coloreados por
   uso y una lectura automática en texto. Todo describe; nada propone retirar.
   ========================================================================== */
const MINIMO_FIABLE = 20;   // volúmenes por debajo de los cuales un % es orientativo

function esqueletoDiagnostico(vista) {
  vista.innerHTML = "";
  const raiz = crear("div", "panel-secciones panel-diagnostico");
  const filtros = crear("div", "barra-superior barra-panel");
  const rejilla = crear("div", "rejilla-diagnostico");
  const indicadores = crear("div", "fila-indicadores");
  const huecos = { raiz, filtros, rejilla, indicadores, kpis: [] };
  for (let i = 0; i < 5; i++) {
    const h = crear("div", "hueco-indicador");
    indicadores.appendChild(h);
    huecos.kpis.push(h);
  }
  rejilla.appendChild(indicadores);
  const hueco = (clase) => { const h = crear("div", `hueco ${clase}`); rejilla.appendChild(h); return h; };
  huecos.rendimiento = hueco("zona-rendimiento");
  huecos.radiografia = hueco("zona-radiografia");
  huecos.anios = hueco("zona-anios");
  raiz.append(filtros, rejilla);
  vista.appendChild(raiz);
  return huecos;
}

let peticionDiagnostico = 0;

async function vistaDiagnostico(vista) {
  soltarMedidores();
  const huecos = esqueletoDiagnostico(vista);
  await refrescarDiagnostico(huecos);
}

async function refrescarDiagnostico(huecos) {
  const c = estado.controles.diagnostico;
  const numero = ++peticionDiagnostico;
  huecos.rejilla.classList.add("actualizando");
  let datos;
  try {
    datos = await API.buscar(estado.sesion, {
      campo: "signatura", texto: c.texto, publico: c.publico, idioma: c.idioma, loc: c.loc,
      por_pagina: 1, ligero: true, ui: IDIOMA,
    });
  } finally {
    if (numero === peticionDiagnostico) huecos.rejilla.classList.remove("actualizando");
  }
  if (numero !== peticionDiagnostico || !huecos.raiz.isConnected) return;

  const recargar = () => refrescarDiagnostico(huecos).catch((e) => huecos.filtros.after(aviso("error", e.message)));
  const analisisDatos = prepararDiagnostico(datos, c);

  pintarFiltrosDiagnostico(huecos.filtros, c, recargar);
  pintarIndicadores(huecos.kpis, analisisDatos);
  pintarRendimiento(huecos.rendimiento, analisisDatos, c);
  pintarRadiografia(huecos.radiografia, analisisDatos);
  pintarAniosUso(huecos.anios, analisisDatos);
}

/* --- Cálculos: todo sale de /buscar en modo ligero ------------------------- */
function prepararDiagnostico(datos, c) {
  const r = datos.resumen;
  const tasaGlobal = r.volumenes ? r.pct_prestamos / 100 : 0;
  const secciones = datos.categorias_lista
    .filter((f) => f.volumenes > 0)
    .map((f) => ({
      clave: f.clave, etiqueta: traducirEtiqueta(f.clave), volumenes: f.volumenes,
      prestados: f.prestados, peso: r.volumenes ? (f.volumenes / r.volumenes) * 100 : 0,
      tasa: f.volumenes ? f.prestados / f.volumenes : 0,
      usoRel: tasaGlobal ? (f.prestados / f.volumenes) / tasaGlobal : null,
    }))
    .sort((a, b) => b.volumenes - a.volumenes);

  const anioActual = estado.config.anio_actual;
  const filasAnio = datos.anios.filas;
  const conAnio = filasAnio.reduce((s, f) => s + f.volumenes, 0) + datos.anios.anteriores;
  const recientes = filasAnio.filter((f) => f.clave >= anioActual - 4).reduce((s, f) => s + f.volumenes, 0);
  const antiguos = filasAnio.filter((f) => f.clave < anioActual - 20).reduce((s, f) => s + f.volumenes, 0)
    + datos.anios.anteriores;

  const fiables = secciones.filter((s) => s.volumenes >= MINIMO_FIABLE && s.usoRel !== null);
  const filtrado = Boolean(c.texto) || c.loc !== "__TODAS__" || c.publico !== "todo" || c.idioma !== "__TODOS__";
  return {
    datos, resumen: r, secciones, fiables, tasaGlobal, filtrado,
    anios: { filas: filasAnio, conAnio, recientes, antiguos, intermedios: conAnio - recientes - antiguos,
             sinAnio: datos.anios.sin_anio, anteriores: datos.anios.anteriores },
    metricas: estado.metricas,
  };
}

/* --- Filtros ---------------------------------------------------------------- */
function pintarFiltrosDiagnostico(barra, c, recargar) {
  barra.innerHTML = "";
  barra.appendChild(campoSignatura(c.texto, (v) => { c.texto = v; recargar(); }));
  barra.appendChild(selector(t("localizacion"), opcionesLoc(), c.loc, (v) => { c.loc = v; recargar(); }));
  barra.appendChild(selector(t("publico"), [
    { valor: "todo", etiqueta: t("todo_fondo") },
    { valor: "adultos", etiqueta: t("solo_adultos") },
    { valor: "infantil", etiqueta: t("solo_infantil") },
  ], c.publico, (v) => { c.publico = v; recargar(); }));
  if (estado.hayIdiomas) {
    barra.appendChild(selector(t("col_idioma"), opcionesIdioma(), c.idioma, (v) => { c.idioma = v; recargar(); }));
  }
  const migas = crear("div", "migas migas-panel");
  if (c.texto) {
    migas.appendChild(crear("span", "rotulo-campo", t("seleccion_activa")));
    migas.appendChild(miga(t("miga_signatura", { n: c.texto }), () => { c.texto = ""; recargar(); }));
  }
  barra.appendChild(migas);
}

/* --- Indicadores ------------------------------------------------------------ */

/** Las cuatro tarjetas del estado general del fondo: volúmenes, documentos
    por habitante, circulación y actualidad. Las usan tanto Diagnóstico como
    la cabecera de Sugerencias de compra, siempre sobre el fondo COMPLETO,
    para que sirvan de referencia constante sin importar qué se esté filtrando
    en la lista de propuestas. */
function tarjetasResumenColeccion(a) {
  const r = a.resumen;
  const m = a.metricas || {};
  const tarjetas = [];

  // 1 · Volúmenes
  tarjetas.push(tarjetaIndicador({
    rotulo: t("col_volumenes"), valor: miles(r.volumenes), acento: PALETA.cian,
    grafico: minigrafica(a.anios.filas.map((f) => f.volumenes), PALETA.cian),
    contexto: a.filtrado
      ? t("kpi_sobre_total", { n: miles(m.total ?? r.volumenes) })
      : t("diag_vol_ctx", { k: miles(a.secciones.length), a: r.anio_medio ?? "—" }),
  }));

  // 2 · Documentos por habitante frente a la referencia de la red
  const pauta = m.pauta;
  if (m.docs_habitante && pauta) {
    const d = m.docs_habitante;
    const nivel = d < pauta.docs_hab_min ? "aviso" : d > pauta.docs_hab_max ? "alto" : "ok";
    const escala = Math.max(pauta.docs_hab_max * 2, 1);
    tarjetas.push(tarjetaIndicador({
      rotulo: t("diag_docs_hab"), valor: decimal(d, 2), acento: PALETA.violeta,
      estado: { nivel, texto: t(nivel === "ok" ? "ref_dentro" : nivel === "alto" ? "ref_encima" : "ref_debajo") },
      grafico: graficoBala({
        valor: d, escala, referencia: [pauta.docs_hab_min, pauta.docs_hab_max],
        bandas: [[0, pauta.docs_hab_min], [pauta.docs_hab_min, pauta.docs_hab_max], [pauta.docs_hab_max, escala]],
        color: PALETA.texto,
      }),
      contexto: t(a.filtrado ? "diag_ref_completo" : "diag_ref", {
        a: decimal(pauta.docs_hab_min, 1), b: decimal(pauta.docs_hab_max, 1), f: pauta.fuente_corta }),
      ayuda: pauta.fuente,
    }));
  } else {
    tarjetas.push(tarjetaIndicador({
      rotulo: t("diag_docs_hab"), valor: "—", acento: PALETA.violeta,
      contexto: m.poblacion ? t("diag_sin_pauta") : t("diag_sin_poblacion"),
    }));
  }

  // 3 · Índice de circulación
  // Sin umbrales de «buena» o «mala» circulación: no hay norma que los funde.
  // Se da la cifra y su lectura en palabras («1 de cada 3»).
  const c = r.pct_prestamos;
  const fraccion = textoFraccion(c);
  tarjetas.push(tarjetaIndicador({
    rotulo: t("m_circulacion"), valor: pct(c), acento: PALETA.verde,
    estado: fraccion ? { nivel: "info", texto: fraccion } : null,
    grafico: graficoBala({ valor: c, escala: 100, color: PALETA.verde }),
    contexto: t("diag_circ_ctx"),
  }));

  // 4 · Actualidad del fondo
  const an = a.anios;
  const base = an.conAnio || 1;
  tarjetas.push(tarjetaIndicador({
    rotulo: t("diag_actualidad"), valor: pct((an.recientes / base) * 100), acento: PALETA.ambar,
    grafico: barraApilada([
      { valor: an.recientes, clase: "tramo-reciente", etiqueta: t("tramo_reciente") },
      { valor: an.intermedios, clase: "tramo-medio", etiqueta: t("tramo_medio") },
      { valor: an.antiguos, clase: "tramo-antiguo", etiqueta: t("tramo_antiguo") },
    ]),
    contexto: t("diag_actualidad_ctx", { v: pct((an.antiguos / base) * 100), s: miles(an.sinAnio) }),
  }));

  return tarjetas;
}

function pintarIndicadores(huecos, a) {
  const tarjetas = tarjetasResumenColeccion(a);

  // 5 · Secciones con más demanda que peso (sin sentido con una sola sección:
  // el uso relativo de una sección frente a sí misma siempre es 1,0)
  const encima = a.fiables.filter((s) => s.usoRel >= 1);
  if (a.fiables.length < 2) {
    tarjetas.push(tarjetaIndicador({
      rotulo: t("diag_demanda"), valor: "—", acento: PALETA.ambar, contexto: t("diag_demanda_una"),
    }));
  } else tarjetas.push(tarjetaIndicador({
    rotulo: t("diag_demanda"), valor: miles(encima.length), acento: PALETA.ambar, explicacion: ayudaUsoRelativo(),
    unidad: t("diag_demanda_unidad", { n: miles(a.fiables.length) }),
    grafico: rejillaCuenta(a.fiables.map((s) => ({
      clase: s.usoRel >= 1 ? "encima" : "debajo",
      titulo: `${s.etiqueta}: ${numeroDecimal(s.usoRel, 2)}`,
    }))),
    contexto: t("diag_demanda_ctx", { m: MINIMO_FIABLE }),
  }));

  tarjetas.forEach((tarjeta, i) => huecos[i].replaceChildren(tarjeta));
}

/* --- Peso y uso relativo por sección ------------------------------------- */
function pintarRendimiento(hueco, a, c) {
  const cuerpo = cuadroPanel(hueco, t("rend_titulo"), null, ayudaUsoRelativo([t("rend_pie", { m: MINIMO_FIABLE })]));
  if (!a.secciones.length || !a.tasaGlobal) {
    cuerpo.appendChild(crear("p", "vacio", t("sin_datos_seccion")));
    return;
  }
  const irASecciones = (clave) => {
    const s = estado.controles.secciones;
    Object.assign(s, { categoria: clave, texto: c.texto, loc: c.loc, publico: c.publico,
                       idioma: c.idioma, pagina: 1 });
    mostrarVista("secciones");
  };
  const textos = {
    titulo: t("rend_titulo"), seccion: t("rend_seccion"), peso: t("rend_peso"), uso: t("rend_uso"),
    otras: (n) => t("rend_otras", { n }),
    detalle: (f) => t("rend_detalle", {
      s: f.etiqueta, v: miles(f.volumenes), p: pct(f.peso),
      r: pct(f.volumenes ? (f.prestados / f.volumenes) * 100 : 0),
      u: f.usoRel === null ? "—" : numeroDecimal(f.usoRel, 2) }),
  };
  cuerpo.appendChild(grafico((ancho, alto) => graficoRendimiento(a.secciones, {
    ancho, alto, tasaGlobal: a.tasaGlobal, minimo: MINIMO_FIABLE, alPulsar: irASecciones, textos,
  }), t("rend_titulo")));
}

/* --- Radiografía en texto --------------------------------------------------- */
function pintarRadiografia(hueco, a) {
  const cuerpo = cuadroPanel(hueco, t("radiografia"));
  const lista = crear("ul", "radiografia");
  radiografiaTextos(a).forEach(({ texto, tono }) => {
    const li = crear("li", tono || "");
    li.textContent = texto;
    lista.appendChild(li);
  });
  cuerpo.appendChild(lista);
}

function radiografiaTextos(a) {
  const salida = [];
  const r = a.resumen;
  const uso = (v) => numeroDecimal(v, 2);
  if (!r.volumenes) return [{ texto: t("sin_datos_seccion") }];

  const k = a.secciones.length;
  if (k === 1) {
    salida.push({ texto: t("rx_tamano_una", { n: miles(r.volumenes), s: a.secciones[0].etiqueta }) });
  } else if (k <= 3) {
    salida.push({ texto: t("rx_tamano_pocas", { n: miles(r.volumenes), k: miles(k) }) });
  } else {
    const tres = a.secciones.slice(0, 3).reduce((s, f) => s + f.volumenes, 0);
    salida.push({ texto: t("rx_tamano", { n: miles(r.volumenes), k: miles(k),
                                          p: pct((tres / r.volumenes) * 100) }) });
  }
  salida.push({ texto: t("rx_circ", { p: pct(r.pct_prestamos) }) });

  if (a.fiables.length >= 2) {
    const orden = [...a.fiables].sort((x, y) => y.usoRel - x.usoRel);
    const mas = orden[0], menos = orden[orden.length - 1];
    salida.push({ texto: t("rx_mas", { s: mas.etiqueta, u: uso(mas.usoRel) }), tono: "calido" });
    salida.push({ texto: t("rx_menos", { s: menos.etiqueta, u: uso(menos.usoRel) }), tono: "frio" });
  }
  const an = a.anios;
  if (an.conAnio) {
    salida.push({ texto: t("rx_actual", { p5: pct((an.recientes / an.conAnio) * 100),
                                          p20: pct((an.antiguos / an.conAnio) * 100) }) });
  }
  const m = a.metricas || {};
  if (m.docs_habitante && m.pauta) {
    const d = m.docs_habitante, p = m.pauta;
    const clave = d < p.docs_hab_min ? "rx_docs_debajo" : d > p.docs_hab_max ? "rx_docs_encima" : "rx_docs_dentro";
    salida.push({ texto: t(clave, { d: decimal(d, 2), a: decimal(p.docs_hab_min, 1), b: decimal(p.docs_hab_max, 1) }) });
    if (d > p.docs_hab_max && m.poblacion && m.poblacion < 5000) salida.push({ texto: t("rx_docs_pequeno"), tono: "nota" });
  }
  if (a.filtrado) salida.push({ texto: t("rx_filtro"), tono: "nota" });
  return salida;
}

/* --- Años de edición coloreados por uso ----------------------------------- */
function pintarAniosUso(hueco, a) {
  const pies = [];
  if (a.anios.anteriores) pies.push(t("anteriores_n", { n: miles(a.anios.anteriores) }));
  if (a.anios.sinAnio) pies.push(t("sin_anio_n", { n: miles(a.anios.sinAnio) }));
  const cuerpo = cuadroPanel(hueco, t("anios_uso_titulo"), pies.join(" · ") || null,
    leyendaGradiente(t("col_rotacion")));
  if (!a.anios.filas.length) { cuerpo.appendChild(crear("p", "vacio", t("sin_datos_seccion"))); return; }
  const puntos = a.anios.filas.map((f) => ({
    anio: f.clave, volumenes: f.volumenes, tasa: f.rotacion,
    detalle: t("anios_detalle", { a: f.clave, v: miles(f.volumenes), r: pct(f.rotacion) }),
  }));
  cuerpo.appendChild(grafico((ancho, alto) => graficoAniosUso(puntos, { ancho, alto, titulo: t("anios_uso_titulo") }), t("anios_uso_titulo")));
}

/* ==========================================================================
   Vista: secciones
   Panel de una sola pantalla centrado en la signatura. El esqueleto se monta
   una vez y cada filtro repinta solo el contenido de los cuadros: así no hay
   parpadeo ni salto, y la tabla resumen conserva su desplazamiento.
   ========================================================================== */

/* --- Gráficos medidos -----------------------------------------------------
   El gráfico se dibuja en píxeles reales con el tamaño de su celda, no con un
   viewBox fijo que se escale: así la letra mide lo mismo en cualquier pantalla
   y el gráfico ocupa el alto que le da la rejilla, no el que le impone su
   propio ancho. Se vuelve a dibujar cuando la celda cambia de tamaño.
   ------------------------------------------------------------------------ */
const MEDIDORES = new Set();

/** Como `lienzoMedido`, pero con la altura dada: sirve dentro de zonas con
    desplazamiento, donde la caja no tiene altura propia que medir. */
function lienzoAncho(dibujar, alto) {
  const caja = crear("div", "lienzo-medido");
  caja.style.height = `${alto}px`;
  let ultimo = 0;
  let pendiente = false;
  const pintar = () => {
    pendiente = false;
    if (!caja.isConnected) { observador.disconnect(); MEDIDORES.delete(observador); return; }
    const ancho = Math.floor(caja.clientWidth);
    if (ancho < 60 || ancho === ultimo) return;
    ultimo = ancho;
    caja.replaceChildren(dibujar(ancho, alto));
  };
  const observador = new ResizeObserver(() => {
    if (!pendiente) { pendiente = true; requestAnimationFrame(pintar); }
  });
  observador.observe(caja);
  MEDIDORES.add(observador);
  return caja;
}

const ICONO_AMPLIAR = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
  stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
  <path d="M15 3h6v6"/><path d="M9 21H3v-6"/><path d="M21 3l-7 7"/><path d="M3 21l7-7"/></svg>`;

/** Abre el mismo gráfico en un cuadro más grande. Se vuelve a invocar la
    misma función que lo dibuja, así que sale con el detalle y la
    interactividad de siempre (pulsar una barra sigue filtrando el panel). */
function abrirGraficoAmpliado(dibujar, titulo, altoFijo) {
  const cuerpo = crear("div", "cuerpo-grafico-ampliado");
  cuerpo.appendChild(altoFijo != null ? lienzoAncho(dibujar, altoFijo) : lienzoMedido(dibujar));
  abrirModal(titulo || t("ampliar_grafico"), cuerpo, null, "modal-grafico");
}

function botonAmpliar(dibujar, titulo, altoFijo) {
  const boton = crear("button", "boton-ampliar");
  boton.type = "button";
  boton.title = t("ampliar_grafico");
  boton.setAttribute("aria-label", t("ampliar_grafico"));
  boton.innerHTML = ICONO_AMPLIAR;
  boton.addEventListener("click", (e) => { e.stopPropagation(); abrirGraficoAmpliado(dibujar, titulo, altoFijo); });
  return boton;
}

/** Como `lienzoMedido`, pero con un cuadradito arriba a la derecha para ver
    el gráfico más grande en una ventana aparte. `titulo` es lo que rotula esa
    ventana; con el mismo dato de siempre, solo cambia el tamaño. */
function grafico(dibujar, titulo) {
  const envoltorio = crear("div", "contenedor-grafico");
  envoltorio.append(lienzoMedido(dibujar), botonAmpliar(dibujar, titulo));
  return envoltorio;
}

/** Igual que `grafico`, para los que miden solo el ancho (alto fijo). */
function graficoAncho(dibujar, alto, titulo) {
  const envoltorio = crear("div", "contenedor-grafico contenedor-grafico-ancho");
  envoltorio.append(lienzoAncho(dibujar, alto), botonAmpliar(dibujar, titulo, Math.max(alto, 420)));
  return envoltorio;
}

function lienzoMedido(dibujar) {
  const caja = crear("div", "lienzo-medido");
  let ultimo = "";
  let pendiente = false;
  const pintar = () => {
    pendiente = false;
    if (!caja.isConnected) { observador.disconnect(); MEDIDORES.delete(observador); return; }
    const ancho = Math.floor(caja.clientWidth);
    const alto = Math.floor(caja.clientHeight);
    if (ancho < 60 || alto < 40) return;
    const clave = `${ancho}x${alto}`;
    if (clave === ultimo) return;
    ultimo = clave;
    caja.replaceChildren(dibujar(ancho, alto));
  };
  const observador = new ResizeObserver(() => {
    if (!pendiente) { pendiente = true; requestAnimationFrame(pintar); }
  });
  observador.observe(caja);
  MEDIDORES.add(observador);
  return caja;
}

function soltarMedidores() {
  MEDIDORES.forEach((o) => o.disconnect());
  MEDIDORES.clear();
}

/* --- Esqueleto -------------------------------------------------------------
   Filas: KPIs · treemap · gráficos · tablas. Las dos filas de gráficos se
   reparten el alto sobrante; KPIs y tablas miden lo que su contenido pide.
   ------------------------------------------------------------------------ */
function esqueletoSecciones(vista) {
  vista.innerHTML = "";
  const raiz = crear("div", "panel-secciones");
  const filtros = crear("div", "barra-superior barra-panel");
  const rejilla = crear("div", "rejilla-secciones");
  const huecos = { raiz, filtros, rejilla, kpis: [] };
  for (let i = 0; i < 4; i++) {
    const kpi = crear("div", "hueco-indicador col-3");
    rejilla.appendChild(kpi);
    huecos.kpis.push(kpi);
  }
  const hueco = (clases) => {
    const nodo = crear("div", `hueco ${clases}`);
    rejilla.appendChild(nodo);
    return nodo;
  };
  huecos.treemap = hueco("zona-treemap");
  huecos.anios = hueco("zona-anios-secc");
  huecos.loc = hueco("zona-loc");
  huecos.resumen = hueco("col-5 fila-tablas");
  huecos.ejemplares = hueco("col-7 fila-tablas");
  raiz.append(filtros, rejilla);
  vista.appendChild(raiz);
  return huecos;
}

// Cuadro compacto: cabecera de una línea y cuerpo que llena la celda.
function cuadroPanel(hueco, titulo, subtitulo, acciones) {
  const p = panel(titulo, subtitulo, acciones);
  p.classList.add("cuadro-panel");
  const cuerpo = crear("div", "cuerpo-cuadro");
  p.appendChild(cuerpo);
  hueco.replaceChildren(p);
  return cuerpo;
}

let peticionSecciones = 0;

async function vistaSecciones(vista) {
  soltarMedidores();
  const huecos = esqueletoSecciones(vista);
  estado.huecosSecciones = huecos;
  await refrescarSecciones(huecos);
}

async function refrescarSecciones(huecos) {
  const c = estado.controles.secciones;
  const numero = ++peticionSecciones;
  huecos.rejilla.classList.add("actualizando");
  let datos;
  try {
    datos = await API.buscar(estado.sesion, {
      campo: "signatura", texto: c.texto,
      publico: c.publico, idioma: c.idioma, loc: c.loc,
      categoria: c.categoria, anio: c.anio, prestamos: c.prestamos,
      anio_desde: c.anio_desde || "", anio_hasta: c.anio_hasta || "",
      pagina: c.pagina, por_pagina: FILAS_EJEMPLARES, ui: IDIOMA,
      // El orden lo hace el servidor sobre TODOS los ejemplares: ordenar solo
      // los cinco de la página daría una lista falsa.
      orden: c.orden || "", descendente: c.desc ? "true" : "",
    });
  } finally {
    // Una respuesta que llega tarde no pisa a la más reciente.
    if (numero === peticionSecciones) huecos.rejilla.classList.remove("actualizando");
  }
  if (numero !== peticionSecciones || !huecos.raiz.isConnected) return;

  const recargar = (reiniciarPagina = true) => {
    if (reiniciarPagina) c.pagina = 1;
    refrescarSecciones(huecos).catch((e) => {
      huecos.filtros.after(aviso("error", e.message));
    });
  };

  pintarFiltrosSecciones(huecos.filtros, c, recargar);
  pintarKpisSecciones(huecos.kpis, datos, c);
  pintarTreemapSecciones(huecos.treemap, datos, c, recargar);
  pintarAniosSecciones(huecos.anios, datos, c);
  pintarLocSecciones(huecos.loc, datos, c, recargar);
  pintarResumenSecciones(huecos.resumen, datos, c, recargar);
  pintarEjemplaresSecciones(huecos.ejemplares, datos, c, recargar);
}

const FILAS_EJEMPLARES = 5;

/* --- Filtros y selección activa en una sola banda ------------------------ */
function pintarFiltrosSecciones(barra, c, recargar) {
  barra.innerHTML = "";
  barra.appendChild(campoSignatura(c.texto, (v) => { c.texto = v; recargar(); }));
  barra.appendChild(selector(t("localizacion"), opcionesLoc(), c.loc,
    (v) => { c.loc = v; recargar(); }));
  barra.appendChild(selector(t("publico"), [
    { valor: "todo", etiqueta: t("todo_fondo") },
    { valor: "adultos", etiqueta: t("solo_adultos") },
    { valor: "infantil", etiqueta: t("solo_infantil") },
  ], c.publico, (v) => { c.publico = v; c.categoria = ""; recargar(); }));
  if (estado.hayIdiomas) {
    barra.appendChild(selector(t("col_idioma"), opcionesIdioma(), c.idioma,
      (v) => { c.idioma = v; recargar(); }));
  }
  barra.appendChild(selector(t("historial"), [
    { valor: "todos", etiqueta: t("opt_todos") },
    { valor: "nunca", etiqueta: t("opt_nunca") },
    { valor: "estandar", etiqueta: t("opt_estandar") },
    { valor: "alta", etiqueta: t("opt_alta") },
  ], c.prestamos, (v) => { c.prestamos = v; recargar(); }));

  // Año de edición: un intervalo, con cualquiera de los dos límites opcional
  // («de» sin «a» es «desde ese año en adelante», y al revés).
  const rangoAnios = crear("div", "campo campo-rango-anios");
  rangoAnios.appendChild(crear("span", "rotulo-campo", t("anio_edicion")));
  const cajaAnios = crear("div", "rango-anios");
  const desde = crear("input");
  desde.type = "number";
  desde.placeholder = t("anio_desde");
  desde.setAttribute("aria-label", t("anio_desde"));
  desde.value = c.anio_desde ?? "";
  const hasta = crear("input");
  hasta.type = "number";
  hasta.placeholder = t("anio_hasta");
  hasta.setAttribute("aria-label", t("anio_hasta"));
  hasta.value = c.anio_hasta ?? "";
  const confirmarRango = () => {
    c.anio_desde = desde.value ? Number(desde.value) : null;
    c.anio_hasta = hasta.value ? Number(hasta.value) : null;
    recargar();
  };
  desde.addEventListener("change", confirmarRango);
  hasta.addEventListener("change", confirmarRango);
  cajaAnios.append(desde, crear("span", "separador-rango", "–"), hasta);
  rangoAnios.appendChild(cajaAnios);
  barra.appendChild(rangoAnios);

  // Las migas van en la misma banda que los filtros: si ocuparan una fila
  // propia, el panel entero saltaría hacia abajo al pulsar un bloque.
  const activos = [];
  if (c.texto) activos.push([t("miga_signatura", { n: c.texto }), () => { c.texto = ""; }]);
  if (c.categoria) activos.push([traducirEtiqueta(c.categoria), () => { c.categoria = ""; }]);
  if (c.anio) activos.push([`${t("col_anio")}: ${c.anio}`, () => { c.anio = ""; }]);
  if (c.anio_desde || c.anio_hasta) {
    const texto = c.anio_desde && c.anio_hasta ? t("anio_rango_ambos", { a: c.anio_desde, b: c.anio_hasta })
      : c.anio_desde ? t("anio_rango_desde", { a: c.anio_desde }) : t("anio_rango_hasta", { a: c.anio_hasta });
    activos.push([texto, () => { c.anio_desde = null; c.anio_hasta = null; }]);
  }
  const migas = crear("div", "migas migas-panel");
  if (activos.length) {
    migas.appendChild(crear("span", "rotulo-campo", t("seleccion_activa")));
    activos.forEach(([texto, quitar]) => migas.appendChild(miga(texto, () => { quitar(); recargar(); })));
  }
  barra.appendChild(migas);
}

/* --- KPIs ------------------------------------------------------------------ */
// Tasa de préstamo del conjunto de secciones (sin la dimensión «sección»):
// es la referencia contra la que se mide el uso relativo de cada una.
function tasaConjunto(datos) {
  const vol = datos.categorias_lista.reduce((s, f) => s + f.volumenes, 0);
  const prest = datos.categorias_lista.reduce((s, f) => s + f.prestados, 0);
  return vol ? prest / vol : 0;
}

function usoRelativo(fila, tasa) {
  return tasa && fila.volumenes ? (fila.prestados / fila.volumenes) / tasa : null;
}

const formatoUso = (v) => (v === null || v === undefined ? "—" : numeroDecimal(v, 2));

function pintarKpisSecciones(huecos, datos, c) {
  const r = datos.resumen;
  const tarjetas = [];

  // 1 · Volúmenes
  tarjetas.push(tarjetaIndicador({
    rotulo: t("col_volumenes"), valor: miles(r.volumenes), acento: PALETA.cian,
    grafico: minigrafica(datos.anios.filas.map((f) => f.volumenes), PALETA.cian),
    contexto: c.categoria ? traducirEtiqueta(c.categoria)
      : t("kpi_sobre_total", { n: miles(estado.metricas ? estado.metricas.total : r.volumenes) }),
  }));

  // 2 · Circulación: cifra, proporción en palabras y reparto del préstamo
  const porEstado = Object.fromEntries(datos.estados_prestamo.map((f) => [f.clave, f.volumenes]));
  const fraccion = textoFraccion(r.pct_prestamos);
  const total = r.volumenes || 1;
  tarjetas.push(tarjetaIndicador({
    rotulo: t("m_circulacion"), valor: pct(r.pct_prestamos), acento: PALETA.verde,
    estado: fraccion ? { nivel: "info", texto: fraccion } : null,
    grafico: barraApilada([
      { valor: porEstado.alta || 0, clase: "prest-alta", etiqueta: t("estado_alta") },
      { valor: porEstado.prestado || 0, clase: "prest-normal", etiqueta: t("estado_prestado") },
      { valor: porEstado.nunca || 0, clase: "prest-sin", etiqueta: t("estado_nunca") },
    ]),
    contexto: t("secc_circ_ctx", { a: pct(((porEstado.alta || 0) / total) * 100),
                                   n: pct(((porEstado.nunca || 0) / total) * 100) }),
  }));

  // 3 · Año medio y tramos de antigüedad
  const tramos = tramosEdad(datos.anios, estado.config.anio_actual);
  const base = tramos.conAnio || 1;
  const antiguedad = r.anio_medio ? estado.config.anio_actual - r.anio_medio : null;
  tarjetas.push(tarjetaIndicador({
    rotulo: t("m_edad"), valor: r.anio_medio ?? "—", acento: PALETA.amarillo,
    estado: antiguedad !== null ? { nivel: "info", texto: t("n_anios_media", { n: antiguedad }) } : null,
    grafico: barraApilada([
      { valor: tramos.recientes, clase: "tramo-reciente", etiqueta: t("tramo_reciente") },
      { valor: tramos.intermedios, clase: "tramo-medio", etiqueta: t("tramo_medio") },
      { valor: tramos.antiguos, clase: "tramo-antiguo", etiqueta: t("tramo_antiguo") },
    ]),
    contexto: t("secc_edad_ctx", { r: pct((tramos.recientes / base) * 100), v: pct((tramos.antiguos / base) * 100) }),
  }));

  // 4 · Uso relativo de la sección elegida, o mapa de secciones si no hay
  const tasa = tasaConjunto(datos);
  const elegida = c.categoria && datos.categorias_lista.find((f) => f.clave === c.categoria);
  if (elegida) {
    const u = usoRelativo(elegida, tasa);
    const encima = u !== null && u >= 1;
    tarjetas.push(tarjetaIndicador({
      rotulo: t("rend_uso"), valor: formatoUso(u), acento: PALETA.ambar, explicacion: ayudaUsoRelativo(),
      estado: u === null ? null : { nivel: encima ? "alto" : "abajo", texto: t(encima ? "uso_encima" : "uso_debajo") },
      grafico: u === null ? null : graficoBala({ valor: u, escala: 2, referencia: [1, 1],
        color: encima ? PALETA.usoEncima : PALETA.usoDebajo }),
      contexto: elegida.volumenes < MINIMO_FIABLE ? t("uso_orientativo", { m: MINIMO_FIABLE }) : t("uso_ctx"),
    }));
  } else {
    const fiables = datos.categorias_lista.filter((f) => f.volumenes >= MINIMO_FIABLE);
    tarjetas.push(tarjetaIndicador({
      rotulo: t("n_secciones"), valor: miles(datos.categorias_lista.length), acento: PALETA.ambar,
      grafico: rejillaCuenta(fiables.map((f) => {
        const u = usoRelativo(f, tasa);
        return { clase: u >= 1 ? "encima" : "debajo", titulo: `${traducirEtiqueta(f.clave)}: ${formatoUso(u)}` };
      })),
      contexto: t("secc_pulsa"),
    }));
  }
  tarjetas.forEach((tarjeta, i) => huecos[i].replaceChildren(tarjeta));
}

/* --- Treemap: selector principal, recortado a lo legible ------------------- */
function pintarTreemapSecciones(hueco, datos, c, recargar) {
  const cuerpo = cuadroPanel(hueco, t("treemap_signaturas"), null, leyendaGradiente(t("col_rotacion")));
  const filas = datos.categorias_lista;
  if (!filas.length) { cuerpo.appendChild(crear("p", "vacio", t("sin_datos_seccion"))); return; }
  const piezas = filas.map((f) => ({
    clave: f.clave, etiqueta: traducirEtiqueta(f.clave), valor: f.volumenes, intensidad: f.rotacion,
  }));
  const nota = crear("p", "nota-pie");
  cuerpo.appendChild(grafico((ancho, alto) => graficoTreemap(piezas, {
    seleccion: c.categoria, ancho, alto, recorte: { ancho: 58, alto: 27 },
    alPulsar: (v) => { c.categoria = v; recargar(); },
    alRecortar: (omitidas) => {
      if (!omitidas.length) { nota.textContent = ""; return; }
      const vol = omitidas.reduce((s, o) => s + o.valor, 0);
      const fuera = c.categoria && omitidas.some((o) => o.clave === c.categoria);
      nota.textContent = t("treemap_omitidas", { n: omitidas.length, v: miles(vol) })
        + (fuera ? ` ${t("treemap_seleccion_fuera", { s: traducirEtiqueta(c.categoria) })}` : "");
    },
  })));
  cuerpo.appendChild(nota);
}

/* --- Años de edición de la selección --------------------------------------- */
function pintarAniosSecciones(hueco, datos, c) {
  const pies = [];
  if (datos.anios.anteriores) pies.push(t("anteriores_n", { n: miles(datos.anios.anteriores) }));
  if (datos.anios.sin_anio) pies.push(t("sin_anio_n", { n: miles(datos.anios.sin_anio) }));
  const sub = c.categoria ? t("anios_de_seccion", { n: traducirEtiqueta(c.categoria) }) : null;
  const cuerpo = cuadroPanel(hueco, t("anios_uso_titulo"), [sub, ...pies].filter(Boolean).join(" · ") || null);
  if (!datos.anios.filas.length) { cuerpo.appendChild(crear("p", "vacio", t("sin_datos_seccion"))); return; }
  const puntos = datos.anios.filas.map((f) => ({
    anio: f.clave, volumenes: f.volumenes, tasa: f.rotacion,
    detalle: t("anios_detalle", { a: f.clave, v: miles(f.volumenes), r: pct(f.rotacion) }),
  }));
  cuerpo.appendChild(grafico((ancho, alto) => graficoAniosUso(puntos, { ancho, alto, titulo: t("anios_uso_titulo") }), t("anios_uso_titulo")));
}

/* --- Localizaciones de la selección (pulsar = filtrar) --------------------- */
function pintarLocSecciones(hueco, datos, c, recargar) {
  const sub = c.categoria ? t("loc_de_seccion", { n: traducirEtiqueta(c.categoria) }) : null;
  const cuerpo = cuadroPanel(hueco, t("loc_titulo"), sub);
  const filas = datos.localizaciones.filter((f) => f.volumenes > 0).map((f) => ({
    clave: f.clave, etiqueta: traducirEtiqueta(f.clave), volumenes: f.volumenes,
    prestados: f.prestados, tasa: f.rotacion,
  }));
  if (!filas.length) { cuerpo.appendChild(crear("p", "vacio", t("sin_datos_seccion"))); return; }
  const textos = {
    titulo: t("loc_titulo"), otras: (n) => t("loc_otras", { n }),
    detalle: (f) => t("loc_detalle", { l: f.etiqueta, v: miles(f.volumenes), r: pct(f.tasa) }),
  };
  // Todas las localizaciones, con desplazamiento dentro del cuadro: antes se
  // agrupaban en «Otras» las que no cabían y no había forma de verlas.
  const caja = crear("div", "lista-desplazable barras-desplazables");
  const alto = Math.max(filas.length * 19 + 8, 60);
  caja.appendChild(graficoAncho((ancho) => graficoBarrasUso(filas, {
    ancho, alto, textos, seleccion: c.loc === "__TODAS__" ? undefined : c.loc,
    alPulsar: (clave) => { c.loc = clave === null ? "__TODAS__" : clave; recargar(); },
  }), alto, t("loc_titulo")));
  cuerpo.appendChild(caja);
}

/* --- Tabla resumen: altura de la fila, desplazamiento interno -------------- */
function pintarResumenSecciones(hueco, datos, c, recargar) {
  const anterior = hueco.querySelector(".envoltorio-tabla");
  const desplazamiento = anterior ? anterior.scrollTop : 0;
  const columnas = [
    { clave: "clave", titulo: t("col_signatura"), destacar: true,
      render: (f) => escapar(traducirEtiqueta(f.clave)), csv: (f) => f.clave },
    { clave: "volumenes", titulo: t("col_volumenes"), tipo: "num" },
    { clave: "distribucion", titulo: t("col_porcentaje"), tipo: "pct" },
    { clave: "rotacion", titulo: t("col_rotacion"), tipo: "pct", barra: true },
    { clave: "uso_rel", titulo: t("col_uso_rel"), tipo: "num",
      render: (f) => {
        if (f.uso_rel === null) return "—";
        const caja = crear("span", `uso-rel ${f.uso_rel >= 1 ? "encima" : "debajo"}${f.volumenes < MINIMO_FIABLE ? " pequena" : ""}`);
        caja.append(crear("span", "flecha", f.uso_rel >= 1 ? "▲" : "▼"), document.createTextNode(formatoUso(f.uso_rel)));
        return caja;
      },
      csv: (f) => (f.uso_rel === null ? "" : f.uso_rel.toFixed(3)) },
    { clave: "anio_medio", titulo: t("col_anio_medio"), tipo: "num" },
  ];
  const tasa = tasaConjunto(datos);
  const filas = datos.categorias_lista.map((f) => ({ ...f, uso_rel: usoRelativo(f, tasa) }));
  const acciones = crear("div", "acciones-cuadro");
  acciones.appendChild(ayudaUsoRelativo());
  if (filas.length) acciones.appendChild(botonCSV("secciones.csv", columnas, filas));
  const cuerpo = cuadroPanel(hueco, t("tabla_secciones"), null, acciones);
  const caja = crear("div", "tabla-desplazable");
  crearTabla(caja, columnas, filas, {
    orden: "volumenes", desc: true, textoVacio: t("sin_datos_seccion"),
    alPulsarFila: (f) => { c.categoria = c.categoria === f.clave ? "" : f.clave; recargar(); },
    filaActiva: (f) => f.clave === c.categoria,
  });
  cuerpo.appendChild(caja);

  const envoltorio = caja.querySelector(".envoltorio-tabla");
  if (envoltorio) {
    envoltorio.scrollTop = desplazamiento;
    // La fila elegida tiene que quedar a la vista aunque se pulsara en otro
    // cuadro (el treemap) y la tabla estuviera desplazada a otra altura.
    const activa = envoltorio.querySelector("tr.activa");
    if (activa) {
      const cabecera = envoltorio.querySelector("thead").offsetHeight;
      const arriba = activa.offsetTop - cabecera;
      const abajo = activa.offsetTop + activa.offsetHeight;
      if (arriba < envoltorio.scrollTop) envoltorio.scrollTop = arriba;
      else if (abajo > envoltorio.scrollTop + envoltorio.clientHeight) {
        envoltorio.scrollTop = abajo - envoltorio.clientHeight;
      }
    }
  }
}

/* --- Ejemplares: cinco filas y paginación en la cabecera ------------------- */
function pintarEjemplaresSecciones(hueco, datos, c, recargar) {
  const columnas = [
    { clave: "signatura_real", titulo: t("col_signatura"), tipo: "mono", ancho: "15%" },
    { clave: "titulo", titulo: t("col_titulo"), ancho: "34%",
      render: (f) => {
        const boton = crear("button", "enlace-ficha", f.titulo || "—");
        boton.title = f.titulo || t("ver_ficha");
        boton.addEventListener("click", () => verFichaSesion(f.record_id));
        return boton;
      },
      csv: (f) => f.titulo },
    { clave: "autor", titulo: t("col_autor"), ancho: "20%" },
    { clave: "year", titulo: t("col_anio"), tipo: "num", ancho: "8%" },
    { clave: "prestamos", titulo: t("col_prestamos"), ancho: "12%",
      render: (f) => (f.prestamos === 0 ? distintivo(t("estado_nunca"), "neutral")
        : f.prestamos === 2 ? distintivo(t("estado_alta"), "calido")
        : distintivo(t("estado_prestado"), "frio")),
      csv: (f) => f.prestamos },
    { clave: "loc", titulo: t("col_loc"), tipo: "mono", ancho: "11%" },
  ];
  const columnasCSV = [{ clave: "record_id", titulo: t("col_codbar") }, ...columnas,
    { clave: "categoria", titulo: t("col_categoria") }, { clave: "idioma", titulo: t("col_idioma") }];

  const acciones = [];
  if (datos.total) {
    const pag = crear("div", "paginacion-compacta");
    const anterior = crear("button", "boton secundario pequeno", "‹");
    anterior.title = t("anterior");
    anterior.setAttribute("aria-label", t("anterior"));
    anterior.disabled = datos.pagina <= 1;
    anterior.addEventListener("click", () => { c.pagina = datos.pagina - 1; recargar(false); });
    const siguiente = crear("button", "boton secundario pequeno", "›");
    siguiente.title = t("siguiente");
    siguiente.setAttribute("aria-label", t("siguiente"));
    siguiente.disabled = datos.pagina >= datos.paginas;
    siguiente.addEventListener("click", () => { c.pagina = datos.pagina + 1; recargar(false); });
    pag.append(anterior, crear("span", "posicion",
      t("pagina_de", { a: miles(datos.pagina), b: miles(datos.paginas) })), siguiente);
    acciones.push(pag);
  }
  if (datos.todas) acciones.push(botonCSV("ejemplares.csv", columnasCSV, datos.todas));

  const titulo = c.categoria
    ? t("ejemplares_de", { n: traducirEtiqueta(c.categoria) }) : t("ejemplares_todos");
  const cuerpo = cuadroPanel(hueco, titulo,
    datos.total ? t("resultados", { n: miles(datos.total) }) : null, acciones);
  const caja = crear("div", "tabla-ejemplares");
  crearTabla(caja, columnas, datos.filas, {
    textoVacio: t("sin_resultados"), orden: c.orden || null, desc: Boolean(c.desc),
    alOrdenar: (clave, desc) => { c.orden = clave; c.desc = desc; recargar(); },
  });
  cuerpo.appendChild(caja);
}

function sinAcentos(texto) {
  return String(texto || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}

function miga(texto, alQuitar) {
  const caja = crear("span", "miga");
  caja.appendChild(document.createTextNode(texto));
  const quitar = crear("button", null, "×");
  quitar.type = "button";
  quitar.title = t("quitar");
  quitar.addEventListener("click", alQuitar);
  caja.appendChild(quitar);
  return caja;
}

/* ==========================================================================
   Fichas y valoraciones
   ========================================================================== */
async function verFichaSesion(recordId) {
  try {
    const ficha = await API.ficha(estado.sesion, recordId);
    const contenido = pintarFicha(ficha);
    // Si el ejemplar está enlazado con el catálogo de la red, también se
    // puede valorar y comentar el propio fondo, no solo lo que falta.
    if (ficha.id_sistema && estado.config.valoraciones && estado.config.valoraciones.activo) {
      const hueco = crear("div");
      contenido.appendChild(hueco);
      abrirModal(t("ficha_titulo"), contenido);
      montarValoraciones(hueco, ficha.id_sistema);
      return;
    }
    abrirModal(t("ficha_titulo"), contenido);
  } catch (e) {
    abrirModal(t("ficha_titulo"), aviso("error", e.message));
  }
}

async function verFichaRed(idSistema) {
  try {
    const ficha = await API.fichaRed(idSistema);
    const contenido = pintarFicha(ficha);
    const hueco = crear("div");
    contenido.appendChild(hueco);
    abrirModal(t("ficha_titulo"), contenido);
    montarValoraciones(hueco, idSistema);
  } catch (e) {
    abrirModal(t("ficha_titulo"), aviso("error", e.message));
  }
}

/* --- Valoraciones: se cargan después de abrir la ficha para no retrasar su
   aparición, y se vuelven a pintar tras cada cambio. --------------------- */
async function montarValoraciones(hueco, idSistema) {
  if (!estado.config.valoraciones || !estado.config.valoraciones.activo) return;

  // Tras cada cambio se repinta el bloque y, si la pestaña «Red» está
  // abierta debajo del modal, también su actividad.
  const pintar = (datos) => {
    hueco.innerHTML = "";
    hueco.appendChild(bloqueValoracion(idSistema, datos,
      async (cuerpo) => { pintar(await API.guardarValoracion(estado.sesion, idSistema, cuerpo)); avisarCambioRed(); },
      async () => { pintar(await API.borrarValoracion(estado.sesion, idSistema)); avisarCambioRed(); },
      async (idValoracion, texto) => {
        pintar(await API.responder(estado.sesion, { id_valoracion: idValoracion, texto }));
        avisarCambioRed();
      },
      async (idRespuesta) => { pintar(await API.borrarRespuesta(estado.sesion, idRespuesta)); avisarCambioRed(); }));
  };

  cargando(hueco);
  try {
    pintar(await API.valoraciones(estado.sesion, idSistema));
  } catch (e) {
    hueco.innerHTML = "";
    hueco.appendChild(aviso("atencion", e.message));
  }
}

/* ==========================================================================
   Vista: sugerencias de compra
   Cruza la demanda del fondo propio (uso relativo, actualidad) con la oferta
   de la red (títulos que otras bibliotecas tienen y esta no). A la izquierda,
   dónde comprar; a la derecha, qué comprar. Todo propone, nada retira.
   ========================================================================== */
let peticionCompras = 0;

function esqueletoCompras(vista) {
  vista.innerHTML = "";
  const raiz = crear("div", "panel-secciones panel-compras");
  const filtros = crear("div", "barra-superior barra-panel");
  const rejilla = crear("div", "rejilla-compras");
  const indicadores = crear("div", "fila-indicadores");
  const huecos = { raiz, filtros, rejilla, indicadores, kpis: [] };
  for (let i = 0; i < 5; i++) {
    const h = crear("div", "hueco-indicador");
    indicadores.appendChild(h);
    huecos.kpis.push(h);
  }
  rejilla.appendChild(indicadores);
  const hueco = (clase) => { const h = crear("div", `hueco ${clase}`); rejilla.appendChild(h); return h; };
  huecos.matriz = hueco("zona-matriz");
  huecos.secciones = hueco("zona-secciones-compra");
  huecos.titulos = hueco("zona-titulos");
  raiz.append(filtros, rejilla);
  raiz.classList.add("con-fuentes");
  vista.appendChild(raiz);
  return huecos;
}

async function vistaCompras(vista) {
  soltarMedidores();
  const c = estado.controles.compras;
  if (!c.anio_minimo) c.anio_minimo = estado.config.anio_actual - 4;   // últimos 5 años
  const huecos = esqueletoCompras(vista);
  await refrescarCompras(huecos);
}

async function refrescarCompras(huecos) {
  const c = estado.controles.compras;
  const numero = ++peticionCompras;
  huecos.rejilla.classList.add("actualizando");
  let datos, datosFondo;
  try {
    // El diagnóstico de cabecera (volúmenes, docs/habitante, circulación,
    // actualidad) es siempre el del fondo COMPLETO, sin los filtros de esta
    // pestaña: es la referencia constante frente a la que se decide comprar.
    [datos, datosFondo] = await Promise.all([
      API.recPanel(estado.sesion, {
        anio_minimo: c.anio_minimo, seccion: c.seccion, idioma: c.idioma, campo: c.campo, texto: c.texto,
        excluir_fondo: c.excluir_fondo, solo_bibliografico: c.solo_bibliografico, limite: 200,
      }),
      API.buscar(estado.sesion, {
        campo: "signatura", texto: "", publico: "todo", idioma: "__TODOS__", loc: "__TODAS__",
        por_pagina: 1, ligero: true, ui: IDIOMA,
      }),
    ]);
  } finally {
    if (numero === peticionCompras) huecos.rejilla.classList.remove("actualizando");
  }
  if (numero !== peticionCompras || !huecos.raiz.isConnected) return;
  const recargar = () => refrescarCompras(huecos).catch((e) => huecos.filtros.after(aviso("error", e.message)));
  const a = prepararCompras(datos);
  const aFondo = prepararDiagnostico(datosFondo, { texto: "", loc: "__TODAS__", publico: "todo", idioma: "__TODOS__" });

  cerrarCajonLibro();
  huecos.filtros.innerHTML = "";
  if (estado.menuPlegado) pintarSelectorFuente(huecos.filtros, c, recargar);
  pintarNavegador();
  const repintarFiltros = () => {
    huecos.filtros.innerHTML = "";
    if (estado.menuPlegado) pintarSelectorFuente(huecos.filtros, c, recargar);
    pintarFiltrosCompras(huecos.filtros, c, datos, recargar);
  };
  estado.repintarFiltrosCompras = repintarFiltros;
  pintarFiltrosCompras(huecos.filtros, c, datos, recargar);
  pintarKpisCompras(huecos.kpis, a, c, aFondo);
  pintarMatrizCompras(huecos.matriz, a, c, recargar);
  pintarSeccionesCompras(huecos.secciones, a, c, recargar);
  // Lo único que cambia entre fuentes es la lista: el diagnóstico de arriba
  // es el mismo y sigue filtrando por sección.
  huecos.titulos.innerHTML = "";
  if (c.fuente === "autores") pintarAutores(huecos.titulos, c, recargar);
  else if (c.fuente === "novedades") pintarNovedades(huecos.titulos, c, recargar);
  else pintarTitulosCompras(huecos.titulos, a, c);
}

/* --- Cruce demanda propia × oferta de la red ------------------------------ */
function prepararCompras(datos) {
  const propias = datos.propias || [];
  const volTotal = propias.reduce((s, p) => s + p.volumenes, 0);
  const prestTotal = propias.reduce((s, p) => s + p.prestados, 0);
  const tasa = volTotal ? prestTotal / volTotal : 0;
  const oferta = Object.fromEntries(datos.secciones.map((s) => [s.clave, s]));
  const puntos = propias
    .filter((p) => p.volumenes >= MINIMO_FIABLE && p.con_anio)
    .map((p) => ({
      clave: p.clave, etiqueta: traducirEtiqueta(p.clave), volumenes: p.volumenes,
      x: (p.recientes / p.con_anio) * 100,
      y: tasa ? (p.prestados / p.volumenes) / tasa : 0,
      oferta: oferta[p.clave] ? oferta[p.clave].candidatos : 0,
    }));
  const xs = puntos.map((p) => p.x).sort((a, b) => a - b);
  const corteX = xs.length ? xs[Math.floor(xs.length / 2)] : 0;
  const prioritarias = puntos.filter((p) => p.y >= 1 && p.x < corteX);
  return { datos, puntos, corteX, prioritarias, oferta };
}

/* --- Filtros ---------------------------------------------------------------- */
function pintarFiltrosCompras(barra, c, datos, recargar) {
  if (c.fuente === "novedades") return pintarFiltrosNovedades(barra, c, recargar);
  if (c.fuente === "autores") return pintarFiltrosAutores(barra, c, recargar);
  const anio = estado.config.anio_actual;
  barra.appendChild(selector(t("editados_desde"), [
    { valor: anio - 2, etiqueta: t("ultimos_n_anios", { n: 3 }) },
    { valor: anio - 4, etiqueta: t("ultimos_n_anios", { n: 5 }) },
    { valor: anio - 9, etiqueta: t("ultimos_n_anios", { n: 10 }) },
  ], c.anio_minimo, (v) => { c.anio_minimo = Number(v); recargar(); }));
  barra.appendChild(selector(t("col_idioma"),
    [{ valor: "__TODOS__", etiqueta: t("todos_idiomas") }].concat(
      (datos.idiomas_red || []).map((i) => ({ valor: i, etiqueta: traducirEtiqueta(i) }))),
    c.idioma, (v) => { c.idioma = v; recargar(); }));
  barra.appendChild(selector(t("buscar_por"), [
    { valor: "titulo", etiqueta: t("opt_titulo") },
    { valor: "autor", etiqueta: t("opt_autor") },
    { valor: "materia", etiqueta: t("opt_materia") },
  ], c.campo, (v) => { c.campo = v; if (c.texto) recargar(); }));
  barra.appendChild(entradaTexto(t("termino"), c.texto, t("placeholder_texto"),
    (v) => { c.texto = v.trim(); recargar(); }, "busqueda"));
  const opciones = crear("div", "casillas-compra");
  opciones.appendChild(casilla(t("excluir_fondo"), c.excluir_fondo, (v) => { c.excluir_fondo = v; recargar(); }));
  opciones.appendChild(casilla(t("solo_bibliografico"), c.solo_bibliografico, (v) => { c.solo_bibliografico = v; recargar(); }));
  barra.appendChild(opciones);
  const migas = crear("div", "migas migas-panel");
  if (c.seccion) {
    migas.appendChild(crear("span", "rotulo-campo", t("seleccion_activa")));
    migas.appendChild(miga(traducirEtiqueta(c.seccion), () => {
      c.seccion = ""; c.aut_seccion = ""; c.nov_seccion = ""; recargar();
    }));
  }
  barra.appendChild(migas);
  if (datos.aviso) barra.appendChild(aviso("atencion", datos.aviso));
}

// Formas del producto en ONIX (lista 150). Se enseñan con su nombre: un
// desplegable con «BC» o «BH» no dice nada a nadie.
const FORMAS_ONIX = {
  BA: "forma_libro", BB: "forma_tapa_dura", BC: "forma_rustica", BE: "forma_espiral",
  BF: "forma_folleto", BG: "forma_piel", BH: "forma_carton", BI: "forma_tela",
  BJ: "forma_bano", BK: "forma_desplegable", BL: "forma_gigante", BP: "forma_tela",
  BZ: "forma_otros", AB: "forma_audio", AC: "forma_audio", AJ: "forma_audio",
  ED: "forma_digital", EA: "forma_digital", DA: "forma_digital",
};

function nombreForma(codigo) {
  const clave = FORMAS_ONIX[(codigo || "").toUpperCase()];
  return clave ? t(clave) : codigo;
}

function pintarFiltrosNovedades(barra, c, recargar) {
  const facetas = c.facetas || {};
  const opciones = (mapa, todos) => [{ valor: "", etiqueta: todos }].concat(
    Object.entries(mapa || {}).map(([k, n]) => ({ valor: k, etiqueta: `${traducirEtiqueta(k)} (${miles(n)})` })));
  barra.appendChild(selector(t("col_idioma"), opciones(facetas.idioma, t("todos_idiomas")),
    c.nov_idioma || "", (v) => { c.nov_idioma = v; recargar(); }));
  barra.appendChild(selector(t("nov_editorial"), opciones(facetas.editorial, t("todas")),
    c.nov_editorial || "", (v) => { c.nov_editorial = v; recargar(); }));
  // Sección: la signatura que le daría la biblioteca, según la tabla de materias
  barra.appendChild(selector(t("col_seccion"), opcionesSeccion(facetas.seccion, t("todas")),
    seccionFiltroDilve(c, "nov_seccion"),
    (v) => { c.nov_seccion = v; c.seccion = claveDeCodigo(v); recargar(); }));
  const formas = [{ valor: "", etiqueta: t("todas") }].concat(
    Object.entries(facetas.forma || {}).map(([k, n]) => ({ valor: k, etiqueta: `${nombreForma(k)} (${miles(n)})` })));
  barra.appendChild(selector(t("nov_forma"), formas,
    c.nov_forma || "", (v) => { c.nov_forma = v; recargar(); }));
  // Materia THEMA: las que tienen las novedades descargadas, con su recuento.
  // Un libro con varias materias (novela romántica y novela gráfica) sale en
  // todas. El enlace lleva al buscador oficial para consultar el resto.
  // Orden alfabético del rótulo: con los encabezados cargados, por nombre.
  const materias = [{ valor: "", etiqueta: t("todas") }].concat(
    Object.entries(facetas.thema || {})
      .map(([k, n]) => ({ valor: k, etiqueta: `${rotuloThema(k)} (${miles(n)})` }))
      .sort((a, b) => a.etiqueta.localeCompare(b.etiqueta, IDIOMA, { sensitivity: "base" })));
  const campoThema = selector(t("nov_thema"), materias, c.nov_thema || "", (v) => { c.nov_thema = v; recargar(); });
  // «?» junto al rótulo: lleva al buscador oficial (a la materia elegida, si hay)
  const ayuda = enlaceThema(c.nov_thema || "", "?", "ayuda-thema");
  ayuda.setAttribute("aria-label", t("thema_consultar"));
  campoThema.querySelector("label").append(" ", ayuda);
  barra.appendChild(campoThema);
  const busqueda = crear("label", "campo ancho");
  const entrada = crear("input");
  entrada.type = "search";
  entrada.value = c.nov_texto || "";
  entrada.placeholder = t("nov_placeholder_texto");
  entrada.addEventListener("change", () => { c.nov_texto = entrada.value; recargar(); });
  busqueda.append(crear("span", "rotulo-campo", t("termino")), entrada);
  barra.appendChild(busqueda);
  // Segunda fila: todas las opciones en una sola línea. Primero el orden por
  // afinidad con su «?» y, si está marcado, la comparación con el histórico;
  // después, qué novedades se ven.
  const casillas = crear("div", "fila-opciones");
  casillas.appendChild(casilla(t("nov_personalizadas"), c.personalizadas, (v) => { c.personalizadas = v; recargar(); }));
  casillas.appendChild(ayudaAfinidad());
  if (c.personalizadas) {
    const comparar = crear("button", "enlace-discreto", t("af_comparar"));
    comparar.addEventListener("click", () => abrirEvaluacionAfinidad());
    casillas.appendChild(comparar);
  }
  casillas.appendChild(casilla(t("excluir_fondo"), c.ocultar_propios !== false, (v) => { c.ocultar_propios = v; recargar(); }));
  // Muchas altas de DILVE son libros que aún no han salido: por defecto se ven
  // solo los que ya están publicados a día de hoy.
  casillas.appendChild(casilla(t("solo_publicados"), c.solo_publicados !== false,
                                 (v) => { c.solo_publicados = v; recargar(); }));
  // Preventas: lo que sale en los próximos 3 meses, ni un día más (hay altas
  // con fecha de 2030). Con las dos casillas: lo publicado y lo inminente.
  casillas.appendChild(casilla(t("proximos_3_meses"), c.proximos_3_meses !== false,
                                 (v) => { c.proximos_3_meses = v; recargar(); }));
  barra.appendChild(casillas);
}

function pintarFiltrosAutores(barra, c, recargar) {
  // El idioma se filtra aquí, no al descargar: hay fichas sin ese dato y no
  // tiene sentido perderlas antes de verlas.
  const cuenta = c.idiomas_autores || {};
  const opciones = [{ valor: "", etiqueta: t("todos_idiomas") },
    ...Object.entries(cuenta).map(([codigo, n]) => ({
      valor: codigo,
      etiqueta: `${codigo === "__SIN__" ? t("idioma_sin_indicar") : traducirEtiqueta(codigo)} (${miles(n)})`,
    }))];
  barra.appendChild(selector(t("col_idioma"), opciones, c.aut_idioma || "",
                             (v) => { c.aut_idioma = v; recargar(); }));
  const nombreFranja = (clave) => ({
    __ADULTOS__: t("grupo_adultos"), __INFANTIL__: t("edad_infantil_otros"),
    __SIN__: t("sin_dato"),
  }[clave] || traducirEtiqueta(clave));
  // Las franjas se ordenan: primero adultos, luego los tramos por edad
  const ORDEN_FRANJA = ["__ADULTOS__", "I0", "I1", "I2", "I3", "JN", "__INFANTIL__", "__SIN__"];
  const conCuenta = (mapa, todos) => [{ valor: "", etiqueta: todos }].concat(
    Object.entries(mapa || {})
      .sort((a, b) => ORDEN_FRANJA.indexOf(a[0]) - ORDEN_FRANJA.indexOf(b[0]))
      .map(([k, n]) => ({ valor: k, etiqueta: `${nombreFranja(k)} (${miles(n)})` })));
  barra.appendChild(selector(t("col_seccion"), opcionesSeccion(c.secciones_autores, t("todas")),
    seccionFiltroDilve(c, "aut_seccion"),
    (v) => { c.aut_seccion = v; c.seccion = claveDeCodigo(v); recargar(); }));
  // La edad solo aparece si hay propuestas infantiles o juveniles
  if (Object.keys(c.edades_autores || {}).length) {
    barra.appendChild(selector(t("aut_edad"), conCuenta(c.edades_autores, t("todas")),
      c.aut_tramo || "", (v) => { c.aut_tramo = v; recargar(); }));
  }
  const casillasAut = crear("div", "casillas-compra");
  casillasAut.appendChild(casilla(t("solo_publicados"), c.solo_publicados !== false,
                                  (v) => { c.solo_publicados = v; recargar(); }));
  barra.appendChild(casillasAut);
  barra.appendChild(crear("p", "ayuda-filtros", t("aut_ayuda")));
  const acciones = crear("div", "casillas-compra");
  const recalcular = crear("button", "boton secundario pequeno", t("aut_recalcular"));
  recalcular.type = "button";
  recalcular.addEventListener("click", async () => {
    recalcular.disabled = true;
    await API.sugerenciasAutores(estado.sesion, true).catch(() => {});
    recargar();
  });
  acciones.appendChild(recalcular);
  barra.appendChild(acciones);
}

/* --- Indicadores ------------------------------------------------------------ */
// Híbrido: el estado general del fondo (como en Diagnóstico) + las secciones
// donde más falta hace comprar (propio de este panel). Es la misma cabecera
// para las tres fuentes (presencia en la red, autores, novedades): da el
// contexto de la colección mientras solo cambia la lista de abajo.
function pintarKpisCompras(huecos, a, c, aFondo) {
  const tarjetas = tarjetasResumenColeccion(aFondo);
  tarjetas.push(tarjetaIndicador({
    rotulo: t("secciones_prioritarias"), valor: miles(a.prioritarias.length),
    unidad: t("diag_demanda_unidad", { n: miles(a.puntos.length) }), acento: PALETA.ambar,
    explicacion: ayudaUsoRelativo(),
    grafico: rejillaCuenta(a.puntos.map((p) => ({
      clase: a.prioritarias.includes(p) ? "encima" : "debajo", titulo: p.etiqueta }))),
    contexto: t("prioritarias_ctx"),
  }));
  tarjetas.forEach((tarjeta, i) => huecos[i].replaceChildren(tarjeta));
}

/* --- Dónde comprar: matriz ------------------------------------------------- */
function pintarMatrizCompras(hueco, a, c, recargar) {
  const cuerpo = cuadroPanel(hueco, t("matriz_titulo"), null, ayudaUsoRelativo());
  if (!a.puntos.length) { cuerpo.appendChild(crear("p", "vacio", t("sin_datos_seccion"))); return; }
  const textos = {
    titulo: t("matriz_titulo"), cuadrante: t("matriz_cuadrante"), ejeX: t("matriz_eje_x"),
    mediana: t("matriz_mediana", { v: pct(a.corteX) }),
    detalle: (p) => t("matriz_detalle", { s: p.etiqueta, u: formatoUso(p.y), x: pct(p.x), n: miles(p.oferta) }),
  };
  estado.clavesSeccionCompras = a.puntos.map((p) => p.clave);
  cuerpo.appendChild(grafico((ancho, alto) => graficoMatrizCompra(a.puntos, {
    ancho, alto, textos, corteX: a.corteX, seleccion: c.seccion,
    // Pulsar un círculo filtra la lista de cualquier fuente: se limpian los
    // desplegables de sección de DILVE para que manden el círculo.
    alPulsar: (clave) => { c.seccion = clave; c.aut_seccion = ""; c.nov_seccion = ""; recargar(); },
  }), t("matriz_titulo")));
}

/* --- Barras por sección ------------------------------------------------------
   En «Presencia en bibliotecas», lo que ofrece la red en cada sección. En las
   fuentes de DILVE eso no aplica: se enseñan los datos de «¿Dónde hace más
   falta comprar?» (uso relativo y actualidad de cada sección) como barras. */
function pintarSeccionesCompras(hueco, a, c, recargar) {
  if (c.fuente === "autores" || c.fuente === "novedades") return pintarDemandaSecciones(hueco, a, c, recargar);
  const cuerpo = cuadroPanel(hueco, t("oferta_titulo"));
  const porClave = Object.fromEntries(a.puntos.map((p) => [p.clave, p]));
  // Primero las prioritarias, luego el resto; dentro de cada grupo, por oferta
  const filas = a.datos.secciones.map((s) => {
    const p = porClave[s.clave];
    return { clave: s.clave, etiqueta: traducirEtiqueta(s.clave), volumenes: s.candidatos, prestados: 0,
             uso: p ? p.y : null, prioritaria: Boolean(p && a.prioritarias.includes(p)) };
  }).sort((x, y) => (y.prioritaria - x.prioritaria) || (y.volumenes - x.volumenes));
  if (!filas.length) { cuerpo.appendChild(crear("p", "vacio", t("sin_recomendaciones"))); return; }
  const textos = {
    titulo: t("oferta_titulo"), otras: (n) => t("loc_otras", { n }),
    detalle: (f) => t("oferta_detalle", { s: f.etiqueta, n: miles(f.volumenes), u: formatoUso(f.uso) }),
  };
  cuerpo.appendChild(grafico((ancho, alto) => graficoBarrasUso(filas, {
    ancho, alto, textos, seleccion: c.seccion || undefined,
    color: (f) => (f.agregada || f.uso === null ? PALETA.gris : f.uso >= 1 ? PALETA.usoEncima : PALETA.usoDebajo),
    texto: (f) => `${miles(f.volumenes)}${f.uso === null ? "" : ` · ${formatoUso(f.uso)}`}${f.prioritaria ? " ★" : ""}`,
    alPulsar: (clave) => { c.seccion = clave || ""; c.aut_seccion = ""; c.nov_seccion = ""; recargar(); },
  }), t("oferta_titulo")));
}

function pintarDemandaSecciones(hueco, a, c, recargar) {
  const cuerpo = cuadroPanel(hueco, t("demanda_titulo"), null, ayudaUsoRelativo());
  if (!a.puntos.length) { cuerpo.appendChild(crear("p", "vacio", t("sin_datos_seccion"))); return; }
  // Primero las prioritarias (más demanda que peso y fondo poco actualizado),
  // luego el resto; dentro de cada grupo, de más a menos uso relativo.
  const filas = a.puntos.map((p) => ({
    clave: p.clave, etiqueta: p.etiqueta, volumenes: Math.round(p.y * 100), prestados: 0,
    uso: p.y, reciente: p.x, prioritaria: a.prioritarias.includes(p),
  })).sort((x, y) => (y.prioritaria - x.prioritaria) || (y.uso - x.uso));
  const textos = {
    titulo: t("demanda_titulo"), otras: (n) => t("loc_otras", { n }),
    detalle: (f) => t("demanda_detalle", { s: f.etiqueta, u: formatoUso(f.uso), x: pct(f.reciente) }),
  };
  // Todas las secciones, con desplazamiento: agrupar en «Otras» sumaría usos
  // relativos, que no se pueden sumar.
  const caja = crear("div", "lista-desplazable barras-desplazables");
  const alto = Math.max(filas.length * 19 + 8, 60);
  caja.appendChild(graficoAncho((ancho, altoGrafico) => graficoBarrasUso(filas, {
    ancho, alto: altoGrafico, textos, seleccion: c.seccion || undefined,
    // Ámbar solo para las prioritarias: las mismas que marca la matriz
    color: (f) => (f.prioritaria ? PALETA.usoEncima : PALETA.usoDebajo),
    texto: (f) => `${formatoUso(f.uso)} · ${pct(f.reciente)}${f.prioritaria ? " ★" : ""}`,
    alPulsar: (clave) => { c.seccion = clave || ""; c.aut_seccion = ""; c.nov_seccion = ""; recargar(); },
  }), alto, t("demanda_titulo")));
  cuerpo.appendChild(caja);
}

/* --- Qué comprar: títulos candidatos --------------------------------------- */
function pintarTitulosCompras(hueco, a, c) {
  const d = a.datos;
  const red = d.resumen.bibliotecas_red || 1;
  const columnas = [
    { clave: "titulo", titulo: t("col_titulo"), ancho: "33%",
      render: (f) => {
        const caja = crear("span", "celda-titulo");
        const boton = crear("button", "enlace-ficha", f.titulo || "—");
        boton.title = t("ver_ficha");
        boton.addEventListener("click", () => verFichaRed(f.id_sistema));
        caja.appendChild(boton);
        if (f.estado_fondo === "POSIBLE") caja.appendChild(distintivo(t("quiza_en_fondo"), "aviso"));
        return caja;
      },
      csv: (f) => f.titulo },
    { clave: "autor", titulo: t("col_autor"), ancho: "17%" },
    { clave: "anio", titulo: t("col_anio"), tipo: "num", ancho: "6%" },
  ];
  if (!c.seccion) columnas.push({ clave: "seccion", titulo: t("col_seccion"), ancho: "15%",
                                 render: (f) => escapar(traducirEtiqueta(f.seccion || "")), csv: (f) => f.seccion });
  columnas.push(
    { clave: "idioma", titulo: t("col_idioma"), ancho: "9%", render: (f) => escapar(traducirEtiqueta(f.idioma || "")),
      csv: (f) => f.idioma },
    { clave: "n_bibliotecas", titulo: t("col_red"), tipo: "num", ancho: "11%",
      render: (f) => {
        const caja = crear("span", "barra-red");
        const pista = crear("span", "pista");
        const barra = crear("span", "relleno");
        barra.style.width = `${Math.min(100, ((f.n_bibliotecas || 0) / red) * 100)}%`;
        pista.appendChild(barra);
        caja.append(pista, crear("span", "cifra-red", miles(f.n_bibliotecas)));
        caja.title = t("en_n_bibliotecas", { n: miles(f.n_bibliotecas), t: miles(red) });
        return caja;
      } },
    { clave: "valoracion_media", titulo: t("col_valoracion"), tipo: "num", ancho: "10%",
      render: (f) => (f.valoracion_n ? `${decimal(f.valoracion_media, 1)} (${f.valoracion_n})` : "—"),
      csv: (f) => f.valoracion_media },
  );
  const titulo = c.seccion ? t("titulos_de", { s: traducirEtiqueta(c.seccion) }) : t("titulos_recomendados");
  const sub = d.total > d.filas.length ? t("mostrando_n_de", { n: miles(d.filas.length), t: miles(d.total) })
    : t("titulos_recomendados_sub", { n: miles(d.total) });
  const cuerpo = cuadroPanel(hueco, titulo, sub,
    d.filas.length ? botonCSV("sugerencias_compra.csv", columnas, d.filas) : null);
  const caja = crear("div", "tabla-desplazable tabla-titulos");
  crearTabla(caja, columnas, d.filas, { textoVacio: t("sin_recomendaciones") });
  cuerpo.appendChild(caja);
}

/* ==========================================================================
   Sugerencias de compra: tres fuentes, un mismo diagnóstico
   La banda de arriba (indicadores, matriz «¿Dónde hace más falta comprar?» y
   oferta por sección) es idéntica en las tres fuentes y sirve de filtro:
   pulsar una sección filtra la lista de abajo. Lo único que cambia es la
   lista y, en su caso, los filtros:
     presencia  títulos que tiene la red y esta biblioteca no (tabla)
     autores    obras del mismo autor de lo más prestado (lista con portada)
     novedades  altas recientes de DILVE (rejilla de portadas)
   ========================================================================== */
const ORDEN_ADULTO = ["N", "C", "P", "T", "0", "1", "159.9", "2", "3", "4", "5", "6", "7", "8", "9"];
const ORDEN_INFANTIL = ["I0", "I1", "I2", "I3", "JN", "IC", "IP", "IT",
                        "I 0", "I 1", "I 2", "I 3", "I 4", "I 5", "I 6", "I 7", "I 8", "I 9"];

function grupoSeccion(seccion) {
  const s = String(seccion || "");
  if (ORDEN_INFANTIL.includes(s) || s.startsWith("Infantil")) return "infantil";
  if (ORDEN_ADULTO.includes(s)) return "adulto";
  return "otras";        // «Sin clasificar», «Libro de texto»…
}

function ordenSeccion(seccion) {
  const s = String(seccion || "");
  const adulto = ORDEN_ADULTO.indexOf(s);
  if (adulto >= 0) return [0, adulto, s];
  const infantil = ORDEN_INFANTIL.indexOf(s);
  if (infantil >= 0) return [1, infantil, s];
  if (s.startsWith("Infantil")) return [1, 90, s];
  return [2, 0, s];
}

/** Opciones de un desplegable de secciones, ordenadas y agrupadas. */
function opcionesSeccion(recuentos, etiquetaTodas) {
  const entradas = Object.entries(recuentos || {})
    .sort((a, b) => { const x = ordenSeccion(a[0]), y = ordenSeccion(b[0]);
                      return x[0] - y[0] || x[1] - y[1] || String(x[2]).localeCompare(String(y[2])); });
  const opciones = [{ valor: "", etiqueta: etiquetaTodas }];
  let grupoActual = null;
  for (const [clave, n] of entradas) {
    const grupo = grupoSeccion(clave);
    if (grupo !== grupoActual) {
      grupoActual = grupo;
      opciones.push({ grupo: t(grupo === "adulto" ? "grupo_adultos" : grupo === "infantil" ? "grupo_infantil" : "grupo_otras") });
    }
    opciones.push({ valor: clave, etiqueta: `${traducirEtiqueta(clave)} (${miles(n)})` });
  }
  return opciones;
}

/** La sección tal como la nombra el catálogo («Ficción / Narrativa»,
    «I1 (Infantil)», «9 - Historia / Geografía») en la notación de la tabla de
    materias que usan las fuentes de DILVE («N», «I1», «9»). Son las mismas
    reglas que `materias.seccion_de_signatura` en el servidor. */
function codigoSeccion(categoria) {
  const texto = String(categoria || "");
  if (!texto) return "";
  if (texto.startsWith("Ficción")) return "N";
  for (const [prefijo, codigo] of [["JN", "JN"], ["IC", "IC"], ["IP", "IP"], ["IT", "IT"], ["C (", "C"]]) {
    if (texto.startsWith(prefijo)) return codigo;
  }
  if (texto === "Teatro") return "T";
  if (texto === "Poesía") return "P";
  let m = texto.match(/^(I[0-3]) /);
  if (m) return m[1];
  m = texto.match(/^I (\d) /);
  if (m) return `I ${m[1]}`;
  m = texto.match(/^(159\.9|\d) /);
  if (m) return m[1];
  return texto;
}

/** Al revés: qué sección del gráfico corresponde a un código elegido en el
    desplegable, para que el círculo quede marcado igual. */
function claveDeCodigo(codigo) {
  if (!codigo) return "";
  return (estado.clavesSeccionCompras || []).find((clave) => codigoSeccion(clave) === codigo) || "";
}

/** La sección que filtra las fuentes de DILVE: la del desplegable si se ha
    elegido ahí, o la del círculo pulsado en el gráfico. */
function seccionFiltroDilve(c, campo) {
  return c[campo] || codigoSeccion(c.seccion);
}

function fuentesCompra() {
  const s = (estado.config.red && estado.config.red.sugerencias) || {};
  // «Autores» necesita credenciales de DILVE para pedir fichas; «Novedades»,
  // que haya novedades descargadas. La casilla «activo» solo rige la descarga
  // automática semanal, así que no esconde las fuentes.
  const credenciales = Boolean(estado.config.dilve_credenciales || estado.config.dilve_activo);
  const hayNovedades = (estado.config.dilve_novedades || 0) > 0;
  return [
    { clave: "presencia", etiqueta: "fuente_presencia", disponible: s.presencia !== false && estado.config.recomendaciones_activas },
    { clave: "autores", etiqueta: "fuente_autores", disponible: s.autores !== false && credenciales },
    { clave: "novedades", etiqueta: "fuente_novedades", disponible: s.novedades !== false && (hayNovedades || credenciales) },
  ].filter((f) => f.disponible);
}

function pintarSelectorFuente(barra, c, recargar) {
  const fuentes = fuentesCompra();
  if (fuentes.length < 2) return;
  const grupo = crear("div", "conmutador conmutador-fuente");
  grupo.setAttribute("role", "group");
  grupo.setAttribute("aria-label", t("fuente_titulo"));
  fuentes.forEach((f) => {
    const b = crear("button", f.clave === c.fuente ? "activo" : "", t(f.etiqueta));
    b.setAttribute("aria-pressed", String(f.clave === c.fuente));
    b.addEventListener("click", () => { if (c.fuente !== f.clave) { c.fuente = f.clave; recargar(); } });
    grupo.appendChild(b);
  });
  barra.appendChild(grupo);
}

/* --- Lista: obras del mismo autor ------------------------------------------ */
async function pintarAutores(hueco, c, recargar) {
  const cuerpo = cuadroPanel(hueco, t("aut_titulo"));
  cargando(cuerpo);
  await cargarThema();
  let d;
  try {
    d = await API.sugerenciasAutores(estado.sesion, false,
                                     { idioma: c.aut_idioma || "", seccion: seccionFiltroDilve(c, "aut_seccion"),
                                       tramo: c.aut_tramo || "",
                                       solo_publicados: c.solo_publicados !== false ? "true" : "false" });
  }
  catch (e) { cuerpo.replaceChildren(aviso("error", e.message)); return; }
  if (!hueco.isConnected) return;
  if (d.en_curso) {
    const p = d.progreso || {};
    // Se explica que esto es solo la primera vez: después queda en la caché
    cuerpo.replaceChildren(aviso("info", t("aut_calculando", { n: miles(p.pedidas || 0), t: miles(p.total || 0) })),
                           crear("p", "nota-pie", t("aut_calculando_nota")));
    setTimeout(() => { if (hueco.isConnected) pintarAutores(hueco, c, recargar); }, 2500);
    return;
  }
  cuerpo.innerHTML = "";
  if (d.error) { cuerpo.appendChild(aviso("atencion", d.error)); return; }
  // Los recuentos por idioma llegan con la lista: en cuanto se conocen, se
  // vuelve a pintar la barra para que el desplegable los muestre.
  const nuevos = JSON.stringify([d.idiomas, d.secciones, d.edades]);
  if (nuevos !== JSON.stringify([c.idiomas_autores, c.secciones_autores, c.edades_autores])) {
    c.idiomas_autores = d.idiomas || {};
    c.secciones_autores = d.secciones || {};
    c.edades_autores = d.edades || {};
    if (estado.repintarFiltrosCompras) estado.repintarFiltrosCompras();
  }
  let filas = d.propuestas || [];
  const seccion = seccionFiltroDilve(c, "aut_seccion");
  if (seccion) filas = filas.filter((f) => seccionesLibro(f).includes(seccion));
  // Sin notas de contexto fijas: solo el aviso si el cálculo se interrumpió
  if (d.interrupcion) cuerpo.appendChild(aviso("atencion", d.interrupcion));
  cuerpo.appendChild(listaLibros(filas, c, { motivo: (f) => t("aut_porque", {
    o: f.origen_titulo || "", n: miles(f.prestamos_origen || 0) }) }));
}

/* --- Lista: novedades ------------------------------------------------------- */
const NOVEDADES_POR_PAGINA = 48;

async function pintarNovedades(hueco, c, recargar) {
  const cuerpo = cuadroPanel(hueco, t("nov_titulo"));
  cargando(cuerpo);
  await cargarThema();
  const filtros = {
    seccion: seccionFiltroDilve(c, "nov_seccion"), idioma: c.nov_idioma || "", editorial: c.nov_editorial || "",
    forma: c.nov_forma || "", thema: c.nov_thema || "",
    texto: c.nov_texto || "", personalizadas: c.personalizadas,
    solo_publicados: c.solo_publicados !== false ? "true" : "false",
    proximos_3_meses: c.proximos_3_meses !== false ? "true" : "false",
    ocultar_propios: c.ocultar_propios !== false,
  };
  // Si cambia cualquier filtro se vuelve a la primera página
  const firma = JSON.stringify(filtros);
  if (firma !== c.nov_firma) { c.nov_firma = firma; c.nov_pagina = 1; }
  let d;
  try {
    d = await API.sugerenciasNovedades(estado.sesion, {
      ...filtros, pagina: c.nov_pagina || 1, por_pagina: NOVEDADES_POR_PAGINA,
    });
  } catch (e) { cuerpo.replaceChildren(aviso("error", e.message)); return; }
  if (!hueco.isConnected) return;
  c.meses = d.ventana_meses;
  // Los recuentos de las facetas llegan con la lista: en cuanto cambian se
  // repinta la barra para que los desplegables los muestren.
  if (JSON.stringify(d.facetas) !== JSON.stringify(c.facetas)) {
    c.facetas = d.facetas;
    if (estado.repintarFiltrosCompras) estado.repintarFiltrosCompras();
  }
  cuerpo.innerHTML = "";
  const cabecera = crear("div", "cabecera-novedades");
  if ((d.paginas || 1) > 1) cabecera.appendChild(paginador(d.pagina, d.paginas, (n) => { c.nov_pagina = n; recargar(); }));
  cuerpo.appendChild(cabecera);
  if (c.personalizadas && !d.hay_perfil) cuerpo.appendChild(aviso("info", t("nov_sin_perfil")));
  const rejilla = rejillaLibros(d.propuestas || [], c);
  cuerpo.appendChild(rejilla);
  // Paginador también al final: tras recorrer una página, la siguiente queda a mano
  if ((d.paginas || 1) > 1) {
    const pie = crear("div", "pie-novedades");
    pie.appendChild(paginador(d.pagina, d.paginas, (n) => { c.nov_pagina = n; recargar(); }));
    rejilla.appendChild(pie);
  }
}

/** Anterior · Página X de Y · Siguiente, con salto a la primera y la última. */
function paginador(pagina, paginas, alCambiar) {
  const caja = crear("div", "paginador");
  const boton = (texto, destino, titulo) => {
    const b = crear("button", "boton-pagina", texto);
    b.type = "button";
    b.title = titulo;
    b.setAttribute("aria-label", titulo);
    b.disabled = destino < 1 || destino > paginas || destino === pagina;
    b.addEventListener("click", () => alCambiar(destino));
    return b;
  };
  caja.append(
    boton("«", 1, t("pagina_primera")),
    boton("‹", pagina - 1, t("pagina_anterior")),
    crear("span", "posicion", t("pagina_de", { a: miles(pagina), b: miles(paginas) })),
    boton("›", pagina + 1, t("pagina_siguiente")),
    boton("»", paginas, t("pagina_ultima")),
  );
  return caja;
}

/* --- Lista con portada (autores) ------------------------------------------- */
function listaLibros(filas, c, opciones = {}) {
  const caja = crear("div", "lista-desplazable lista-libros");
  if (!filas.length) { caja.appendChild(crear("p", "vacio", t("sin_recomendaciones"))); return caja; }
  const lista = crear("ol", "libros");
  filas.forEach((f) => {
    const li = crear("li", "libro");
    li.tabIndex = 0;
    li.setAttribute("role", "button");
    const abrir = () => abrirCajonLibro(f, opciones);
    li.addEventListener("click", abrir);
    li.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); abrir(); } });
    li.appendChild(miniaturaLibro(f, "mediana"));
    const datos = crear("div", "datos-libro");
    datos.appendChild(crear("strong", "titulo-libro", f.titulo || "—"));
    datos.appendChild(crear("span", "autor-libro", [f.autor, f.editorial, (f.fecha || "").slice(0, 4)].filter(Boolean).join(" · ")));
    if (opciones.motivo) datos.appendChild(crear("span", "motivo-libro", opciones.motivo(f)));
    // Un avance del resumen: da contexto sin tener que abrir la ficha, y
    // aprovecha el ancho de la tarjeta.
    if (f.resumen) datos.appendChild(crear("span", "avance-libro", f.resumen));
    datos.appendChild(insigniasLibro(f));
    li.appendChild(datos);
    lista.appendChild(li);
  });
  caja.appendChild(lista);
  return caja;
}

/* --- Rejilla de portadas (novedades) --------------------------------------- */
function rejillaLibros(filas, c) {
  const caja = crear("div", "lista-desplazable");
  if (!filas.length) { caja.appendChild(crear("p", "vacio", t("sin_recomendaciones"))); return caja; }
  const rejilla = crear("div", "rejilla-libros");
  filas.forEach((f) => {
    const tarjeta = crear("button", "tarjeta-libro");
    tarjeta.type = "button";
    tarjeta.addEventListener("click", () => abrirCajonLibro(f, {}));
    tarjeta.appendChild(miniaturaLibro(f, "grande"));
    tarjeta.appendChild(crear("span", "titulo-libro", f.titulo || "—"));
    tarjeta.appendChild(crear("span", "autor-libro", f.autor || ""));
    tarjeta.appendChild(insigniasLibro(f));
    rejilla.appendChild(tarjeta);
  });
  caja.appendChild(rejilla);
  return caja;
}

function miniaturaLibro(f, tamano) {
  const caja = crear("span", `portada ${tamano}`);
  if (f.cubierta) {
    const img = crear("img");
    img.loading = "lazy";
    img.alt = "";
    img.src = f.cubierta;
    img.addEventListener("error", () => { img.remove(); caja.classList.add("sin-portada"); caja.textContent = (f.titulo || "?").slice(0, 2); });
    caja.appendChild(img);
  } else {
    caja.classList.add("sin-portada");
    caja.textContent = (f.titulo || "?").slice(0, 2).toUpperCase();
  }
  return caja;
}

function insigniasLibro(f) {
  const caja = crear("span", "insignias");
  caja.appendChild(distintivo(traducirEtiqueta(f.seccion || "—"), "info"));
  // Las otras secciones que le dan sus materias (novela gráfica, cómic…)
  (f.otras_secciones || []).forEach(([s]) => caja.appendChild(distintivo(traducirEtiqueta(s), "info")));
  caja.appendChild(distintivo(f.idioma ? traducirEtiqueta(f.idioma) : t("idioma_sin_indicar"),
                              f.idioma ? "frio" : "neutral"));
  if (f.edad !== null && f.edad !== undefined) caja.appendChild(distintivo(t("desde_n_anios", { n: f.edad }), "neutral"));
  if (f.ya_en_fondo) caja.appendChild(distintivo(t("en_tu_fondo"), "aviso"));
  if (f.del_autor === false) caja.appendChild(distintivo(t("sug_editorial"), "aviso"));
  if ((f.premios || []).length) caja.appendChild(distintivo(f.premios[0], "ok"));
  return caja;
}

/* --- Explicación del orden por afinidad (transparencia) ---------------------
   Con los pesos que usa de verdad el servidor, por si la red los ha cambiado. */
function ayudaAfinidad() {
  const b = (estado.config && estado.config.pesos_afinidad) || {};
  const n = (v, def) => numeroDecimal(v === undefined ? def : v, 1);
  const parrafos = [1, 2].map((i) => t(`af_ayuda_${i}`, {
    a: n(b.autor, 1), s: n(b.serie, 0.8), t: n(b.thema, 0.7), e: n(b.sello, 0.4),
    q: n(b.calificador, 0.4), k: n(b.clave, 0.3), p: n(b.premio, 1) }));
  if (estado.config && estado.config.afinidad_ajustada) parrafos[1] += " " + t("af_ayuda_ajustada");
  return ayudaDesplegable(t("af_ayuda_titulo"), parrafos, "ayuda-larga");
}

/* --- Comparación de algoritmos con el histórico propio ----------------------
   Prueba retrospectiva: con lo editado antes del corte se predice el préstamo
   de lo editado después, y se mide qué orden acierta más. */
async function abrirEvaluacionAfinidad(corte) {
  const caja = crear("div", "evaluacion-afinidad");
  cargando(caja);
  const cerrarModal = abrirModal(t("af_eval_titulo"), caja);
  let d;
  try { d = await API.evaluacionAfinidad(estado.sesion, corte); }
  catch (e) { caja.replaceChildren(aviso("error", e.message)); return; }
  caja.replaceChildren();
  const anio = (estado.config && estado.config.anio_actual) || new Date().getFullYear();
  const cortes = [];
  for (let a = anio - 6; a <= anio - 1; a++) cortes.push({ valor: String(a), etiqueta: String(a) });
  const selCorte = selector(t("af_eval_corte"), cortes, String(d.corte), (v) => {
    cerrarModal(); abrirEvaluacionAfinidad(Number(v));
  });
  caja.appendChild(selCorte);
  if ((d.avisos || []).includes("insuficiente")) {
    caja.appendChild(aviso("atencion", t("af_eval_insuficiente", { n: miles(d.n_prueba || 0) })));
    return;
  }
  caja.appendChild(crear("p", "nota-pie", t("af_eval_contexto", {
    a: d.anios_prueba[0], b: d.anios_prueba[1], n: miles(d.n_prueba), k: d.k,
    f: miles(d.cobertura.con_ficha), t: miles(d.cobertura.titulos), z: pct(d.base_nunca * 100) })));
  const tabla = crear("table", "datos tabla-evaluacion");
  const cab = crear("tr");
  [t("af_eval_metodo"), "Spearman", `nDCG@${d.k}`, "AUC", t("af_eval_nunca")].forEach((x, i) =>
    cab.appendChild(crear("th", i ? "num" : "", x)));
  tabla.appendChild(cab);
  const fmt = (v, porcentaje) => (v === null || v === undefined ? "—" : porcentaje ? pct(v * 100) : numeroDecimal(v, 3));
  ["nuevo", "anterior", "seccion", "azar"].filter((m) => d.metodos[m]).forEach((m) => {
    const x = d.metodos[m];
    const fila = crear("tr", m === "nuevo" ? "destacada" : "");
    fila.appendChild(crear("td", null, t(`af_m_${m}`)));
    [fmt(x.spearman), fmt(x.ndcg), fmt(x.auc), fmt(x.nunca_en_top, true)].forEach((v) => fila.appendChild(crear("td", "num", v)));
    tabla.appendChild(fila);
  });
  const envoltorio = crear("div", "tabla-desplazable");
  envoltorio.appendChild(tabla);
  caja.appendChild(envoltorio);
  Object.entries(d.mejora || {}).forEach(([rival, m]) => {
    if (!m.spearman || !m.ndcg) return;
    const claro = m.spearman.bajo > 0 && m.ndcg.bajo > 0;
    caja.appendChild(aviso(claro ? "ok" : "info", t("af_eval_mejora", {
      r: t(`af_m_${rival}`), s: numeroDecimal(m.spearman.media, 3),
      sb: numeroDecimal(m.spearman.bajo, 3), sa: numeroDecimal(m.spearman.alto, 3),
      d: numeroDecimal(m.ndcg.media, 3), db: numeroDecimal(m.ndcg.bajo, 3), da: numeroDecimal(m.ndcg.alto, 3) })));
  });
  (d.avisos || []).forEach((a) => caja.appendChild(aviso("atencion", t(`af_aviso_${a}`))));
  caja.appendChild(crear("p", "nota-pie", t("af_eval_ayuda")));
}

/* --- Materias THEMA ---------------------------------------------------------
   Los códigos llegan con cada libro; los encabezados («Novela romántica»)
   solo si la red ha dejado la lista de EDItEUR en la carpeta de datos. Se
   piden una vez por idioma. Sin ellos se enseña el código, con enlace. */
const THEMA = { idioma: null, nombres: {}, pedido: null };

async function cargarThema() {
  if (THEMA.idioma === IDIOMA) return;
  if (!THEMA.pedido) {
    THEMA.pedido = API.thema(IDIOMA)
      .then((d) => { THEMA.nombres = (d && d.nombres) || {}; })
      .catch(() => { THEMA.nombres = {}; })      // la demo no lo tiene grabado
      .finally(() => { THEMA.idioma = IDIOMA; THEMA.pedido = null; });
  }
  await THEMA.pedido;
}

function rotuloThema(codigo) {
  const nombre = THEMA.nombres[codigo];
  return nombre ? `${nombre} · ${codigo}` : codigo;
}

function urlThema(codigo) {
  // El buscador de EDItEUR tiene la traducción oficial al castellano (FGEE)
  const lengua = IDIOMA === "en" ? "en" : "es";
  return `https://ns.editeur.org/thema/${lengua}${codigo ? `/${encodeURIComponent(codigo)}` : ""}`;
}

function enlaceThema(codigo, texto, clase = "enlace-discreto enlace-thema") {
  const a = crear("a", clase, texto);
  a.href = urlThema(codigo);
  a.target = "_blank";
  a.rel = "noopener noreferrer";
  a.title = t("thema_consultar");
  return a;
}

function seccionesLibro(f) {
  return [f.seccion, ...(f.otras_secciones || []).map(([s]) => s)];
}

/* --- Cajón de detalle ------------------------------------------------------- */
const CLAVE_ANCHO_CAJON = "bildumargi.ancho_ficha";
const ANCHO_CAJON_NORMAL = 380;
const ANCHO_CAJON_AMPLIADO = 720;
const ICONO_REDUCIR = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
  stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
  <path d="M4 14h6v6"/><path d="M20 10h-6V4"/><path d="M14 10l7-7"/><path d="M3 21l7-7"/></svg>`;

/** Lo más ancho que puede ser la ficha: casi todo el panel, dejando ver un
    poco de la lista para no perder el contexto. */
function anchoMaximoCajon(cajon) {
  const contenedor = cajon.parentElement || document.body;
  return Math.max(ANCHO_CAJON_NORMAL, contenedor.clientWidth - 120);
}

/** Borde izquierdo de la ficha: se arrastra para darle el ancho que se quiera
    (también con las flechas del teclado). */
function asaCajon(cajon, alCambiar) {
  const asa = crear("div", "asa-cajon");
  asa.setAttribute("role", "separator");
  asa.setAttribute("aria-orientation", "vertical");
  asa.setAttribute("aria-label", t("redimensionar_ficha"));
  asa.title = t("redimensionar_ficha");
  asa.tabIndex = 0;
  const fijar = (ancho) => {
    const limpio = Math.round(Math.min(anchoMaximoCajon(cajon), Math.max(300, ancho)));
    cajon.style.width = `${limpio}px`;
    cajon.classList.toggle("ampliado", limpio >= ANCHO_CAJON_AMPLIADO);
    try { localStorage.setItem(CLAVE_ANCHO_CAJON, String(limpio)); } catch { /* sin almacenamiento */ }
    alCambiar();
  };
  asa.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    asa.setPointerCapture(e.pointerId);
    const derecha = cajon.getBoundingClientRect().right;
    cajon.classList.add("arrastrando");
    const mover = (ev) => fijar(derecha - ev.clientX);
    const soltar = () => {
      cajon.classList.remove("arrastrando");
      asa.removeEventListener("pointermove", mover);
      asa.removeEventListener("pointerup", soltar);
    };
    asa.addEventListener("pointermove", mover);
    asa.addEventListener("pointerup", soltar);
  });
  asa.addEventListener("keydown", (e) => {
    const actual = cajon.getBoundingClientRect().width;
    if (e.key === "ArrowLeft") { e.preventDefault(); fijar(actual + 40); }
    if (e.key === "ArrowRight") { e.preventDefault(); fijar(actual - 40); }
  });
  return asa;
}

/** Las fechas de ONIX llegan como AAAAMMDD, AAAAMM o AAAA: se enseñan como
    fecha legible («26/10/2025», «10/2025», «2025»). */
function fechaOnix(valor) {
  const d = String(valor || "").replace(/\D/g, "");
  if (d.length >= 8) return `${d.slice(6, 8)}/${d.slice(4, 6)}/${d.slice(0, 4)}`;
  if (d.length === 6) return `${d.slice(4, 6)}/${d.slice(0, 4)}`;
  return d.slice(0, 4) || "";
}

function abrirCajonLibro(f, opciones = {}) {
  cerrarCajonLibro();
  const cajon = crear("aside", "cajon-libro");
  cajon.setAttribute("role", "dialog");
  cajon.setAttribute("aria-label", f.titulo || "");
  // Anchura: la que dejó el bibliotecario la última vez (arrastrando el borde
  // o con el botón de ampliar). Se recuerda en este navegador.
  const anchoGuardado = Number(localStorage.getItem(CLAVE_ANCHO_CAJON)) || 0;
  if (anchoGuardado) cajon.style.width = `${anchoGuardado}px`;
  if (anchoGuardado >= ANCHO_CAJON_AMPLIADO) cajon.classList.add("ampliado");

  const botones = crear("div", "botones-cajon");
  const ampliar = crear("button", "boton-cajon");
  ampliar.type = "button";
  const rotularAmpliar = () => {
    const amplio = cajon.classList.contains("ampliado");
    ampliar.innerHTML = amplio ? ICONO_REDUCIR : ICONO_AMPLIAR;
    ampliar.title = t(amplio ? "reducir_ficha" : "ampliar_ficha");
    ampliar.setAttribute("aria-label", ampliar.title);
  };
  ampliar.addEventListener("click", () => {
    const amplio = !cajon.classList.contains("ampliado");
    cajon.classList.toggle("ampliado", amplio);
    const ancho = amplio ? Math.min(ANCHO_CAJON_AMPLIADO, anchoMaximoCajon(cajon)) : ANCHO_CAJON_NORMAL;
    cajon.style.width = `${ancho}px`;
    try { localStorage.setItem(CLAVE_ANCHO_CAJON, String(ancho)); } catch { /* sin almacenamiento */ }
    rotularAmpliar();
  });
  rotularAmpliar();
  const cerrar = crear("button", "boton-cajon cerrar-cajon", "×");
  cerrar.type = "button";
  cerrar.setAttribute("aria-label", t("cerrar"));
  cerrar.addEventListener("click", cerrarCajonLibro);
  botones.append(ampliar, cerrar);
  cajon.appendChild(botones);
  cajon.appendChild(asaCajon(cajon, rotularAmpliar));

  // Cabecera: portada y datos, que en la ficha ampliada van lado a lado
  const cabecera = crear("div", "cabecera-cajon");
  cabecera.appendChild(miniaturaLibro(f, "grande"));
  const principal = crear("div", "principal-cajon");
  principal.appendChild(crear("h3", null, f.titulo || "—"));
  if (f.subtitulo) principal.appendChild(crear("p", "sub-cajon", f.subtitulo));
  cabecera.appendChild(principal);
  cajon.appendChild(cabecera);
  const ficha = crear("dl", "ficha-cajon");
  const dato = (etiqueta, valor) => {
    if (!valor) return;
    ficha.appendChild(crear("dt", null, etiqueta));
    ficha.appendChild(crear("dd", null, String(valor)));
  };
  dato(t("col_autor"), f.autor);
  dato(t("ficha_editorial"), f.editorial);
  dato(t("ficha_publicacion"), fechaOnix(f.fecha));
  dato(t("nov_coleccion"), f.coleccion);
  dato(t("col_seccion"), `${traducirEtiqueta(f.seccion || "")} (${f.motivo_seccion || ""})`);
  if ((f.otras_secciones || []).length) {
    dato(t("tambien_en"), f.otras_secciones.map(([s, m]) => `${traducirEtiqueta(s)} (${m})`).join(" · "));
  }
  dato(t("col_idioma"), f.idioma ? traducirEtiqueta(f.idioma) : t("idioma_sin_indicar"));
  dato(t("col_paginas"), f.paginas);
  dato("ISBN", f.isbn);
  principal.appendChild(ficha);
  if (opciones.motivo) cajon.appendChild(aviso("info", opciones.motivo(f)));
  if (f.parecido && f.parecido.length) cajon.appendChild(aviso("info", t("nov_parecido", { s: f.parecido.join(" · ") })));
  if (f.resumen) {
    cajon.appendChild(crear("h4", null, t("nov_resumen")));
    cajon.appendChild(crear("p", "resumen-cajon", f.resumen));
  }
  if ((f.claves || []).length) {
    cajon.appendChild(crear("h4", null, t("nov_claves")));
    const claves = crear("div", "claves");
    f.claves.forEach((k) => claves.appendChild(distintivo(k, "neutral")));
    cajon.appendChild(claves);
  }
  if ((f.thema || []).length) {
    // Materias THEMA con su encabezado (si la red ha cargado la lista) y
    // enlace a su definición en el buscador oficial de EDItEUR.
    cajon.appendChild(crear("h4", null, t("ficha_thema")));
    const caja = crear("div", "claves");
    f.thema.forEach((codigo) => {
      const enlace = enlaceThema(codigo, rotuloThema(codigo), "distintivo info enlace-thema");
      caja.appendChild(enlace);
    });
    cajon.appendChild(caja);
  }
  document.querySelector(".panel-compras").appendChild(cajon);
  document.addEventListener("keydown", _escCajon);
  cerrar.focus();
}

function _escCajon(e) { if (e.key === "Escape") cerrarCajonLibro(); }

function cerrarCajonLibro() {
  const abierto = document.querySelector(".cajon-libro");
  if (abierto) abierto.remove();
  document.removeEventListener("keydown", _escCajon);
}

/* ==========================================================================
   Vista: red
   Lo que las bibliotecas se cuentan sobre los libros: actividad reciente,
   mejor valorados y más comentados. Cada biblioteca firma con su nombre; no
   hay usuarios ni datos personales. Se comentan libros, no personas.
   ========================================================================== */
let peticionRed = 0;
let refrescoRedPendiente = null;

// Lo llama la ficha tras guardar, borrar o responder: si la pestaña «Red»
// está abierta, su actividad se actualiza sin tener que salir y volver.
function avisarCambioRed() {
  if (estado.vista !== "red" || !estado.huecosRed) return;
  clearTimeout(refrescoRedPendiente);
  refrescoRedPendiente = setTimeout(() => refrescarRed(estado.huecosRed).catch(() => {}), 150);
}

function esqueletoRed(vista) {
  vista.innerHTML = "";
  const raiz = crear("div", "panel-secciones panel-red");
  const filtros = crear("div", "barra-superior barra-panel");
  const rejilla = crear("div", "rejilla-red");
  const huecos = { raiz, filtros, rejilla, kpis: [] };
  for (let i = 0; i < 4; i++) {
    const h = crear("div", "hueco-indicador col-3");
    rejilla.appendChild(h);
    huecos.kpis.push(h);
  }
  const hueco = (clase) => { const h = crear("div", `hueco ${clase}`); rejilla.appendChild(h); return h; };
  huecos.actividad = hueco("zona-actividad");
  huecos.mejores = hueco("zona-mejores");
  huecos.comentados = hueco("zona-comentados");
  raiz.append(filtros, rejilla);
  vista.appendChild(raiz);
  return huecos;
}

async function vistaRed(vista) {
  soltarMedidores();
  estado.huecosRed = esqueletoRed(vista);
  await refrescarRed(estado.huecosRed);
}

async function refrescarRed(huecos) {
  const c = estado.controles.red;
  const numero = ++peticionRed;
  huecos.rejilla.classList.add("actualizando");
  let datos;
  try {
    datos = await API.red(estado.sesion, { filtro: c.filtro, limite: 80 });
  } finally {
    if (numero === peticionRed) huecos.rejilla.classList.remove("actualizando");
  }
  if (numero !== peticionRed || !huecos.raiz.isConnected) return;
  const recargar = () => refrescarRed(huecos).catch((e) => huecos.filtros.after(aviso("error", e.message)));

  pintarBarraRed(huecos.filtros, datos, c, recargar);
  pintarKpisRed(huecos.kpis, datos);
  pintarActividadRed(huecos.actividad, datos, c);
  pintarRankingRed(huecos.mejores, t("red_mejores"), t("red_mejores_sub"), datos.mejor_valorados, (f) => {
    const caja = crear("span", "valor-ranking");
    caja.append(estrellas(Math.round(f.media)), crear("span", null, `${decimal(f.media, 1)} (${f.n_puntuaciones})`));
    return caja;
  });
  pintarRankingRed(huecos.comentados, t("red_comentados"), t("red_comentados_sub"), datos.mas_comentados,
    (f) => crear("span", "valor-ranking", t("red_conversacion", { c: f.comentarios, r: f.respuestas })));
}

/* --- Barra: qué actividad ver y normas de uso ----------------------------- */
function pintarBarraRed(barra, datos, c, recargar) {
  barra.innerHTML = "";
  const grupo = crear("div", "conmutador conmutador-red");
  grupo.setAttribute("role", "group");
  grupo.setAttribute("aria-label", t("red_ver"));
  [["todo", t("red_filtro_todo")],
   ["a_mi", t("red_filtro_a_mi", { n: datos.respuestas_a_mi })],
   ["mia", t("red_filtro_mia")]].forEach(([valor, texto]) => {
    const b = crear("button", valor === c.filtro ? "activo" : "", texto);
    b.setAttribute("aria-pressed", String(valor === c.filtro));
    b.addEventListener("click", () => { if (c.filtro !== valor) { c.filtro = valor; recargar(); } });
    grupo.appendChild(b);
  });
  barra.appendChild(grupo);
  barra.appendChild(crear("p", "normas-uso normas-barra", t("normas_uso")));
  if (!datos.disponible) barra.appendChild(aviso("atencion", datos.error || t("valoraciones_desactivadas")));
}

/* --- Indicadores de participación ----------------------------------------- */
function pintarKpisRed(huecos, d) {
  const e = d.estadisticas;
  const tarjetas = [
    tarjetaIndicador({ rotulo: t("red_bibliotecas"), valor: miles(e.bibliotecas), acento: PALETA.cian,
      unidad: d.bibliotecas_red ? t("de_n_bibliotecas", { n: miles(d.bibliotecas_red) }) : null,
      grafico: d.bibliotecas_red ? graficoBala({ valor: e.bibliotecas, escala: d.bibliotecas_red, color: PALETA.cian }) : null,
      contexto: t("red_bibliotecas_ctx") }),
    tarjetaIndicador({ rotulo: t("red_titulos"), valor: miles(e.titulos), acento: PALETA.violeta,
      contexto: t("red_titulos_ctx", { n: miles(e.valoraciones) }) }),
    tarjetaIndicador({ rotulo: t("red_conversaciones"), valor: miles(e.comentarios + e.respuestas), acento: PALETA.ambar,
      contexto: t("red_conversaciones_ctx", { c: miles(e.comentarios), r: miles(e.respuestas) }) }),
    tarjetaIndicador({ rotulo: t("red_a_mi"), valor: miles(d.respuestas_a_mi), acento: PALETA.verde,
      contexto: t("red_reciente_ctx", { n: miles(e.actividad_reciente) }) }),
  ];
  tarjetas.forEach((tarjeta, i) => huecos[i].replaceChildren(tarjeta));
}

/* --- Actividad reciente ---------------------------------------------------- */
function botonTitulo(f) {
  const b = crear("button", "enlace-ficha", f.titulo || f.id_sistema);
  b.title = t("ver_ficha_y_conversacion");
  b.addEventListener("click", () => verFichaRed(f.id_sistema));
  return b;
}

function pintarActividadRed(hueco, d, c) {
  const subtitulos = { todo: t("red_actividad_sub"), a_mi: t("red_actividad_a_mi_sub"), mia: t("red_actividad_mia_sub") };
  const cuerpo = cuadroPanel(hueco, t("red_actividad"), subtitulos[c.filtro]);
  const lista = crear("ol", "actividad");
  if (!d.actividad.length) {
    cuerpo.appendChild(crear("p", "vacio", t(c.filtro === "todo" ? "red_sin_actividad" : "red_sin_actividad_filtro")));
    return;
  }
  d.actividad.forEach((f) => {
    const li = crear("li", `evento ${f.tipo}${f.biblioteca === d.biblioteca ? " propio" : ""}`);
    const cabeza = crear("div", "cabeza-evento");
    cabeza.appendChild(crear("span", "quien", f.biblioteca));
    cabeza.appendChild(crear("span", "accion", f.tipo === "respuesta"
      ? t("red_respondio", { n: f.destino }) : f.texto ? t("red_comento") : t("red_valoro")));
    const cuando = crear("time", "cuando", fechaRelativa(f.fecha));
    cuando.dateTime = f.fecha;
    cuando.title = fechaCorta(f.fecha);
    cabeza.appendChild(cuando);
    li.appendChild(cabeza);
    const linea = crear("div", "titulo-evento");
    linea.appendChild(botonTitulo(f));
    if (f.autor) linea.appendChild(crear("span", "autor-evento", f.autor));
    if (f.en_fondo) linea.appendChild(distintivo(t("en_tu_fondo"), "frio"));
    if (f.puntuacion) linea.appendChild(estrellas(f.puntuacion));
    li.appendChild(linea);
    if (f.texto) li.appendChild(crear("p", "texto-evento", f.texto));   // textContent vía crear
    lista.appendChild(li);
  });
  const desplazable = crear("div", "lista-desplazable");
  desplazable.appendChild(lista);
  cuerpo.appendChild(desplazable);
}

/* --- Rankings -------------------------------------------------------------- */
function pintarRankingRed(hueco, titulo, subtitulo, filas, valor) {
  const cuerpo = cuadroPanel(hueco, titulo, subtitulo);
  if (!filas.length) { cuerpo.appendChild(crear("p", "vacio", t("red_ranking_vacio"))); return; }
  const lista = crear("ol", "ranking");
  filas.forEach((f, i) => {
    const li = crear("li");
    li.appendChild(crear("span", "posicion-ranking", String(i + 1)));
    const texto = crear("span", "texto-ranking");
    texto.appendChild(botonTitulo(f));
    const pie = crear("span", "autor-evento", f.autor || "");
    if (f.en_fondo) pie.appendChild(distintivo(t("en_tu_fondo"), "frio"));
    texto.appendChild(pie);
    li.append(texto, valor(f));
    lista.appendChild(li);
  });
  const desplazable = crear("div", "lista-desplazable");
  desplazable.appendChild(lista);
  cuerpo.appendChild(desplazable);
}

/* ==========================================================================
   Configuración de la biblioteca
   Tema, paleta de los gráficos, pestañas visibles y pestaña de inicio. Se
   guarda en el navegador (para aplicarse desde la primera pantalla) y, con
   una sesión abierta, en el servidor para esa biblioteca (para que sea la
   misma en todos sus ordenadores).
   ========================================================================== */
const CLAVE_PREFERENCIAS = "bildumargi.preferencias";
const PREFS_DEFECTO = { tema: "oscuro", paleta: "okabe", pestanas_ocultas: [], inicio: "diagnostico", idioma: null };

// Valores de partida de una biblioteca: los de la red, si los ha fijado.
function prefsDefecto() {
  const red = configRed();
  return { ...PREFS_DEFECTO, tema: red.tema_defecto || PREFS_DEFECTO.tema,
           paleta: red.paleta_defecto || PREFS_DEFECTO.paleta, pestanas_ocultas: [] };
}

function preferenciasLocales() {
  try {
    const guardadas = JSON.parse(localStorage.getItem(CLAVE_PREFERENCIAS));
    return guardadas ? { ...prefsDefecto(), ...guardadas, _guardadas: true } : { ...prefsDefecto() };
  } catch { return { ...prefsDefecto() }; }
}

function guardarPreferenciasLocales(prefs) {
  try { localStorage.setItem(CLAVE_PREFERENCIAS, JSON.stringify(prefs)); } catch { /* navegador sin almacenamiento */ }
}

async function cargarPreferenciasBiblioteca() {
  try {
    const r = await API.preferencias(estado.sesion);
    estado.prefsServidor = r;
    if (r.preferencias) {
      estado.preferencias = { ...PREFS_DEFECTO, ...r.preferencias };
      guardarPreferenciasLocales(estado.preferencias);
      aplicarApariencia(estado.preferencias);
      const idioma = idiomaPreferido();
      if (idioma !== IDIOMA) aplicarIdioma(idioma);   // la vista se pinta después, ya traducida
    }
  } catch { /* sin preferencias en el servidor: se quedan las del navegador */ }
}

function vistaInicial() {
  const visibles = seccionesDisponibles().map((s) => s.clave);
  return visibles.includes(estado.preferencias.inicio) ? estado.preferencias.inicio : visibles[0];
}

const ICONO_CONFIG = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
  <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>`;

function montarBotonConfiguracion() {
  const derecha = document.querySelector(".cabecera .derecha");
  if (!derecha || derecha.querySelector(".boton-config")) return;
  const boton = crear("button", "boton-config");
  boton.type = "button";
  boton.innerHTML = ICONO_CONFIG;
  boton.addEventListener("click", () => abrirConfiguracion());
  derecha.appendChild(boton);
  rotularBotonConfiguracion();
}

function rotularBotonConfiguracion() {
  const boton = document.querySelector(".boton-config");
  if (!boton) return;
  boton.title = t("configuracion");
  boton.setAttribute("aria-label", t("configuracion"));
}

// Repinta la vista abierta (si la hay) para que los gráficos tomen la paleta.
function repintarVista() {
  if (estado.sesion && estado.vista) mostrarVista(estado.vista);
}

function grupoOpciones(opciones, valor, alElegir) {
  const grupo = crear("div", "opciones-tarjeta");
  grupo.setAttribute("role", "radiogroup");
  const botones = opciones.map((o) => {
    const b = crear("button", "opcion-tarjeta");
    b.type = "button";
    b.setAttribute("role", "radio");
    b.setAttribute("aria-checked", String(o.valor === valor));
    b.appendChild(o.muestra);
    b.appendChild(crear("span", "nombre", o.nombre));
    if (o.detalle) b.appendChild(crear("span", "detalle", o.detalle));
    b.addEventListener("click", () => {
      botones.forEach((x) => x.setAttribute("aria-checked", String(x === b)));
      alElegir(o.valor);
    });
    grupo.appendChild(b);
    return b;
  });
  return grupo;
}

// `inicial`: valores con los que abrir el panel (Restablecer lo reabre con
// los de por defecto). Lo guardado sigue siendo `estado.preferencias` hasta
// que se pulsa Guardar; cerrar sin guardar vuelve a ello.
function abrirConfiguracion(inicial) {
  const original = { ...estado.preferencias, pestanas_ocultas: [...estado.preferencias.pestanas_ocultas] };
  const base = inicial && inicial.tema ? inicial : original;
  const borrador = { ...base, pestanas_ocultas: [...base.pestanas_ocultas] };
  let guardado = false;
  const contenido = crear("div", "config");

  const previsualizar = () => { aplicarApariencia(borrador); repintarVista(); };

  // --- Idioma de la interfaz
  const fsIdioma = crear("fieldset");
  fsIdioma.appendChild(crear("legend", null, t("config_idioma")));
  fsIdioma.appendChild(grupoOpciones(idiomasPermitidos().map((i) => ({
    valor: i.codigo, nombre: i.nombre, muestra: crear("span", "muestra-idioma", i.codigo.toUpperCase()),
  })), borrador.idioma || idiomaPreferido(), (v) => { borrador.idioma = v; }));
  contenido.appendChild(fsIdioma);

  // --- Tema
  const fsTema = crear("fieldset");
  fsTema.appendChild(crear("legend", null, t("config_tema")));
  const muestraTema = (clase) => { const m = crear("span", `muestra-tema ${clase}`); m.append(crear("span"), crear("span"), crear("span")); return m; };
  fsTema.appendChild(grupoOpciones([
    { valor: "oscuro", nombre: t("tema_oscuro"), detalle: t("tema_oscuro_det"), muestra: muestraTema("oscuro") },
    { valor: "claro", nombre: t("tema_claro"), detalle: t("tema_claro_det"), muestra: muestraTema("claro") },
  ], borrador.tema, (v) => { borrador.tema = v; previsualizar(); }));
  contenido.appendChild(fsTema);

  // --- Paleta de los gráficos
  const fsPaleta = crear("fieldset");
  fsPaleta.appendChild(crear("legend", null, t("config_paleta")));
  fsPaleta.appendChild(crear("p", "ayuda-config", t("config_paleta_ayuda")));
  const muestraPaleta = (clave) => {
    const p = PALETAS_GRAFICOS[clave];
    const caja = crear("span");
    const escala = crear("span", "muestra-paleta");
    escala.style.display = "block";
    escala.style.background = `linear-gradient(90deg, ${p.escala.join(", ")})`;
    const uso = crear("span", "muestra-uso");
    uso.style.marginTop = "5px";
    const a = crear("span"); a.style.background = p.encima;
    const b = crear("span"); b.style.background = p.debajo;
    uso.append(a, b);
    caja.append(escala, uso);
    return caja;
  };
  fsPaleta.appendChild(grupoOpciones(["okabe", "viridis", "azules"].map((clave) => ({
    valor: clave, nombre: t(`paleta_${clave}`), detalle: t(`paleta_${clave}_det`), muestra: muestraPaleta(clave),
  })), borrador.paleta, (v) => { borrador.paleta = v; previsualizar(); }));
  contenido.appendChild(fsPaleta);

  // --- Pestañas visibles y pestaña de inicio
  const fsPestanas = crear("fieldset");
  fsPestanas.appendChild(crear("legend", null, t("config_pestanas")));
  fsPestanas.appendChild(crear("p", "ayuda-config", t("config_pestanas_ayuda")));
  const lista = crear("div", "lista-pestanas");
  const posibles = seccionesPosibles();
  const disponibles = new Set(posibles.filter((s) => s.disponible).map((s) => s.clave));
  const selectorInicio = crear("select");
  const pintarInicio = () => {
    selectorInicio.innerHTML = "";
    posibles.filter((s) => disponibles.has(s.clave) && !borrador.pestanas_ocultas.includes(s.clave)).forEach((s) => {
      const o = crear("option", null, t(s.etiqueta));
      o.value = s.clave;
      o.selected = s.clave === borrador.inicio;
      selectorInicio.appendChild(o);
    });
    if (!selectorInicio.value && selectorInicio.options.length) selectorInicio.selectedIndex = 0;
    borrador.inicio = selectorInicio.value;
  };
  posibles.forEach((s) => {
    const etiqueta = crear("label", disponibles.has(s.clave) ? "" : "no-disponible");
    const casillaP = crear("input");
    casillaP.type = "checkbox";
    casillaP.checked = !borrador.pestanas_ocultas.includes(s.clave);
    casillaP.addEventListener("change", () => {
      const ocultas = new Set(borrador.pestanas_ocultas);
      if (casillaP.checked) ocultas.delete(s.clave); else ocultas.add(s.clave);
      borrador.pestanas_ocultas = posibles.map((p) => p.clave).filter((c) => ocultas.has(c));
      pintarInicio();
    });
    etiqueta.append(casillaP, document.createTextNode(t(s.etiqueta)));
    if (!disponibles.has(s.clave)) {
      casillaP.disabled = true;
      etiqueta.appendChild(crear("small", null, ` · ${t(s.motivo || "config_no_disponible")}`));
    }
    lista.appendChild(etiqueta);
  });
  fsPestanas.appendChild(lista);
  const campoInicio = crear("label", "campo");
  campoInicio.append(crear("span", "rotulo-campo", t("config_inicio")), selectorInicio);
  selectorInicio.addEventListener("change", () => { borrador.inicio = selectorInicio.value; });
  pintarInicio();
  fsPestanas.appendChild(campoInicio);
  contenido.appendChild(fsPestanas);

  // --- Secciones por signatura (solo con una biblioteca abierta)
  let editorSig = null;
  if (estado.sesion) {
    const fsSig = crear("fieldset");
    fsSig.appendChild(crear("legend", null, t("sig_titulo")));
    fsSig.appendChild(crear("p", "ayuda-config", t("sig_ayuda")));
    const huecoSig = crear("div");
    cargando(huecoSig);
    fsSig.appendChild(huecoSig);
    contenido.appendChild(fsSig);
    API.signaturas(estado.sesion).then((d) => {
      huecoSig.innerHTML = "";
      huecoSig.appendChild(crear("p", "nota-pie", t(`sig_origen_${d.origen}`)));
      const restaurar = d.red || (estado.config && estado.config.signaturas_defecto) || [];
      editorSig = editorSignaturas(d.reglas, restaurar, t(d.red ? "sig_restaurar_red" : "sig_restaurar"));
      huecoSig.appendChild(editorSig.nodo);
    }).catch((e) => { huecoSig.replaceChildren(aviso("error", e.message)); });
  }

  // --- Pie: dónde se guarda y acciones
  const pie = crear("div", "pie-config");
  pie.appendChild(crear("span", "donde", estado.sesion
    ? t("config_guardado_biblioteca", { n: estado.biblioteca || "" })
    : t("config_guardado_navegador")));
  if (estado.config.admin_disponible) {
    const admin = crear("button", "enlace-discreto enlace-admin", t("admin_titulo"));
    admin.type = "button";
    admin.addEventListener("click", () => { cerrar(); abrirAdministracion(); });
    pie.appendChild(admin);
  }
  const restablecer = crear("button", "boton secundario", t("restablecer"));
  const cancelar = crear("button", "boton secundario", t("cancelar"));
  const guardar = crear("button", "boton", t("guardar"));
  pie.append(restablecer, cancelar, guardar);
  const mensajes = crear("div");
  contenido.append(pie, mensajes);

  const cerrar = abrirModal(t("configuracion"), contenido, () => {
    if (guardado) return;
    // Cerrar sin guardar deshace la previsualización
    aplicarApariencia(original);
    repintarVista();
  });

  restablecer.addEventListener("click", () => {
    guardado = true;                 // no deshacer: se reabre con los valores por defecto
    cerrar();
    const defecto = { ...prefsDefecto() };
    aplicarApariencia(defecto);
    repintarVista();
    abrirConfiguracion(defecto);
  });
  cancelar.addEventListener("click", () => cerrar());
  guardar.addEventListener("click", async () => {
    mensajes.innerHTML = "";
    const visibles = posibles.filter((s) => disponibles.has(s.clave) && !borrador.pestanas_ocultas.includes(s.clave));
    if (!visibles.length) { mensajes.appendChild(aviso("error", t("config_una_pestana"))); return; }
    guardar.disabled = true;
    estado.preferencias = { ...borrador, pestanas_ocultas: [...borrador.pestanas_ocultas] };
    guardarPreferenciasLocales(estado.preferencias);
    if (estado.sesion) {
      try {
        const r = await API.guardarPreferencias(estado.sesion, estado.preferencias);
        estado.preferencias = { ...PREFS_DEFECTO, ...r.preferencias };
        guardarPreferenciasLocales(estado.preferencias);
        // La tabla de signaturas reclasifica el fondo en el servidor al guardar
        if (editorSig && editorSig.cambiado()) await API.guardarSignaturas(estado.sesion, editorSig.leer());
      } catch (e) {
        mensajes.appendChild(aviso("atencion", t("config_error_guardar", { e: e.message })));
        guardar.disabled = false;
        return;
      }
    }
    guardado = true;
    cerrar();
    aplicarApariencia(estado.preferencias);
    if (idiomaPreferido() !== IDIOMA) {
      cambiarIdioma(idiomaPreferido());   // traduce todo y repinta la vista
      if (estado.sesion) pintarNavegador();
      return;
    }
    if (estado.sesion) {
      pintarNavegador();
      const visiblesAhora = seccionesDisponibles().map((s) => s.clave);
      mostrarVista(visiblesAhora.includes(estado.vista) ? estado.vista : vistaInicial());
    }
  });
}

/* --- Editor de la tabla de signaturas (Configuración y Administración) -----
   Dos columnas editables: cómo empieza la signatura y a qué sección va. Gana
   el prefijo más largo. `restaurar` es la tabla a la que vuelve el botón
   (la de la red para una biblioteca, la estándar para la red). */
function editorSignaturas(reglas, restaurar, rotuloRestaurar) {
  const nodo = crear("div", "editor-signaturas");
  const cuerpoTabla = crear("tbody");
  const inicial = JSON.stringify(normalizarFilas(reglas));
  const fila = (prefijo = "", seccion = "") => {
    const tr = crear("tr");
    const celda = (valor, marcador, clase) => {
      const td = crear("td");
      const i = crear("input", clase);
      i.type = "text"; i.value = valor; i.placeholder = marcador; i.maxLength = clase === "sig-prefijo" ? 20 : 60;
      td.appendChild(i);
      return td;
    };
    const quitar = crear("button", "boton-quitar", "×");
    quitar.type = "button";
    quitar.title = t("sig_quitar");
    quitar.setAttribute("aria-label", t("sig_quitar"));
    quitar.addEventListener("click", () => tr.remove());
    const tdQuitar = crear("td");
    tdQuitar.appendChild(quitar);
    tr.append(celda(prefijo, "VIA", "sig-prefijo"), celda(seccion, t("sig_ejemplo_seccion"), "sig-seccion"), tdQuitar);
    return tr;
  };
  const rellenar = (lista) => {
    cuerpoTabla.innerHTML = "";
    (lista || []).forEach((r) => cuerpoTabla.appendChild(fila(r.prefijo, r.seccion)));
  };
  const tabla = crear("table", "datos tabla-signaturas");
  const cab = crear("tr");
  [t("sig_empieza"), t("sig_seccion"), ""].forEach((x) => cab.appendChild(crear("th", null, x)));
  const thead = crear("thead");
  thead.appendChild(cab);
  tabla.append(thead, cuerpoTabla);
  const caja = crear("div", "caja-signaturas");
  caja.appendChild(tabla);
  const acciones = crear("div", "acciones-signaturas");
  const anadir = crear("button", "boton secundario", t("sig_anadir"));
  anadir.type = "button";
  anadir.addEventListener("click", () => {
    const tr = fila();
    cuerpoTabla.prepend(tr);
    caja.scrollTop = 0;
    tr.querySelector("input").focus();
  });
  const volver = crear("button", "enlace-discreto", rotuloRestaurar);
  volver.type = "button";
  volver.addEventListener("click", () => rellenar(restaurar));
  acciones.append(anadir, volver);
  nodo.append(caja, acciones);
  rellenar(reglas);
  const leer = () => normalizarFilas([...cuerpoTabla.querySelectorAll("tr")].map((tr) => ({
    prefijo: tr.querySelector(".sig-prefijo").value, seccion: tr.querySelector(".sig-seccion").value })));
  return { nodo, leer, cambiado: () => JSON.stringify(leer()) !== inicial };
}

function normalizarFilas(lista) {
  const vistas = new Map();
  (lista || []).forEach((r) => {
    const p = String(r.prefijo || "").replace(/\s+/g, " ").trim().toUpperCase();
    const s = String(r.seccion || "").replace(/\s+/g, " ").trim();
    if (p && s) vistas.set(p, s);
  });
  return [...vistas].map(([prefijo, seccion]) => ({ prefijo, seccion }));
}

/* ==========================================================================
   Informe imprimible
   Radiografía del fondo completo en hojas A4, siempre en tema claro, para
   imprimir o guardar como PDF desde el navegador (sin librerías: funciona sin
   conexión). Reutiliza los cálculos y gráficos del panel, así que dice lo
   mismo que la pantalla. Pensado para acompañar una petición de presupuesto.
   ========================================================================== */
const ANCHO_INFORME = 680;   // px ≈ 180 mm: el ancho útil de una hoja A4

async function abrirInforme() {
  if (!estado.sesion || document.querySelector(".velo-informe")) return;
  const velo = crear("div", "velo-informe");
  velo.setAttribute("role", "dialog");
  velo.setAttribute("aria-modal", "true");
  velo.setAttribute("aria-label", t("informe_titulo"));
  const barra = crear("div", "informe-barra");
  barra.appendChild(crear("strong", null, t("informe_titulo")));
  const modo = selector(t("informe_colores"), [
    { valor: "color", etiqueta: t("informe_color") },
    { valor: "bn", etiqueta: t("informe_bn") },
  ], "color", (v) => construir(v));
  barra.appendChild(modo);
  const imprimir = crear("button", "boton", t("imprimir"));
  imprimir.addEventListener("click", () => window.print());
  const cerrar = crear("button", "boton secundario", t("cerrar"));
  barra.append(imprimir, cerrar);
  const hojas = crear("div", "informe");
  velo.append(barra, hojas);
  document.body.appendChild(velo);
  document.body.classList.add("con-informe");

  const salir = () => {
    velo.remove();
    document.body.classList.remove("con-informe");
    document.removeEventListener("keydown", alPulsar);
    aplicarApariencia(estado.preferencias);   // vuelve el tema de la biblioteca
    repintarVista();
  };
  const alPulsar = (e) => { if (e.key === "Escape") salir(); };
  cerrar.addEventListener("click", salir);
  document.addEventListener("keydown", alPulsar);
  imprimir.focus();

  let datos = null, compra = null;
  const construir = async (modoColor) => {
    // El informe se dibuja siempre en claro; en «blanco y negro», con la
    // paleta de un solo tono. Al cerrar se restaura la de la biblioteca.
    aplicarApariencia({ tema: "claro", paleta: modoColor === "bn" ? "azules" : estado.preferencias.paleta });
    cargando(hojas);
    try {
      if (!datos) {
        datos = await API.buscar(estado.sesion, { por_pagina: 1, ligero: true, ui: IDIOMA });
        if (estado.config.recomendaciones_activas) {
          compra = await API.recPanel(estado.sesion, { anio_minimo: estado.config.anio_actual - 4, limite: 200 })
            .catch(() => null);
        }
      }
      hojas.replaceChildren(...componerInforme(datos, compra));
      paginarInforme(hojas);
    } catch (e) {
      hojas.replaceChildren(aviso("error", e.message));
    }
  };
  await construir("color");
}

function componerInforme(datos, compra) {
  const sinFiltros = { texto: "", loc: "__TODAS__", publico: "todo", idioma: "__TODOS__" };
  const a = prepararDiagnostico(datos, sinFiltros);
  const pc = compra ? prepararCompras(compra) : null;
  const hojas = [hojaResumen(a), hojaSecciones(a, datos)];
  if (pc && pc.puntos.length) hojas.push(hojaCompra(pc, compra));
  // Notas al final de la última hoja
  hojas[hojas.length - 1].querySelector(".cuerpo-hoja").appendChild(notasInforme(a));
  hojas.forEach((h) => h.appendChild(pieHoja()));
  return hojas;
}

function pieHoja() {
  const pie = crear("footer", "pie-hoja");
  const fecha = new Date().toLocaleDateString(LOCALE_FECHAS[IDIOMA] || "es-ES");
  pie.append(crear("span", null, `Bildumargi · ${estado.biblioteca || ""} · ${fecha}`),
             crear("span", "numero-pagina"));
  return pie;
}

/* Paginación: lo que no cabe en una hoja pasa, bloque a bloque, a una hoja de
   continuación. Se mide ya en el documento, con los tamaños reales de cada
   gráfico y tabla, y al final se numeran todas las hojas. */
function paginarInforme(contenedor) {
  let hoja = contenedor.querySelector(".hoja");
  while (hoja) {
    const cuerpo = hoja.querySelector(".cuerpo-hoja");
    let vueltas = 0;
    while (cuerpo.scrollHeight > cuerpo.clientHeight + 1 && vueltas++ < 12) {
      const bloques = [...cuerpo.children].filter((c) => c.matches(".bloque-informe, table"));
      if (bloques.length <= 1) break;   // un bloque que no cabe ni solo se queda (se recorta)
      let siguiente = hoja.nextElementSibling;
      if (!siguiente || !siguiente.classList.contains("continuacion")) {
        siguiente = nuevaHoja();
        siguiente.classList.add("continuacion");
        siguiente.appendChild(pieHoja());
        hoja.after(siguiente);
      }
      siguiente.querySelector(".cuerpo-hoja").prepend(bloques[bloques.length - 1]);
    }
    hoja = hoja.nextElementSibling;
  }
  const todas = [...contenedor.querySelectorAll(".hoja")];
  todas.forEach((h, i) => {
    h.querySelector(".numero-pagina").textContent = t("pagina_n", { a: i + 1, b: todas.length });
  });
}

function nuevaHoja(titulo, subtitulo) {
  const hoja = crear("section", "hoja");
  const cuerpo = crear("div", "cuerpo-hoja");
  if (titulo) {
    const cab = crear("header", "cabeza-seccion-informe");
    cab.appendChild(crear("h2", null, titulo));
    if (subtitulo) cab.appendChild(crear("p", null, subtitulo));
    cuerpo.appendChild(cab);
  }
  hoja.appendChild(cuerpo);
  return hoja;
}

function bloqueInforme(titulo, subtitulo) {
  const bloque = crear("div", "bloque-informe");
  bloque.appendChild(crear("h3", null, titulo));
  if (subtitulo) bloque.appendChild(crear("p", "sub-informe", subtitulo));
  return bloque;
}

/* --- Hoja 1: indicadores, lectura y peso/uso por sección ------------------- */
function hojaResumen(a) {
  const hoja = nuevaHoja();
  const cuerpo = hoja.querySelector(".cuerpo-hoja");
  const m = a.metricas || {};

  const portada = crear("header", "portada-informe");
  const logo = crear("img");
  logo.src = "imagenes/completo.svg";
  logo.alt = "Bildumargi";
  const textos = crear("div");
  textos.appendChild(crear("p", "antetitulo", t("informe_titulo")));
  textos.appendChild(crear("h1", null, estado.biblioteca || ""));
  const datosBib = [];
  if (m.poblacion) datosBib.push(`${miles(m.poblacion)} ${t("habitantes")}`);
  if (estado.config.nombre_red) datosBib.push(estado.config.nombre_red);
  datosBib.push(t("informe_fondo_completo"));
  textos.appendChild(crear("p", "datos-portada", datosBib.join(" · ")));
  portada.append(textos, logo);
  cuerpo.appendChild(portada);

  const kpis = crear("div", "kpis-informe");
  const huecos = Array.from({ length: 5 }, () => crear("div"));
  huecos.forEach((h) => kpis.appendChild(h));
  pintarIndicadores(huecos, a);
  cuerpo.appendChild(kpis);

  const rx = bloqueInforme(t("radiografia"));
  const lista = crear("ul", "radiografia");
  radiografiaTextos(a).forEach(({ texto, tono }) => { const li = crear("li", tono || ""); li.textContent = texto; lista.appendChild(li); });
  rx.appendChild(lista);
  cuerpo.appendChild(rx);

  if (a.secciones.length && a.tasaGlobal) {
    const rend = bloqueInforme(t("rend_titulo"), t("rend_sub"));
    const filas = Math.min(a.secciones.length, 18);
    rend.appendChild(graficoRendimiento(a.secciones, {
      ancho: ANCHO_INFORME, alto: 30 + filas * 21, tasaGlobal: a.tasaGlobal, minimo: MINIMO_FIABLE,
      textos: {
        titulo: t("rend_titulo"), seccion: t("rend_seccion"), peso: t("rend_peso"), uso: t("rend_uso"),
        otras: (n) => t("rend_otras", { n }),
        detalle: (f) => f.etiqueta,
      },
    }));
    rend.appendChild(crear("p", "nota-pie", t("rend_pie_informe", { m: MINIMO_FIABLE })));
    cuerpo.appendChild(rend);
  }
  return hoja;
}

/* --- Hoja 2: tabla de secciones y años de edición -------------------------- */
function hojaSecciones(a, datos) {
  const hoja = nuevaHoja(t("informe_secciones"), t("informe_secciones_sub"));
  const cuerpo = hoja.querySelector(".cuerpo-hoja");
  const perfil = Object.fromEntries((datos.perfil_secciones || []).map((p) => [p.clave, p]));
  const tabla = crear("table", "tabla-informe");
  const cab = crear("tr");
  [t("rend_seccion"), t("col_volumenes"), t("col_porcentaje"), t("col_rotacion"), t("col_uso_rel"),
   t("col_anio_medio"), t("col_recientes")].forEach((c, i) => {
    const th = crear("th", i ? "num" : "", c);
    cab.appendChild(th);
  });
  const thead = crear("thead"); thead.appendChild(cab); tabla.appendChild(thead);
  const tbody = crear("tbody");
  const porClave = Object.fromEntries(datos.categorias_lista.map((f) => [f.clave, f]));
  a.secciones.forEach((s) => {
    const f = porClave[s.clave] || {};
    const p = perfil[s.clave];
    const tr = crear("tr", s.volumenes < MINIMO_FIABLE ? "pequena" : "");
    const uso = s.usoRel === null ? "—" : `${s.usoRel >= 1 ? "▲" : "▼"} ${formatoUso(s.usoRel)}`;
    [s.etiqueta, miles(s.volumenes), pct(s.peso), pct(s.tasa * 100), uso, f.anio_medio ?? "—",
     p && p.con_anio ? pct((p.recientes / p.con_anio) * 100) : "—"].forEach((v, i) => {
      const td = crear("td", i ? "num" : "", String(v));
      if (i === 4 && s.usoRel !== null) td.classList.add(s.usoRel >= 1 ? "encima" : "debajo");
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  tabla.appendChild(tbody);
  cuerpo.appendChild(tabla);

  if (a.anios.filas.length) {
    const b = bloqueInforme(t("anios_uso_titulo"), t("anios_uso_sub"));
    const puntos = a.anios.filas.map((f) => ({ anio: f.clave, volumenes: f.volumenes, tasa: f.rotacion, detalle: "" }));
    b.appendChild(graficoAniosUso(puntos, { ancho: ANCHO_INFORME, alto: 190, titulo: t("anios_uso_titulo") }));
    b.appendChild(leyendaGradiente(t("col_rotacion")));
    cuerpo.appendChild(b);
  }
  return hoja;
}

/* --- Hoja 3: prioridades de compra (solo con base de la red) -------------- */
function hojaCompra(pc, compra) {
  const hoja = nuevaHoja(t("informe_compra"), t("informe_compra_sub"));
  const cuerpo = hoja.querySelector(".cuerpo-hoja");
  const b = bloqueInforme(t("matriz_titulo"), t("matriz_sub"));
  b.appendChild(graficoMatrizCompra(pc.puntos, {
    ancho: ANCHO_INFORME, alto: 280, corteX: pc.corteX,
    textos: { titulo: t("matriz_titulo"), cuadrante: t("matriz_cuadrante"), ejeX: t("matriz_eje_x"),
              mediana: t("matriz_mediana", { v: pct(pc.corteX) }), detalle: (p) => p.etiqueta },
  }));
  cuerpo.appendChild(b);

  const prioritarias = pc.prioritarias.slice().sort((x, y) => y.y - x.y);
  const bloqueTitulos = bloqueInforme(t("informe_titulos"),
    prioritarias.length ? t("informe_titulos_sub") : t("informe_sin_prioritarias"));
  const tabla = crear("table", "tabla-informe");
  const cab = crear("tr");
  [t("col_titulo"), t("col_autor"), t("col_anio"), t("col_seccion"), t("col_red")].forEach((c, i) =>
    cab.appendChild(crear("th", i >= 2 && i !== 3 ? "num" : "", c)));
  const thead = crear("thead"); thead.appendChild(cab); tabla.appendChild(thead);
  const tbody = crear("tbody");
  const elegidos = prioritarias.length
    ? prioritarias.flatMap((p) => compra.filas.filter((f) => f.seccion === p.clave).slice(0, 4))
    : compra.filas.slice(0, 14);
  elegidos.slice(0, 16).forEach((f) => {
    const tr = crear("tr");
    [f.titulo || "—", f.autor || "", f.anio || "", traducirEtiqueta(f.seccion || ""),
     miles(f.n_bibliotecas)].forEach((v, i) => tr.appendChild(crear("td", i >= 2 && i !== 3 ? "num" : "", String(v))));
    tbody.appendChild(tr);
  });
  tabla.appendChild(tbody);
  bloqueTitulos.appendChild(tabla);
  if (prioritarias.length) {
    bloqueTitulos.appendChild(crear("p", "nota-pie", t("informe_prioritarias_lista", {
      s: prioritarias.map((p) => `${p.etiqueta} (${formatoUso(p.y)})`).join(" · ") })));
  }
  cuerpo.appendChild(bloqueTitulos);
  return hoja;
}

function notasInforme(a) {
  const b = bloqueInforme(t("informe_notas"));
  b.classList.add("notas-informe");
  const ol = crear("ol");
  const pauta = a.metricas && a.metricas.pauta;
  [t("nota_uso"), t("nota_prestamo"), t("nota_edicion"),
   pauta ? t("nota_pauta", { f: pauta.fuente }) : null, t("nota_decisiones")]
    .filter(Boolean).forEach((n) => ol.appendChild(crear("li", null, n)));
  b.appendChild(ol);
  return b;
}

/* ==========================================================================
   Administración de la red
   Lo que decide la red para todas las bibliotecas. Se entra con la clave de
   config.py (CLAVE_ADMIN); el acceso dura dos horas.
   ========================================================================== */
async function abrirAdministracion() {
  const contenido = crear("div", "config admin");
  const cerrar = abrirModal(t("admin_titulo"), contenido);

  const pintarEntrada = (error) => {
    contenido.innerHTML = "";
    contenido.appendChild(crear("p", "ayuda-config", t("admin_intro")));
    const campo = crear("label", "campo");
    const entrada = crear("input");
    entrada.type = "password";
    entrada.autocomplete = "current-password";
    campo.append(crear("span", "rotulo-campo", t("admin_clave")), entrada);
    contenido.appendChild(campo);
    if (error) contenido.appendChild(aviso("error", error));
    // No hay recuperación de clave por correo (haría falta un servidor de
    // correo que mantener): si se olvida, la administración pone otra.
    contenido.appendChild(crear("p", "ayuda-config", t("admin_olvido")));
    const pie = crear("div", "pie-config");
    const entrar = crear("button", "boton", t("admin_entrar"));
    const cancelar = crear("button", "boton secundario", t("cancelar"));
    cancelar.addEventListener("click", cerrar);
    pie.append(cancelar, entrar);
    contenido.appendChild(pie);
    const enviar = async () => {
      entrar.disabled = true;
      try {
        const r = await API.adminEntrar(entrada.value);
        estado.tokenAdmin = r.token;
        pintarFormulario(r.configuracion);
      } catch (e) { pintarEntrada(e.message); }
    };
    entrar.addEventListener("click", enviar);
    entrada.addEventListener("keydown", (e) => { if (e.key === "Enter") enviar(); });
    entrada.focus();
  };

  const pintarFormulario = (conf) => {
    contenido.innerHTML = "";
    const borrador = JSON.parse(JSON.stringify(conf));
    contenido.appendChild(crear("p", "ayuda-config", t("admin_ayuda")));

    const grupoCasillas = (leyenda, ayuda, opciones, lista) => {
      const fs = crear("fieldset");
      fs.appendChild(crear("legend", null, leyenda));
      if (ayuda) fs.appendChild(crear("p", "ayuda-config", ayuda));
      const caja = crear("div", "lista-pestanas");
      opciones.forEach(([valor, etiqueta]) => {
        const l = crear("label");
        const c = crear("input");
        c.type = "checkbox";
        c.checked = borrador[lista].includes(valor);
        c.addEventListener("change", () => {
          const s = new Set(borrador[lista]);
          if (c.checked) s.add(valor); else s.delete(valor);
          borrador[lista] = opciones.map(([v]) => v).filter((v) => s.has(v));
        });
        l.append(c, document.createTextNode(etiqueta));
        caja.appendChild(l);
      });
      fs.appendChild(caja);
      return fs;
    };
    contenido.appendChild(grupoCasillas(t("admin_pestanas"), t("admin_pestanas_ayuda"),
      [["diagnostico", t("nav_diagnostico")], ["secciones", t("nav_secciones")], ["compras", t("nav_compras")],
       ["red", t("nav_red")], ["seguimiento", t("nav_seguimiento")]], "pestanas_activas"));
    contenido.appendChild(grupoCasillas(t("admin_idiomas"), null,
      IDIOMAS_INTERFAZ.map((i) => [i.codigo, i.nombre]), "idiomas"));

    // Apariencia y lengua por defecto para las bibliotecas que no elijan otra
    const fsDef = crear("fieldset");
    fsDef.appendChild(crear("legend", null, t("admin_defecto")));
    fsDef.appendChild(crear("p", "ayuda-config", t("admin_defecto_ayuda")));
    const fila = crear("div", "fila-admin");
    fila.appendChild(selector(t("config_idioma"), [{ valor: "", etiqueta: t("admin_idioma_instalacion") },
      ...IDIOMAS_INTERFAZ.map((i) => ({ valor: i.codigo, etiqueta: i.nombre }))],
      borrador.idioma_defecto || "", (v) => { borrador.idioma_defecto = v || null; }));
    fila.appendChild(selector(t("config_tema"), [{ valor: "oscuro", etiqueta: t("tema_oscuro") },
      { valor: "claro", etiqueta: t("tema_claro") }], borrador.tema_defecto, (v) => { borrador.tema_defecto = v; }));
    fila.appendChild(selector(t("config_paleta"), ["okabe", "viridis", "azules"].map((p) => ({ valor: p, etiqueta: t(`paleta_${p}`) })),
      borrador.paleta_defecto, (v) => { borrador.paleta_defecto = v; }));
    fsDef.appendChild(fila);
    contenido.appendChild(fsDef);

    // Historial de cargas
    const fsHist = crear("fieldset");
    fsHist.appendChild(crear("legend", null, t("admin_historial")));
    fsHist.appendChild(crear("p", "ayuda-config", t("admin_historial_ayuda")));
    const filaH = crear("div", "fila-admin");
    filaH.appendChild(casilla(t("admin_historial_activo"), borrador.historial, (v) => { borrador.historial = v; }));
    filaH.appendChild(entradaNumero(t("admin_max_cargas"), borrador.max_cargas,
      (v) => { borrador.max_cargas = v; }, { min: 1, max: 60 }));
    fsHist.appendChild(filaH);
    contenido.appendChild(fsHist);

    // --- Secciones por signatura de la red
    const fsSig = crear("fieldset");
    fsSig.appendChild(crear("legend", null, t("sig_titulo")));
    fsSig.appendChild(crear("p", "ayuda-config", t("sig_admin_ayuda")));
    const defecto = (estado.config && estado.config.signaturas_defecto) || [];
    const editorRed = editorSignaturas(borrador.signaturas || defecto, defecto, t("sig_restaurar"));
    fsSig.appendChild(editorRed.nodo);
    contenido.appendChild(fsSig);

    // --- Novedades de DILVE
    contenido.appendChild(seccionDilve(borrador));

    const mensajes = crear("div");
    const pie = crear("div", "pie-config");
    pie.appendChild(crear("span", "donde", t("admin_donde")));
    const cancelar = crear("button", "boton secundario", t("cancelar"));
    const guardar = crear("button", "boton", t("guardar"));
    cancelar.addEventListener("click", cerrar);
    pie.append(cancelar, guardar);
    contenido.append(mensajes, pie);
    guardar.addEventListener("click", async () => {
      mensajes.innerHTML = "";
      if (!borrador.pestanas_activas.length) { mensajes.appendChild(aviso("error", t("config_una_pestana"))); return; }
      if (!borrador.idiomas.length) { mensajes.appendChild(aviso("error", t("admin_un_idioma"))); return; }
      guardar.disabled = true;
      // Igual que la estándar = sin tabla propia de la red
      const tablaRed = editorRed.leer();
      borrador.signaturas = JSON.stringify(tablaRed) === JSON.stringify(normalizarFilas(defecto)) ? null : tablaRed;
      try {
        const r = await API.adminGuardar(estado.tokenAdmin, borrador);
        estado.config.red = r.configuracion;
        cerrar();
        aplicarConfiguracionRed();
      } catch (e) {
        guardar.disabled = false;
        if (e.estado === 403) { estado.tokenAdmin = null; pintarEntrada(e.message); return; }
        mensajes.appendChild(aviso("error", e.message));
      }
    });
  };

  pintarEntrada();
}

/* --- Novedades de DILVE dentro de la administración ------------------------
   Las credenciales y las descargas van por su propio endpoint: la
   configuración (qué idiomas, cada cuántos días) viaja con el resto. */
function seccionDilve(borrador) {
  const fs = crear("fieldset", "fieldset-dilve");
  fs.appendChild(crear("legend", null, t("dilve_titulo")));
  fs.appendChild(crear("p", "ayuda-config", t("dilve_ayuda")));
  const d = borrador.dilve;

  const opciones = crear("div", "fila-admin");
  opciones.appendChild(casilla(t("dilve_activo"), d.activo, (v) => { d.activo = v; }));
  opciones.appendChild(casilla(t("dilve_descarga_inicial"), d.descarga_inicial, (v) => { d.descarga_inicial = v; }));
  opciones.appendChild(casilla(t("dilve_solo_libros"), d.solo_libros, (v) => { d.solo_libros = v; }));
  opciones.appendChild(entradaNumero(t("dilve_meses"), d.meses_novedades, (v) => { d.meses_novedades = v; }, { min: 1, max: 12 }));
  opciones.appendChild(entradaNumero(t("dilve_cada"), d.cada_dias, (v) => { d.cada_dias = v; }, { min: 1, max: 90 }));
  opciones.appendChild(entradaNumero(t("dilve_max_llamadas"), d.max_llamadas_dia ?? 300,
    (v) => { d.max_llamadas_dia = v; }, { min: 20, max: 5000 }));
  opciones.appendChild(entradaNumero(t("dilve_pausa"), d.pausa_llamadas ?? 6,
    (v) => { d.pausa_llamadas = v; }, { min: 6, max: 60, paso: 1 }));
  fs.appendChild(opciones);
  fs.appendChild(crear("p", "ayuda-config", t("dilve_ventana_ayuda")));

  const caja = crear("div", "estado-dilve");
  fs.appendChild(caja);
  // Se pinta cuando el panel ya está en la página: el estado se pide al
  // servidor y la función se detiene si su caja no está insertada.
  setTimeout(() => pintarEstadoDilve(caja), 0);
  return fs;
}

let refrescoDilve = null;

async function pintarEstadoDilve(caja) {
  clearTimeout(refrescoDilve);
  if (!caja.isConnected) return;
  let datos;
  try { datos = await API.adminDilve(estado.tokenAdmin); }
  catch (e) { caja.replaceChildren(aviso("atencion", e.message)); return; }
  caja.innerHTML = "";

  // Credenciales: del entorno (no se tocan) o guardadas desde aquí
  const cred = datos.credenciales;
  if (cred.origen === "entorno") {
    caja.appendChild(crear("p", "ayuda-config", t("dilve_cred_entorno", { u: cred.usuario })));
  } else {
    const fila = crear("div", "fila-admin");
    const usuario = crear("input");
    usuario.type = "text";
    usuario.value = cred.usuario || "";
    usuario.autocomplete = "off";
    const clave = crear("input");
    clave.type = "password";
    clave.autocomplete = "new-password";
    const campoU = crear("label", "campo");
    campoU.append(crear("span", "rotulo-campo", t("dilve_usuario")), usuario);
    const campoC = crear("label", "campo");
    campoC.append(crear("span", "rotulo-campo", t("dilve_clave")), clave);
    const guardar = crear("button", "boton secundario", t("dilve_guardar_cred"));
    guardar.type = "button";
    guardar.addEventListener("click", async () => {
      guardar.disabled = true;
      try {
        await API.adminDilveCredenciales(estado.tokenAdmin, usuario.value, clave.value);
        pintarEstadoDilve(caja);
      } catch (e) {
        guardar.disabled = false;
        caja.appendChild(aviso("error", e.message));
      }
    });
    fila.append(campoU, campoC, guardar);
    caja.appendChild(fila);
    caja.appendChild(crear("p", "ayuda-config", t("dilve_cred_ayuda")));
  }

  // Estado de la base y de la descarga
  const b = datos.base;
  const resumen = crear("div", "resumen-dilve");
  resumen.appendChild(crear("span", null, t("dilve_base", { r: b.ruta })));
  resumen.appendChild(crear("strong", null, t("dilve_registros", { n: miles(b.registros || 0) })));
  if (b.registros) {
    resumen.appendChild(crear("span", null, t("dilve_periodo", { a: b.desde || "—", b: b.hasta || "—" })));
    resumen.appendChild(crear("span", null, t("dilve_cubiertas", { n: miles(b.con_cubierta || 0) })));
  }
  if (b.ultima_sincronizacion) resumen.appendChild(crear("span", null, t("dilve_ultima", { f: b.ultima_sincronizacion })));
  const forma = (datos.tarea.progreso && datos.tarea.progreso.forma) || b.forma_lista;
  if (forma) resumen.appendChild(crear("span", null, t(forma === "uno" ? "dilve_forma_uno" : "dilve_forma_lotes")));
  if (datos.cuota) {
    resumen.appendChild(crear("span", null, t("dilve_llamadas_hoy", {
      n: miles(datos.cuota.hoy || 0), m: miles(datos.cuota.maximo || 0) })));
  }
  if (b.ultimo_resultado) resumen.appendChild(crear("span", "detalle-resumen", b.ultimo_resultado));
  caja.appendChild(resumen);
  if (b.error) caja.appendChild(aviso("error", b.error));
  // Usuario o contraseña rechazados: no se vuelve a llamar con los mismos
  // datos (insistir puede hacer que DILVE bloquee la cuenta). Al cambiar la
  // contraseña, el aviso desaparece solo.
  if (datos.cuota && datos.cuota.credenciales_erroneas) {
    caja.appendChild(aviso("error", t("dilve_credenciales_mal", {
      f: (datos.cuota.credenciales_erroneas.desde || "").slice(0, 10),
      m: datos.cuota.credenciales_erroneas.mensaje || "" })));
  }
  // DILVE denegó el acceso: no se le vuelve a llamar hasta que la red lo
  // desbloquee (después de que asistencia@dilve.es restablezca la cuenta).
  if (datos.cuota && datos.cuota.bloqueo) {
    const bloqueo = crear("div");
    bloqueo.appendChild(aviso("error", t("dilve_bloqueo", {
      f: (datos.cuota.bloqueo.desde || "").slice(0, 10), m: datos.cuota.bloqueo.mensaje || "" })));
    const quitar = crear("button", "boton secundario", t("dilve_desbloquear"));
    quitar.type = "button";
    quitar.addEventListener("click", async () => {
      await API.adminDilveAccion(estado.tokenAdmin, "desbloquear"); pintarEstadoDilve(caja);
    });
    bloqueo.appendChild(quitar);
    caja.appendChild(bloqueo);
  }
  if (datos.tarea.error) caja.appendChild(aviso("atencion", datos.tarea.error));

  const acciones = crear("div", "fila-admin");
  if (datos.tarea.en_curso) {
    const p = datos.tarea.progreso || {};
    caja.appendChild(aviso("info", t("dilve_en_curso", {
      f: datos.tarea.fase === "inicial" ? t("dilve_accion_inicial") : t("dilve_accion_actualizar"),
      v: p.ventana || 1, t: p.ventanas || 1, n: miles(p.guardados || 0) })));
    const parar = crear("button", "boton secundario", t("dilve_parar"));
    parar.type = "button";
    parar.addEventListener("click", async () => { await API.adminDilveAccion(estado.tokenAdmin, "parar"); pintarEstadoDilve(caja); });
    acciones.appendChild(parar);
    refrescoDilve = setTimeout(() => pintarEstadoDilve(caja), 2500);   // sigue el avance
  } else if (cred.hay) {
    [["inicial", t("dilve_accion_inicial")], ["actualizar", t("dilve_accion_actualizar")]].forEach(([accion, texto]) => {
      const b2 = crear("button", "boton secundario", texto);
      b2.type = "button";
      b2.addEventListener("click", async () => {
        b2.disabled = true;
        try { await API.adminDilveAccion(estado.tokenAdmin, accion); } catch (e) { caja.appendChild(aviso("error", e.message)); }
        pintarEstadoDilve(caja);
      });
      acciones.appendChild(b2);
    });
  }
  caja.appendChild(acciones);
}

// Tras cambiar la configuración de la red: idioma, apariencia y pestañas.
function aplicarConfiguracionRed() {
  if (!estado.preferencias._guardadas) {
    estado.preferencias = { ...prefsDefecto(), idioma: null };
    aplicarApariencia(estado.preferencias);
  }
  if (idiomaPreferido() !== IDIOMA) cambiarIdioma(idiomaPreferido());
  if (estado.sesion) {
    pintarNavegador();
    mostrarVista(estado.vista);
  }
}

/* ==========================================================================
   Vista: seguimiento
   Evolución de los indicadores entre cargas y el historial de cargas de la
   biblioteca: se puede reabrir una carga anterior sin volver a subir los
   ficheros, o borrarla.
   ========================================================================== */
const INDICADORES_SEGUIMIENTO = [
  { clave: "volumenes", rotulo: "col_volumenes", formato: (v) => miles(v), color: () => PALETA.cian },
  { clave: "pct_prestamos", rotulo: "m_circulacion", formato: (v) => pct(v), color: () => PALETA.verde, puntos: true },
  { clave: "pct_recientes", rotulo: "diag_actualidad", formato: (v) => pct(v), color: () => PALETA.amarillo, puntos: true },
  { clave: "anio_medio", rotulo: "m_edad", formato: (v) => String(v), color: () => PALETA.violeta },
];

async function vistaSeguimiento(vista) {
  soltarMedidores();
  const datos = await API.historial(estado.sesion);
  vista.innerHTML = "";
  const raiz = crear("div", "panel-secciones panel-seguimiento");
  const rejilla = crear("div", "rejilla-seguimiento");
  raiz.appendChild(rejilla);
  vista.appendChild(raiz);

  const cargas = datos.cargas.slice().reverse();   // de la más antigua a la más reciente
  if (!datos.activo) rejilla.appendChild(aviso("info", t("seg_desactivado")));
  if (datos.error) rejilla.appendChild(aviso("atencion", datos.error));

  // Indicadores: último valor y cambio respecto a la carga anterior
  const ultima = cargas[cargas.length - 1];
  const fila = crear("div", "fila-indicadores fila-seguimiento");
  const conDato = (c, clave) => c && c[clave] !== null && c[clave] !== undefined;
  INDICADORES_SEGUIMIENTO.forEach((ind) => {
    const v = ultima ? ultima[ind.clave] : null;
    // Se compara con la última carga anterior que tenga el dato (una carga
    // sin listado de no prestados no tiene circulación: se salta).
    const previa = cargas.slice(0, -1).reverse().find((c) => conDato(c, ind.clave));
    const p = previa ? previa[ind.clave] : null;
    let contexto = cargas.length < 2 ? t("seg_una_carga") : t("seg_sin_comparar");
    let estadoChip = null;
    if (v !== null && v !== undefined && p !== null && p !== undefined) {
      const d = v - p;
      const unidad = ind.clave.startsWith("pct_") ? t("seg_puntos") : "";
      const texto = `${d > 0 ? "+" : d < 0 ? "−" : "±"}${ind.clave.startsWith("pct_") ? decimal(Math.abs(d), 1) : miles(Math.abs(Math.round(d)))}${unidad}`;
      estadoChip = { nivel: d > 0 ? "alto" : d < 0 ? "abajo" : "info", texto };
      contexto = t("seg_respecto", { f: fechaCorta(previa.fecha) });
    }
    const serie = cargas.map((c) => c[ind.clave]).filter((x) => x !== null && x !== undefined);
    fila.appendChild(tarjetaIndicador({
      rotulo: t(ind.rotulo), valor: v === null || v === undefined ? "—" : ind.formato(v), acento: ind.color(),
      estado: estadoChip, grafico: serie.length > 1 ? minigrafica(serie, ind.color()) : null, contexto,
    }));
  });
  rejilla.appendChild(fila);

  // Evolución: un gráfico pequeño por indicador (small multiples)
  const hueco = crear("div", "hueco zona-evolucion");
  rejilla.appendChild(hueco);
  const cuerpo = cuadroPanel(hueco, t("seg_evolucion"));
  if (cargas.length < 2) {
    cuerpo.appendChild(crear("p", "vacio", t("seg_una_carga_largo")));
  } else {
    const multiples = crear("div", "multiples");
    INDICADORES_SEGUIMIENTO.forEach((ind) => {
      const celda = crear("div", "multiple");
      celda.appendChild(crear("h3", null, t(ind.rotulo)));
      const puntos = cargas.map((c) => ({ fecha: c.fecha, valor: c[ind.clave] }));
      celda.appendChild(grafico((ancho, alto) => graficoEvolucion(puntos, {
        ancho, alto, color: ind.color(), formato: ind.formato, titulo: t(ind.rotulo) }), t(ind.rotulo)));
      multiples.appendChild(celda);
    });
    cuerpo.appendChild(multiples);
    if (cargas.some((c) => c.sin_no_prestados)) cuerpo.appendChild(crear("p", "nota-pie", t("seg_nota_sin_nunca")));
  }

  // Historial de cargas
  const huecoTabla = crear("div", "hueco zona-cargas");
  rejilla.appendChild(huecoTabla);
  pintarTablaCargas(huecoTabla, datos);
}

function pintarTablaCargas(hueco, datos) {
  const cuerpo = cuadroPanel(hueco, t("seg_cargas"),
    t("seg_cargas_sub", { n: datos.max_cargas }));
  if (!datos.cargas.length) { cuerpo.appendChild(crear("p", "vacio", t("seg_sin_cargas"))); return; }
  const tabla = crear("table", "datos tabla-cargas");
  const cab = crear("tr");
  [t("seg_fecha"), t("seg_ficheros"), t("col_volumenes"), t("m_circulacion"), t("col_recientes"), ""].forEach((c, i) =>
    cab.appendChild(crear("th", i >= 2 && i <= 4 ? "num" : "", c)));
  const thead = crear("thead"); thead.appendChild(cab); tabla.appendChild(thead);
  const tbody = crear("tbody");
  datos.cargas.forEach((c) => {
    const tr = crear("tr", c.id === estado.carga ? "activa" : "");
    const fecha = crear("td");
    fecha.appendChild(crear("span", null, new Date(c.fecha).toLocaleString(LOCALE_FECHAS[IDIOMA] || "es-ES",
      { dateStyle: "medium", timeStyle: "short" })));
    if (c.id === estado.carga) fecha.appendChild(distintivo(t("seg_en_pantalla"), "info"));
    tr.appendChild(fecha);
    const tipos = Object.keys(c.ficheros || {});
    const fich = crear("td", "ficheros-carga", tipos.map((tp) => t(HUECOS.find((h) => h.clave === tp)?.etiqueta || tp)).join(" · "));
    fich.title = Object.values(c.ficheros || {}).flat().join("\n");
    tr.appendChild(fich);
    tr.appendChild(crear("td", "num", miles(c.volumenes)));
    tr.appendChild(crear("td", "num", c.pct_prestamos === null || c.pct_prestamos === undefined ? t("seg_sin_dato_prestamo") : pct(c.pct_prestamos)));
    tr.appendChild(crear("td", "num", c.pct_recientes === null || c.pct_recientes === undefined ? "—" : pct(c.pct_recientes)));
    const acciones = crear("td", "acciones-carga");
    if (c.id !== estado.carga) {
      const abrir = crear("button", "boton secundario pequeno", t("seg_abrir"));
      abrir.addEventListener("click", async () => {
        abrir.disabled = true;
        try {
          const r = await API.abrirCarga(estado.sesion, c.id);
          await entrarEnAnalisis(r, { fecha: c.fecha, anterior: c.id !== datos.cargas[0].id });
        } catch (e) { hueco.querySelector(".cuerpo-cuadro").prepend(aviso("error", e.message)); abrir.disabled = false; }
      });
      const borrar = crear("button", "enlace-discreto", t("borrar"));
      borrar.addEventListener("click", async () => {
        if (!window.confirm(t("seg_confirmar_borrar"))) return;
        await API.borrarCarga(estado.sesion, c.id);
        mostrarVista("seguimiento");
      });
      acciones.append(abrir, borrar);
    }
    tr.appendChild(acciones);
    tbody.appendChild(tr);
  });
  tabla.appendChild(tbody);
  const caja = crear("div", "tabla-desplazable");
  const envoltorio = crear("div", "envoltorio-tabla");
  envoltorio.appendChild(tabla);
  caja.appendChild(envoltorio);
  cuerpo.appendChild(caja);
}

/* ==========================================================================
   Arranque
   ========================================================================== */
function pintarPastillaBase() {
  const pastilla = $("#pastilla-base");
  const activa = estado.config.recomendaciones_activas;
  pastilla.innerHTML = "";
  const punto = crear("span", activa ? "punto" : "punto apagado");
  pastilla.append(punto, document.createTextNode(activa ? t("base_conectada") : t("base_sin_enlazar")));
  pastilla.title = activa ? "" : (estado.config.base_datos.error || "");
}

function pintarAvisosDeArranque() {
  const avisos = $("#avisos-globales");
  avisos.innerHTML = "";
  const cfg = estado.config;
  if (cfg.directorio.error) {
    avisos.appendChild(aviso("error", `${t("directorio_error")}: ${cfg.directorio.error}`));
  } else if (cfg.directorio.avisos.length) {
    avisos.appendChild(aviso("atencion", "", cfg.directorio.avisos));
  }
  if (!cfg.recomendaciones_activas) {
    const detalle = cfg.base_datos.error ? ` (${cfg.base_datos.error})` : "";
    avisos.appendChild(aviso("info", t("recomendaciones_ocultas") + detalle));
  }
}

function idiomasPermitidos() {
  const red = configRed().idiomas;
  const lista = IDIOMAS_INTERFAZ.filter((i) => !red || red.includes(i.codigo));
  return lista.length ? lista : IDIOMAS_INTERFAZ;
}

function idiomaPreferido() {
  const permitidos = idiomasPermitidos().map((i) => i.codigo);
  const candidatos = [estado.preferencias && estado.preferencias.idioma, configRed().idioma_defecto,
                      estado.config && estado.config.idioma];
  return candidatos.find((c) => c && permitidos.includes(c)) || permitidos[0];
}

// Traduce todo lo que está fuera de las vistas (cabecera, pasos de carga,
// avisos). cambiarIdioma, además, vuelve a pintar la vista abierta.
function aplicarIdioma(codigo) {
  fijarIdioma(codigo);
  traducirPlantilla();
  rotularBotonConfiguracion();
  if (estado.config) pintarPastillaBase();
  if (estado.sesion && estado.identidad) pintarIdentidad(estado.identidad);
  pintarPasos();
  pintarAccesoClave();
  actualizarBotonAnalizar();
  pintarAvisosDeArranque();
}

function cambiarIdioma(codigo) {
  aplicarIdioma(codigo);
  if (estado.sesion) {
    pintarNavegador();
    mostrarVista(estado.vista);
  }
}

async function iniciar() {
  // Tema y paleta antes de pintar nada: así no hay un destello del tema
  // oscuro en un navegador configurado en claro.
  estado.preferencias = preferenciasLocales();
  aplicarApariencia(estado.preferencias);
  try { estado.menuPlegado = localStorage.getItem("bildumargi.menu") === "1"; } catch { /* sin almacenamiento */ }
  document.body.classList.toggle("menu-plegado", estado.menuPlegado);
  try {
    estado.config = await API.config();
    Object.assign(ETIQUETAS_SERVIDOR.eu, estado.config.nombres_idioma_eu || {});
  } catch (e) {
    document.body.innerHTML = `<p style="padding:2rem">${escapar(t("error_generico"))}</p>`;
    return;
  }
  if (!estado.preferencias._guardadas) {
    estado.preferencias = { ...prefsDefecto() };
    aplicarApariencia(estado.preferencias);
  }
  fijarIdioma(idiomaPreferido());
  traducirPlantilla();
  montarBotonConfiguracion();

  $("#nombre-red").textContent = estado.config.nombre_red || "";
  if (estado.config.licencia) $("#enlace-licencia").textContent = estado.config.licencia;
  // La AGPLv3 exige ofrecer el código a quien usa el programa por red.
  if (estado.config.url_codigo) $("#enlace-codigo").href = estado.config.url_codigo;
  pintarPastillaBase();
  if (estado.config.autoria) {
    $("#autoria").innerHTML = escapar(estado.config.autoria)
      .replace("bildumargi@gmail.com", '<a href="mailto:bildumargi@gmail.com">bildumargi@gmail.com</a>');
  }

  $("#btn-reiniciar").addEventListener("click", reiniciar);
  $("#btn-informe").addEventListener("click", abrirInforme);

  pintarPasos();
  actualizarBotonAnalizar();
  pintarAvisosDeArranque();
  cambiarIdioma(idiomaPreferido());
}

document.addEventListener("DOMContentLoaded", iniciar);


/* ==========================================================================
   Grabación de la demo y modo demostración
   ========================================================================== */
const esperar = (ms) => new Promise((r) => setTimeout(r, ms));

/** Espera a que no quede ninguna petición en curso durante medio segundo. */
async function esperarQuieto(maximo = 60000) {
  const inicio = Date.now();
  let quieto = 0;
  while (Date.now() - inicio < maximo) {
    await esperar(100);
    quieto = PETICIONES_EN_CURSO === 0 ? quieto + 100 : 0;
    if (quieto >= 500) return;
  }
}

/** Espera a que «Autores más prestados» termine de calcular (consulta DILVE). */
async function esperarAutores(maximo = 600000) {
  const inicio = Date.now();
  while (Date.now() - inicio < maximo) {
    const clave = Object.keys(GRABACION).find((k) => k.startsWith("GET /api/sesion/S/sugerencias/autores"));
    if (clave && GRABACION[clave] && !GRABACION[clave].en_curso) return;
    await esperar(1000);
  }
}

function ultimaGrabada(prefijo, condicion = () => true) {
  const claves = Object.keys(GRABACION).filter((k) => k.startsWith(prefijo) && condicion(GRABACION[k]));
  return claves.length ? GRABACION[claves[claves.length - 1]] : null;
}

let panelGrabacion = null;

function actualizarPanelGrabacion(texto) {
  if (!panelGrabacion) return;
  panelGrabacion.querySelector(".cuenta-grabacion").textContent =
    t("grab_cuenta", { n: miles(Object.keys(GRABACION).length) });
  if (texto !== undefined) panelGrabacion.querySelector(".estado-grabacion").textContent = texto;
}

function descargarGrabacion() {
  const contenido = JSON.stringify({
    formato: "bildumargi-grabacion", version: 1, fecha: new Date().toISOString(),
    biblioteca: estado.biblioteca || null, datos: GRABACION,
  });
  const enlace = crear("a");
  enlace.href = URL.createObjectURL(new Blob([contenido], { type: "application/json" }));
  enlace.download = "bildumargi-grabacion.json";
  document.body.appendChild(enlace);
  enlace.click();
  setTimeout(() => { URL.revokeObjectURL(enlace.href); enlace.remove(); }, 1000);
}

/** Recorre solo la aplicación pidiendo lo que el jefe podría pulsar: cada
    pestaña, cada sección, cada fuente de sugerencias con cada filtro y las
    fichas de los títulos que aparecen. Todo queda grabado. */
async function recorridoAutomatico() {
  if (!estado.sesion) { actualizarPanelGrabacion(t("grab_primero_analiza")); return; }
  const paso = async (texto, accion) => {
    actualizarPanelGrabacion(texto);
    await accion();
    await esperarQuieto();
  };
  const disponibles = seccionesDisponibles().map((x) => x.clave);
  const vistas = ["diagnostico", "secciones", "compras", "red", "seguimiento"];
  for (const v of vistas) {
    if (!disponibles.includes(v)) continue;
    await paso(t("grab_vista", { v }), () => mostrarVista(v));
  }

  // --- Secciones: cada categoría, cada localización, cada filtro de préstamo y cada orden
  if (disponibles.includes("secciones")) {
    const c = estado.controles.secciones;
    const base = ultimaGrabada("GET /api/sesion/S/buscar", (d) => d && d.categorias_lista);
    const categorias = (base?.categorias_lista || []).map((f) => f.clave);
    const localizaciones = (base?.localizaciones || []).map((f) => f.clave);
    for (const cat of categorias) {
      await paso(t("grab_seccion", { s: cat }), () => { Object.assign(c, { categoria: cat, pagina: 1 }); return mostrarVista("secciones"); });
    }
    c.categoria = "";
    for (const loc of localizaciones) {
      await paso(t("grab_seccion", { s: loc }), () => { Object.assign(c, { loc, pagina: 1 }); return mostrarVista("secciones"); });
    }
    c.loc = "__TODAS__";
    for (const prestamos of ["nunca", "estandar", "alta"]) {
      await paso(t("grab_seccion", { s: prestamos }), () => { Object.assign(c, { prestamos, pagina: 1 }); return mostrarVista("secciones"); });
    }
    c.prestamos = "todos";
    for (const orden of ["signatura_real", "titulo", "autor", "year", "prestamos", "loc"]) {
      for (const desc of [false, true]) {
        await paso(t("grab_seccion", { s: orden }), () => { Object.assign(c, { orden, desc, pagina: 1 }); return mostrarVista("secciones"); });
      }
    }
    // …y dentro de las ocho secciones con más volúmenes
    for (const cat of categorias.slice(0, 8)) {
      for (const orden of ["titulo", "autor", "year", "prestamos"]) {
        for (const desc of [false, true]) {
          await paso(t("grab_seccion", { s: `${cat} · ${orden}` }), () => {
            Object.assign(c, { categoria: cat, orden, desc, pagina: 1 }); return mostrarVista("secciones"); });
        }
      }
    }
    Object.assign(c, { categoria: "", orden: null, desc: false, pagina: 1 });
  }

  // --- Sugerencias de compra: las tres fuentes con sus filtros
  if (disponibles.includes("compras")) {
    const c = estado.controles.compras;
    for (const fuente of fuentesCompra().map((f) => f.clave)) {
      c.fuente = fuente;
      c.seccion = "";
      await paso(t("grab_fuente", { f: fuente }), () => mostrarVista("compras"));
      if (fuente === "presencia") {
        const panel = ultimaGrabada("GET /api/sesion/S/recomendaciones/panel");
        const claves = panel ? prepararCompras(panel).puntos.map((p) => p.clave) : [];
        for (const seccion of claves) {
          await paso(t("grab_fuente", { f: seccion }), () => { c.seccion = seccion; return mostrarVista("compras"); });
        }
        c.seccion = "";
      }
      if (fuente === "autores") {
        await esperarAutores();
        await paso(t("grab_fuente", { f: fuente }), () => mostrarVista("compras"));
        const grupos = [["aut_idioma", c.idiomas_autores], ["aut_seccion", c.secciones_autores], ["aut_tramo", c.edades_autores]];
        for (const [campo, valores] of grupos) {
          for (const valor of Object.keys(valores || {})) {
            await paso(t("grab_fuente", { f: valor }), () => { c[campo] = valor; return mostrarVista("compras"); });
          }
          c[campo] = "";
        }
      }
      if (fuente === "novedades") {
        const facetas = c.facetas || {};
        const grupos = [["nov_seccion", facetas.seccion], ["nov_idioma", facetas.idioma],
                        ["nov_forma", facetas.forma], ["nov_editorial", facetas.editorial]];
        for (const [campo, valores] of grupos) {
          // Las editoriales pueden ser cientos: se graban las 20 con más títulos
          const lista = Object.keys(valores || {}).slice(0, campo === "nov_editorial" ? 20 : 60);
          for (const valor of lista) {
            await paso(t("grab_fuente", { f: valor }), () => { c[campo] = valor; return mostrarVista("compras"); });
          }
          c[campo] = "";
        }
        await paso(t("grab_fuente", { f: "personalizadas" }), () => { c.personalizadas = true; return mostrarVista("compras"); });
        c.personalizadas = false;
      }
    }
    c.fuente = "presencia";
  }

  // --- Fichas de los títulos que han aparecido (catálogo propio y red)
  const ids = new Set(), sistemas = new Set();
  const recorrer = (v) => {
    if (Array.isArray(v)) v.forEach(recorrer);
    else if (v && typeof v === "object") {
      if (v.record_id != null) ids.add(v.record_id);
      if (v.id_sistema != null) sistemas.add(String(v.id_sistema));
      // «todas» es la lista completa para el CSV: sus fichas no se ven en pantalla
      Object.entries(v).forEach(([k, x]) => { if (k !== "todas") recorrer(x); });
    }
  };
  recorrer(Object.values(GRABACION));
  let n = 0;
  for (const id of [...ids].slice(0, 400)) {
    await API.ficha(estado.sesion, id).catch(() => null);
    if (++n % 25 === 0) actualizarPanelGrabacion(t("grab_fichas", { n }));
  }
  for (const id of [...sistemas].slice(0, 300)) {
    await API.fichaRed(id).catch(() => null);
    await API.valoraciones(estado.sesion, id).catch(() => null);
    if (++n % 25 === 0) actualizarPanelGrabacion(t("grab_fichas", { n }));
  }
  await paso(t("grab_vista", { v: "diagnostico" }), () => mostrarVista("diagnostico"));
  actualizarPanelGrabacion(t("grab_terminado"));
}

function montarPanelGrabacion() {
  panelGrabacion = crear("div", "panel-grabacion");
  panelGrabacion.setAttribute("role", "status");
  const cabecera = crear("div", "cabecera-grabacion");
  cabecera.append(crear("span", "punto-grabacion"), crear("strong", null, t("grab_titulo")),
                  crear("span", "cuenta-grabacion"));
  panelGrabacion.appendChild(cabecera);
  panelGrabacion.appendChild(crear("p", "estado-grabacion", t("grab_ayuda")));
  const botones = crear("div", "botones-grabacion");
  const recorrer = crear("button", "boton secundario", t("grab_recorrer"));
  recorrer.type = "button";
  recorrer.addEventListener("click", async () => {
    recorrer.disabled = true;
    try { await recorridoAutomatico(); } finally { recorrer.disabled = false; }
  });
  const descargar = crear("button", "boton", t("grab_descargar"));
  descargar.type = "button";
  descargar.addEventListener("click", descargarGrabacion);
  const terminar = crear("button", "boton secundario", t("grab_terminar"));
  terminar.type = "button";
  terminar.addEventListener("click", () => {
    try { sessionStorage.removeItem("bildumargi.grabar"); } catch { /* sin almacenamiento */ }
    location.href = location.pathname;
  });
  botones.append(recorrer, descargar, terminar);
  panelGrabacion.appendChild(botones);
  document.body.appendChild(panelGrabacion);
  actualizarPanelGrabacion();
}

function montarAvisoDemo() {
  const aviso = crear("div", "aviso-demo", t("demo_banner"));
  aviso.setAttribute("role", "note");
  document.body.appendChild(aviso);
  document.body.classList.add("con-aviso-demo");
}

document.addEventListener("DOMContentLoaded", () => {
  if (MODO_DEMO) montarAvisoDemo();
  if (GRABANDO) montarPanelGrabacion();
});
