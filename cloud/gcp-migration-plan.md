# Houston Cloud — Plan de migración a GCP (multi-tenant con aislamiento por equipo)

> Objetivo: dejar de ser solo app de escritorio y ofrecer Houston como servicio
> en GCP, donde **cada equipo solo accede a sus propios agentes** (aunque sea la
> misma organización), con una separación que **no es lógica/por prompt sino a
> nivel de kernel** (sandbox tipo microVM/gVisor), **sin VPS dedicada por
> cliente** y **con costo controlado**.

Este documento resuelve los "Unknowns to solve" de `cloud/README.md` y
`teams/README.md`.

---

## 1. Principio rector — el tenant es el EQUIPO, y el aislamiento es de cómputo

La pregunta de fondo es: ¿qué frontera separa los agentes de un equipo de los de
otro? Tres opciones, de peor a mejor:

| Modelo | Frontera | Por qué NO / SÍ |
|---|---|---|
| Un engine compartido, filtrado por `tenant_id` / RBAC | Lógica (código) | ❌ Un bug en una query o un fallo de autorización filtra datos entre equipos. Es "separación por prompt/código". Rechazado explícitamente. |
| Un proceso engine por equipo, mismo SO/host | Proceso | 🟡 Mejor, pero comparten kernel y filesystem; un escape de proceso cruza tenants. |
| **Un engine por equipo dentro de su propio sandbox de kernel** | **microVM / gVisor** | ✅ Lo que pedís: "casi a nivel de hardware". Cada equipo corre en su sandbox, con su volumen y su token. El escape requiere romper el sandbox de kernel, no solo un check de código. |

**Decisión: `tenant = team`. Un engine `houston-engine` por equipo, ejecutándose
en un sandbox de kernel.** El engine ya soporta esto: es un binario standalone
parametrizado por `HOUSTON_HOME` (datos) y `HOUSTON_ENGINE_TOKEN` (auth) —ver
`knowledge-base/engine-server.md`. No hay que reescribir el engine; hay que
construir el **plano de control** que provisiona, enruta y aísla esas instancias.

Org → Team → Agents. La organización es solo agrupación de facturación/admin; la
unidad de aislamiento real es el equipo.

---

## 2. El aislamiento "casi a nivel de hardware, barato, sin VPS dedicada"

GCP no expone Firecracker directamente, pero sí dos sustratos que dan
aislamiento de kernel sobre **nodos compartidos** (= barato, sin VM por cliente):

### Opción A — Cloud Run gen2 (recomendada como default)
- Cada engine de equipo = un **servicio Cloud Run** (gen2). Cada instancia corre
  en una **microVM con gVisor** gestionada por Google. Aislamiento de kernel sin
  que administremos VMs.
- **Scale-to-zero**: equipo inactivo = 0 instancias = $0 cómputo. Esto es la
  palanca de costo más fuerte y encaja con uso intermitente (un equipo no chatea
  24/7).
- Volumen de datos por equipo vía **Cloud Run volume mounts** (GCS bucket por
  equipo con gcsfuse, o Filestore para equipos pesados).
- Límites a vigilar: ejecución de subprocesos CLI largos (timeout de request no
  aplica a la instancia si usamos el modo "instance-based billing" + min/max
  instances; las sesiones de chat son cortas, las routines pueden necesitar el
  tier B).

### Opción B — GKE + GKE Sandbox (gVisor) para el tier "Always On"
- Para equipos que necesitan agentes **24/7** (routines, scheduler, ver
  `houston-scheduler`), scale-to-zero no sirve. Ahí: un **pod por equipo** en un
  cluster GKE con **GKE Sandbox (gVisor)** activado.
- Un pod por equipo, **namespace por equipo**, bin-packing de muchos pods en
  pocos nodos → barato. Nodos en **Spot VMs** (preemptibles) para el grueso.
- `NetworkPolicy` deny-all entre namespaces → cero tráfico este-oeste entre
  equipos.

### Decisión tomada: híbrido por tier desde el inicio
Como el caso de uso principal son **agentes 24/7 con routines** (`houston-scheduler`),
el caballo de batalla es **GKE Sandbox**, no Cloud Run. Dos tiers, ambos sobre la
**misma imagen** de engine y el mismo plano de control:

