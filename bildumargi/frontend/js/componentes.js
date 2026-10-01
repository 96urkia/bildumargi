/* ==========================================================================
   Bildumargi · componentes de interfaz
   Tablas ordenables, gráficos SVG y ventana de ficha. Los gráficos se dibujan
   a mano: la aplicación tiene que funcionar en una intranet sin salida a
   internet, así que no se carga ninguna librería externa.
   ========================================================================== */

const NS = "http://www.w3.org/2000/svg";

const PALETA = {
  azul: "#3E9BE4", azulClaro: "#86C3EE", cian: "#56B4E9", verde: "#2EB88A",
  lima: "#82C45F", ambar: "#E69F00", rosa: "#F0703A", violeta: "#CC79A7",
  amarillo: "#F0E442", gris: "#5A5A66", texto: "#EDEDF0", suave: "#B3B3BD", tenue: "#8C8C97",
  borde: "#2A2A31", bordeSuave: "#1F1F25", panel: "#131316", panelAlto: "#1B1B20",
  fondo: "#0A0A0C",
};

// Serie de color para repartos categóricos (Okabe-Ito). El orden es fijo: así
// una misma categoría conserva su color entre gráficos y entre sesiones.
const SERIE = [PALETA.cian, PALETA.ambar, PALETA.verde, PALETA.violeta,
               PALETA.amarillo, "#3E7FC4", PALETA.rosa, "#9E9EAA",
               PALETA.azulClaro, "#F5C26B", "#7FD3B5", "#E3A9C9"];

const colorSerie = (i) => SERIE[i % SERIE.length];

function svgEl(nombre, atributos, texto) {
  const nodo = document.createElementNS(NS, nombre);
  for (const [k, v] of Object.entries(atributos || {})) nodo.setAttribute(k, v);
  if (texto !== undefined) nodo.textContent = texto;
  return nodo;
}

function lienzo(ancho, alto, etiqueta) {
  // width/height explícitos: son el tamaño natural del gráfico. El CSS solo
  // permite reducirlo, nunca ampliarlo.
  const svg = svgEl("svg", {
    viewBox: `0 0 ${ancho} ${alto}`, width: ancho, height: alto, class: "grafico",
    preserveAspectRatio: "xMidYMid meet", role: "img",
  });
  if (etiqueta) svg.appendChild(svgEl("title", {}, etiqueta));
  return svg;
}

/* --- Escala de intensidad: de azul apagado a cian vivo -------------------- */
function mezclar(hexA, hexB, t) {
  const a = hexA.match(/\w\w/g).map((h) => parseInt(h, 16));
  const b = hexB.match(/\w\w/g).map((h) => parseInt(h, 16));
  return `#${a.map((v, i) => Math.round(v + (b[i] - v) * t).toString(16).padStart(2, "0")).join("")}`;
}
function colorIntensidad(t, escala) {
  const v = Math.max(0, Math.min(1, Number.isFinite(t) ? t : 0));
  const [ini, med, fin] = escala === "ambar"
    ? ["#3F3016", "#B4720F", "#F59E0B"]
    : ["#1E3A5F", "#2F6FD0", "#22D3EE"];
  return v <= 0.5 ? mezclar(ini, med, v * 2) : mezclar(med, fin, (v - 0.5) * 2);
}

/* ==========================================================================
   Tabla
   columnas: [{clave, titulo, tipo:"texto"|"num"|"pct"|"mono", barra, render, csv}]
   ========================================================================== */
function crearTabla(contenedor, columnas, filas, opciones = {}) {
  const estado = { orden: opciones.orden || null, desc: opciones.desc || false };

  function pintar() {
    let datos = filas.slice();
    if (estado.orden && !opciones.alOrdenar) {
      const col = columnas.find((c) => c.clave === estado.orden);
      datos.sort((x, y) => {
        const a = x[estado.orden], b = y[estado.orden];
        if (a === null || a === undefined) return 1;
        if (b === null || b === undefined) return -1;
        const cmp = (col && col.tipo !== "texto" && col.tipo !== "mono")
          ? Number(a) - Number(b) : String(a).localeCompare(String(b), "es");
        return estado.desc ? -cmp : cmp;
      });
    }

    const maximos = {};
    for (const col of columnas) {
      if (col.barra) maximos[col.clave] = Math.max(...filas.map((f) => Number(f[col.clave]) || 0), 1);
    }

    contenedor.innerHTML = "";
    if (!filas.length) {
      const vacio = document.createElement("p");
      vacio.className = "vacio";
      vacio.textContent = opciones.textoVacio || t("sin_resultados");
      contenedor.appendChild(vacio);
      return;
    }

    const tabla = document.createElement("table");
    tabla.className = "datos";

    const thead = document.createElement("thead");
    const trh = document.createElement("tr");
    for (const col of columnas) {
      const th = document.createElement("th");
      th.textContent = col.titulo;
      if (col.ancho) th.style.width = col.ancho;
      if (col.tipo === "num" || col.tipo === "pct") th.style.textAlign = "right";
      if (col.ordenable !== false) {
        th.className = "ordenable";
        th.tabIndex = 0;
        if (estado.orden === col.clave) {
          const flecha = document.createElement("span");
          flecha.className = "flecha";
          flecha.textContent = estado.desc ? " ↓" : " ↑";
          th.appendChild(flecha);
        }
        const ordenar = () => {
          estado.desc = estado.orden === col.clave ? !estado.desc : true;
          estado.orden = col.clave;
          // Con `alOrdenar`, quien crea la tabla se encarga: así los listados
          // paginados se ordenan enteros en el servidor y no solo la página.
          if (opciones.alOrdenar) opciones.alOrdenar(estado.orden, estado.desc);
          else pintar();
        };
        th.addEventListener("click", ordenar);
        th.addEventListener("keydown", (e) => { if (e.key === "Enter") ordenar(); });
      }
      trh.appendChild(th);
    }
    thead.appendChild(trh);
    tabla.appendChild(thead);

    const tbody = document.createElement("tbody");
    for (const fila of datos) {
      const tr = document.createElement("tr");
      // Filas seleccionables: al pulsarlas, el resto de la vista se actualiza
      // con ese registro. Se marcan como tales para el teclado y el ratón.
      if (opciones.alPulsarFila) {
        tr.className = "fila-pulsable";
        tr.tabIndex = 0;
        if (opciones.filaActiva && opciones.filaActiva(fila)) tr.classList.add("activa");
        const activar = (e) => {
          if (e.target.closest("button, a, input, select")) return;
          opciones.alPulsarFila(fila);
        };
        tr.addEventListener("click", activar);
        tr.addEventListener("keydown", (e) => { if (e.key === "Enter") activar(e); });
      }
      for (const col of columnas) {
        const td = document.createElement("td");
        const valor = fila[col.clave];
        if (col.render) {
          const salida = col.render(fila, td);
          if (salida instanceof Node) td.appendChild(salida);
          else if (salida !== undefined) td.innerHTML = salida;
        } else if (col.tipo === "num") {
          td.className = "num";
          td.textContent = miles(valor);
        } else if (col.tipo === "pct") {
          td.className = "num";
          if (col.barra) {
            const caja = document.createElement("div");
            caja.className = "barra-celda";
            const texto = document.createElement("span");
            texto.textContent = pct(valor);
            const pista = document.createElement("span");
            pista.className = "barra-pista";
            const relleno = document.createElement("span");
            relleno.className = "barra-relleno";
            relleno.style.width = `${Math.min(100, (Number(valor) / maximos[col.clave]) * 100)}%`;
            if (col.escala === "ambar") relleno.style.background = PALETA.ambar;
            pista.appendChild(relleno);
            caja.append(texto, pista);
            td.appendChild(caja);
          } else {
            td.textContent = pct(valor);
          }
        } else if (col.tipo === "mono") {
          td.className = "mono";
          td.textContent = valor === null || valor === undefined || valor === "" ? "—" : valor;
        } else {
          if (col.destacar) td.className = "clave";
          td.textContent = valor === null || valor === undefined || valor === "" ? "—" : valor;
        }
        tr.appendChild(td);
      }
      tbody.appendChild(tr);
    }
    tabla.appendChild(tbody);

    const envoltorio = document.createElement("div");
    envoltorio.className = "envoltorio-tabla";
    envoltorio.appendChild(tabla);
    contenedor.appendChild(envoltorio);
  }

  pintar();
}

function distintivo(texto, tono = "neutral") {
  const span = document.createElement("span");
  span.className = `distintivo ${tono}`;
  span.textContent = texto;
  return span;
}

function botonCSV(nombre, columnas, filas) {
  const boton = document.createElement("button");
  boton.className = "boton secundario pequeno";
  boton.textContent = t("descargar_csv");
  boton.addEventListener("click", () => {
    descargarCSV(nombre, columnas.map((c) => c.titulo),
      filas.map((f) => columnas.map((c) => (c.csv ? c.csv(f) : f[c.clave]))));
  });
  return boton;
}

/* ==========================================================================
   Gráfico de área: evolución año a año
   ========================================================================== */
