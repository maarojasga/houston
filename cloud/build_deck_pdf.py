#!/usr/bin/env python3
"""Render Houston Cloud deck a PDF (reportlab) — abre en cualquier visor."""
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

pdfmetrics.registerFont(TTFont("DJ",  "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("DJB", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))

IN = 72.0
W, H = 13.333 * IN, 7.5 * IN

BG    = HexColor("#0B1022")
PANEL = HexColor("#151D38")
DARK  = HexColor("#10162E")
INK   = HexColor("#EDF1FF")
MUTE  = HexColor("#9AA6C8")
BLUE  = HexColor("#5B8DEF")
AMBER = HexColor("#F5A623")
GREEN = HexColor("#3DD598")
RED   = HexColor("#F26D6D")
WHITE = HexColor("#FFFFFF")

OUT = "/home/user/houston/cloud/houston-cloud-gcp.pdf"
c = canvas.Canvas(OUT, pagesize=(W, H))


def fnt(bold): return "DJB" if bold else "DJ"


def rect(x, y, w, h, fill=None, stroke=None, sw=0.75):
    if fill is not None:
        c.setFillColor(fill)
    if stroke is not None:
        c.setStrokeColor(stroke); c.setLineWidth(sw)
    c.rect(x * IN, H - (y + h) * IN, w * IN, h * IN,
           fill=1 if fill is not None else 0,
           stroke=1 if stroke is not None else 0)


def sw_(s, font, size): return pdfmetrics.stringWidth(s, font, size)


def line(x, y_top, s, size, color, bold=False, align="l", w=None):
    f = fnt(bold)
    base = H - y_top * IN - size * 0.82
    tx = x * IN
    if align == "c" and w:
        tx = x * IN + (w * IN - sw_(s, f, size)) / 2
    elif align == "r" and w:
        tx = x * IN + (w * IN - sw_(s, f, size))
    c.setFillColor(color); c.setFont(f, size)
    c.drawString(tx, base, s)


def vcell(x, y_top, w, h, s, size, color, bold=False, align="l"):
    f = fnt(bold)
    base = H - (y_top + h / 2) * IN - size * 0.34
    tx = x * IN + 0.08 * IN
    if align == "c":
        tx = x * IN + (w * IN - sw_(s, f, size)) / 2
    c.setFillColor(color); c.setFont(f, size)
    c.drawString(tx, base, s)


def wrap_runs(runs, max_w_in, size):
    """runs: list of (text,bold,color). Returns list of lines (list of (word,bold,color))."""
    max_w = max_w_in * IN
    words = []
    for (t, b, col) in runs:
        for tok in t.split(" "):
            if tok != "":
                words.append((tok, b, col))
    space = sw_(" ", "DJ", size)
    lines, cur, curw = [], [], 0.0
    for (word, b, col) in words:
        ww = sw_(word, fnt(b), size)
        add = ww + (space if cur else 0)
        if cur and curw + add > max_w:
            lines.append(cur); cur, curw = [], 0.0; add = ww
        cur.append((word, b, col)); curw += add
    if cur:
        lines.append(cur)
    return lines


def para(x, y_top, max_w, runs, size, color_default=INK, leading=1.35, gap_after=0):
    lines = wrap_runs(runs, max_w, size)
    y = y_top
    space = sw_(" ", "DJ", size)
    for ln in lines:
        cx = x * IN
        base = H - y * IN - size * 0.82
        for (word, b, col) in ln:
            f = fnt(b)
            c.setFillColor(col); c.setFont(f, size)
            c.drawString(cx, base, word)
            cx += sw_(word, f, size) + space
        y += (size * leading) / IN
    return y + gap_after


def bg():
    rect(0, 0, 13.333, 7.5, fill=BG)


def header(kicker, title):
    rect(0.55, 0.55, 0.12, 0.62, fill=AMBER)
    line(0.8, 0.45, kicker, 12, AMBER, bold=True)
    line(0.8, 0.72, title, 26, INK, bold=True)
    rect(0.8, 1.62, 11.8, 0.018, fill=BLUE)


def card(x, y, w, h, tag, title, body, accent=BLUE, ts=15):
    rect(x, y, w, h, fill=PANEL)
    rect(x, y, w, 0.09, fill=accent)
    line(x + 0.22, y + 0.2, tag, 10.5, accent, bold=True)
    line(x + 0.22, y + 0.48, title, ts, INK, bold=True)
    yy = y + 1.02
    for b in body:
        para(x + 0.22, yy, w - 0.42, [(b, False, MUTE)], 11.5)
        yy += 0.27


def table(x, y, w, rows, col_w, head_fill=BLUE, font=11.0, row_h=0.42, head_h=0.46):
    ncol = len(rows[0]); total = sum(col_w)
    cw = [cc / total * w for cc in col_w]
    hx = x
    for j in range(ncol):
        rect(hx, y, cw[j], head_h, fill=head_fill)
        al = "l"
        vcell(hx, y, cw[j], head_h, str(rows[0][j]), font, WHITE, bold=True, align=al)
        hx += cw[j]
    yy = y + head_h
    for i in range(1, len(rows)):
        fill = PANEL if i % 2 else DARK
        hx = x
        for j in range(ncol):
            rect(hx, yy, cw[j], row_h, fill=fill)
            col = INK if j == 0 else MUTE
            vcell(hx, yy, cw[j], row_h, str(rows[i][j]), font, col, bold=(j == 0))
            hx += cw[j]
        yy += row_h


def bullets(x, y, max_w, items, size=14, gap=0.30):
    yy = y
    for it in items:
        lead, rest = it if isinstance(it, tuple) else ("", it)
        runs = [("•  ", True, AMBER), (lead, True, INK), (rest, False, MUTE)]
        ny = para(x, yy, max_w, runs, size, leading=1.3)
        yy = ny + gap - (size * 0.3) / IN
    return yy


def page():
    c.showPage()


# ===================================================== 1. PORTADA
bg()
rect(0, 0, 0.25, 7.5, fill=AMBER)
line(1.0, 2.0, "HOUSTON CLOUD", 16, AMBER, bold=True)
line(1.0, 2.45, "De app de escritorio a", 36, INK, bold=True)
line(1.0, 3.1, "servicio multi-tenant en GCP", 36, BLUE, bold=True)
para(1.0, 4.4, 11.0,
     [("Aislamiento por equipo a nivel de kernel, sin VPS dedicada, con costo controlado",
       False, MUTE)], 16)
rect(1.0, 5.5, 4.2, 0.018, fill=BLUE)
line(1.0, 5.7, "Plan técnico + estimación de costos   ·   Junio 2026", 12, MUTE)
page()

# ===================================================== 2. OBJETIVO
bg(); header("CONTEXTO", "El objetivo en una frase")
para(0.8, 1.95, 11.8,
     [("Hoy Houston es una app de escritorio (Tauri) donde cada usuario corre su propio "
       "engine local. Queremos ofrecerlo ", False, INK),
      ("hosteado en GCP", True, BLUE),
      (", donde cada equipo solo accede a sus agentes y la separación es de cómputo, no de código.",
       False, INK)], 15, leading=1.4)
card(0.8, 3.4, 3.75, 3.3, "PUNTO 1", "Subir a la nube (GCP)",
     ["Dejar el escritorio.", "El engine corre en GCP.",
      "Web + PWA como clientes.", "Acceso desde cualquier lado."], BLUE)
card(4.78, 3.4, 3.75, 3.3, "PUNTO 2", "Cada equipo, sus agentes",
     ["Aislamiento por equipo.", "Aunque sea la misma org.",
      "Seguridad por membership.", "Nada de fugas entre teams."], AMBER)
card(8.78, 3.4, 3.75, 3.3, "PUNTO 3", "Aislamiento barato",
     ["Casi a nivel de hardware.", "Sandbox de kernel (gVisor).",
      "Sin VPS dedicada por team.", "Nodos compartidos = barato."], GREEN)
page()

# ===================================================== 3. PUNTO 1
bg(); header("PUNTO 1", "De escritorio a cloud en GCP")
para(0.8, 1.85, 11.8,
     [("El engine ya es un binario standalone que habla HTTP/WS. No se reescribe; se "
       "hostea y se le construye el entorno cloud alrededor.", False, MUTE)], 13.5)
bullets(0.85, 2.75, 11.7, [
    ("Engine standalone listo  ", "— houston-engine, parametrizado por HOUSTON_HOME + token."),
    ("Cliente web reemplaza a Tauri  ", "— mismas vistas de ui/; examples/smartbooks ya lo prueba."),
    ("PWA móvil ya existe  ", "— mismo protocolo, solo cambia el baseUrl."),
    ("Login de proveedor headless  ", "— device-code flow ya soportado (sin navegador local)."),
    ("Base de imagen ya hecha  ", "— always-on/ trae Dockerfile + compose + systemd."),
], size=14.5, gap=0.34)
rect(0.8, 6.5, 11.75, 0.62, fill=PANEL)
para(1.0, 6.62, 11.4,
     [("Trabajo real:  ", True, AMBER),
      ("shell web + control plane + gateway de tenancy + provisioning con sandbox. "
       "El núcleo del engine no se toca.", False, INK)], 12.5)
page()

# ===================================================== 4. PUNTO 2
bg(); header("PUNTO 2", "Cada equipo solo ve sus agentes")
line(0.8, 1.78, "El tenant es el EQUIPO. La frontera correcta NO es lógica.", 15, INK, bold=True)
rows = [
    ["Modelo", "Frontera", "Veredicto"],
    ["Engine compartido + filtro por tenant_id", "Código (lógica)", "Un bug filtra datos. Es 'separar por prompt'."],
    ["Un proceso engine por equipo, mismo host", "Proceso", "Mejor, pero comparten kernel y disco."],
    ["Un engine por equipo en su sandbox kernel", "microVM / gVisor", "Elegido: escape = romper el kernel."],
]
table(0.8, 2.45, 11.75, rows, [4.3, 2.2, 4.7], head_fill=BLUE, row_h=0.6, font=11)
rect(0.8, 5.35, 11.75, 1.55, fill=PANEL); rect(0.8, 5.35, 0.1, 1.55, fill=AMBER)
para(1.1, 5.5, 11.2,
     [("Decisión:  ", True, AMBER),
      ("tenant = team. Un houston-engine por equipo, en su propio sandbox, con su volumen y su token.",
       False, INK)], 14)
para(1.1, 6.05, 11.2,
     [("Org → Team → Agents.  ", True, BLUE),
      ("La org agrupa facturación/admin; el equipo es la unidad de aislamiento. El gateway "
       "valida membership antes de rutear; el token del engine nunca llega al cliente.",
       False, MUTE)], 12)
page()

# ===================================================== 5. PUNTO 3
bg(); header("PUNTO 3", "Aislamiento de kernel, barato, sin VPS dedicada")
para(0.8, 1.78, 11.8,
     [("GCP no expone Firecracker directo, pero da aislamiento de kernel sobre nodos COMPARTIDOS:",
       False, MUTE)], 13.5)
card(0.8, 2.4, 5.78, 2.05, "DEFAULT PRUEBA", "Cloud Run gen2",
     ["microVM + gVisor gestionada.", "Scale-to-zero: team idle = $0.",
      "Ideal para uso interactivo."], BLUE)
card(6.75, 2.4, 5.78, 2.05, "DEFAULT PAGO 24/7", "GKE + GKE Sandbox",
     ["Pod gVisor por equipo, namespace aislado.",
      "Spot VMs + bin-packing = barato.", "Soporta routines 24/7."], GREEN)
line(0.8, 4.7, "Por qué cumple lo que pediste:", 14, AMBER, bold=True)
bullets(0.85, 5.15, 11.7, [
    ("Frontera de kernel  ", "— gVisor/microVM, no un check de código. No es 'separar por prompt'."),
    ("Sin VPS por cliente  ", "— muchos sandboxes bin-packeados en pocos nodos compartidos."),
    ("Económico  ", "— Spot VMs + scale-to-zero (prueba) + un solo control plane compartido."),
], size=13.5, gap=0.3)
page()

# ===================================================== 6. ARQUITECTURA
bg(); header("ARQUITECTURA", "Componentes en GCP")
card(0.8, 2.0, 2.7, 1.5, "CLIENTE", "Web + PWA",
     ["@houston-ai/engine-client", "Supabase JWT (Google SSO)"], BLUE, ts=14)
card(4.0, 2.0, 2.9, 1.5, "BORDE", "Gateway / Router",
     ["Valida JWT + membership", "Rutea user→team→engine"], AMBER, ts=14)
card(7.4, 2.0, 2.7, 1.5, "PLANO CONTROL", "Provisioner",
     ["Orgs / teams / roles", "Crea engines + volúmenes"], AMBER, ts=14)
card(10.3, 2.0, 2.25, 1.5, "METADATA", "Postgres",
     ["orgs, teams,", "memberships (RLS)"], BLUE, ts=14)
line(0.8, 3.8, "Data plane — un engine aislado por equipo:", 13, INK, bold=True)
card(0.8, 4.25, 3.7, 2.35, "TEAM A", "Engine (gVisor)",
     ["HOUSTON_HOME vol A", "DB + workspaces + .houston/", "Token propio"], GREEN, ts=14)
card(4.7, 4.25, 3.7, 2.35, "TEAM B", "Engine (gVisor)",
     ["HOUSTON_HOME vol B", "Aislado de A", "Token propio"], GREEN, ts=14)
card(8.6, 4.25, 3.95, 2.35, "TRANSVERSAL", "Plataforma",
     ["Secret Manager (tokens/keys)", "Artifact Registry (imagen firmada)",
      "Logging / Monitoring / Audit", "VPC + Cloud NAT (egress allowlist)"], BLUE, ts=14)
page()

# ===================================================== 7. TIERS
bg(); header("MODELO", "Dos tiers: prueba (barato) y pago (fuerte)")
rows = [
    ["", "Prueba / Free", "Pago / Pro"],
    ["Sustrato", "Cloud Run gen2", "GKE + GKE Sandbox"],
    ["Ejecución", "On-demand, scale-to-zero", "24/7 routines, min 1 réplica"],
    ["Aislamiento", "microVM + gVisor (¡se conserva!)", "pod gVisor + namespace"],
    ["Billing API", "BYO key (la trae el team)", "Central con markup + cuotas"],
    ["Infra fija que usa", "Solo Cloud Run + Supabase", "GKE + NAT + Cloud SQL"],
    ["Costo p/ nosotros", "~$0 idle · fijo ~$22/mes", "~$5-8 /equipo · fijo ~$186"],
]
table(0.8, 1.95, 11.75, rows, [2.6, 4.4, 4.4], head_fill=BLUE, row_h=0.55, font=11)
rect(0.8, 6.15, 11.75, 0.9, fill=PANEL); rect(0.8, 6.15, 0.1, 0.9, fill=AMBER)
para(1.1, 6.28, 11.2,
     [("Clave del ahorro  ", True, AMBER),
      ("— el tier de prueba quita GKE/NAT/Cloud SQL pero MANTIENE el sandbox de kernel. "
       "Promoción free→pro = mover el volumen, sin migrar datos.", False, INK)], 12.5)
page()

# ===================================================== 8. SEGURIDAD
bg(); header("SEGURIDAD", "Defensa en capas")
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
x0, y0, cw, ch, gx, gy = 0.8, 2.05, 5.78, 1.05, 0.2, 0.18
for i, (t, b, col) in enumerate(layers):
    cc = i % 2; rr = i // 2
    x = x0 + cc * (cw + gx); y = y0 + rr * (ch + gy)
    rect(x, y, cw, ch, fill=PANEL); rect(x, y, 0.09, ch, fill=col)
    line(x + 0.25, y + 0.12, t, 13.5, col, bold=True)
    para(x + 0.25, y + 0.5, cw - 0.4, [(b, False, MUTE)], 11)
page()

# ===================================================== 9. COSTOS supuestos
bg(); header("COSTOS", "Estimación — supuestos")
para(0.8, 1.85, 11.8,
     [("Orden de magnitud, región us-central1, USD/mes. Infra propia; el costo de API LLM "
       "va aparte (ver nota).", False, MUTE)], 13)
line(0.8, 2.5, "Fijo / compartido — Pago vs Prueba", 14, AMBER, bold=True)
rows = [
    ["Concepto", "Pago", "Prueba"],
    ["GKE cluster fee", "$73", "—"],
    ["Cloud SQL (control plane)", "$35", "—"],
    ["Cloud NAT", "$33", "—"],
    ["Gateway + control plane (CR)", "$20", "$15"],
    ["Supabase (metadata)", "incl.", "$0*"],
    ["Logging / Monitoring", "$20", "$5"],
    ["Secret Manager + misc", "$5", "$2"],
    ["TOTAL FIJO", "≈ $186", "≈ $22"],
]
table(0.8, 2.9, 5.9, rows, [3.4, 1.25, 1.25], head_fill=BLUE, row_h=0.36, head_h=0.4, font=10.5)
line(7.0, 2.5, "Variable por equipo (infra, sin API)", 14, AMBER, bold=True)
rows2 = [
    ["Concepto", "Pago 24/7", "Prueba"],
    ["Cómputo (Spot/CR)", "$3.0", "$0-2"],
    ["Storage GCS", "$0.30", "$0.10"],
    ["NAT / egress datos", "$1.0", "~$0"],
    ["Logs / secrets / misc", "$0.70", "~$0"],
    ["POR EQUIPO", "≈ $5-8", "≈ $0-2"],
]
table(7.0, 2.9, 5.55, rows2, [2.8, 1.4, 1.4], head_fill=GREEN, row_h=0.4, head_h=0.44, font=10.5)
rect(7.0, 5.55, 5.55, 1.1, fill=PANEL)
para(7.2, 5.68, 5.2,
     [("API LLM:  ", True, AMBER),
      ("Prueba = BYO (costo $0 para nosotros). Pago = pass-through + markup → ingreso positivo, "
       "no costo neto.", False, MUTE)], 11)
rect(0.8, 6.4, 5.9, 0.65, fill=PANEL)
para(1.0, 6.5, 5.6,
     [("* ", True, AMBER),
      ("Uso ligero de prueba cae en la cuota always-free de Cloud Run = $0 cómputo. Filestore "
       "(caro) solo opt-in en Pago.", False, MUTE)], 10.5)
page()

# ===================================================== 10. COSTOS escenarios
bg(); header("COSTOS", "Escenarios y comparación")
rows = [
    ["Escenario", "Fijo", "Variable", "Total infra/mes", "Por equipo"],
    ["Solo prueba: 2,000 free (BYO)", "$22", "~$0 idle", "≈ $22-100", "≈ $0.02"],
    ["50 equipos Pago", "$186", "50 × $7 = $350", "≈ $536", "≈ $10.7"],
    ["200 equipos Pago", "$186", "200 × $6 = $1,200", "≈ $1,386", "≈ $6.9"],
    ["100 Pago + 400 prueba", "$186", "$700 + ~$0", "≈ $886", "≈ $1.8"],
    ["500 equipos Pago", "$186", "500 × $5.5 = $2,750", "≈ $2,936", "≈ $5.9"],
]
table(0.8, 2.05, 11.75, rows, [3.1, 1.2, 2.6, 2.4, 1.5], head_fill=BLUE, row_h=0.5, font=11)
line(0.8, 5.0, "Vs. el modelo que rechazamos (1 VPS dedicada por equipo):", 14, AMBER, bold=True)
bullets(0.85, 5.45, 11.7, [
    ("200 VPS dedicadas (e2-small on-demand)  ", "≈ $2,600/mes solo cómputo — sin bin-packing ni scale-to-zero."),
    ("Nuestro modelo a 200 Pago  ", "≈ $1,386/mes con aislamiento de kernel MÁS fuerte. ~2x más barato."),
    ("La economía mejora con escala  ", "— mejor bin-packing baja el costo por equipo al crecer."),
], size=13.5, gap=0.27)
page()

# ===================================================== 11. ROADMAP
bg(); header("EJECUCIÓN", "Roadmap por fases")
phases = [
    ("0", "Web shell", "Frontend web sobre engine-client (sin Tauri). 1 engine remoto.", BLUE),
    ("1", "Tenancy + control plane", "Orgs/teams/memberships + gateway JWT + provisioner.", AMBER),
    ("2", "Aislamiento híbrido", "Cloud Run gVisor (prueba) + GKE Sandbox (pago) + volúmenes.", GREEN),
    ("3", "Hardening red + datos", "Egress allowlist, NetworkPolicy, CMEK, Binary Authorization.", BLUE),
    ("4", "Billing dual + cuotas", "BYO (prueba) + central markup (pago), medición y rate-limit.", AMBER),
    ("5", "Producto", "Panel admin, roles, observabilidad por tenant, SLA.", GREEN),
]
y = 2.0
for num, t, b, col in phases:
    rect(0.8, y, 0.75, 0.72, fill=col)
    vcell(0.8, y, 0.75, 0.72, num, 24, BG, bold=True, align="c")
    rect(1.7, y, 10.85, 0.72, fill=PANEL)
    vcell(1.9, y, 3.0, 0.72, t, 14, INK, bold=True)
    vcell(5.0, y, 7.4, 0.72, b, 11.5, MUTE)
    y += 0.84
page()

# ===================================================== 12. CIERRE
bg(); header("RESUMEN", "Decisiones tomadas y próximos pasos")
line(0.8, 1.9, "Lo que ya está decidido:", 15, AMBER, bold=True)
bullets(0.85, 2.35, 11.7, [
    ("Tenant = equipo  ", "— un engine aislado por team, sandbox de kernel (no RBAC lógico)."),
    ("Sustrato híbrido  ", "— Cloud Run (prueba) + GKE Sandbox (pago 24/7) desde el inicio."),
    ("Billing dual  ", "— BYO key en prueba, central con markup + cuotas en pago."),
    ("Caso central = 24/7 routines  ", "— define Pago como producto; scale-to-zero en prueba."),
], size=14, gap=0.3)
rect(0.8, 4.95, 11.75, 1.95, fill=PANEL); rect(0.8, 4.95, 0.1, 1.95, fill=GREEN)
line(1.1, 5.1, "Próximos pasos", 15, GREEN, bold=True)
para(1.1, 5.55, 11.2, [("1.  Confirmar storage default del tier Pago (propuesta: GCS, Filestore opt-in).", False, INK)], 13)
para(1.1, 5.95, 11.2, [("2.  Arrancar Fase 0: shell web sobre @houston-ai/engine-client.", False, INK)], 13)
para(1.1, 6.35, 11.2, [("3.  Diseñar el esquema del control plane (orgs/teams/memberships + RLS).", False, INK)], 13)
page()

c.save()
print("PDF OK ->", OUT)