| Tier | Sustrato | Ejecución | Billing API | Aislamiento |
|---|---|---|---|---|
| **Free / Lite** | **Cloud Run gen2** | On-demand, **scale-to-zero** (sin routines 24/7) | **BYO key** (la trae el equipo) | microVM + gVisor |
| **Pro / Always On** | **GKE + GKE Sandbox** | **24/7**, min 1 réplica por equipo, Spot VMs | **Central con markup** (cuotas + rate-limit por equipo) | pod gVisor, namespace por equipo |

- El tier free no corre el scheduler de forma persistente → puede hibernar a cero.
  Cuando un equipo free necesita routines 24/7, **sube a Pro** y su engine migra de
  Cloud Run a un pod GKE (mismo `HOUSTON_HOME`, solo cambia el sustrato).
- El plano de control elige el sustrato al provisionar según el tier; el binario y
  los datos son idénticos, así que la promoción free→pro es mover el volumen, no
  migrar datos.

#### El tier de prueba (Free) abarata el costo FIJO, no solo el por-equipo
El por-equipo del free ya es ~$0 (scale-to-zero). Lo caro es el costo fijo
compartido (~$186/mes), inflado por GKE ($73), Cloud NAT ($33) y Cloud SQL ($35)
— **infra que el free no necesita**. La ruta del tier de prueba evita las tres:

| Pieza | Pro / pago | Prueba / free |
|---|---|---|
| Sustrato | GKE Sandbox (24/7) | **Cloud Run gVisor** (scale-to-zero) |
| DB metadata | Cloud SQL | **Supabase** (ya existe, $0 incremental) |
| Egress | Cloud NAT + allowlist | egress gestionado de Cloud Run (sin NAT) |
| Storage | bucket/volumen por equipo (+ Filestore opt-in) | **1 bucket GCS compartido, prefijo + IAM por equipo** |
| Cluster fee | GKE $73/mes | $0 (no hay cluster) |

→ **Fijo del tier de prueba ≈ $15–35/mes**, casi independiente del nº de equipos
(escalan a cero). Uso ligero puede caer en la **cuota always-free de Cloud Run**
(2M req, 360k vCPU-s/mes) = **$0 de cómputo real**.

Controles para que el free no se dispare: cap de 1–2 agentes, **sin scheduler 24/7**
(es feature de Pro), minutos de sesión limitados, hibernación + **TTL de datos**
(borrar datos de free dormido tras 30–60 días, avisando).

**Importante:** el tier de prueba **conserva el sandbox de kernel** (gVisor de
Cloud Run). No bajamos la garantía de aislamiento para ahorrar; solo quitamos
infra fija que el free no usa.

> Palanca extra (no recomendada salvo necesidad): un **engine único compartido**
> para free con separación lógica (OS-user/cgroups) sería aún más barato a alta
> concurrencia, pero **pierde la frontera de kernel** entre equipos free. Solo si
> los datos de prueba fueran desechables. Documentada, no elegida.

> Por qué esto cumple lo que pediste: gVisor/microVM = frontera de **kernel** sin
> una VM dedicada por cliente; bin-packing/scale-to-zero sobre nodos compartidos
> = económico; un sandbox por equipo = **no es separación por prompt**.

### Endurecimiento dentro del sandbox (defensa en profundidad)
Aunque cada equipo ya esté aislado, cada engine corre:
- como **usuario no-root**, rootfs **read-only** salvo el volumen del equipo,
- `no-new-privileges`, capabilities **dropeadas** (sin `NET_RAW`), seccomp,
- **egress allowlist** por equipo (solo APIs de proveedores LLM + Composio +
  Supabase) vía Cloud NAT + reglas de firewall / política de egress. Esto frena
  exfiltración aunque un agente sea inducido a ello (prompt injection).
- secrets montados desde **Secret Manager**, nunca horneados en la imagen.

---

## 3. Arquitectura GCP (componentes)