function graficoArea(puntos, opciones = {}) {
  // puntos: [{etiqueta, valor}]
  const ancho = opciones.ancho || 1060, alto = opciones.alto || 230;
  const m = { arriba: 18, derecha: 16, abajo: 26, izquierda: 44 };
  const w = ancho - m.izquierda - m.derecha;
  const h = alto - m.arriba - m.abajo;
  const svg = lienzo(ancho, alto, opciones.titulo);

  if (!puntos.length) return svg;
  const maximo = Math.max(...puntos.map((p) => p.valor), 1);
  const x = (i) => m.izquierda + (puntos.length === 1 ? w / 2 : (w / (puntos.length - 1)) * i);
  const y = (v) => m.arriba + h - (v / maximo) * h;

  const idGrad = `grad-${Math.random().toString(36).slice(2, 8)}`;
  const defs = svgEl("defs", {});
  const grad = svgEl("linearGradient", { id: idGrad, x1: "0", y1: "0", x2: "0", y2: "1" });
  grad.appendChild(svgEl("stop", { offset: "0%", "stop-color": PALETA.cian, "stop-opacity": ".38" }));
  grad.appendChild(svgEl("stop", { offset: "100%", "stop-color": PALETA.cian, "stop-opacity": "0" }));
  defs.appendChild(grad);
  svg.appendChild(defs);

  // Rejilla y eje de valores
  // Tramos de la rejilla según el alto: en un cuadro bajo, cinco rótulos se pisan.
  const tramos = Math.max(1, Math.min(4, Math.floor(h / 30)));
  for (let i = 0; i <= tramos; i++) {
    const py = m.arriba + (h / tramos) * i;
    svg.appendChild(svgEl("line", {
      x1: m.izquierda, y1: py, x2: m.izquierda + w, y2: py,
      class: i === tramos ? "eje" : "rejilla-linea",
    }));
    svg.appendChild(svgEl("text", {
      x: m.izquierda - 9, y: py + 3.5, "text-anchor": "end", class: "valor-mono",
    }, miles(Math.round((maximo / tramos) * (tramos - i)))));
  }

  const linea = puntos.map((p, i) => `${i ? "L" : "M"}${x(i)},${y(p.valor)}`).join(" ");
  svg.appendChild(svgEl("path", {
    d: `${linea} L${x(puntos.length - 1)},${m.arriba + h} L${x(0)},${m.arriba + h} Z`,
    fill: `url(#${idGrad})`,
  }));
  svg.appendChild(svgEl("path", {
    d: linea, fill: "none", stroke: PALETA.cian, "stroke-width": 2,
    "stroke-linejoin": "round", "stroke-linecap": "round",
  }));

  // Etiquetas del eje horizontal: una de cada n, para que no se amontonen.
  // Una etiqueta cada ~60 px de ancho útil.
  const salto = Math.max(1, Math.ceil(puntos.length / Math.max(2, Math.floor(w / 60))));
  // El último año se rotula siempre, salvo que choque con el anterior rotulado.
  const ultimoRegular = Math.floor((puntos.length - 1) / salto) * salto;
  const cabeUltimo = x(puntos.length - 1) - x(ultimoRegular) >= 40;
  puntos.forEach((p, i) => {
    if (i % salto === 0 || (i === puntos.length - 1 && cabeUltimo)) {
      svg.appendChild(svgEl("text", {
        x: x(i), y: m.arriba + h + 16, "text-anchor": "middle",
      }, p.etiqueta));
    }
    const punto = svgEl("circle", {
      cx: x(i), cy: y(p.valor), r: 8, fill: "transparent",
    });
    punto.appendChild(svgEl("title", {}, `${p.etiqueta}: ${miles(p.valor)}`));
    svg.appendChild(punto);
  });

  // Solo se marca el máximo: un punto por año convierte la línea en un collar.
  const iMax = puntos.reduce((mejor, p, i) => (p.valor > puntos[mejor].valor ? i : mejor), 0);
  svg.appendChild(svgEl("circle", {
    cx: x(iMax), cy: y(puntos[iMax].valor), r: 4,
    fill: PALETA.cian, stroke: PALETA.panel, "stroke-width": 2,
  }));
  if (opciones.etiquetaMaximo) {
    const px = Math.min(Math.max(x(iMax), m.izquierda + 46), m.izquierda + w - 46);
    const py = Math.max(y(puntos[iMax].valor) - 26, m.arriba + 2);
    // Etiqueta en claro sobre oscuro: el azul de marca no contrasta lo
    // suficiente con el fondo del panel para un texto tan pequeño.
    svg.appendChild(svgEl("rect", {
      x: px - 46, y: py, width: 92, height: 20, rx: 10,
      fill: PALETA.texto, stroke: PALETA.cian, "stroke-width": 1,
    }));
    svg.appendChild(svgEl("text", {
      x: px, y: py + 14, "text-anchor": "middle", fill: "#0B1220",
      style: "font-size:11px;font-weight:700",
    }, `${puntos[iMax].etiqueta} · ${miles(puntos[iMax].valor)}`));
  }
  return svg;
}

/* ==========================================================================
   Donut con total al centro
   ========================================================================== */
function graficoDonut(segmentos, opciones = {}) {
  // segmentos: [{etiqueta, valor, detalle}]
  const total = segmentos.reduce((s, x) => s + x.valor, 0);
  const caja = document.createElement("div");
  caja.className = "donut-envoltorio";
  if (!total) {
    caja.innerHTML = `<p class="vacio">${escapar(t("sin_datos_seccion"))}</p>`;
    return caja;
  }

  const tam = 158, r = 60, grosor = 21, c = tam / 2;
  const svg = lienzo(tam, tam, opciones.titulo);
  const circunferencia = 2 * Math.PI * r;
  let acumulado = 0;

  svg.appendChild(svgEl("circle", {
    cx: c, cy: c, r, fill: "none", stroke: PALETA.panelAlto, "stroke-width": grosor,
  }));

  segmentos.forEach((seg, i) => {
    const fraccion = seg.valor / total;
    if (fraccion <= 0) return;
    const arco = svgEl("circle", {
      cx: c, cy: c, r, fill: "none",
      stroke: seg.color || colorSerie(i), "stroke-width": grosor,
      "stroke-dasharray": `${circunferencia * fraccion - 1.5} ${circunferencia}`,
      "stroke-dashoffset": -circunferencia * acumulado,
      transform: `rotate(-90 ${c} ${c})`,
    });
    arco.appendChild(svgEl("title", {}, `${seg.etiqueta}: ${miles(seg.valor)} (${pct(fraccion * 100)})`));
    svg.appendChild(arco);
    acumulado += fraccion;
  });

  const centro = svgEl("text", {
    x: c, y: c - 2, "text-anchor": "middle", fill: PALETA.texto,
    style: "font-size:18px;font-weight:700;font-variant-numeric:tabular-nums",
  }, miles(opciones.total ?? total));
  svg.appendChild(centro);
  svg.appendChild(svgEl("text", {
    x: c, y: c + 14, "text-anchor": "middle", fill: PALETA.tenue,
    style: "font-size:9px;letter-spacing:.1em;text-transform:uppercase",
  }, opciones.rotulo || ""));

  const leyenda = document.createElement("div");
  leyenda.className = "leyenda";
  segmentos.forEach((seg, i) => {
    const fila = document.createElement("div");
    fila.className = "leyenda-fila";
    fila.innerHTML = `
      <span class="muestra" style="background:${seg.color || colorSerie(i)}"></span>
      <span class="nombre">${escapar(seg.etiqueta)}
        ${seg.detalle ? `<span class="detalle" style="display:block;font-weight:400">${escapar(seg.detalle)}</span>` : ""}
      </span>
      <span class="cifra" style="color:${seg.color || colorSerie(i)}">${pct((seg.valor / total) * 100)}</span>`;
    leyenda.appendChild(fila);
  });

  caja.append(svg, leyenda);
  return caja;
}

/* ==========================================================================
   Barras horizontales, con línea de referencia opcional
   ========================================================================== */
function graficoBarrasH(datos, opciones = {}) {
  // datos: [{etiqueta, valor, texto, color}]
  const filas = datos.length;
  const pieReferencia = opciones.referencia ? 26 : 8;
  // Con alto dado, las filas se reparten ese alto (máximo 32 px cada una) y el
  // bloque se centra; sin él, el gráfico mide lo que piden sus filas.
  const altoFila = opciones.alto && filas
    ? Math.max(18, Math.min(32, Math.floor((opciones.alto - pieReferencia) / filas))) : 32;
  const anchoEtiqueta = opciones.anchoEtiqueta || 170;
  const ancho = opciones.ancho || 520;
  const alto = opciones.alto || filas * altoFila + pieReferencia;
  const margenArriba = opciones.alto ? Math.max(0, (alto - filas * altoFila - pieReferencia) / 2) : 0;
  const x0 = anchoEtiqueta;
  const w = ancho - x0 - 92;
  const svg = lienzo(ancho, alto, opciones.titulo);
  if (!filas) return svg;

  const maximo = opciones.maximo || Math.max(...datos.map((d) => d.valor), 1);

  // Grosor y línea base proporcionales a la fila: 15 y 16 px con la fila de
  // 32 px de siempre, menos cuando el cuadro obliga a apretar.
  const grosor = Math.min(15, altoFila - 8);
  const base = Math.round(altoFila / 2) + 4;
  const arribaBarra = Math.round((altoFila - grosor) / 2) - 1;

  datos.forEach((d, i) => {
    const y = 2 + margenArriba + i * altoFila;
    svg.appendChild(svgEl("text", {
      x: x0 - 12, y: y + base, "text-anchor": "end", fill: PALETA.suave,
      style: "font-size:11.5px",
    }, d.etiqueta.length > 26 ? `${d.etiqueta.slice(0, 25)}…` : d.etiqueta))
      .appendChild(svgEl("title", {}, d.etiqueta));
    svg.appendChild(svgEl("rect", { x: x0, y: y + arribaBarra, width: w, height: grosor, rx: 4, fill: PALETA.panelAlto }));
    const largo = Math.max((d.valor / maximo) * w, 2);
    const barra = svgEl("rect", {
      x: x0, y: y + arribaBarra, width: largo, height: grosor, rx: 4, fill: d.color || PALETA.azul,
    });
    barra.appendChild(svgEl("title", {}, `${d.etiqueta}: ${d.texto || miles(d.valor)}`));
    svg.appendChild(barra);
    svg.appendChild(svgEl("text", {
      x: x0 + w + 10, y: y + base, fill: PALETA.texto, class: "valor-mono",
      style: "font-weight:600",
    }, d.texto || miles(d.valor)));
  });

  if (opciones.referencia) {
    const xr = x0 + (opciones.referencia.valor / maximo) * w;
    svg.appendChild(svgEl("line", {
      x1: xr, y1: 0, x2: xr, y2: filas * altoFila,
      stroke: PALETA.ambar, "stroke-width": 1.2, "stroke-dasharray": "4 3",
    }));
    svg.appendChild(svgEl("text", {
      x: xr, y: filas * altoFila + 16, "text-anchor": "middle", fill: PALETA.ambar,
      style: "font-size:10px",
    }, opciones.referencia.etiqueta));
  }
  return svg;
}

/* ==========================================================================
   Barras verticales con intensidad de color
   ========================================================================== */
function graficoBarras(datos, opciones = {}) {
  // datos: [{etiqueta, valor, intensidad}]
  const ancho = Math.max(420, datos.length * 40);
  const alto = 232;
  const m = { arriba: 14, derecha: 10, abajo: 76, izquierda: 48 };
  const w = ancho - m.izquierda - m.derecha;
  const h = alto - m.arriba - m.abajo;
  const svg = lienzo(ancho, alto, opciones.titulo);
  if (!datos.length) return svg;

  const maximo = Math.max(...datos.map((d) => d.valor), 1);
  const paso = w / datos.length;
  const anchoBarra = Math.min(26, paso * 0.62);

  for (let i = 0; i <= 4; i++) {
    const y = m.arriba + (h / 4) * i;
    svg.appendChild(svgEl("line", {
      x1: m.izquierda, y1: y, x2: m.izquierda + w, y2: y,
      class: i === 4 ? "eje" : "rejilla-linea",
    }));
    svg.appendChild(svgEl("text", {
      x: m.izquierda - 9, y: y + 3.5, "text-anchor": "end", class: "valor-mono",
    }, miles(Math.round((maximo / 4) * (4 - i)))));
  }

  datos.forEach((d, i) => {
    const alturaBarra = (d.valor / maximo) * h;
    const x = m.izquierda + paso * i + (paso - anchoBarra) / 2;
    const y = m.arriba + h - alturaBarra;
    const barra = svgEl("rect", {
      x, y, width: anchoBarra, height: Math.max(alturaBarra, 2), rx: 3,
      fill: colorIntensidad((d.intensidad || 0) / 100, opciones.escala),
    });
    barra.appendChild(svgEl("title", {},
      `${d.etiqueta}: ${miles(d.valor)}${d.intensidad !== undefined ? ` · ${pct(d.intensidad)}` : ""}`));
    svg.appendChild(barra);

  });

  etiquetarEje(svg, datos, { x: (i) => m.izquierda + paso * i + paso / 2, base: m.arriba + h, paso });
  return svg;
}

