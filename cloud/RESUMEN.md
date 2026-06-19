# Houston Cloud en GCP — Resumen ejecutivo y técnico

Documento de consolidación. Reúne, en detalle, **(1) lo que ya existe** (en el
repo y como entregables de esta sesión), **(2) las decisiones tomadas con su
justificación**, **(3) la solución técnica**, **(4) costos**, y **(5) el plan a
1 semana y 1 mes**. Fuente larga: `cloud/gcp-migration-plan.md`.

---

## 1. Lo que ya hay

### 1.1 Entregables producidos en esta sesión (rama `claude/focused-euler-t39816`)

| Archivo | Qué es |
|---|---|
| `cloud/gcp-migration-plan.md` | Plan completo (arquitectura, tenancy, aislamiento, seguridad, costos, roadmap). Documento maestro. |
| `cloud/houston-cloud-gcp.pdf` | Deck de 12 páginas para abrir/presentar (cualquier visor). **Usar este para abrir.** |
| `cloud/houston-cloud-gcp.pptx` | Mismo deck, formato editable PowerPoint. |
| `cloud/build_deck.py` | Generador del `.pptx` (python-pptx). Editar aquí y regenerar. |
| `cloud/build_deck_pdf.py` | Generador del `.pdf` (reportlab). |

> Nota: el LibreOffice del entorno no abre `.pptx`, por eso se generó el PDF
> directo con reportlab. El `.pptx` queda como fuente editable.

### 1.2 Lo que el repo YA aporta a favor de la migración

Esto es clave: el trabajo pesado del backend está hecho. No se reescribe el engine.

| Activo existente | Por qué sirve |
|---|---|
| **Engine standalone** (`houston-engine`) | Binario que habla HTTP/WS, parametrizado por `HOUSTON_HOME` (datos) y `HOUSTON_ENGINE_TOKEN` (auth). Un proceso aislado por tenant = configurar esas dos variables. |
| **`always-on/`** | Dockerfile + docker-compose + unit de systemd ya escritos → base directa de la imagen de cloud. |
| **Auth Supabase + Google SSO** (`knowledge-base/auth.md`) | Identidad ya resuelta: PKCE, JWT, sesiones. Falta solo el modelo org/team encima. |
| **Login de proveedor headless** (device-code) | Imprescindible en cloud (no hay navegador local). Ya soportado para Claude/Codex/Gemini. |
| **`examples/smartbooks/`** | Prueba end-to-end de un frontend NO-Tauri sobre el engine (~400 LOC). Patrón del shell web. |
| **`ui/@houston-ai/*`** + `engine-client` | Componentes y cliente TS reutilizables para el frontend web. |
| **Reactividad por eventos** (WS + file watcher) | No asume webview local; funciona igual contra un engine remoto. |
| **Escritura atómica + anti path-traversal** (`houston-agent-files`) | Aislamiento dentro del volumen del tenant ya endurecido. |

### 1.3 Lo que NO existe todavía (lo que hay que construir)

- **Gateway de tenancy** (verifica JWT, resuelve `user→team→engine`, proxya HTTP+WS).
- **Control plane / provisioner** (crea/destruye engines, volúmenes y tokens; modelo orgs/teams/memberships).
- **Shell web** (reemplaza al cliente Tauri).
- **IaC** (Terraform/gcloud) + imagen del engine en Artifact Registry.

---

## 2. Decisiones tomadas (con justificación)

| # | Decisión | Por qué |
|---|---|---|
| **D1** | **Tenant = equipo.** Un `houston-engine` aislado por team. | La org agrupa facturación/admin; el equipo es la unidad de acceso. "Cada equipo solo ve sus agentes, aunque sea la misma org." |
| **D2** | **Aislamiento de CÓMPUTO, no lógico.** Sandbox de kernel (gVisor/microVM), no un engine compartido con filtro por `tenant_id`. | Un filtro por código se rompe con un bug = fuga entre equipos. El requisito fue "no por prompt, casi a nivel de hardware". |
| **D3** | **Sustrato híbrido desde el inicio.** Cloud Run gen2 (gVisor) para prueba + GKE Sandbox (gVisor) para pago. | Cubre los dos modos sin reescribir: scale-to-zero barato para prueba, 24/7 para pago. |
| **D4** | **Billing de API dual.** Prueba = BYO key; Pago = central con markup + cuotas. | Prueba sin costo de API para nosotros; pago con mejor UX y control de abuso. |
| **D5** | **Caso de uso central = agentes 24/7 con routines.** | Define el tier Pago como producto principal; scale-to-zero queda solo para prueba. |
| **D6** | **Dos tiers explícitos: pago (fuerte) y prueba (barato).** | Pedido directo del usuario: "una para clientes pagos y otra para usuarios de prueba". |
| **D7** | **El tier de prueba recorta el costo FIJO, no baja el aislamiento.** Quita GKE/NAT/Cloud SQL, mantiene gVisor. | El por-equipo del free ya era ~$0 (scale-to-zero); lo caro era el fijo compartido. Se abarata sin sacrificar la frontera de kernel. |

