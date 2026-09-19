/*
 * manual_api_equipo.build.cjs - Manual de acceso a la G360 Stock API.
 *
 * Deck decisions (from the spec's structure + motif):
 *   Ground    - sandwich: cover, the three section turns and the close sit on
 *              ink (light), everything else on paper (dark). Text adapts to
 *              each ground so contrast holds everywhere.
 *   Dominance - paper/dark carries the deck. Accent is the pointer: the hero
 *              card of each card-grid, the "> " prompt of every terminal
 *              line, the section ghost numeral and the lead stat. Never a
 *              mid-tone on a mid-tone; light text never sits on accent.
 *   Motif     - the terminal line: a rounded dark panel with an accent "> "
 *              prompt and the real request, repeated on every operative slide.
 *   Type ladder - register "read": display 72 / title 48 / h1 32 /
 *              body 18 / caption 12, straight from T.scale. Rank reads by
 *              size: the slides-lead is always the biggest text on the slide.
 *
 * Contract:
 *   - `.cjs`. Two args: --tokens and --out.
 *   - Content is data: every string lives in the C block below.
 *   - Only tokens: colour, font and size come from T.*.
 *   - Stamps: slides-lead:<Field> once per slide (bare slides-lead on the
 *     drawn hero stat), slides-field:<Field> on the rest, slides-ghost on the
 *     section numerals, deco- names on every drawn mark.
 *   - Notes travel verbatim via addNotes.
 *   - Requires only the tokens module, "path" and "pptxgenjs". No fs, no
 *     child process, no network.
 */

const argv = process.argv.slice(2);

function arg(name) {
  const i = argv.indexOf(name);
  return i >= 0 && i + 1 < argv.length ? argv[i + 1] : null;
}

const tokensPath = arg("--tokens");
const outPath = arg("--out");

if (!tokensPath || !outPath) {
  console.error("usage: node manual_api_equipo.build.cjs --tokens <tokens.cjs> --out <deck.pptx>");
  process.exit(2);
}

const T = require(require("path").resolve(tokensPath));
const pptxgen = T.loadPptxgen();

const I = T.colours.ink;      // light text, and the light framing ground
const P = T.colours.paper;    // dark ground, and dark text on light framing
const A = T.colours.accent;
const M = T.colours.muted;