function leyendaIntensidad(texto, escala) {
  const div = document.createElement("div");
  div.className = "leyenda-linea";
  div.innerHTML = `<span>${escapar(texto)}</span>` +
    [0, 0.5, 1].map((v) =>
      `<span><i class="muestra" style="background:${colorIntensidad(v, escala)}"></i>${v * 100}%</span>`).join("");
  return div;
}

/* ==========================================================================
   Ventana modal
   ========================================================================== */
function abrirModal(titulo, contenido, alCerrar, claseModal = "") {
  const velo = document.createElement("div");
  velo.className = "velo";
  velo.innerHTML = `
    <div class="modal ${escapar(claseModal)}" role="dialog" aria-modal="true" aria-label="${escapar(titulo)}">
      <header>
        <h2>${escapar(titulo)}</h2>
        <button class="cerrar" aria-label="${escapar(t("cerrar"))}">×</button>
      </header>
      <div class="cuerpo-modal"></div>
    </div>`;
  const cuerpo = velo.querySelector(".cuerpo-modal");
  if (contenido instanceof Node) cuerpo.appendChild(contenido);
  else cuerpo.innerHTML = contenido;

  const cerrar = () => {
    if (!velo.isConnected) return;
    velo.remove();
    document.removeEventListener("keydown", alPulsar);
    if (alCerrar) alCerrar();
  };
  const alPulsar = (e) => { if (e.key === "Escape") cerrar(); };
  velo.querySelector(".cerrar").addEventListener("click", cerrar);
  velo.addEventListener("click", (e) => { if (e.target === velo) cerrar(); });
  document.addEventListener("keydown", alPulsar);
  document.body.appendChild(velo);
  velo.querySelector(".cerrar").focus();
  return cerrar;
}

/* ---------- Ficha catalográfica -------------------------------------------- */
function pintarFicha(ficha) {
  const div = document.createElement("div");
  const parrafo = [ficha.titulo || t("ficha_sin_titulo")];
  if (ficha.autor) parrafo.push(`/ ${ficha.autor}`);
  if (ficha.detalle_isbd) parrafo.push(ficha.detalle_isbd);
  const materias = (ficha.materias || []).map((m, i) => `${i + 1}. ${m}.`).join(" ");
  const nota = ficha.fuente === "marc" ? t("ficha_red")
    : ficha.fuente === "basico" ? t("ficha_basica") : t("ficha_sesion");

  div.innerHTML = `
    <div class="isbd">
      ${ficha.signatura ? `<div class="signatura">${escapar(ficha.signatura)}</div>` : ""}
      ${ficha.autor ? `<div class="autor">${escapar(ficha.autor)}</div>` : ""}
      <div class="parrafo">${escapar(parrafo.join(" "))}</div>
      ${materias ? `<div class="materias">${escapar(materias)}</div>` : ""}
      ${ficha.isbn ? `<div class="isbn">ISBN ${escapar(ficha.isbn)}</div>` : ""}
      <div class="procedencia">${escapar(nota)}</div>
    </div>`;

  const pares = [
    [t("col_anio"), ficha.anio], [t("ficha_editorial"), ficha.editorial],
    [t("ficha_edicion"), ficha.edicion],
    [t("col_idioma"), ficha.idioma], [t("col_loc"), ficha.loc],
  ].filter(([, v]) => v);
  if (pares.length) {
    const dl = document.createElement("dl");
    dl.className = "lista-datos";
    dl.innerHTML = pares.map(([k, v]) => `<dt>${escapar(k)}</dt><dd>${escapar(v)}</dd>`).join("");
    div.appendChild(dl);
  }

  if (ficha.ejemplares && ficha.ejemplares.length) {
    const titulo = document.createElement("h3");
    titulo.textContent = `${t("ficha_ejemplares")} (${ficha.ejemplares.length})`;
    titulo.style.margin = "1.1rem 0 .5rem";
    div.appendChild(titulo);
    const caja = document.createElement("div");
    crearTabla(caja, [
      { clave: "biblioteca", titulo: t("col_biblioteca") },
      { clave: "signatura", titulo: t("col_signatura"), tipo: "mono" },
      { clave: "codigo_barras", titulo: t("col_codbar"), tipo: "mono" },
    ], ficha.ejemplares, { orden: "biblioteca" });
    div.appendChild(caja);
  }
  return div;
}


/* ==========================================================================
   Valoraciones entre bibliotecas
   ========================================================================== */
function estrellas(valor, alElegir) {
  const caja = document.createElement("div");
  caja.className = "estrellas" + (alElegir ? "" : " solo-lectura");
  for (let n = 1; n <= 5; n++) {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = n <= (valor || 0) ? "★" : "☆";
    b.className = n <= (valor || 0) ? "activa" : "";
    b.setAttribute("aria-label", t("n_estrellas", { n }));
    if (alElegir) b.addEventListener("click", () => alElegir(n));
    else b.tabIndex = -1;
    caja.appendChild(b);
  }
  return caja;
}

function fechaCorta(iso) {
  if (!iso) return "";
  const f = new Date(iso);
  return Number.isNaN(f.getTime()) ? "" : f.toLocaleDateString(LOCALE_FECHAS[IDIOMA] || "es-ES");
}

function bloqueValoracion(idSistema, datos, alGuardar, alBorrar, alResponder, alBorrarRespuesta) {
  const caja = document.createElement("div");
  caja.className = "bloque-valoracion";
  caja.appendChild(Object.assign(document.createElement("h3"),
    { textContent: t("valoraciones_titulo") }));
  caja.appendChild(Object.assign(document.createElement("p"),
    { className: "firma", textContent: t("firmas_como", { n: datos.biblioteca || "—" }) }));

  if (!datos.disponible) {
    const aviso = document.createElement("div");
    aviso.className = "aviso atencion";
    aviso.textContent = datos.error || t("valoraciones_desactivadas");
    caja.appendChild(aviso);
    return caja;
  }

  // Media de la red
  const media = document.createElement("div");
  media.className = "media-valoracion";
  if (datos.media !== null && datos.media !== undefined) {
    const cifra = document.createElement("span");
    cifra.className = "cifra";
    cifra.appendChild(document.createTextNode(decimal(datos.media, 1)));
    const sobre = document.createElement("small");
    sobre.textContent = " / 5";
    cifra.appendChild(sobre);
    media.append(cifra, estrellas(Math.round(datos.media)));
    media.appendChild(Object.assign(document.createElement("span"),
      { className: "detalle",
        textContent: t(datos.n_puntuaciones === 1 ? "n_valoraciones_red_una" : "n_valoraciones_red",
                       { n: datos.n_puntuaciones }) }));
  } else {
    media.appendChild(Object.assign(document.createElement("span"),
      { className: "detalle", textContent: t("sin_valoraciones") }));
  }
  caja.appendChild(media);

  // Formulario propio
  const mia = datos.mia || {};
  let puntuacion = mia.puntuacion || 0;

  const form = document.createElement("div");
  form.className = "formulario-valoracion";

  const filaEstrellas = document.createElement("div");
  filaEstrellas.style.cssText = "display:flex;align-items:center;gap:.6rem;flex-wrap:wrap";
  const rotulo = document.createElement("span");
  rotulo.className = "metrica-rotulo";
  rotulo.style.margin = "0";
  rotulo.textContent = t("tu_puntuacion");
  const contenedorEstrellas = document.createElement("span");
  const pintarEstrellas = () => {
    contenedorEstrellas.innerHTML = "";
    contenedorEstrellas.appendChild(estrellas(puntuacion, (n) => {
      puntuacion = (puntuacion === n) ? 0 : n;  // volver a pulsar quita la nota
      pintarEstrellas();
    }));
  };
  pintarEstrellas();
  filaEstrellas.append(rotulo, contenedorEstrellas);
  form.appendChild(filaEstrellas);

  const texto = document.createElement("textarea");
  texto.placeholder = t("placeholder_comentario");
  texto.maxLength = 2000;
  texto.value = mia.comentario || "";
  form.appendChild(texto);

  const acciones = document.createElement("div");
  acciones.className = "acciones-valoracion";
  const guardar = document.createElement("button");
  guardar.className = "boton";
  guardar.textContent = t("guardar_valoracion");
  acciones.appendChild(guardar);

  if (mia.puntuacion || mia.comentario) {
    const borrar = document.createElement("button");
    borrar.className = "boton secundario";
    borrar.textContent = t("borrar_valoracion");
    borrar.addEventListener("click", () => alBorrar());
    acciones.appendChild(borrar);
  }
  const contador = document.createElement("span");
  contador.className = "contador";
  const refrescarContador = () => { contador.textContent = `${texto.value.length} / 2000`; };
  refrescarContador();
  texto.addEventListener("input", refrescarContador);
  acciones.appendChild(contador);
  form.appendChild(acciones);

  const error = document.createElement("div");
  error.style.display = "none";
  form.appendChild(error);

  guardar.addEventListener("click", async () => {
    guardar.disabled = true;
    error.style.display = "none";
    try {
      await alGuardar({ puntuacion: puntuacion || null, comentario: texto.value });
    } catch (e) {
      error.style.display = "";
      error.className = "aviso error";
      error.textContent = e.message;
      guardar.disabled = false;
    }
  });
  form.appendChild(Object.assign(document.createElement("p"),
    { className: "normas-uso", textContent: t("normas_uso") }));
  caja.appendChild(form);

  // Opiniones de las demás bibliotecas
  const conComentario = (datos.valoraciones || []).filter((v) => v.comentario);
  if (conComentario.length) {
    const lista = document.createElement("div");
    lista.className = "lista-opiniones";
    for (const v of conComentario) {
      const op = document.createElement("div");
      op.className = "opinion" + (v.biblioteca === datos.biblioteca ? " propia" : "");
      const cabeza = document.createElement("div");
      cabeza.className = "cabeza";
      const quien = document.createElement("span");
      quien.className = "quien";
      quien.textContent = v.biblioteca;
      const derecha = document.createElement("span");
      derecha.style.cssText = "display:flex;align-items:center;gap:.5rem";
      if (v.puntuacion) derecha.appendChild(estrellas(v.puntuacion));
      derecha.appendChild(Object.assign(document.createElement("span"),
        { className: "cuando", textContent: fechaCorta(v.actualizado) }));
      cabeza.append(quien, derecha);
      op.appendChild(cabeza);
      const cuerpo = document.createElement("div");
      cuerpo.className = "texto";
      cuerpo.textContent = v.comentario;   // textContent: nunca HTML de terceros
      op.appendChild(cuerpo);
      if (alResponder) op.appendChild(hiloRespuestas(v, datos.biblioteca, alResponder, alBorrarRespuesta));
      lista.appendChild(op);
    }
    caja.appendChild(lista);
  }
  return caja;
}