**Decisión menor pendiente:** storage default del tier Pago — propuesta **GCS+gcsfuse** (barato) con **Filestore opt-in** (rápido, caro) para I/O intensivo.

**Opción documentada pero NO elegida:** un engine único compartido con separación
lógica (OS-user/cgroups) para el free sería aún más barato, pero pierde la
frontera de kernel entre equipos de prueba. Solo valdría si esos datos fueran
desechables. Queda como palanca futura, no recomendada.

---

## 3. La solución técnica

### 3.1 Por qué el engine ya lo permite
Dos engines con distinto `HOUSTON_HOME` + token son dos universos de datos que no
se ven entre sí. El control plane provisiona uno por equipo; el núcleo no se toca.

### 3.2 Flujo de un request
```
Browser ──HTTPS/WSS──▶  Gateway  ──▶  Engine del team (sandbox gVisor)
  (Supabase JWT)          1. verifica JWT (JWKS de Supabase)
                          2. user_id → consulta membership
                          3. resuelve team → engine_url + token
                          4. proxya HTTP+WS inyectando el token
                             (el cliente NUNCA ve ese token)
```
**Garantía:** no hay ruta de un usuario al engine de otro team. El ruteo lo decide
el `membership` y el token del engine no sale del gateway. URL adivinada sin token = 401.

### 3.3 Aislamiento de cómputo
- **Cloud Run gen2 (prueba):** cada instancia = microVM + gVisor gestionada. gVisor
  intercepta syscalls en user-space → el agente no habla directo con el kernel del
  host. Scale-to-zero = $0 idle.
- **GKE + GKE Sandbox (pago 24/7):** un pod gVisor por team, namespace propio,
  Spot VMs bin-packeadas, `NetworkPolicy` deny-all este-oeste.
- Misma imagen en ambos; el provisioner elige el sustrato según el tier.

### 3.4 Aislamiento de datos
`HOUSTON_HOME` por team → volumen propio (bucket GCS montado, o Filestore para I/O
pesado). Escritura atómica + anti path-traversal ya están en el engine.

### 3.5 Credenciales de proveedor
Flujo headless ya soportado (device-code / API key). Prueba = BYO (en el volumen
del team); Pago = inyectadas por el control plane desde Secret Manager.

### 3.6 Seguridad en capas
1. **Identidad** — Supabase + Google SSO (existe). JWT con claims org/team.
2. **Autorización** — gateway valida membership; token del engine nunca sale del borde.
3. **Cómputo** — sandbox de kernel (gVisor) por team. Garantía dura, no un `if`.
4. **Red** — NetworkPolicy deny-all + egress allowlist por team.
5. **Secrets** — Secret Manager por team, rotación, nunca en imagen ni logs.
6. **Datos en reposo** — buckets/discos por team con CMEK.
7. **Cadena de suministro** — Artifact Registry + scan + Binary Authorization.
8. **Auditoría** — Cloud Audit Logs + tracing por request.

---

## 4. Costos (orden de magnitud, us-central1, USD/mes)

### 4.1 Costo fijo compartido — Pago vs Prueba

| Concepto | Pago | Prueba |
|---|---|---|
| GKE cluster fee | $73 | — |
| Cloud SQL (control plane) | $35 | — |
| Cloud NAT | $33 | — |
| Gateway + control plane (Cloud Run) | $20 | $15 |
| Supabase (metadata) | incl. | $0* |
| Logging / Monitoring | $20 | $5 |
| Secret Manager + misc | $5 | $2 |
| **TOTAL FIJO** | **≈ $186** | **≈ $22** |

\* Uso ligero de prueba cae en la cuota always-free de Cloud Run = $0 cómputo.

### 4.2 Costo variable por equipo (infra, sin API)

| Concepto | Pago 24/7 | Prueba |
|---|---|---|
| Cómputo (Spot/Cloud Run) | $3.0 | $0–2 |
| Storage GCS | $0.30 | $0.10 |
| NAT / egress | $1.0 | ~$0 |
| Logs / secrets / misc | $0.70 | ~$0 |
| **POR EQUIPO** | **≈ $5–8** | **≈ $0–2** |