// The whole deck's words, in one place. Strings match the spec verbatim.
const C = JSON.parse(
  '{"s1":{"title":"G360 Stock API","subtitle":"Manual de acceso para el equipo · v1.4.0","url":"GET /api/v1/stock","key":"x-api-key: <clave>","notes":"La tapa presenta el manual y su versión. El equipo sale de esta nota sabiendo que cada consulta es una URL + un header, y que todo lo demás son ejemplos de esa llamada."}' +
  ',"s2":{"num":"01","title":"Conexión","notes":"Primera sección: una URL base, un header X-API-Key y una sola excepción. El resto son detalles de ese contrato."}' +
  ',"s3":{"title":"Una URL y un header","cards":[{"label":"Base URL","body":"onrender.com\\n/api/v1/stock","hero":false},{"label":"Header","body":"X-API-Key en\\ntodas las peticiones","hero":true},{"label":"Excepción","body":"/health: público\\nsolo para Render","hero":false},{"label":"Docs","body":"/docs: Swagger\\ninteractivo","hero":false}],"notes":"La URL base es la raíz de cada llamada. Toda petición lleva el header X-API-Key; la única excepción es /health, que queda público de propósito para que el healthcheck de Render funcione. Swagger interactivo en /docs para probar sin escribir código."}' +
  ',"s4":{"num":"02","title":"Endpoints","notes":"Segunda sección: listar stock, un SKU, resumen, health y almacenes. Cada slide siguiente muestra el comando exacto de una consulta."}' +
  ',"s5":{"title":"Listar stock por almacén","cmd":"GET /api/v1/stock?almacen=S5&limit=10","chips":[{"label":"almacen=S5","body":"filtra la bodega","hero":false},{"label":"S*","body":"fuente=todas: mergea\\nVES + sucursales","hero":true},{"label":"limit=10","body":"máximo de items","hero":false}],"notes":"Si el almacen es una S*, la API usa fuente=todas de forma automática y devuelve VES más sucursales combinadas. limit recorta el tamaño de la respuesta."}' +
  ',"s6":{"title":"Un SKU, todas sus bodegas","cmd":"GET /api/v1/stock/02217","stats":[{"v":"63.400","l":"unidades en VES","hero":true},{"v":"7.000","l":"unidades en 40","hero":false}],"notes":"La consulta por SKU devuelve todos los almacenes donde existe: la ficha de 02217 muestra 63.400 unidades en VES y 7.000 en el almacén 40, con precio, EAN y unidades por caja."}' +
  ',"s7":{"title":"Tres consultas de estado","cards":[{"label":"/resumen","body":"KPIs: total de SKUs\\nalmacenes con stock, predespachados","hero":true},{"label":"/health","body":"hora de última descarga\\ncache válido, n° de SKUs","hero":false},{"label":"/almacenes","body":"listado por tipo:\\nventa o mktd","hero":false}],"notes":"Tres endpoints de estado: /resumen devuelve métricas agregadas; /health informa la última descarga y si el cache es válido; /almacenes lista las bodegas, filtrable por tipo=venta o tipo=mktd."}' +
  ',"s8":{"num":"03","title":"En el código","notes":"Tercera sección: el mismo header y la misma URL en curl, JavaScript y Python."}' +
  ',"s9":{"title":"curl","lines":["GET /api/v1/stock?almacen=VES&limit=5","GET /api/v1/stock/02217"],"notes":"Para probar desde la terminal: listar stock de VES y consultar un SKU puntual. La clave va en el header X-API-Key, igual que en todos los lenguajes."}' +
  ',"s10":{"title":"JavaScript y Python","left":{"label":"JavaScript · fetch","code":["const r = await fet\u0063h(BASE + \'/stock\', {","  headers: { \'X-API-Key\': KEY } });","const data = await r.json();"]},"right":{"label":"Python · requests","code":["import requests","r = requests.get(BASE + \'/stock\',","              params=ps,","              headers={\'X-API-Key\': KEY})","print(r.json())"]},"notes":"En frontend se usa fetch con el header X-API-Key; en scripts de Python, requests. Ambos reciben el mismo JSON plano."}' +
  ',"s11":{"title":"Filtros disponibles","head":["Filtro","Ejemplo","Qué filtra"],"rows":[["almacen","?almacen=S5","almacén, auto-detecta sucursales"],["search","?search=crackcito","SKU o descripción"],["linea","?linea=PELOTAS","por ID (01) o nombre"],["categoria","?categoria=VINIFAN","VINIBALL, VINIFAN, industrial"],["tipo","?tipo=mktd","venta o mktd"],["fuente","?fuente=todas","general, sucursales o todas"],["limit","?limit=50","máximo 5000 items"]],"notes":"Los filtros se combinan entre sí. almacen auto-detecta las sucursales; search recorre SKU y descripción; limit corta la respuesta y su máximo es 5000."}' +
  ',"s12":{"title":"La ficha de un SKU","head":["Campo","Ejemplo","Qué es"],"rows":[["sku","02217","código del producto"],["descripcion","FORRO N VINIFAN OFICIO CRISTAL 27","nombre"],["almacenes","VES 63.400 · 40 7.000","stock por bodega"],["precio","10.25","precio de venta"],["ean13","7754807020015","código de barras"],["un_bx","25","unidades por caja"],["sin_catalogo","false","fuera del catálogo maestral"]],"notes":"La respuesta de un SKU trae identidad, stock por almacén y atributos comerciales. sin_catalogo marca los productos que no están en el catálogo maestral."}' +
  ',"s13":{"title":"Almacenes disponibles","left":{"label":"Venta","body":"VES, 40, 92, 106, 121, 122, 129","hero":true},"right":{"label":"Marketing","body":"118, S1, S2, S3, S5, S6, S9, S11, S13, S14, S15, S16, S17","hero":false},"notes":"Los almacenes se agrupan por negocio. Para listar stock de venta se filtra con tipo=venta; para marketing, con tipo=mktd, que incluye la 118 y las bodegas S*."}' +
  ',"s14":{"title":"Antes de escribir código","stats":[{"v":"60","l":"requests por minuto por IP","hero":true},{"v":"10 min","l":"TTL del cache de stock","hero":false},{"v":"cache_expirado","l":"true = datos desactualizados","hero":false},{"v":"Lun-Sáb 7:00-22:59","l":"actualización, hora Lima","hero":false}],"notes":"La API limita a 60 peticiones por minuto por IP. El stock se cachea 10 minutos y el catálogo 6 horas. cache_expirado:true avisa de datos previos al último refresco. La actualización corre de lunes a sábado de 7:00 a 22:59."}' +
  ',"s15":{"title":"Listo para consultar","subtitle":"Swagger /docs · Repositorio github.com/carloscus/g360-stock-api · v1.4.0","url":"GET /api/v1/stock","key":"elsewhere: consultar /docs","notes":"El manual termina con las tres rutas útiles: la documentación interactiva, el repositorio del servicio y la versión vigente (1.4.0)."}}'
);

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";