/* ==========================================================================
   Gráfico combinado: columnas + línea sobre dos ejes verticales
   Volúmenes a la izquierda en barras, % de préstamos a la derecha en línea.
   Son dos magnitudes con unidades distintas, así que comparten el eje
   horizontal pero nunca la escala vertical.
   ========================================================================== */
function graficoCombinado(datos, opciones = {}) {
  // datos: [{etiqueta, valor, linea, clave}]
  const ancho = opciones.ancho || 760;
  const m = { arriba: 16, derecha: 46, abajo: 0, izquierda: 50 };
  const w = ancho - m.izquierda - m.derecha;
  const paso = w / Math.max(datos.length, 1);
  // El hueco de las etiquetas se calcula ANTES de repartir la altura: si se
  // fija a ojo, o sobra franja vacía o las etiquetas se salen del lienzo.
  m.abajo = opciones.abajo || Math.round(altoEtiquetas(datos, paso));
  const alto = (opciones.alto || 300) + Math.max(0, m.abajo - 44);
  const h = alto - m.arriba - m.abajo;
  const svg = lienzo(ancho, alto, opciones.titulo);
  svg.classList.add("elastico");
  if (!datos.length) return svg;

  const maxVol = Math.max(...datos.map((d) => d.valor), 1);
  const maxLinea = 100;
  const anchoBarra = Math.min(opciones.anchoBarra || 34, paso * 0.62);
  const x = (i) => m.izquierda + paso * i + paso / 2;
  const yVol = (v) => m.arriba + h - (v / maxVol) * h;
  const yLinea = (v) => m.arriba + h - (v / maxLinea) * h;

  // Rejilla y ejes
  for (let i = 0; i <= 4; i++) {
    const py = m.arriba + (h / 4) * i;
    svg.appendChild(svgEl("line", {
      x1: m.izquierda, y1: py, x2: m.izquierda + w, y2: py,
      class: i === 4 ? "eje" : "rejilla-linea",
    }));
    svg.appendChild(svgEl("text", {
      x: m.izquierda - 8, y: py + 3.5, "text-anchor": "end", class: "valor-mono",
    }, miles(Math.round((maxVol / 4) * (4 - i)))));
    svg.appendChild(svgEl("text", {
      x: m.izquierda + w + 8, y: py + 3.5, "text-anchor": "start",
      class: "valor-mono", fill: PALETA.ambar,
    }, `${Math.round((maxLinea / 4) * (4 - i))}%`));
  }

  // Columnas
  datos.forEach((d, i) => {
    const altura = (d.valor / maxVol) * h;
    const activo = opciones.seleccion !== undefined
      && String(opciones.seleccion || "") === String(d.clave);
    const barra = svgEl("rect", {
      x: x(i) - anchoBarra / 2, y: yVol(d.valor),
      width: anchoBarra, height: Math.max(altura, 2), rx: 3,
      fill: activo ? PALETA.cian : PALETA.azul,
      opacity: opciones.seleccion && !activo ? ".45" : "1",
      style: opciones.alPulsar ? "cursor:pointer" : "",
    });
    barra.appendChild(svgEl("title", {},
      `${d.etiqueta}: ${miles(d.valor)} · ${pct(d.linea)}`));
    if (opciones.alPulsar) {
      barra.addEventListener("click", () => opciones.alPulsar(activo ? "" : d.clave));
    }
    svg.appendChild(barra);
  });

  // Línea de porcentaje, por encima de las barras
  const camino = datos.map((d, i) => `${i ? "L" : "M"}${x(i)},${yLinea(d.linea || 0)}`).join(" ");
  svg.appendChild(svgEl("path", {
    d: camino, fill: "none", stroke: PALETA.ambar, "stroke-width": 2,
    "stroke-linejoin": "round", style: "pointer-events:none",
  }));
  datos.forEach((d, i) => {
    svg.appendChild(svgEl("circle", {
      cx: x(i), cy: yLinea(d.linea || 0), r: 3,
      fill: PALETA.ambar, stroke: PALETA.panel, "stroke-width": 1.5,
      style: "pointer-events:none",
    }));
  });

  // Etiquetas del eje horizontal
  etiquetarEje(svg, datos, {
    x, base: m.arriba + h, paso,
    activa: (d) => opciones.seleccion && String(opciones.seleccion) === String(d.clave),
  });

  return svg;
}

/* --- Etiquetas del eje horizontal, sin solapes --------------------------
   Decide sola entre tres formas según el espacio por columna: una línea,
   dos renglones o rotada 45°. Y si ni rotando caben (un eje de cuarenta
   años en 700 px), escribe una de cada n. Antes se escribían todas siempre
   y en los ejes poblados se pisaban unas a otras hasta ser ilegibles.
   ---------------------------------------------------------------------- */
const ANCHO_CARACTER = 5.4;   // aproximación para 10 px de cuerpo

function etiquetarEje(svg, datos, opciones) {
  const { x, base, paso } = opciones;
  const largoMaximo = Math.max(...datos.map((d) => String(d.etiqueta).length), 1);
  const cabenPorLinea = Math.max(1, Math.floor(paso / ANCHO_CARACTER));

  let modo;
  if (largoMaximo <= cabenPorLinea) modo = "recta";
  // Etiquetas cortas (años, signaturas): antes de rotar cuarenta rótulos de
  // cuatro cifras, que es ilegible y feo, se escriben rectas y salteadas.
  else if (largoMaximo <= 6) modo = "recta";
  else if (largoMaximo <= cabenPorLinea * 2 && paso >= 34) modo = "dos-lineas";
  else modo = "rotada";

  // En modo recto, si ni una etiqueta corta cabe, se salta de n en n.
  const salto = modo === "recta"
    ? Math.max(1, Math.ceil((largoMaximo * ANCHO_CARACTER + 6) / paso)) : 1;

  datos.forEach((d, i) => {
    const activa = opciones.activa ? opciones.activa(d) : false;
    if (modo === "recta" && i % salto !== 0 && !activa && i !== datos.length - 1) return;

    const color = activa ? PALETA.cian : PALETA.tenue;
    const peso = activa ? "font-weight:700;" : "";

    if (modo === "rotada") {
      const texto = String(d.etiqueta).length > 22
        ? `${String(d.etiqueta).slice(0, 21)}…` : String(d.etiqueta);
      const nodo = svgEl("text", {
        x: x(i), y: base + 12, "text-anchor": "end", fill: color,
        transform: `rotate(-45 ${x(i)} ${base + 12})`,
        style: `font-size:10px;${peso}`,
      }, texto);
      nodo.appendChild(svgEl("title", {}, d.etiqueta));
      svg.appendChild(nodo);
      return;
    }

    const lineas = modo === "dos-lineas"
      ? partirEtiqueta(d.etiqueta, cabenPorLinea) : [String(d.etiqueta)];
    lineas.slice(0, 2).forEach((linea, n) => {
      const nodo = svgEl("text", {
        x: x(i), y: base + 14 + n * 11, "text-anchor": "middle", fill: color,
        style: `font-size:10px;${peso}`,
      }, linea);
      if (n === 0) nodo.appendChild(svgEl("title", {}, d.etiqueta));
      svg.appendChild(nodo);
    });
  });
}

/* Espacio que hay que reservar bajo el eje para que quepan las etiquetas. */
function altoEtiquetas(datos, paso) {
  const largoMaximo = Math.max(...datos.map((d) => String(d.etiqueta).length), 1);
  const cabenPorLinea = Math.max(1, Math.floor(paso / ANCHO_CARACTER));
  if (largoMaximo <= cabenPorLinea || largoMaximo <= 6) return 26;
  if (largoMaximo <= cabenPorLinea * 2 && paso >= 34) return 38;
  return 22 + Math.min(largoMaximo, 22) * 4.6;   // rotadas a 45°
}

function partirEtiqueta(texto, ancho) {
  const palabras = String(texto || "").split(/\s+/);
  const lineas = [];
  let actual = "";
  for (const palabra of palabras) {
    if ((actual + " " + palabra).trim().length > ancho && actual) {
      lineas.push(actual);
      actual = palabra;
    } else {
      actual = (actual + " " + palabra).trim();
    }
  }
  if (actual) lineas.push(actual);
  if (lineas.length > 2) {
    lineas[1] = `${lineas[1].slice(0, ancho - 1)}…`;
    return lineas.slice(0, 2);
  }
  return lineas;
}

function leyendaCombinada(rotuloBarras, rotuloLinea) {
  const div = document.createElement("div");
  div.className = "leyenda-linea";
  div.innerHTML =
    `<span><i class="muestra" style="background:${PALETA.azul}"></i>${escapar(rotuloBarras)}</span>` +
    `<span><i class="muestra" style="background:${PALETA.ambar};border-radius:50%"></i>${escapar(rotuloLinea)}</span>`;
  return div;
}




/* ==========================================================================
   Treemap
   Superficie = volúmenes, color = índice de circulación. Reparto squarified:
   coloca las cajas en franjas eligiendo en cada paso la orientación que deja
   los rectángulos menos alargados. Un treemap de tiras simples deja astillas
   ilegibles en cuanto hay una categoría que se lleva un tercio del fondo,
   que es exactamente lo que pasa con Ficción en una biblioteca pública.
   ========================================================================== */

// Escala fría -> cálida para el porcentaje de uso.
// Uso de menos a más: azul frío → naranja cálido, legible con daltonismo.
let ESCALA_USO = ["#15406A", "#1F72B8", "#56B4E9", "#F2C46D", "#E69F00"];   // la cambia aplicarApariencia

function colorUso(pct100) {
  const v = Math.max(0, Math.min(100, Number(pct100) || 0)) / 100;
  const tramos = ESCALA_USO.length - 1;
  const i = Math.min(Math.floor(v * tramos), tramos - 1);
  return mezclar(ESCALA_USO[i], ESCALA_USO[i + 1], v * tramos - i);
}

function _peorRelacion(fila, largo, suma) {
  const max = Math.max(...fila);
  const min = Math.min(...fila);
  const s2 = suma * suma;
  const l2 = largo * largo;
  return Math.max((l2 * max) / s2, s2 / (l2 * min));
}

