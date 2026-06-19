#!/usr/bin/env python3
"""Genera la presentación Houston Cloud — migración a GCP."""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

# ---- paleta (tema espacial Houston) ----
BG      = RGBColor(0x0B, 0x10, 0x22)   # navy profundo
PANEL   = RGBColor(0x15, 0x1D, 0x38)   # panel
INK     = RGBColor(0xED, 0xF1, 0xFF)   # texto claro
MUTE    = RGBColor(0x9A, 0xA6, 0xC8)   # texto atenuado
BLUE    = RGBColor(0x5B, 0x8D, 0xEF)   # acento azul
AMBER   = RGBColor(0xF5, 0xA6, 0x23)   # acento ámbar
GREEN   = RGBColor(0x3D, 0xD5, 0x98)   # ok
RED     = RGBColor(0xF2, 0x6D, 0x6D)   # warn

prs = Presentation()
prs.slide_width  = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]
SW, SH = prs.slide_width, prs.slide_height


def slide():
    s = prs.slides.add_slide(BLANK)
    r = s.shapes.add_shape(1, 0, 0, SW, SH)
    r.fill.solid(); r.fill.fore_color.rgb = BG
    r.line.fill.background()
    r.shadow.inherit = False
    return s


def box(s, x, y, w, h, fill=None, line=None, line_w=1.0):
    shp = s.shapes.add_shape(1, Inches(x), Inches(y), Inches(w), Inches(h))
    if fill is None:
        shp.fill.background()
    else:
        shp.fill.solid(); shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line; shp.line.width = Pt(line_w)
    shp.shadow.inherit = False
    return shp