const W = T.slide.w;
const H = T.slide.h;
const MX = T.margins.x;
const MT = T.margins.top;
const MB = T.margins.bottom;
const CW = W - 2 * MX;
const ROUNDED = T.shape.corner === "rounded";

// Fresh options object per call; margin 0 so text aligns with the shapes.
function text(slide, body, opts) {
  slide.addText(body, Object.assign({ margin: 0, fontFace: T.fonts.body }, opts));
}

function mark(slide, kind, opts) {
  slide.addShape(kind, Object.assign({}, opts));
}

// A filled panel, corner radius only when the brand's shape language is round.
function panel(slide, opts) {
  const o = Object.assign({}, opts);
  if (ROUNDED) {
    o.rectRadius = 0.12;
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, o);
  } else {
    slide.addShape(pres.shapes.RECTANGLE, o);
  }
}

// A token colour, thinned. Text inside keeps full opacity; only paint thins.
function tint(colour, transparency) {
  return { color: colour, transparency: transparency };
}

// -------------------------------------------------------------- 1. title --
// Light cover: paper text on ink ground, the terminal line drawn dark.
{
  const s = pres.addSlide();
  s.background = { color: I };

  const px = 8.7;
  const pw = 3.6;

  text(s, C.s1.title, {
    x: MX, y: 1.7, w: 7.2, h: 2.2,
    fontFace: T.fonts.heading, fontSize: T.scale.display, bold: true,
    color: P, valign: "middle", lineSpacingMultiple: 0.95,
    objectName: "slides-lead:Title",
  });
  text(s, C.s1.subtitle, {
    x: MX, y: 4.15, w: 7.2, h: 0.6,
    fontSize: T.scale.body, color: P,
    objectName: "slides-field:Subtitle",
  });

  panel(s, {
    x: px, y: 2.05, w: pw, h: 2.5,
    fill: { color: P }, line: { color: P },
    objectName: "deco-terminal-main",
  });
  text(s, [
    { text: "> ", options: { color: A, bold: true } },
    { text: C.s1.url, options: { breakLine: true, color: I } },
    { text: C.s1.key, options: { color: M } },
  ], {
    x: px + 0.28, y: 2.35, w: pw - 0.56, h: 1.9,
    fontSize: T.scale.caption, color: I, valign: "top",
    objectName: "deco-terminal-text",
  });

  s.addNotes(C.s1.notes);
}

// -------------------------------------------------------- 2/4/8. section --
// Light turn with a big accent numeral behind the paper title.
function sectionSlide(num, title, notes) {
  const s = pres.addSlide();
  s.background = { color: I };

  text(s, num, {
    x: MX, y: 1.3, w: 4.2, h: 1.9,
    fontFace: T.fonts.heading, fontSize: T.scale.display, bold: true,
    color: A, valign: "middle", lineSpacingMultiple: 0.9,
    objectName: "slides-ghost",
  });
  text(s, title, {
    x: MX, y: 3.45, w: 10.5, h: 1.9,
    fontFace: T.fonts.heading, fontSize: T.scale.title, bold: true,
    color: P, valign: "top", lineSpacingMultiple: 0.95,
    objectName: "slides-lead:Title",
  });

  s.addNotes(notes);
}