function _squarify(valores, x, y, ancho, alto) {
  // Devuelve rectángulos en el mismo orden que los valores recibidos.
  const cajas = [];
  let indice = 0;
  let restantes = valores.slice();
  let libre = { x, y, ancho, alto };
  const total = valores.reduce((s, v) => s + v, 0) || 1;
  let areaRestante = libre.ancho * libre.alto;
  let sumaRestante = total;

  while (restantes.length) {
    const escala = areaRestante / sumaRestante;
    const horizontal = libre.ancho >= libre.alto;
    const largo = horizontal ? libre.alto : libre.ancho;

    const fila = [];
    let sumaFila = 0;
    while (restantes.length) {
      const siguiente = restantes[0] * escala;
      const prueba = fila.concat([siguiente]);
      const sumaPrueba = sumaFila + siguiente;
      if (fila.length && _peorRelacion(prueba, largo, sumaPrueba)
          > _peorRelacion(fila, largo, sumaFila)) break;
      fila.push(siguiente);
      sumaFila = sumaPrueba;
      restantes.shift();
    }

    const grosor = sumaFila / largo;
    let desplazamiento = 0;
    for (const area of fila) {
      const lado = area / grosor;
      cajas.push(horizontal
        ? { x: libre.x, y: libre.y + desplazamiento, ancho: grosor, alto: lado }
        : { x: libre.x + desplazamiento, y: libre.y, ancho: lado, alto: grosor });
      desplazamiento += lado;
      indice++;
    }

    if (horizontal) { libre.x += grosor; libre.ancho -= grosor; }
    else { libre.y += grosor; libre.alto -= grosor; }
    areaRestante = Math.max(libre.ancho * libre.alto, 0);
    sumaRestante -= fila.reduce((s, a) => s + a, 0) / escala;
    if (areaRestante <= 0 || sumaRestante <= 0) break;
  }
  return cajas;
}

function graficoTreemap(datos, opciones = {}) {
  // datos: [{clave, etiqueta, valor, intensidad}]
  const ancho = opciones.ancho || 1000;
  const alto = opciones.alto || 420;
  const svg = lienzo(ancho, alto, opciones.titulo);
  svg.classList.add("elastico");
  if (!datos.length) return svg;

  let ordenados = datos.slice().sort((a, b) => b.valor - a.valor)
    .filter((d) => d.valor > 0);
  let cajas = _squarify(ordenados.map((d) => d.valor), 0, 0, ancho, alto);

  // Recorte por legibilidad: se quitan secciones por la cola hasta que todas
  // las teselas admiten rótulo. Prima el tamaño de la visualización sobre la
  // representación completa; lo omitido se comunica fuera (alRecortar).
  if (opciones.recorte) {
    const { ancho: minAncho, alto: minAlto } = opciones.recorte;
    let k = ordenados.length;
    while (k > 1 && !cajas.every((c) => c.ancho >= minAncho && c.alto >= minAlto)) {
      k -= 1;
      cajas = _squarify(ordenados.slice(0, k).map((d) => d.valor), 0, 0, ancho, alto);
    }
    const omitidas = ordenados.slice(k);
    ordenados = ordenados.slice(0, k);
    if (opciones.alRecortar) opciones.alRecortar(omitidas);
  }

  ordenados.forEach((d, i) => {
    const caja = cajas[i];
    if (!caja || caja.ancho < 1 || caja.alto < 1) return;
    const activo = opciones.seleccion && String(opciones.seleccion) === String(d.clave);
    const grupo = svgEl("g", { style: opciones.alPulsar ? "cursor:pointer" : "" });

    grupo.appendChild(svgEl("rect", {
      x: caja.x + 1, y: caja.y + 1,
      width: Math.max(caja.ancho - 2, 1), height: Math.max(caja.alto - 2, 1),
      rx: 3, fill: colorUso(d.intensidad),
      stroke: activo ? "#FFFFFF" : PALETA.fondo,
      "stroke-width": activo ? 2.5 : 1.5,
      opacity: opciones.seleccion && !activo ? ".55" : "1",
    }));

    // Rótulos solo donde caben: un texto recortado estorba más que ayuda.
    const caben = Math.floor((caja.ancho - 14) / 6.2);
    if (caja.ancho > 54 && caja.alto > 24 && caben > 3) {
      // Tinta según la luminancia real del relleno: sobre azul claro o
      // naranja, texto oscuro; sobre azul profundo, claro.
      const oscuro = luminancia(colorUso(d.intensidad)) > .3;
      const tinta = oscuro ? "#0A0A0C" : "#F2F2F5";
      const suave = oscuro ? "rgba(10,10,12,.72)" : "rgba(242,242,245,.75)";
      const lineas = partirEtiqueta(d.etiqueta, caben);
      const maxLineas = caja.alto > 58 ? 2 : 1;
      lineas.slice(0, maxLineas).forEach((linea, n) => {
        grupo.appendChild(svgEl("text", {
          x: caja.x + 8, y: caja.y + 17 + n * 12,
          style: `font-size:11px;font-weight:600;fill:${tinta}`,
        }, linea));
      });
      const base = caja.y + 17 + Math.min(lineas.length, maxLineas) * 12;
      if (base + 4 < caja.y + caja.alto) {
        grupo.appendChild(svgEl("text", {
          x: caja.x + 8, y: base + 2, style: `font-size:10px;fill:${suave}`,
        }, `${miles(d.valor)} · ${pct(d.intensidad)}`));
      }
    }

    grupo.appendChild(svgEl("title", {},
      `${d.etiqueta}\n${miles(d.valor)} ${t("col_volumenes").toLowerCase()} · ${pct(d.intensidad)} ${t("col_rotacion").toLowerCase()}`));
    if (opciones.alPulsar) {
      grupo.setAttribute("tabindex", "0");
      grupo.setAttribute("role", "button");
      grupo.setAttribute("aria-label", d.etiqueta);
      const pulsar = () => opciones.alPulsar(activo ? "" : d.clave);
      grupo.addEventListener("click", pulsar);
      grupo.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pulsar(); } });
    }
    svg.appendChild(grupo);
  });
  return svg;
}

/* Luminancia relativa (WCAG) de un color #rrggbb. */
function luminancia(hex) {
  const n = parseInt(String(hex).replace("#", ""), 16);
  const canal = (v) => { const c = v / 255; return c <= .03928 ? c / 12.92 : ((c + .055) / 1.055) ** 2.4; };
  return .2126 * canal((n >> 16) & 255) + .7152 * canal((n >> 8) & 255) + .0722 * canal(n & 255);
}

/* Barra de color continua, para explicar la escala del treemap. */
function leyendaGradiente(rotulo) {
  const caja = document.createElement("div");
  caja.className = "leyenda-gradiente";
  const texto = document.createElement("span");
  texto.textContent = rotulo;
  const barra = document.createElement("span");
  barra.className = "barra-gradiente";
  barra.style.background = `linear-gradient(90deg, ${ESCALA_USO.join(", ")})`;
  const cero = document.createElement("span");
  cero.textContent = "0 %";
  const cien = document.createElement("span");
  cien.textContent = "100 %";
  caja.append(texto, cero, barra, cien);
  return caja;
}

/* ==========================================================================
   Indicadores del Diagnóstico
   Tarjeta de cinco capas (rótulo · estado · cifra · micrográfico · contexto).
   El estado nunca va solo en color: lleva icono y texto.
   ========================================================================== */
const ICONO_ESTADO = { ok: "✓", aviso: "!", bajo: "▼", alto: "▲", info: "i" };

function nodo(etiqueta, clase, texto) {
  const n = document.createElement(etiqueta);
  if (clase) n.className = clase;
  if (texto !== undefined && texto !== null) n.textContent = texto;
  return n;
}

function chipEstado(texto, nivel) {
  const chip = nodo("span", `chip-estado ${nivel}`);
  chip.append(nodo("span", "icono", ICONO_ESTADO[nivel] || "•"), document.createTextNode(texto));
  return chip;
}

function tarjetaIndicador({ rotulo, valor, unidad, contexto, estado, grafico, acento, ayuda, explicacion }) {
  const caja = nodo("div", "indicador");
  if (acento) caja.style.setProperty("--acento", acento);
  const cabeza = nodo("div", "cabeza-indicador");
  const titulo = nodo("span", "titulo-indicador");
  titulo.appendChild(nodo("span", "rotulo", rotulo));
  if (explicacion) titulo.appendChild(explicacion);
  cabeza.appendChild(titulo);
  if (estado) cabeza.appendChild(chipEstado(estado.texto, estado.nivel));
  caja.appendChild(cabeza);
  const cifra = nodo("div", "cifra", valor);
  if (unidad) cifra.appendChild(nodo("span", "unidad", unidad));
  caja.appendChild(cifra);
  if (grafico) {
    const micro = nodo("div", "micro");
    micro.appendChild(grafico);
    caja.appendChild(micro);
  }
  if (contexto) caja.appendChild(nodo("div", "contexto", contexto));
  if (ayuda) caja.title = ayuda;
  return caja;
}

/* Gráfico de bala (Stephen Few): bandas cualitativas en grises de una sola
   tonalidad, barra del valor y, si lo hay, tramo de referencia marcado. Si el
   valor se sale de la escala, la barra llega al final con una punta. */
function graficoBala({ valor, escala, bandas = [], referencia = null, color = PALETA.texto, titulo }) {
  const caja = nodo("div", "bala");
  if (titulo) caja.title = titulo;
  const x = (v) => `${Math.max(0, Math.min(100, (v / escala) * 100))}%`;
  bandas.forEach(([desde, hasta], i) => {
    const b = nodo("span", `banda b${i}`);
    b.style.left = x(desde);
    b.style.width = `calc(${x(hasta)} - ${x(desde)})`;
    caja.appendChild(b);
  });
  if (referencia) {
    const r = nodo("span", "referencia");
    r.style.left = x(referencia[0]);
    r.style.width = `calc(${x(referencia[1])} - ${x(referencia[0])})`;
    caja.appendChild(r);
  }
  const barra = nodo("span", "valor-bala");
  barra.style.width = x(valor);
  barra.style.background = color;
  if (valor > escala) barra.classList.add("desborda");
  caja.appendChild(barra);
  return caja;
}

/* Barra apilada al 100 % con leyenda implícita en el contexto de la tarjeta. */
function barraApilada(tramos) {
  const caja = nodo("div", "apilada");
  const total = tramos.reduce((s, t) => s + t.valor, 0) || 1;
  tramos.forEach((t) => {
    if (!t.valor) return;
    const parte = nodo("span", t.clase || "");
    parte.style.width = `${(t.valor / total) * 100}%`;
    if (t.color) parte.style.background = t.color;
    parte.title = `${t.etiqueta}: ${miles(t.valor)} (${pct((t.valor / total) * 100)})`;
    caja.appendChild(parte);
  });
  return caja;
}