```
                         ┌─────────────────────────────────────────────┐
  Browser / Mobile PWA   │                  GCP                          │
        │                │                                               │
        │  HTTPS/WSS     │   ┌───────────────┐    ┌──────────────────┐   │
        └────────────────┼──▶│  Gateway /     │    │  Control Plane    │  │
                         │   │  Router (CR)   │◀──▶│  (Cloud Run)      │  │
        Supabase JWT  ───┼──▶│  valida JWT +  │    │  provisiona/rutea │  │
        (Google SSO)     │   │  membership    │    │  orgs/teams/engines│  │
                         │   └───────┬───────┘    └─────────┬────────┘   │
                         │           │ rutea a su engine     │           │
                         │           ▼                       ▼           │
                         │   ┌──────────────┐        Cloud SQL / Supabase │
                         │   │ Engine team A │        (orgs, teams,        │
                         │   │ (gVisor pod / │         memberships,        │
                         │   │  Cloud Run)   │         engine registry)    │
                         │   │  HOUSTON_HOME │                             │
                         │   │  vol team A   │   Secret Manager (tokens,   │
                         │   └──────────────┘   provider creds por equipo) │
                         │   ┌──────────────┐                             │
                         │   │ Engine team B │   Artifact Registry         │
                         │   │  vol team B   │   (imagen engine firmada)   │
                         │   └──────────────┘                             │
                         └─────────────────────────────────────────────┘
```

| Componente | Servicio GCP | Qué hace | Estado en el repo |
|---|---|---|---|
| **Frontend web** | Cloud Run / Firebase Hosting + CDN | Sirve la app web (reusa `ui/@houston-ai/*`). La PWA móvil ya existe (`mobile/`). | Falta el "shell" web que reemplace al adapter Tauri |
| **Gateway / Router** | Cloud Run (o API Gateway / GCLB) | Termina TLS, valida JWT de Supabase, resuelve `user → team → engine`, enruta a la instancia del equipo, fuerza el token del engine. | Nuevo |
| **Control plane** | Cloud Run | API de orgs/teams/invites/provisioning. Crea/destruye engines, volúmenes, tokens. | Nuevo (`teams/` placeholder) |
| **Engines por equipo** | Cloud Run gen2 / GKE Sandbox | El `houston-engine` aislado por equipo. | ✅ binario listo |
| **Metadata DB** | Supabase (Postgres) o Cloud SQL | orgs, teams, memberships, roles, engine registry. RLS. | Parcial: auth ya existe |
| **Datos por equipo** | GCS bucket o Filestore (1 por equipo) | `HOUSTON_HOME` aislado: DB libSQL, workspaces, `.houston/`. | ✅ engine ya parametriza `HOUSTON_HOME`/`HOUSTON_DOCS` |
| **Secrets** | Secret Manager | token del engine, credenciales de proveedor por equipo. | Nuevo |
| **Imagen** | Artifact Registry + Binary Authorization | imagen engine escaneada y firmada. | Hay `always-on/Dockerfile` como base |
| **Observabilidad** | Cloud Logging / Monitoring / Trace | logs, métricas, auditoría. | Engine ya emite `tracing` |

---

## 4. Cambios de código (mapeados al repo real)

El engine **no** necesita reescritura; la mayoría del trabajo es plano de control
y un shell web. Lo concreto:

### 4.1 Frontend web (reemplazar el adapter Tauri)
- Hoy el cliente es Tauri (`app/`). `@houston-ai/engine-client` ya habla HTTP/WS
  puro, así que un **shell web** (Vite + React) puede montar las mismas vistas de
  `ui/`. Referencia ya existente: `examples/smartbooks/` (frontend custom sobre
  el engine, ~400 LOC).
- Las features OS-native (file picker, reveal-in-finder) ya se deshabilitan
  cuando el engine es remoto — el guard `osIsTauri()` existe (ver `auth.md`,
  sección de re-auth). Reusarlo.
- El **prompt de producto** hoy vive en la app (`app/src-tauri/src/houston_prompt.rs`)
  y se pasa al engine por `HOUSTON_APP_SYSTEM_PROMPT`. En cloud, **el control
  plane** lo inyecta al provisionar el engine. El engine sigue prompt-agnóstico.

### 4.2 Auth de proveedor headless (ya soportado, validar)
- En cloud no hay navegador local para el OAuth callback de claude/codex. El
  engine **ya** soporta device-code flow (`codex login --device-auth`, paste-back
  de claude) — ver `auth.md` "Headless connect". Esto es crítico y ya está.