def text(s, x, y, w, h, runs, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
         space=4):
    """runs: list of paragraphs; each paragraph = list of (txt,size,color,bold)."""
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame; tf.word_wrap = True
    tf.vertical_anchor = anchor
    for i, para in enumerate(runs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(space)
        for (txt, size, color, bold) in para:
            r = p.add_run(); r.text = txt
            r.font.size = Pt(size); r.font.color.rgb = color
            r.font.bold = bold; r.font.name = "Arial"
    return tb


def header(s, kicker, title):
    box(s, 0.55, 0.55, 0.12, 0.62, fill=AMBER)
    text(s, 0.8, 0.45, 12, 0.4, [[(kicker, 12, AMBER, True)]])
    text(s, 0.8, 0.72, 12.2, 0.9, [[(title, 30, INK, True)]])
    box(s, 0.8, 1.62, 11.8, 0.02, fill=PANEL, line=BLUE, line_w=0.75)


def bullets(s, x, y, w, items, size=15, gap=8):
    runs = []
    for it in items:
        if isinstance(it, tuple):
            lead, rest = it
            runs.append([("•  ", size, AMBER, True), (lead, size, INK, True),
                         (rest, size, MUTE, False)])
        else:
            runs.append([("•  ", size, AMBER, True), (it, size, INK, False)])
    text(s, x, y, w, 5, runs, space=gap)


def card(s, x, y, w, h, tag, title, body, accent=BLUE):
    box(s, x, y, w, h, fill=PANEL)
    box(s, x, y, w, 0.09, fill=accent)
    text(s, x+0.25, y+0.22, w-0.5, 0.4, [[(tag, 11, accent, True)]])
    text(s, x+0.25, y+0.52, w-0.5, 0.7, [[(title, 16, INK, True)]])
    text(s, x+0.25, y+1.15, w-0.5, h-1.2,
         [[(line, 12.5, MUTE, False)] for line in body], space=5)


def table(s, x, y, w, rows, col_w, header_fill=BLUE, font=11.5,
          row_h=0.42, head_h=0.46):
    n = len(rows); ncol = len(rows[0])
    total = sum(col_w)
    cw = [c / total * w for c in col_w]
    cx = x
    # header
    hx = x
    for j in range(ncol):
        box(s, hx, y, cw[j], head_h, fill=header_fill)
        text(s, hx+0.08, y, cw[j]-0.16, head_h,
             [[(str(rows[0][j]), font, RGBColor(0xFF,0xFF,0xFF), True)]],
             anchor=MSO_ANCHOR.MIDDLE)
        hx += cw[j]
    yy = y + head_h
    for i in range(1, n):
        fill = PANEL if i % 2 else RGBColor(0x10, 0x16, 0x2E)
        hx = x
        for j in range(ncol):
            box(s, hx, yy, cw[j], row_h, fill=fill)
            col = INK if j == 0 else MUTE
            bold = j == 0
            text(s, hx+0.08, yy, cw[j]-0.16, row_h,
                 [[(str(rows[i][j]), font, col, bold)]],
                 anchor=MSO_ANCHOR.MIDDLE)
            hx += cw[j]
        yy += row_h


# ============================================================== 1. PORTADA
s = slide()
box(s, 0, 0, SW, SH, fill=BG)
# acentos
box(s, 0, 0, 0.25, SH, fill=AMBER)
text(s, 1.0, 2.0, 11.5, 0.5, [[("HOUSTON CLOUD", 16, AMBER, True)]])
text(s, 1.0, 2.5, 11.5, 1.6,
     [[("De app de escritorio a", 40, INK, True)],
      [("servicio multi-tenant en GCP", 40, BLUE, True)]], space=2)
text(s, 1.0, 4.5, 11.5, 0.9,
     [[("Aislamiento por equipo a nivel de kernel, sin VPS dedicada, con costo controlado", 17, MUTE, False)]])
box(s, 1.0, 5.6, 4.2, 0.02, fill=PANEL, line=BLUE)
text(s, 1.0, 5.75, 11.5, 0.5,
     [[("Plan técnico + estimación de costos  ·  ", 12, MUTE, False),
       ("Junio 2026", 12, AMBER, True)]])

# ============================================================== 2. OBJETIVO
s = slide()
header(s, "CONTEXTO", "El objetivo en una frase")
text(s, 0.8, 2.0, 11.8, 1.2,
     [[("Hoy Houston es una app de escritorio (Tauri) donde cada usuario corre su "
        "propio engine local. Queremos ofrecerlo ", 16, INK, False),
       ("hosteado en GCP", 16, BLUE, True),
       (", donde cada equipo solo accede a sus agentes y la separación es de "
        "cómputo, no de código.", 16, INK, False)]], space=6)
card(s, 0.8, 3.5, 3.75, 3.2, "PUNTO 1", "Subir a la nube (GCP)",
     ["Dejar el escritorio.", "El engine corre en GCP.",
      "Web + PWA como clientes.", "Acceso desde cualquier lado."], BLUE)
card(s, 4.78, 3.5, 3.75, 3.2, "PUNTO 2", "Cada equipo, sus agentes",
     ["Aislamiento por equipo.", "Aunque sea la misma org.",
      "Seguridad por membership.", "Nada de fugas entre teams."], AMBER)
card(s, 8.78, 3.5, 3.75, 3.2, "PUNTO 3", "Aislamiento barato",
     ["Casi a nivel de hardware.", "Sandbox de kernel (gVisor).",
      "Sin VPS dedicada por team.", "Nodos compartidos = económico."], GREEN)

# ============================================================== 3. PUNTO 1
s = slide()
header(s, "PUNTO 1", "De escritorio a cloud en GCP")
text(s, 0.8, 1.85, 11.8, 0.7,
     [[("El engine ya es un binario standalone que habla HTTP/WS. No se reescribe; "
        "se hostea y se le construye el entorno cloud alrededor.", 14.5, MUTE, False)]])
bullets(s, 0.9, 2.9, 11.6, [
    ("Engine standalone listo  ", "— `houston-engine`, parametrizado por HOUSTON_HOME + token. Ya marcado 'Teams → futuro'."),
    ("Cliente web reemplaza a Tauri  ", "— mismas vistas de ui/@houston-ai/*; `examples/smartbooks` ya lo prueba (~400 LOC)."),
    ("PWA móvil ya existe  ", "— mismo protocolo, solo cambia el baseUrl."),
    ("Login de proveedor headless  ", "— device-code flow ya soportado (no hay navegador local en la nube)."),
    ("Base de imagen ya hecha  ", "— always-on/ trae Dockerfile + compose + systemd."),
], size=15, gap=11)
box(s, 0.8, 6.55, 11.75, 0.6, fill=PANEL)
text(s, 1.0, 6.62, 11.4, 0.5,
     [[("Trabajo real:  ", 13, AMBER, True),
       ("shell web  +  control plane  +  gateway de tenancy  +  provisioning con sandbox.  El núcleo del engine no se toca.", 13, INK, False)]])

# ============================================================== 4. PUNTO 2
s = slide()
header(s, "PUNTO 2", "Cada equipo solo ve sus agentes")
text(s, 0.8, 1.8, 11.8, 0.6,
     [[("El tenant es el EQUIPO. La frontera correcta NO es lógica.", 15, INK, True)]])
rows = [
    ["Modelo", "Frontera", "Veredicto"],
    ["Engine compartido + filtro por tenant_id / RBAC", "Código (lógica)", "Un bug filtra datos. Es 'separar por prompt'."],
    ["Un proceso engine por equipo, mismo host", "Proceso", "Mejor, pero comparten kernel y disco."],
    ["Un engine por equipo en su sandbox de kernel", "microVM / gVisor", "Lo elegido: escape = romper el kernel."],
]
table(s, 0.8, 2.6, 11.75, rows, [4.5, 2.2, 4.5], header_fill=BLUE, row_h=0.62)
box(s, 0.8, 5.45, 11.75, 1.5, fill=PANEL)
box(s, 0.8, 5.45, 0.1, 1.5, fill=AMBER)
text(s, 1.1, 5.6, 11.2, 1.3,
     [[("Decisión:  ", 15, AMBER, True),
       ("tenant = team. Un houston-engine por equipo, en su propio sandbox, con su "
        "volumen y su token.", 15, INK, False)],
      [("Org → Team → Agents.  ", 13, BLUE, True),
       ("La org agrupa facturación/admin; el equipo es la unidad de aislamiento. "
        "El gateway valida membership antes de rutear; el token del engine nunca "
        "llega al cliente.", 13, MUTE, False)]], space=8)

# ============================================================== 5. PUNTO 3
s = slide()
header(s, "PUNTO 3", "Aislamiento de kernel, barato, sin VPS dedicada")
text(s, 0.8, 1.8, 11.8, 0.55,
     [[("GCP no expone Firecracker directo, pero da aislamiento de kernel sobre nodos COMPARTIDOS:", 14.5, MUTE, False)]])
card(s, 0.8, 2.5, 5.78, 2.05, "DEFAULT FREE", "Cloud Run gen2",
     ["microVM + gVisor gestionada.", "Scale-to-zero: team idle = $0.",
      "Ideal para uso interactivo."], BLUE)
card(s, 6.75, 2.5, 5.78, 2.05, "DEFAULT PRO 24/7", "GKE + GKE Sandbox",
     ["Pod gVisor por equipo, namespace aislado.",
      "Spot VMs + bin-packing = barato.", "Soporta routines 24/7."], GREEN)
text(s, 0.8, 4.75, 11.8, 0.4, [[("Por qué cumple lo que pediste:", 14, AMBER, True)]])
bullets(s, 0.9, 5.2, 11.6, [
    ("Frontera de kernel  ", "— gVisor/microVM, no un check de código. No es 'separar por prompt'."),
    ("Sin VPS por cliente  ", "— muchos sandboxes bin-packeados en pocos nodos compartidos."),
    ("Económico  ", "— Spot VMs + scale-to-zero (free) + un solo control plane compartido."),
], size=14, gap=8)

# ============================================================== 6. ARQUITECTURA
s = slide()
header(s, "ARQUITECTURA", "Componentes en GCP")
# cliente
card(s, 0.8, 2.0, 2.7, 1.5, "CLIENTE", "Web + PWA",
     ["@houston-ai/engine-client", "Supabase JWT (Google SSO)"], BLUE)
# gateway
card(s, 4.0, 2.0, 2.9, 1.5, "BORDE", "Gateway / Router",
     ["Valida JWT + membership", "Rutea user→team→engine"], AMBER)
# control plane
card(s, 7.4, 2.0, 2.7, 1.5, "PLANO CONTROL", "Provisioner",
     ["Orgs / teams / roles", "Crea engines + volúmenes"], AMBER)
# datos
card(s, 10.3, 2.0, 2.25, 1.5, "METADATA", "Postgres",
     ["orgs, teams,", "memberships (RLS)"], BLUE)
# engines
text(s, 0.8, 3.85, 12, 0.4, [[("Data plane — un engine aislado por equipo:", 13, INK, True)]])
card(s, 0.8, 4.3, 3.7, 2.3, "TEAM A", "Engine (gVisor)",
     ["HOUSTON_HOME vol A", "DB + workspaces + .houston/", "Token propio"], GREEN)
card(s, 4.7, 4.3, 3.7, 2.3, "TEAM B", "Engine (gVisor)",
     ["HOUSTON_HOME vol B", "Aislado de A", "Token propio"], GREEN)
card(s, 8.6, 4.3, 3.95, 2.3, "TRANSVERSAL", "Plataforma",
     ["Secret Manager (tokens/keys)", "Artifact Registry (imagen firmada)",
      "Logging / Monitoring / Audit", "VPC + Cloud NAT (egress allowlist)"], BLUE)

# ============================================================== 7. TENANCY/TIERS
s = slide()
header(s, "MODELO", "Dos tiers, misma imagen")
rows = [
    ["", "Free / Lite", "Pro / Always On"],
    ["Sustrato", "Cloud Run gen2", "GKE + GKE Sandbox"],
    ["Ejecución", "On-demand, scale-to-zero", "24/7 (routines), min 1 réplica"],
    ["Aislamiento", "microVM + gVisor", "pod gVisor + namespace"],
    ["Billing API", "BYO key (la trae el team)", "Central con markup + cuotas"],
    ["Costo p/ nosotros", "~$0 idle, centavos activo", "~$5–8 / equipo / mes (infra)"],
]
table(s, 0.8, 2.1, 11.75, rows, [2.4, 4.2, 4.6], header_fill=BLUE, row_h=0.6)
box(s, 0.8, 6.05, 11.75, 0.95, fill=PANEL)
box(s, 0.8, 6.05, 0.1, 0.95, fill=AMBER)
text(s, 1.1, 6.18, 11.2, 0.8,
     [[("Promoción free → pro  ", 13.5, AMBER, True),
       ("= mover el volumen entre sustratos. Mismo binario, mismo HOUSTON_HOME, "
        "sin migrar datos.", 13.5, INK, False)]])

# ============================================================== 8. SEGURIDAD
s = slide()
header(s, "SEGURIDAD", "Defensa en capas")
layers = [
    ("1 · Identidad", "Supabase + Google SSO (ya existe). JWT con claims org/team.", BLUE),
    ("2 · Autorización", "Gateway valida membership. El token del engine nunca sale del borde.", BLUE),
    ("3 · Cómputo", "Sandbox de kernel (gVisor) por team. Garantía dura, no un if.", GREEN),
    ("4 · Red", "NetworkPolicy deny-all este-oeste + egress allowlist por team.", AMBER),
    ("5 · Secrets", "Secret Manager por team, rotación, nunca en imagen ni logs.", AMBER),
    ("6 · Datos reposo", "Buckets/discos por team con CMEK. Path-traversal ya cubierto.", BLUE),
    ("7 · Suministro", "Artifact Registry + scan + Binary Authorization (solo firmadas).", BLUE),
    ("8 · Auditoría", "Cloud Audit Logs + tracing por request. Quién accedió a qué.", GREEN),
]
x0, y0, cw, ch, gx, gy = 0.8, 2.1, 5.78, 1.05, 0.2, 0.18
for i, (t, b, c) in enumerate(layers):
    col = i % 2; row = i // 2
    x = x0 + col * (cw + gx); y = y0 + row * (ch + gy)
    box(s, x, y, cw, ch, fill=PANEL); box(s, x, y, 0.09, ch, fill=c)
    text(s, x+0.25, y+0.12, cw-0.4, 0.4, [[(t, 13.5, c, True)]])
    text(s, x+0.25, y+0.5, cw-0.4, 0.5, [[(b, 11, MUTE, False)]])

# ============================================================== 9. COSTOS supuestos
s = slide()
header(s, "COSTOS", "Estimación — supuestos")
text(s, 0.8, 1.85, 11.8, 0.5,
     [[("Orden de magnitud, región us-central1, USD/mes. Infra propia; el costo de "
        "API LLM va aparte (ver nota).", 13.5, MUTE, False)]])
text(s, 0.8, 2.5, 5.9, 0.4, [[("Fijo / compartido (control plane)", 15, AMBER, True)]])
rows = [
    ["Concepto", "USD/mes"],
    ["GKE cluster management fee", "$73"],
    ["Cloud SQL (control plane)", "$35"],
    ["Gateway + control plane (Cloud Run)", "$20"],
    ["Cloud NAT", "$33"],
    ["Logging / Monitoring / Audit", "$20"],
    ["Secret Manager + misc", "$5"],
    ["TOTAL FIJO", "≈ $186"],
]
table(s, 0.8, 2.95, 5.9, rows, [4.2, 1.4], header_fill=BLUE, row_h=0.41, head_h=0.43, font=11)
text(s, 7.0, 2.5, 5.5, 0.4, [[("Variable por equipo (infra, sin API)", 15, AMBER, True)]])
rows2 = [
    ["Concepto", "Pro 24/7", "Free"],
    ["Cómputo (Spot/CR)", "$3.0", "$0–2"],
    ["Storage GCS", "$0.30", "$0.10"],
    ["NAT / egress datos", "$1.0", "~$0"],
    ["Logs / secrets / misc", "$0.70", "~$0"],
    ["POR EQUIPO", "≈ $5–8", "≈ $0–2"],
]
table(s, 7.0, 2.95, 5.55, rows2, [2.8, 1.4, 1.4], header_fill=GREEN, row_h=0.41, head_h=0.43, font=11)
box(s, 7.0, 5.95, 5.55, 1.15, fill=PANEL)
text(s, 7.2, 6.05, 5.2, 1.0,
     [[("API LLM:  ", 12, AMBER, True),
       ("Free = BYO (costo $0 para nosotros).  Pro = pass-through + markup → "
        "ingreso positivo, no costo neto.", 12, MUTE, False)]], space=4)
box(s, 0.8, 6.5, 5.9, 0.6, fill=PANEL)
text(s, 1.0, 6.58, 5.6, 0.5,
     [[("Filestore (caro) solo opt-in.  ", 11.5, RED, True),
       ("Default = GCS+gcsfuse.", 11.5, MUTE, False)]])

# ============================================================== 10. COSTOS escenarios
s = slide()
header(s, "COSTOS", "Escenarios y comparación")
rows = [
    ["Escenario", "Fijo", "Variable", "Total infra/mes", "Por equipo"],
    ["50 equipos Pro", "$186", "50 × $7 = $350", "≈ $536", "≈ $10.7"],
    ["200 equipos Pro", "$186", "200 × $6 = $1,200", "≈ $1,386", "≈ $6.9"],
    ["100 Pro + 400 Free", "$186", "$700 + $400", "≈ $1,286", "≈ $2.6"],
    ["500 equipos Pro", "$186", "500 × $5.5 = $2,750", "≈ $2,936", "≈ $5.9"],
]
table(s, 0.8, 2.1, 11.75, rows, [2.9, 1.3, 2.7, 2.4, 1.6], header_fill=BLUE, row_h=0.52)
text(s, 0.8, 5.0, 11.8, 0.4,
     [[("Vs. el modelo que rechazamos (1 VPS dedicada por equipo):", 14, AMBER, True)]])
bullets(s, 0.9, 5.45, 11.6, [
    ("200 VPS dedicadas (e2-small on-demand)  ", "≈ $2,600/mes solo cómputo — sin bin-packing ni scale-to-zero, más ops."),
    ("Nuestro modelo a 200 Pro  ", "≈ $1,386/mes con aislamiento de kernel MÁS fuerte. ~2x más barato."),
    ("La economía mejora con escala  ", "— mejor bin-packing baja el costo por equipo a medida que crecemos."),
], size=13.5, gap=7)

# ============================================================== 11. ROADMAP
s = slide()
header(s, "EJECUCIÓN", "Roadmap por fases")
phases = [
    ("0", "Web shell", "Frontend web sobre engine-client (sin Tauri). 1 engine remoto.", BLUE),
    ("1", "Tenancy + control plane", "Orgs/teams/memberships + gateway JWT + provisioner.", AMBER),
    ("2", "Aislamiento híbrido", "Cloud Run gen2 (free) + GKE Sandbox (pro) + volúmenes + secrets.", GREEN),
    ("3", "Hardening red + datos", "Egress allowlist, NetworkPolicy, CMEK, Binary Authorization.", BLUE),
    ("4", "Billing dual + cuotas", "BYO (free) + central markup (pro), medición y rate-limit.", AMBER),
    ("5", "Producto", "Panel admin, roles, observabilidad por tenant, SLA.", GREEN),
]
y = 2.0
for num, t, b, c in phases:
    box(s, 0.8, y, 0.75, 0.72, fill=c)
    text(s, 0.8, y, 0.75, 0.72, [[(num, 26, BG, True)]], align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    box(s, 1.7, y, 10.85, 0.72, fill=PANEL)
    text(s, 1.9, y+0.06, 3.0, 0.62, [[(t, 14.5, INK, True)]], anchor=MSO_ANCHOR.MIDDLE)
    text(s, 5.0, y+0.06, 7.4, 0.62, [[(b, 12, MUTE, False)]], anchor=MSO_ANCHOR.MIDDLE)
    y += 0.84

# ============================================================== 12. CIERRE
s = slide()
header(s, "RESUMEN", "Decisiones tomadas y próximos pasos")
text(s, 0.8, 1.9, 11.8, 0.4, [[("Lo que ya está decidido:", 15, AMBER, True)]])
bullets(s, 0.9, 2.4, 11.6, [
    ("Tenant = equipo  ", "— un engine aislado por team, sandbox de kernel (no RBAC lógico)."),
    ("Sustrato híbrido  ", "— Cloud Run (free) + GKE Sandbox (pro 24/7) desde el inicio."),
    ("Billing dual  ", "— BYO key en free, central con markup + cuotas en pro."),
    ("Caso central = 24/7 routines  ", "— define Pro como producto; scale-to-zero solo en free."),
], size=14.5, gap=8)
box(s, 0.8, 5.0, 11.75, 1.9, fill=PANEL)
box(s, 0.8, 5.0, 0.1, 1.9, fill=GREEN)
text(s, 1.1, 5.15, 11.2, 1.7,
     [[("Próximos pasos", 15, GREEN, True)],
      [("1.  Confirmar storage default del tier Pro (propuesta: GCS, Filestore opt-in).", 13, INK, False)],
      [("2.  Arrancar Fase 0: shell web sobre @houston-ai/engine-client.", 13, INK, False)],
      [("3.  Diseñar el esquema del control plane (orgs/teams/memberships + RLS).", 13, INK, False)]], space=7)

prs.save("/home/user/houston/cloud/houston-cloud-gcp.pptx")
print("OK:", len(prs.slides.__iter__.__self__._sldIdLst), "slides")