/* Rejilla de cuadritos, uno por elemento: cuenta visual de «cuántos de cuántos». */
function rejillaCuenta(elementos) {
  const caja = nodo("div", "rejilla-cuenta");
  elementos.forEach((e) => {
    const c = nodo("span", e.clase || "");
    c.title = e.titulo || "";
    caja.appendChild(c);
  });
  return caja;
}

/* Minigráfica de área sin ejes (sparkline). */
function minigrafica(valores, color = PALETA.cian) {
  const ancho = 200, alto = 28;
  const svg = svgEl("svg", { viewBox: `0 0 ${ancho} ${alto}`, preserveAspectRatio: "none",
                            class: "minigrafica", "aria-hidden": "true" });
  if (valores.length < 2) return svg;
  const max = Math.max(...valores, 1);
  const puntos = valores.map((v, i) =>
    `${(i / (valores.length - 1)) * ancho},${alto - 1 - (v / max) * (alto - 3)}`);
  svg.appendChild(svgEl("path", { d: `M0,${alto} L${puntos.join(" L")} L${ancho},${alto} Z`,
                                  fill: color, opacity: .18 }));
  svg.appendChild(svgEl("polyline", { points: puntos.join(" "), fill: "none", stroke: color,
                                      "stroke-width": 1.5, "vector-effect": "non-scaling-stroke" }));
  return svg;
}

/* --------------------------------------------------------------------------
   Rendimiento por sección: peso en el fondo y uso relativo, fila a fila.
   Uso relativo = % prestado de la sección / % prestado del conjunto (1,0 =
   la sección rinde lo que pesa). Método de uso relativo de Bonn (1974) y
   «percentage of expected use» de Mills (1981), adaptado a préstamo sí/no.
   Solo caben las filas que permite el alto; el resto se agrupa en «Otras».
   -------------------------------------------------------------------------- */
function graficoRendimiento(filas, opciones) {
  const { ancho, alto, tasaGlobal, minimo = 20, seleccion, alPulsar, textos } = opciones;
  const cabecera = 24;
  const altoFilaMin = 21;
  const capacidad = Math.max(3, Math.floor((alto - cabecera - 4) / altoFilaMin));

  let visibles = filas;
  if (filas.length > capacidad) {
    visibles = filas.slice(0, capacidad - 1);
    const resto = filas.slice(capacidad - 1);
    const vol = resto.reduce((s, f) => s + f.volumenes, 0);
    const prest = resto.reduce((s, f) => s + f.prestados, 0);
    visibles.push({
      clave: null, etiqueta: textos.otras(resto.length), volumenes: vol, prestados: prest,
      peso: resto.reduce((s, f) => s + f.peso, 0),
      usoRel: vol && tasaGlobal ? (prest / vol) / tasaGlobal : null, agregada: true,
    });
  }
  const altoFila = Math.min(30, (alto - cabecera - 4) / visibles.length);

  const svg = lienzo(ancho, alto, textos.titulo);
  svg.classList.add("rendimiento");
  const xEtiqueta = 8;
  const anchoEtiqueta = Math.min(200, Math.max(110, ancho * .28));
  const x0Peso = anchoEtiqueta + 14;
  const anchoPeso = Math.max(70, (ancho - x0Peso) * .34);
  const x0Uso = x0Peso + anchoPeso + 58;
  const anchoUso = Math.max(80, ancho - x0Uso - 52);
  const maxPeso = Math.max(...visibles.map((f) => f.peso), 1);
  const TOPE = 2;
  const xUso = (v) => x0Uso + (Math.min(v, TOPE) / TOPE) * anchoUso;
  const xUno = xUso(1);

  const rotulo = (x, texto, ancla = "start") => svg.appendChild(svgEl("text", {
    x, y: 14, "text-anchor": ancla, class: "rotulo-columna" }, texto));
  rotulo(xEtiqueta, textos.seccion);
  rotulo(x0Peso, textos.peso);
  rotulo(x0Uso, textos.uso);
  svg.appendChild(svgEl("text", { x: xUno, y: 14, "text-anchor": "middle", class: "rotulo-columna fuerte" }, numeroDecimal(1, 1)));

  // Línea de referencia 1,0 a lo largo de todas las filas
  svg.appendChild(svgEl("line", { x1: xUno, x2: xUno, y1: cabecera - 4,
                                  y2: cabecera + visibles.length * altoFila, class: "linea-referencia" }));

  visibles.forEach((f, i) => {
    const y = cabecera + i * altoFila;
    const medio = y + altoFila / 2;
    const grupo = svgEl("g", { class: `fila-rendimiento${f.agregada ? " agregada" : ""}${f.clave && f.clave === seleccion ? " activa" : ""}` });
    grupo.appendChild(svgEl("rect", { x: 0, y, width: ancho, height: altoFila, class: "fondo-fila" }));

    const etiqueta = f.etiqueta.length > 30 ? `${f.etiqueta.slice(0, 29)}…` : f.etiqueta;
    grupo.appendChild(svgEl("text", { x: xEtiqueta, y: medio + 4, class: "etiqueta-fila" }, etiqueta));

    // Peso en el fondo
    const grosor = Math.min(12, altoFila - 8);
    grupo.appendChild(svgEl("rect", { x: x0Peso, y: medio - grosor / 2, height: grosor, rx: 2,
                                      width: Math.max(2, (f.peso / maxPeso) * anchoPeso), class: "barra-peso" }));
    grupo.appendChild(svgEl("text", { x: x0Peso + anchoPeso + 50, y: medio + 4, "text-anchor": "end",
                                      class: "valor-mono" }, pct(f.peso)));

    // Uso relativo, divergente desde 1,0
    if (f.usoRel !== null && f.usoRel !== undefined) {
      const v = f.usoRel;
      const desde = Math.min(xUno, xUso(v));
      const largo = Math.max(2, Math.abs(xUso(v) - xUno));
      const pequena = !f.agregada && f.volumenes < minimo;
      const barra = svgEl("rect", { x: desde, y: medio - grosor / 2, width: largo, height: grosor, rx: 2,
        class: `barra-uso ${v >= 1 ? "encima" : "debajo"}${pequena ? " pequena" : ""}` });
      grupo.appendChild(barra);
      if (v > TOPE) {
        const xp = xUso(TOPE);
        grupo.appendChild(svgEl("path", { d: `M${xp},${medio - grosor / 2 - 2} l6,${grosor / 2 + 2} l-6,${grosor / 2 + 2} Z`,
                                          class: "barra-uso encima" }));
      }
      grupo.appendChild(svgEl("text", { x: ancho - 6, y: medio + 4, "text-anchor": "end",
        class: `valor-mono${pequena ? " tenue" : ""}` },
        `${numeroDecimal(v, 2)}${pequena ? "*" : ""}`));
    }

    const titulo = textos.detalle(f);
    grupo.appendChild(svgEl("title", {}, titulo));
    if (!f.agregada && alPulsar) {
      grupo.classList.add("pulsable");
      grupo.setAttribute("tabindex", "0");
      grupo.setAttribute("role", "button");
      grupo.setAttribute("aria-label", titulo);
      grupo.addEventListener("click", () => alPulsar(f.clave));
      grupo.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); alPulsar(f.clave); } });
    }
    svg.appendChild(grupo);
  });
  return svg;
}

/* Columnas por año de edición, coloreadas por el % prestado de cada año
   (el patrón de GreenGlass): una sola escala vertical, sin doble eje. */
function graficoAniosUso(puntos, { ancho, alto, titulo }) {
  const svg = lienzo(ancho, alto, titulo);
  const m = { arriba: 10, derecha: 8, abajo: 22, izquierda: 40 };
  const w = ancho - m.izquierda - m.derecha;
  const h = alto - m.arriba - m.abajo;
  const maximo = Math.max(...puntos.map((p) => p.volumenes), 1);
  const tramos = Math.max(1, Math.min(4, Math.floor(h / 30)));
  for (let i = 0; i <= tramos; i++) {
    const py = m.arriba + (h / tramos) * i;
    svg.appendChild(svgEl("line", { x1: m.izquierda, y1: py, x2: m.izquierda + w, y2: py,
                                    class: i === tramos ? "eje" : "rejilla-linea" }));
    svg.appendChild(svgEl("text", { x: m.izquierda - 7, y: py + 3.5, "text-anchor": "end", class: "valor-mono" },
      miles(Math.round((maximo / tramos) * (tramos - i)))));
  }
  const paso = w / puntos.length;
  const grosor = Math.max(1, paso - Math.min(3, paso * .25));
  const salto = Math.max(1, Math.ceil(puntos.length / Math.max(2, Math.floor(w / 56))));
  puntos.forEach((p, i) => {
    const alturaBarra = (p.volumenes / maximo) * h;
    const x = m.izquierda + i * paso + (paso - grosor) / 2;
    const barra = svgEl("rect", { x, y: m.arriba + h - alturaBarra, width: grosor, height: Math.max(0, alturaBarra),
                                  rx: Math.min(2, grosor / 3), fill: colorUso(p.tasa) });
    barra.appendChild(svgEl("title", {}, p.detalle));
    svg.appendChild(barra);
    if (i % salto === 0) {
      svg.appendChild(svgEl("text", { x: x + grosor / 2, y: m.arriba + h + 15, "text-anchor": "middle",
                                      class: "etiqueta-eje" }, String(p.anio)));
    }
  });
  return svg;
}

/* --------------------------------------------------------------------------
   Barras de volumen coloreadas por uso: la gramática de Secciones.
   Longitud = volúmenes, color = % prestado (misma escala que el treemap).
   Solo se pintan las filas que caben; el resto se agrupa en «Otras».
   -------------------------------------------------------------------------- */