**API LLM aparte:** prueba = BYO ($0 para nosotros); pago = pass-through + markup
(ingreso, no costo neto).

### 4.3 Escenarios

| Escenario | Total infra/mes | Por equipo |
|---|---|---|
| Solo prueba: 2,000 free (BYO) | ≈ $22–100 | ≈ $0.02 |
| 50 equipos Pago | ≈ $536 | ≈ $10.7 |
| 200 equipos Pago | ≈ $1,386 | ≈ $6.9 |
| 100 Pago + 400 prueba | ≈ $886 | ≈ $1.8 |
| 500 equipos Pago | ≈ $2,936 | ≈ $5.9 |

**Vs. VPS dedicada por equipo (lo rechazado):** 200 VPS on-demand ≈ $2,600/mes solo
cómputo; nuestro modelo a 200 Pago ≈ $1,386 con aislamiento de kernel **más fuerte**
(~2x más barato). Mejora con escala por mejor bin-packing.

---

## 5. Plan: 1 semana vs 1 mes

**Reparto:** yo escribo Dockerfile, gateway, control plane, shell web, Terraform,
CI. Una persona hace en GCP lo que requiere consola/billing: crear proyecto GCP +
billing, Service Account/permisos, dominio/DNS, y el proyecto Supabase (ya existe).

### 5.1 En 1 SEMANA — PoC demoable (no producción)
Objetivo: probar el principio end-to-end con **2 equipos reales** y aislamiento de kernel.

1. Imagen del engine para cloud (reusar `always-on/Dockerfile`) → Artifact Registry.
2. Desplegar **2 servicios Cloud Run** (team A, team B), cada uno con su `HOUSTON_HOME`
   en GCS y su token en Secret Manager.
3. **Gateway mínimo** (axum/Node): verifica JWT Supabase, mapa estático user→team,
   proxya HTTP **y WebSocket** con el token del engine.
4. **Shell web mínimo** (Vite + `engine-client` + chat de `ui/`), o atajo: usar el
   "connect remote engine" existente.
5. IaC reproducible + README de demo.

**Resultado:** entras por navegador, login Google, chateas con un agente de tu
equipo; un usuario del team B **no puede** alcanzar el engine del team A. El
aislamiento gVisor es gratis (Cloud Run gen2 lo da).

**No entra:** provisioning automático (teams a mano), UI pulida, tier 24/7, egress
allowlist, CMEK, billing. Es para enseñar y validar.

**Cuello de botella técnico de la semana:** el proxy de WebSocket con auth en el gateway.

### 5.2 En 1 MES — MVP del tier de prueba (free), self-service
Objetivo: cualquiera se registra y obtiene su equipo aislado, automático, en Cloud Run.

| Área | Entregable |
|---|---|
| **Control plane** | API + Postgres (orgs, teams, memberships, engine-registry). **Provisioning automático**: crear team → Cloud Run service + volumen + token. Deprovision/hibernación. |
| **Tenancy** | Supabase **RLS** sobre la metadata; invitaciones; roles admin/miembro. Gateway con ruteo por subdominio + JWKS cache + WS estable. |
| **Web** | Shell real: sign-in, selector de equipo, board + chat (`ui/`), conexión headless de proveedor (BYO key). |
| **Seguridad base** | Contenedor non-root + rootfs read-only, secrets desde Secret Manager, HTTPS-only, audit logging. |
| **Ops** | CI/CD (build+push imagen, deploy gateway/control-plane), Terraform versionado, health checks + alertas. |
| **Validación** | Onboardar un puñado de equipos free reales y medir. |

**Stretch (probablemente segundo mes para production-grade):** tier **GKE Sandbox 24/7**,
**egress allowlist**, **CMEK**, **Binary Authorization**, **billing/medición** (Stripe)
y cuotas. Andamiaje posible en el mes; endurecerlo para clientes de pago es trabajo extra.

**Cuello de botella técnico del mes:** provisioning automático + RLS.

### 5.3 Honestidad
- **Semana** = funciona y se demuestra el aislamiento por equipo en GCP. Frágil, manual.
- **Mes** = tier de prueba usable de verdad, self-service. El tier de pago 24/7 es lo siguiente.
- El resto es relativamente directo porque **el engine ya está hecho**.

---

## 6. Próximos pasos sugeridos
1. Confirmar storage default del tier Pago (propuesta: GCS, Filestore opt-in).
2. Despejar prerequisitos GCP (proyecto + billing + Service Account + dominio).
3. Arrancar Fase 0 / semana 1: scaffolding en `cloud/poc/` (Dockerfile + Terraform de
   los 2 Cloud Run + esqueleto del gateway con verificación de JWT).