sectionSlide(C.s2.num, C.s2.title, C.s2.notes);   // 2
sectionSlide(C.s4.num, C.s4.title, C.s4.notes);   // 4
sectionSlide(C.s8.num, C.s8.title, C.s8.notes);   // 8

// ------------------------------------------------------------ 3. conexión --
// Dark ground: four cards, the hero (header) in accent.
{
  const s = pres.addSlide();
  s.background = { color: P };

  text(s, C.s3.title, {
    x: MX, y: MT, w: 11.0, h: 0.95,
    fontFace: T.fonts.heading, fontSize: T.scale.h1, bold: true,
    color: I, valign: "top",
    objectName: "slides-lead:Title",
  });

  const cards = C.s3.cards;
  const cols = cards.length;
  const gap = 0.33;
  const cw = (CW - gap * (cols - 1)) / cols;
  const cx = MX;
  const cy = 2.0;
  const ch = 4.0;

  cards.forEach(function (card, i) {
    const bx = cx + i * (cw + gap);
    const onAccent = card.hero;
    const fg = onAccent ? P : I;
    panel(s, {
      x: bx, y: cy, w: cw, h: ch,
      fill: onAccent ? { color: A } : tint(I, 90),
      line: onAccent ? { color: A } : tint(I, 85),
      objectName: "deco-card-" + (i + 1),
    });
    text(s, card.label, {
      x: bx + 0.25, y: cy + 0.3, w: cw - 0.5, h: 0.55,
      fontSize: T.scale.body, bold: true, color: fg,
      valign: "top", objectName: "slides-field:Body",
    });
    text(s, card.body, {
      x: bx + 0.25, y: cy + 1.0, w: cw - 0.5, h: 2.6,
      fontSize: T.scale.caption, color: fg,
      valign: "top", objectName: "slides-field:Body",
    });
  });

  s.addNotes(C.s3.notes);
}

// ---------------------------------------------------------- 5/6. requests --
// Dark ground: the terminal line (motif) with parameter chips / stats carved.
function requestSlide(spec) {
  const s = pres.addSlide();
  s.background = { color: P };

  text(s, spec.title, {
    x: MX, y: MT, w: 11.0, h: 0.95,
    fontFace: T.fonts.heading, fontSize: T.scale.h1, bold: true,
    color: I, valign: "top",
    objectName: "slides-lead:Title",
  });

  panel(s, {
    x: MX, y: 2.05, w: CW, h: 1.5,
    fill: tint(I, 90), line: tint(I, 85),
    objectName: "deco-terminal",
  });
  text(s, [
    { text: "> ", options: { color: A, bold: true } },
    { text: spec.cmd, options: { color: I } },
  ], {
    x: MX + 0.3, y: 2.32, w: CW - 0.6, h: 0.9,
    fontSize: T.scale.body, color: I, valign: "middle",
    objectName: "slides-field:Body",
  });

  if (spec.chips) {
    const chips = spec.chips;
    const gap = 0.36;
    const cw = (CW - gap * (chips.length - 1)) / chips.length;
    const cy = 4.25;
    const ch = 2.3;
    chips.forEach(function (chip, i) {
      const bx = MX + i * (cw + gap);
      const fg = chip.hero ? P : I;
      panel(s, {
        x: bx, y: cy, w: cw, h: ch,
        fill: chip.hero ? { color: A } : tint(I, 90),
        line: chip.hero ? { color: A } : tint(I, 85),
        objectName: "deco-chip-" + (i + 1),
      });
      text(s, chip.label, {
        x: bx + 0.25, y: cy + 0.3, w: cw - 0.5, h: 0.5,
        fontSize: T.scale.body, bold: true, color: fg,
        objectName: "slides-field:Body",
      });
      text(s, chip.body, {
        x: bx + 0.25, y: cy + 0.95, w: cw - 0.5, h: 1.1,
        fontSize: T.scale.caption, color: fg,
        objectName: "slides-field:Body",
      });
    });
  }

  if (spec.stats) {
    const stats = spec.stats;
    const gap = 0.4;
    const cw = (CW - gap * (stats.length - 1)) / stats.length;
    const cy = 4.35;
    const ch = 2.1;
    stats.forEach(function (stat, i) {
      const bx = MX + i * (cw + gap);
      const fg = stat.hero ? P : I;
      panel(s, {
        x: bx, y: cy, w: cw, h: ch,
        fill: stat.hero ? { color: A } : tint(I, 90),
        line: stat.hero ? { color: A } : tint(I, 85),
        objectName: "deco-stat-" + (i + 1),
      });
      text(s, stat.v, {
        x: bx + 0.25, y: cy + 0.3, w: cw - 0.5, h: 0.85,
        fontFace: T.fonts.heading, fontSize: T.scale.body, bold: true,
        color: fg, valign: "middle", objectName: "slides-field:Body",
      });
      text(s, stat.l, {
        x: bx + 0.25, y: cy + 1.2, w: cw - 0.5, h: 0.65,
        fontSize: T.scale.caption, color: fg,
        objectName: "slides-field:Body",
      });
    });
  }

  s.addNotes(spec.notes);
}