function graficoBarrasUso(filas, opciones) {
  const { ancho, alto, seleccion, alPulsar, textos } = opciones;
  const altoFilaMin = 17;
  const capacidad = Math.max(2, Math.floor((alto - 4) / altoFilaMin));
  let visibles = filas.slice();
  if (filas.length > capacidad) {
    visibles = filas.slice(0, capacidad - 1);
    const resto = filas.slice(capacidad - 1);
    const vol = resto.reduce((s, f) => s + f.volumenes, 0);
    const prest = resto.reduce((s, f) => s + f.prestados, 0);
    visibles.push({ clave: null, etiqueta: textos.otras(resto.length), volumenes: vol, prestados: prest,
                    tasa: vol ? (prest / vol) * 100 : 0, agregada: true });
  }
  const altoFila = Math.min(28, (alto - 4) / visibles.length);
  const svg = lienzo(ancho, alto, textos.titulo);
  svg.classList.add("barras-uso");
  const anchoEtiqueta = Math.min(150, Math.max(70, ancho * .26));
  const x0 = anchoEtiqueta + 10;
  const anchoValor = 96;
  const anchoBarra = Math.max(40, ancho - x0 - anchoValor);
  const maximo = Math.max(...visibles.map((f) => f.volumenes), 1);

  visibles.forEach((f, i) => {
    const y = 2 + i * altoFila;
    const medio = y + altoFila / 2;
    const activa = f.clave !== null && seleccion !== undefined && String(f.clave) === String(seleccion);
    const grupo = svgEl("g", { class: `fila-barra${f.agregada ? " agregada" : ""}${activa ? " activa" : ""}` });
    grupo.appendChild(svgEl("rect", { x: 0, y, width: ancho, height: altoFila, class: "fondo-fila" }));
    const etiqueta = f.etiqueta.length > 22 ? `${f.etiqueta.slice(0, 21)}…` : f.etiqueta;
    grupo.appendChild(svgEl("text", { x: anchoEtiqueta, y: medio + 4, "text-anchor": "end", class: "etiqueta-fila" }, etiqueta));
    const grosor = Math.min(13, altoFila - 7);
    grupo.appendChild(svgEl("rect", { x: x0, y: medio - grosor / 2, width: Math.max(2, (f.volumenes / maximo) * anchoBarra),
                                      height: grosor, rx: 2, fill: opciones.color ? opciones.color(f) : colorUso(f.tasa) }));
    grupo.appendChild(svgEl("text", { x: ancho - 4, y: medio + 4, "text-anchor": "end", class: "valor-mono" },
      opciones.texto ? opciones.texto(f) : `${miles(f.volumenes)} · ${pct(f.tasa)}`));
    const titulo = textos.detalle(f);
    grupo.appendChild(svgEl("title", {}, titulo));
    if (!f.agregada && alPulsar) {
      grupo.classList.add("pulsable");
      grupo.setAttribute("tabindex", "0");
      grupo.setAttribute("role", "button");
      grupo.setAttribute("aria-label", titulo);
      const pulsar = () => alPulsar(activa ? null : f.clave);
      grupo.addEventListener("click", pulsar);
      grupo.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pulsar(); } });
    }
    svg.appendChild(grupo);
  });
  return svg;
}

/* «1 de cada 3»: una proporción dicha en palabras, sin juicio de valor.
   Busca la fracción de denominador más pequeño (hasta 10) que se acerca lo
   bastante; por debajo del 10 % usa «1 de cada N». */
function fraccionLegible(porcentaje) {
  const p = Number(porcentaje) / 100;
  if (!Number.isFinite(p) || p <= 0) return null;
  if (p >= .995) return { a: 1, b: 1, todos: true };
  if (p < .1) return { a: 1, b: Math.round(1 / p) };
  let mejor = null;
  for (let b = 2; b <= 10; b++) {
    const a = Math.min(b - 1, Math.max(1, Math.round(p * b)));
    const error = Math.abs(a / b - p);
    if (error <= .015) return { a, b };
    if (!mejor || error < mejor.error) mejor = { a, b, error };
  }
  return { a: mejor.a, b: mejor.b };
}

function textoFraccion(porcentaje) {
  const f = fraccionLegible(porcentaje);
  if (!f) return null;
  return f.todos ? t("fraccion_todos") : t("fraccion", { a: f.a, b: f.b });
}

/* Tramos de antigüedad a partir del histograma por año de /buscar. */
function tramosEdad(anios, anioActual) {
  const filas = anios.filas;
  const conAnio = filas.reduce((s, f) => s + f.volumenes, 0) + anios.anteriores;
  const recientes = filas.filter((f) => f.clave >= anioActual - 4).reduce((s, f) => s + f.volumenes, 0);
  const antiguos = filas.filter((f) => f.clave < anioActual - 20).reduce((s, f) => s + f.volumenes, 0) + anios.anteriores;
  return { conAnio, recientes, antiguos, intermedios: conAnio - recientes - antiguos,
           sinAnio: anios.sin_anio, anteriores: anios.anteriores };
}

/* --------------------------------------------------------------------------
   Ayuda desplegable («?»). Se abre en posición fija para que no la recorte
   el cuadro que la contiene; un clic fuera la cierra.
   -------------------------------------------------------------------------- */
function ayudaDesplegable(titulo, parrafos, clase = "") {
  const d = nodo("details", `ayuda ${clase}`.trim());
  const s = nodo("summary", null, "?");
  s.title = titulo;
  s.setAttribute("aria-label", titulo);
  const caja = nodo("div", "ayuda-caja");
  caja.setAttribute("role", "note");
  caja.appendChild(nodo("strong", null, titulo));
  parrafos.forEach((p) => caja.appendChild(nodo("p", null, p)));
  d.append(s, caja);
  d.addEventListener("toggle", () => {
    if (!d.open) return;
    const r = s.getBoundingClientRect();
    const anchoCaja = Math.min(d.classList.contains("ayuda-larga") ? 480 : 320, window.innerWidth - 24);
    caja.style.width = `${anchoCaja}px`;
    caja.style.left = `${Math.max(12, Math.min(r.right - anchoCaja, window.innerWidth - anchoCaja - 12))}px`;
    caja.style.top = `${r.bottom + 6}px`;
  });
  return d;
}

document.addEventListener("click", (e) => {
  document.querySelectorAll("details.ayuda[open]").forEach((d) => { if (!d.contains(e.target)) d.open = false; });
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") document.querySelectorAll("details.ayuda[open]").forEach((d) => { d.open = false; });
});

function ayudaUsoRelativo(extra = []) {
  // Las aclaraciones de los gráficos viven aquí, a demanda, y no como notas fijas
  return ayudaDesplegable(t("ayuda_uso_titulo"),
    [t("ayuda_uso_1"), t("ayuda_uso_2"), t("ayuda_uso_3"), t("ayuda_uso_4"), ...extra]);
}

/* --------------------------------------------------------------------------
   Matriz de compra: cada sección propia según su actualidad (eje X, % del
   fondo editado en los últimos 5 años) y su uso relativo (eje Y). El tamaño
   del círculo es la oferta de la red (títulos candidatos). El cuadrante
   superior izquierdo reúne más demanda que peso con un fondo menos
   actualizado: donde una compra tiene más recorrido.
   -------------------------------------------------------------------------- */
function graficoMatrizCompra(puntos, opciones) {
  const { ancho, alto, seleccion, alPulsar, textos, corteX } = opciones;
  const svg = lienzo(ancho, alto, textos.titulo);
  svg.classList.add("matriz-compra");
  const m = { arriba: 12, derecha: 14, abajo: 30, izquierda: 40 };
  const w = ancho - m.izquierda - m.derecha;
  const h = alto - m.arriba - m.abajo;
  const maxX = Math.max(10, ...puntos.map((p) => p.x)) * 1.08;
  const maxY = Math.min(3, Math.max(2, ...puntos.map((p) => p.y)) * 1.05);
  const X = (v) => m.izquierda + (Math.min(v, maxX) / maxX) * w;
  const Y = (v) => m.arriba + h - (Math.min(v, maxY) / maxY) * h;
  const maxOferta = Math.max(1, ...puntos.map((p) => p.oferta));
  const radio = (v) => 4 + Math.sqrt(v / maxOferta) * Math.min(22, h / 7);

  // Cuadrante prioritario sombreado + rótulos de cuadrante, muy discretos
  svg.appendChild(svgEl("rect", { x: m.izquierda, y: m.arriba, width: X(corteX) - m.izquierda, height: Y(1) - m.arriba,
                                  class: "cuadrante-prioritario" }));
  const rotuloCuadrante = (x, y, texto, ancla, clase = "") => svg.appendChild(svgEl("text",
    { x, y, "text-anchor": ancla, class: `rotulo-cuadrante ${clase}` }, texto));
  rotuloCuadrante(m.izquierda + 6, m.arriba + 13, textos.cuadrante, "start", "fuerte");

  // Ejes y referencias
  for (let i = 0; i <= 4; i++) {
    const vx = (maxX / 4) * i;
    svg.appendChild(svgEl("text", { x: X(vx), y: m.arriba + h + 14, "text-anchor": "middle", class: "etiqueta-eje" },
      `${Math.round(vx)}%`));
  }
  [0, 1, 2, 3].filter((v) => v <= maxY).forEach((v) => {
    svg.appendChild(svgEl("text", { x: m.izquierda - 7, y: Y(v) + 3.5, "text-anchor": "end", class: "etiqueta-eje" },
      numeroDecimal(v, 1)));
  });
  svg.appendChild(svgEl("line", { x1: m.izquierda, x2: m.izquierda + w, y1: m.arriba + h, y2: m.arriba + h, class: "eje" }));
  svg.appendChild(svgEl("line", { x1: m.izquierda, x2: m.izquierda + w, y1: Y(1), y2: Y(1), class: "linea-referencia" }));
  svg.appendChild(svgEl("line", { x1: X(corteX), x2: X(corteX), y1: m.arriba, y2: m.arriba + h, class: "linea-referencia" }));
  svg.appendChild(svgEl("text", { x: m.izquierda + w, y: m.arriba + h + 27, "text-anchor": "end", class: "titulo-eje" }, textos.ejeX));
  svg.appendChild(svgEl("text", { x: X(corteX) + 4, y: m.arriba + h - 4, class: "etiqueta-eje" }, textos.mediana));

  // Burbujas: primero las grandes, para que las pequeñas queden encima
  const orden = puntos.slice().sort((a, b) => b.oferta - a.oferta);
  const rotular = new Set(orden.filter((p) => p.y >= 1 && p.x < corteX).slice(0, 6).map((p) => p.clave));
  if (seleccion) rotular.add(seleccion);
  orden.forEach((p) => {
    const activa = seleccion && p.clave === seleccion;
    const g = svgEl("g", { class: `burbuja ${p.y >= 1 ? "encima" : "debajo"}${activa ? " activa" : ""}${seleccion && !activa ? " atenuada" : ""}` });
    g.appendChild(svgEl("circle", { cx: X(p.x), cy: Y(p.y), r: p.oferta ? radio(p.oferta) : 3.5,
                                    class: p.oferta ? "" : "sin-oferta" }));
    g.appendChild(svgEl("title", {}, textos.detalle(p)));
    if (alPulsar) {
      g.setAttribute("tabindex", "0");
      g.setAttribute("role", "button");
      g.setAttribute("aria-label", textos.detalle(p));
      const pulsar = () => alPulsar(activa ? "" : p.clave);
      g.addEventListener("click", pulsar);
      g.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pulsar(); } });
    }
    svg.appendChild(g);
  });
  // Rótulos al final, por encima de las burbujas, sin pisarse entre sí: se
  // prueba a la derecha y a la izquierda; si no cabe, se omite (el nombre
  // sigue en la ayuda emergente). La sección elegida se rotula siempre.
  const ocupados = [{ x0: m.izquierda, x1: m.izquierda + 250, y0: m.arriba, y1: m.arriba + 16 }];
  const choca = (c) => ocupados.some((o) => c.x0 < o.x1 && c.x1 > o.x0 && c.y0 < o.y1 && c.y1 > o.y0);
  const candidatos = orden.filter((p) => rotular.has(p.clave))
    .sort((a, b) => (b.clave === seleccion) - (a.clave === seleccion));
  candidatos.forEach((p) => {
    const r = p.oferta ? radio(p.oferta) : 3.5;
    const texto = p.etiqueta.length > 24 ? `${p.etiqueta.slice(0, 23)}…` : p.etiqueta;
    const anchoTexto = texto.length * 5.9;
    const cx = X(p.x), cy = Y(p.y);
    const opciones = [
      { x: cx + r + 4, ancla: "start", x0: cx + r + 4, x1: cx + r + 4 + anchoTexto },
      { x: cx - r - 4, ancla: "end", x0: cx - r - 4 - anchoTexto, x1: cx - r - 4 },
    ].map((o) => ({ ...o, y0: cy - 8, y1: cy + 6 }))
      .filter((o) => o.x0 >= 0 && o.x1 <= ancho);
    const libre = opciones.find((o) => !choca(o)) || (p.clave === seleccion ? opciones[0] : null);
    if (!libre) return;
    ocupados.push(libre);
    svg.appendChild(svgEl("text", { x: libre.x, y: cy + 4, "text-anchor": libre.ancla,
      class: `rotulo-burbuja${p.clave === seleccion ? " activa" : ""}` }, texto));
  });
  return svg;
}