- **Billing de API (decidido): modelo dual por tier.**
  - **Free → BYO key**: el equipo conecta su propia cuenta/key vía el flujo
    headless. Las credenciales viven en el **volumen aislado del equipo**
    (`~/.codex/auth.json`, `~/.gemini/.env`, sesión de claude) — nunca en nuestra
    DB. Costo de API = del equipo.
  - **Pro → billing central con markup**: la key la inyecta el **plano de control**
    desde Secret Manager al provisionar el engine (env var por equipo). Debemos
    añadir **cuotas + rate-limit por equipo** y medición de uso (tokens) para
    facturar. La medición sale del feed de sesiones del engine; el límite se
    aplica en el gateway / control plane, no dentro del engine (que sigue
    agnóstico).

### 4.3 Plano de control (nuevo, en `cloud/` + `teams/`)
- Servicio que expone: crear org, crear team, invitar miembros, asignar roles
  (admin/editor/viewer — ya listados en `teams/README.md`).
- **Provisioner**: al crear un team → crea bucket/volumen, genera token en Secret
  Manager, despliega el engine (Cloud Run service o GKE pod), registra
  `team → engine_url` en la DB.
- **Reaper / hibernación**: scale-to-zero automático; destruye recursos al borrar
  el team.

### 4.4 Gateway de tenancy
- Middleware que: valida el JWT de Supabase → extrae `user_id` → consulta
  membership → resuelve el engine del team → proxya HTTP/WS inyectando el
  `HOUSTON_ENGINE_TOKEN` del team (el cliente nunca lo ve).
- Enrutamiento por **subdominio** (`team-<id>.app.gethouston.ai`) o por path. El
  JWT ya puede portar claims de org/team (hoy `HOUSTON_APP_USER_ID` se pasa como
  opaco — `auth.md`).

### 4.5 Modelo de datos (Supabase/Cloud SQL + RLS)
```sql
orgs(id, name, created_at)
teams(id, org_id, name, engine_url, engine_secret_ref, tier, created_at)
memberships(user_id, team_id, role)   -- role: admin|editor|viewer
-- RLS: un usuario solo lee teams donde tiene membership.
```
Esto solo gobierna **metadata/ruteo**. Los datos de los agentes viven aislados en
el volumen de cada engine, no en esta DB.

---

## 5. Seguridad (capas)

1. **Identidad** — Supabase + Google SSO (ya existe, `auth.md`). JWT con claims
   de org/team.
2. **Autorización** — el gateway valida membership antes de rutear. No existe ruta
   de un usuario al engine de otro team: el ruteo es por membership y el token del
   engine nunca sale del gateway.
3. **Aislamiento de cómputo** — sandbox de kernel (gVisor/microVM) por team (§2).
   Esta es la garantía dura, no un check de código.
4. **Red** — VPC; `NetworkPolicy` deny-all este-oeste entre engines; **egress
   allowlist** por team (solo APIs necesarias) vía Cloud NAT + firewall.
5. **Secrets** — Secret Manager; montados por team; rotación; nunca en la imagen
   ni en logs (el engine ya evita loguear su token — `engine-server.md`).
6. **Datos en reposo** — buckets/discos por team con **CMEK** (claves gestionadas
   por cliente). Path-traversal ya cubierto en el engine (`safe_relative`).
7. **Cadena de suministro** — Artifact Registry + escaneo de vulnerabilidades +
   **Binary Authorization** (solo imágenes firmadas corren).
8. **Auditoría** — Cloud Audit Logs (plano de control) + `tracing` del engine por
   request. Quién accedió a qué team y cuándo.

---

## 6. Costo / economía

Con **24/7 routines** como caso principal, el tier Pro NO puede escalar a cero, así
que el costo se controla distinto en cada tier:

**Tier Pro (GKE 24/7) — el que carga costo fijo, por eso es de pago:**
- **Spot/preemptible VMs** para el grueso de los nodos (el scheduler tolera
  reinicios; el engine reanuda routines al rearrancar). Un pool pequeño on-demand
  para lo que no tolere preemption.
- **Bin-packing** denso de pods gVisor: muchos teams por nodo compartido (el
  aislamiento lo da gVisor, no el nodo). Cluster Autoscaler ajusta nodos a la
  demanda agregada.
- **Right-sizing**: requests de CPU/mem ajustados; un engine idle entre routines
  consume casi nada. VPA para afinar.
- El precio del tier Pro debe cubrir: nodo prorrateado + storage + markup de API.

**Tier de prueba / Free (Cloud Run on-demand) — barato por diseño:**
- **Scale-to-zero**: team free inactivo = $0 cómputo (cold start de segundos,
  aceptable porque no corre routines persistentes).