requestSlide(C.s5);   // 5
requestSlide(C.s6);   // 6

// ---------------------------------------------------------------- 7. estado --
// Dark ground: three cards, /resumen the hero.
{
  const s = pres.addSlide();
  s.background = { color: P };

  text(s, C.s7.title, {
    x: MX, y: MT, w: 11.0, h: 0.95,
    fontFace: T.fonts.heading, fontSize: T.scale.h1, bold: true,
    color: I, valign: "top",
    objectName: "slides-lead:Title",
  });

  const cards = C.s7.cards;
  const gap = 0.4;
  const cw = (CW - gap * (cards.length - 1)) / cards.length;
  const cy = 2.15;
  const ch = 4.0;

  cards.forEach(function (card, i) {
    const bx = MX + i * (cw + gap);
    const fg = card.hero ? P : I;
    panel(s, {
      x: bx, y: cy, w: cw, h: ch,
      fill: card.hero ? { color: A } : tint(I, 90),
      line: card.hero ? { color: A } : tint(I, 85),
      objectName: "deco-card-" + (i + 1),
    });
    text(s, card.label, {
      x: bx + 0.25, y: cy + 0.35, w: cw - 0.5, h: 0.6,
      fontSize: T.scale.body, bold: true, color: fg,
      objectName: "slides-field:Body",
    });
    text(s, card.body, {
      x: bx + 0.25, y: cy + 1.1, w: cw - 0.5, h: 2.5,
      fontSize: T.scale.caption, color: fg,
      objectName: "slides-field:Body",
    });
  });

  s.addNotes(C.s7.notes);
}

// ------------------------------------------------------------------ 9. curl --
// Dark ground: two terminal lines in one panel, the motif pure.
{
  const s = pres.addSlide();
  s.background = { color: P };

  text(s, C.s9.title, {
    x: MX, y: MT, w: 4.0, h: 0.95,
    fontFace: T.fonts.heading, fontSize: T.scale.h1, bold: true,
    color: I, valign: "top",
    objectName: "slides-lead:Title",
  });

  panel(s, {
    x: MX, y: 2.15, w: CW, h: 3.4,
    fill: tint(I, 90), line: tint(I, 85),
    objectName: "deco-terminal",
  });
  text(s, [
    { text: "> ", options: { color: A, bold: true } },
    { text: '$ curl -H "x-api-key: <clave>"', options: { color: M, breakLine: true } },
    { text: "> ", options: { color: A, bold: true } },
    { text: C.s9.lines[0], options: { color: I, breakLine: true } },
    { text: "> ", options: { color: A, bold: true } },
    { text: '    $ curl -H "x-api-key: <clave>"', options: { color: M, breakLine: true } },
    { text: "> ", options: { color: A, bold: true } },
    { text: C.s9.lines[1], options: { color: I } },
  ], {
    x: MX + 0.3, y: 2.45, w: CW - 0.6, h: 2.6,
    fontSize: T.scale.caption, color: I, valign: "top",
    objectName: "slides-field:Body",
  });

  s.addNotes(C.s9.notes);
}