/* --- Hilo de respuestas bajo un comentario --------------------------------- */
function hiloRespuestas(valoracion, miBiblioteca, alResponder, alBorrarRespuesta) {
  const caja = nodo("div", "hilo");
  (valoracion.respuestas || []).forEach((r) => {
    const item = nodo("div", `respuesta${r.biblioteca === miBiblioteca ? " propia" : ""}`);
    const cabeza = nodo("div", "cabeza");
    cabeza.append(nodo("span", "quien", r.biblioteca), nodo("span", "cuando", fechaCorta(r.creado)));
    if (r.biblioteca === miBiblioteca && alBorrarRespuesta) {
      const borrar = nodo("button", "enlace-discreto", t("borrar"));
      borrar.addEventListener("click", () => alBorrarRespuesta(r.id));
      cabeza.appendChild(borrar);
    }
    item.appendChild(cabeza);
    item.appendChild(nodo("div", "texto", r.texto));   // textContent: nunca HTML de terceros
    caja.appendChild(item);
  });
  const abrir = nodo("button", "enlace-discreto", t("responder"));
  const formulario = nodo("div", "formulario-respuesta oculto");
  const area = nodo("textarea");
  area.maxLength = 1000;
  area.rows = 2;
  area.placeholder = t("placeholder_respuesta", { n: valoracion.biblioteca });
  const enviar = nodo("button", "boton pequeno", t("enviar"));
  const error = nodo("div", "aviso error oculto");
  enviar.addEventListener("click", async () => {
    if (!area.value.trim()) return;
    enviar.disabled = true;
    try { await alResponder(valoracion.id, area.value); }
    catch (e) { error.textContent = e.message; error.classList.remove("oculto"); enviar.disabled = false; }
  });
  abrir.addEventListener("click", () => { formulario.classList.toggle("oculto"); area.focus(); });
  formulario.append(area, enviar, error);
  caja.append(abrir, formulario);
  return caja;
}

/* «hace 3 días»: la actividad se lee mejor en tiempo relativo. */
function fechaRelativa(iso) {
  const f = new Date(iso);
  if (Number.isNaN(f.getTime())) return "";
  const segundos = (f.getTime() - Date.now()) / 1000;
  const unidades = [["year", 31536000], ["month", 2592000], ["week", 604800], ["day", 86400], ["hour", 3600], ["minute", 60]];
  try {
    const rtf = new Intl.RelativeTimeFormat(IDIOMA || "es", { numeric: "auto" });
    for (const [unidad, s] of unidades) {
      if (Math.abs(segundos) >= s || unidad === "minute") return rtf.format(Math.round(segundos / s), unidad);
    }
  } catch { /* navegador sin RelativeTimeFormat */ }
  return fechaCorta(iso);
}


/* ==========================================================================
   Apariencia: tema (oscuro / claro) y paleta de los gráficos
   Los gráficos SVG leen sus colores de PALETA y ESCALA_USO al dibujarse, y el
   CSS de las variables de :root; aplicarApariencia cambia las dos cosas y la
   vista se vuelve a pintar.
   ========================================================================== */
const TEMAS = {
  oscuro: { texto: "#EDEDF0", suave: "#B3B3BD", tenue: "#8C8C97", borde: "#2A2A31", bordeSuave: "#1F1F25",
            panel: "#131316", panelAlto: "#1B1B20", fondo: "#0A0A0C", gris: "#5A5A66", logo: "imagenes/completo-negativo.svg" },
  claro: { texto: "#16181D", suave: "#434852", tenue: "#5C626D", borde: "#D6D9DF", bordeSuave: "#E4E6EA",
           panel: "#FFFFFF", panelAlto: "#F1F2F5", fondo: "#F6F7F9", gris: "#A3A8B1", logo: "imagenes/completo.svg" },
};

// Tres paletas, todas legibles con las formas más comunes de daltonismo.
// escala: de menos a más uso; encima / debajo: más o menos demanda que peso.
const PALETAS_GRAFICOS = {
  okabe: { escala: ["#15406A", "#1F72B8", "#56B4E9", "#F2C46D", "#E69F00"], encima: "#E69F00", debajo: "#56B4E9" },
  viridis: { escala: ["#440154", "#3B528B", "#21918C", "#5EC962", "#FDE725"], encima: "#35B779", debajo: "#3B528B" },
  azules: { escala: ["#1B2A3A", "#2F4F6F", "#4F7EA8", "#8DB3D6", "#CFE0EF"], encima: "#4F7EA8", debajo: "#B7CDE3" },
};

function aplicarApariencia(prefs) {
  const tema = TEMAS[prefs.tema] ? prefs.tema : "oscuro";
  const paleta = PALETAS_GRAFICOS[prefs.paleta] || PALETAS_GRAFICOS.okabe;
  const raiz = document.documentElement;
  raiz.dataset.tema = tema;
  raiz.style.colorScheme = tema === "claro" ? "light" : "dark";
  const { logo, ...neutros } = TEMAS[tema];
  Object.assign(PALETA, neutros);
  ESCALA_USO = paleta.escala.slice();
  PALETA.usoEncima = paleta.encima;
  PALETA.usoDebajo = paleta.debajo;
  raiz.style.setProperty("--uso-encima", paleta.encima);
  raiz.style.setProperty("--uso-debajo", paleta.debajo);
  // Para texto, en el tema claro se oscurece el color: sobre blanco, un
  // naranja o un azul claros no alcanzan el contraste mínimo.
  const oscurecer = tema === "claro" ? .38 : 0;
  raiz.style.setProperty("--uso-encima-texto", mezclar(paleta.encima, "#000000", oscurecer));
  raiz.style.setProperty("--uso-debajo-texto", mezclar(paleta.debajo, "#000000", oscurecer));
  raiz.style.setProperty("--escala-uso", `linear-gradient(90deg, ${paleta.escala.join(", ")})`);
  document.querySelectorAll("img[data-logo]").forEach((img) => { img.src = logo; });
}

/* --------------------------------------------------------------------------
   Evolución entre cargas: línea con un punto por carga. Los huecos (cargas
   sin el dato, p. ej. sin listado de no prestados) cortan la línea en vez de
   inventar un valor.
   -------------------------------------------------------------------------- */
function graficoEvolucion(puntos, { ancho, alto, color, formato, titulo }) {
  const svg = lienzo(ancho, alto, titulo);
  const valores = puntos.map((p) => p.valor).filter((v) => v !== null && v !== undefined);
  if (!valores.length) return svg;
  let min = Math.min(...valores), max = Math.max(...valores);
  // Margen izquierdo según el rótulo más largo del eje (unos 6,6 px por carácter)
  const rotuloMasLargo = Math.max(formato(min).length, formato(max).length);
  const m = { arriba: 14, derecha: 14, abajo: 20, izquierda: Math.max(34, rotuloMasLargo * 6.6 + 12) };
  const w = ancho - m.izquierda - m.derecha;
  const h = alto - m.arriba - m.abajo;
  const margen = (max - min) * .15 || Math.max(1, Math.abs(max) * .05);
  min -= margen; max += margen;
  const X = (i) => m.izquierda + (puntos.length === 1 ? w / 2 : (i / (puntos.length - 1)) * w);
  const Y = (v) => m.arriba + h - ((v - min) / (max - min)) * h;
  [min + margen, max - margen].forEach((v) => {
    svg.appendChild(svgEl("line", { x1: m.izquierda, x2: m.izquierda + w, y1: Y(v), y2: Y(v), class: "rejilla-linea" }));
    svg.appendChild(svgEl("text", { x: m.izquierda - 6, y: Y(v) + 3.5, "text-anchor": "end", class: "valor-mono" }, formato(v)));
  });
  let tramo = [];
  const cerrarTramo = () => {
    if (tramo.length > 1) svg.appendChild(svgEl("polyline", { points: tramo.join(" "), fill: "none", stroke: color, "stroke-width": 2 }));
    tramo = [];
  };
  puntos.forEach((p, i) => {
    if (p.valor === null || p.valor === undefined) { cerrarTramo(); return; }
    tramo.push(`${X(i)},${Y(p.valor)}`);
  });
  cerrarTramo();
  const salto = Math.max(1, Math.ceil(puntos.length / Math.max(2, Math.floor(w / 70))));
  puntos.forEach((p, i) => {
    const fecha = new Date(p.fecha).toLocaleDateString(LOCALE_FECHAS[IDIOMA] || "es-ES", { day: "numeric", month: "short", year: "2-digit" });
    if (p.valor !== null && p.valor !== undefined) {
      const c = svgEl("circle", { cx: X(i), cy: Y(p.valor), r: 3.5, fill: color });
      c.appendChild(svgEl("title", {}, `${fecha}: ${formato(p.valor)}`));
      svg.appendChild(c);
    }
    if (i % salto === 0 || i === puntos.length - 1) {
      // Los extremos se alinean hacia dentro para que no se corten
      const ancla = puntos.length > 1 && i === 0 ? "start" : puntos.length > 1 && i === puntos.length - 1 ? "end" : "middle";
      svg.appendChild(svgEl("text", { x: X(i), y: m.arriba + h + 15, "text-anchor": ancla, class: "etiqueta-eje" }, fecha));
    }
  });
  return svg;
}