- **BYO key**: el costo de API no es nuestro.
- **Costo fijo recortado**: su ruta no usa GKE/NAT/Cloud SQL → el fijo del tier de
  prueba es **~$15–35/mes** (control plane Cloud Run + Supabase + bucket
  compartido), casi independiente del nº de equipos. Uso ligero entra en la cuota
  always-free de Cloud Run = $0 cómputo. Mantiene el sandbox gVisor.

**Transversal:**
- **Control plane compartido** (no por tenant): costo fijo pequeño.
- **Storage barato**: GCS + gcsfuse por defecto; Filestore (caro) solo para teams
  Pro que lo justifiquen por I/O. Evitar Persistent Disk siempre-encendido por team
  free.
- **Hibernación** de teams Pro genuinamente dormidos (sin routines activas ni
  sesiones por N días) → escalar su Deployment a 0 réplicas y rearrancar on-demand.

---

## 7. Decisiones tomadas

1. **Sustrato: híbrido desde el inicio.** GKE Sandbox (gVisor) como caballo de
   batalla para el tier Pro 24/7; Cloud Run gen2 para el tier Free on-demand.
2. **Billing de API: dual por tier.** Free = BYO key (credenciales en el volumen
   del equipo); Pro = central con markup (key inyectada desde Secret Manager +
   cuotas/rate-limit por equipo).
3. **Caso principal: agentes 24/7 con routines.** Define el tier Pro como producto
   central; scale-to-zero queda solo para el tier Free.

Queda **una** decisión menor por confirmar:
- **Storage default del tier Pro**: GCS+gcsfuse (barato, mayor latencia) vs
  Filestore (rápido, caro). Propuesta: GCS por defecto, Filestore opt-in para
  equipos con I/O intensivo. Confírmalo cuando lleguemos a Fase 2.

---

## 8. Roadmap por fases

| Fase | Entregable | Aislamiento | GCP |
|---|---|---|---|
| **0. Web shell** | Frontend web sobre `@houston-ai/engine-client` (sin Tauri). Conecta a UN engine remoto (modo Always On ya existente). | Ninguno (single-tenant dev) | Cloud Run (1 engine) |
| **1. Tenancy + control plane** | Control plane + modelo orgs/teams/memberships + gateway con JWT. Provisioner que crea 1 engine por team. | Contenedor por team | Cloud Run por team + Cloud SQL/Supabase |
| **2. Aislamiento fuerte (híbrido)** | Sustrato dual: **Cloud Run gen2 (free)** + **GKE Sandbox (pro 24/7)**, volúmenes por team + Secret Manager + reaper/hibernación. Promoción free→pro mueve el volumen. | **Kernel (gVisor) en ambos** | Cloud Run gen2 + GKE Sandbox + GCS/Filestore |
| **3. Hardening de red + datos** | Egress allowlist por team, NetworkPolicy deny-all este-oeste, CMEK, Binary Authorization, auditoría. | + red + reposo | VPC, Cloud NAT, KMS |
| **4. Billing dual + cuotas** | BYO key (free) + billing central con markup (pro): medición de tokens, cuotas y rate-limit por team en el gateway. Spot VMs + bin-packing afinados. | — | Stripe, Monitoring |
| **5. Producto** | Panel admin, roles (admin/editor/viewer), observabilidad por tenant, SLA. | — | Monitoring |

Cada fase es desplegable y testeable por sí sola. Library-first: lo reusable
(web shell, engine) antes que lo específico de cloud.

---

## 9. Qué del repo ya juega a favor

- ✅ Engine standalone HTTP/WS, parametrizado por `HOUSTON_HOME` + token.
- ✅ `always-on/` ya tiene Dockerfile + compose + systemd → base de la imagen.
- ✅ Auth Supabase + Google SSO + JWT.
- ✅ Headless provider login (device-code) — imprescindible en cloud.
- ✅ `examples/smartbooks/` prueba que un frontend no-Tauri funciona end-to-end.
- ✅ Reactividad por eventos WS + file watcher (no asume webview local).
- ✅ Path-traversal y escritura atómica ya endurecidos en `houston-agent-files`.

Lo que falta es **plano de control + gateway de tenancy + shell web + provisioning
con sandbox**, no tocar el núcleo del engine.