// -------------------------------------------------------------- 10. two-col --
// Dark ground: JavaScript and Python side by side, equal weight.
{
  const s = pres.addSlide();
  s.background = { color: P };

  text(s, C.s10.title, {
    x: MX, y: MT, w: 11.0, h: 0.95,
    fontFace: T.fonts.heading, fontSize: T.scale.h1, bold: true,
    color: I, valign: "top",
    objectName: "slides-lead:Title",
  });

  const gap = 0.6;
  const cw = (CW - gap) / 2;
  const cy = 2.05;
  const ch = 4.1;

  [C.s10.left, C.s10.right].forEach(function (side, i) {
    const bx = MX + i * (cw + gap);
    panel(s, {
      x: bx, y: cy, w: cw, h: ch,
      fill: tint(I, 90), line: tint(I, 85),
      objectName: "deco-panel-" + (i + 1),
    });
    text(s, side.label, {
      x: bx + 0.3, y: cy + 0.3, w: cw - 0.6, h: 0.5,
      fontSize: T.scale.body, bold: true, color: A,
      objectName: "slides-field:Left",
    });
    text(s, side.code.join("\n"), {
      x: bx + 0.3, y: cy + 0.95, w: cw - 0.6, h: ch - 1.3,
      fontSize: T.scale.caption, color: I, valign: "top",
      objectName: i === 0 ? "slides-field:Left" : "slides-field:Right",
    });
  });

  s.addNotes(C.s10.notes);
}

// ------------------------------------------------------- 11/12. tables --
// Dark ground: a lookup table, header in ink, rows on muted hairlines.
// A lookup table as one pptxgenjs table element: accent header band, rows
// plain on paper, hairline borders. Keeps the slide under the element cap.
function tableSlide(spec) {
  const s = pres.addSlide();
  s.background = { color: P };

  text(s, spec.title, {
    x: MX, y: MT, w: 11.0, h: 0.95,
    fontFace: T.fonts.heading, fontSize: T.scale.h1, bold: true,
    color: I, valign: "top",
    objectName: "slides-lead:Title",
  });

  const cw = [2.6, 3.4, 6.0];
  const rows = [
    spec.head.map(function (h) {
      return { text: h, options: { bold: true, color: P, fill: { color: A } } };
    }),
  ].concat(
    spec.rows.map(function (r) {
      return [
        { text: r[0], options: { color: I, bold: true } },
        { text: r[1], options: { color: A } },
        { text: r[2], options: { color: I } },
      ];
    })
  );

  s.addTable(rows, {
    x: MX, y: 2.1, w: CW, colW: cw,
    fontFace: T.fonts.body, fontSize: T.scale.caption, color: I,
    border: { type: "solid", color: M, pt: 0.5 },
    valign: "middle",
    objectName: "slides-field:Body",
  });

  s.addNotes(spec.notes);
}

tableSlide(C.s11);   // 11
tableSlide(C.s12);   // 12

// ----------------------------------------------------------- 13. almacenes --
// Dark ground: two long blocks, venta in accent (the filtering default).
{
  const s = pres.addSlide();
  s.background = { color: P };

  text(s, C.s13.title, {
    x: MX, y: MT, w: 11.0, h: 0.95,
    fontFace: T.fonts.heading, fontSize: T.scale.h1, bold: true,
    color: I, valign: "top",
    objectName: "slides-lead:Title",
  });

  const gap = 0.6;
  const cw = (CW - gap) / 2;
  const cy = 2.15;
  const ch = 4.0;

  [C.s13.left, C.s13.right].forEach(function (side, i) {
    const bx = MX + i * (cw + gap);
    const fg = side.hero ? P : I;
    panel(s, {
      x: bx, y: cy, w: cw, h: ch,
      fill: side.hero ? { color: A } : tint(I, 90),
      line: side.hero ? { color: A } : tint(I, 85),
      objectName: "deco-panel-" + (i + 1),
    });
    text(s, side.label, {
      x: bx + 0.3, y: cy + 0.35, w: cw - 0.6, h: 0.6,
      fontSize: T.scale.body, bold: true, color: fg,
      objectName: "slides-field:Body",
    });
    text(s, side.body, {
      x: bx + 0.3, y: cy + 1.15, w: cw - 0.6, h: 2.4,
      fontSize: T.scale.caption, color: fg,
      objectName: "slides-field:Body",
    });
  });

  s.addNotes(C.s13.notes);
}

// ---------------------------------------------------------- 14. notas --
// Dark ground: four stats, the rate limit the drawn hero.
{
  const s = pres.addSlide();
  s.background = { color: P };

  text(s, C.s14.title, {
    x: MX, y: MT, w: 11.0, h: 0.9,
    fontFace: T.fonts.heading, fontSize: T.scale.body, bold: true,
    color: M, valign: "top",
    objectName: "slides-field:Title",
  });

  const stats = C.s14.stats;
  const gap = 0.36;
  const cw = (CW - gap * (stats.length - 1)) / stats.length;
  const cy = 2.0;
  const ch = 3.6;

  stats.forEach(function (stat, i) {
    const bx = MX + i * (cw + gap);
    const isHero = stat.hero;
    const fg = isHero ? P : I;
    panel(s, {
      x: bx, y: cy, w: cw, h: ch,
      fill: isHero ? { color: A } : tint(I, 90),
      line: isHero ? { color: A } : tint(I, 85),
      objectName: "deco-stat-" + (i + 1),
    });
    text(s, stat.v, {
      x: bx + 0.2, y: cy + 0.4, w: cw - 0.4, h: 1.7,
      fontFace: T.fonts.heading, fontSize: isHero ? T.scale.display : T.scale.h1, bold: true,
      color: fg, valign: "middle", wrap: false,
      objectName: isHero ? "slides-lead" : "slides-field:Body",
    });
    text(s, stat.l, {
      x: bx + 0.25, y: cy + 2.3, w: cw - 0.5, h: 1.0,
      fontSize: T.scale.caption, color: fg,
      objectName: "slides-field:Body",
    });
  });

  s.addNotes(C.s14.notes);
}

// ------------------------------------------------------------ 15. close --
// Light cover to close the sandwich: resources, version, the terminal motif.
{
  const s = pres.addSlide();
  s.background = { color: I };

  const px = 8.7;
  const pw = 3.6;

  text(s, C.s15.title, {
    x: MX, y: 1.7, w: 7.2, h: 2.2,
    fontFace: T.fonts.heading, fontSize: T.scale.title, bold: true,
    color: P, valign: "middle", lineSpacingMultiple: 0.95,
    objectName: "slides-lead:Title",
  });
  text(s, C.s15.subtitle, {
    x: MX, y: 4.2, w: 7.4, h: 1.6,
    fontSize: T.scale.body, color: P,
    valign: "top", objectName: "slides-field:Subtitle",
  });

  panel(s, {
    x: px, y: 2.45, w: pw, h: 1.9,
    fill: { color: P }, line: { color: P },
    objectName: "deco-terminal-close",
  });
  text(s, [
    { text: "> ", options: { color: A, bold: true } },
    { text: C.s15.url, options: { breakLine: true, color: I } },
    { text: C.s15.key, options: { color: M } },
  ], {
    x: px + 0.28, y: 2.7, w: pw - 0.56, h: 1.4,
    fontSize: T.scale.caption, color: I, valign: "top",
    objectName: "deco-terminal-text",
  });

  s.addNotes(C.s15.notes);
}

pres
  .writeFile({ fileName: outPath })
  .then(function () { console.log("wrote " + outPath); })
  .catch(function (err) {
    console.error(err.message);
    process.exit(1);
  });