# Módulo de Fuerza y Pasadas — Plan de trabajo

Documento único de decisiones. Lo leen Tomi, Claude (chat) y Claude Code (VS Code).
Última actualización: 2026-11-03. Rama de trabajo: `fuerza-gym`.

## 1. Objetivo

Sumar a CN Hockey (Streamlit) una sección de **fuerza (gimnasio) + pasadas (carreras)** con:
- catálogo de ejercicios,
- planificación por día del microciclo (MD-5, MD-4, MD-2),
- registro de lo ejecutado con historial de todas las sesiones,
- cuantificación de la carga con la misma lógica aguda/crónica (ACWR) que ya usa la carga GPS.

Mock up de referencia (diseño): artifact "Planificación de Fuerza CN Hockey" en claude.ai (datos de ejemplo).

## 2. Decisiones tomadas

| # | Decisión |
|---|---|
| D1 | El plan se arma **en la app** y se guarda en **Supabase**. Streamlit Cloud no puede escribir en Sheets ni en archivos del repo. |
| D2 | Lo **ejecutado** se registra a **nivel equipo** primero. La carga individual (por jugadora) viene después y reutiliza `fuerza_registro`. |
| D3 | La intensidad de fuerza se prescribe en **% de RM**. Las jugadoras cargan su RM en la app (`registros_rm`). |
| D4 | Ejercicios **sin RM** (ABD, Remo TRX, etc.): carga baja. Intensidad base **editable** por ejercicio (columna `INTENSIDAD_BASE` en el Sheet). Valor por defecto provisorio: 50%. |
| D5 | Las **pasadas** (carreras) se miden en **metros**, no en UA: metros totales y metros a alta intensidad. No se suman a la carga de fuerza. Umbral de alta intensidad **editable**, provisorio 85% de Vmáx. |
| D6 | Las pasadas se prescriben por **distancia y zona de velocidad** (% de la velocidad máxima de cada jugadora, que sale del GPS). Detalle en la sección 6. |
| D7 | `Ejercicios_fisico` (Google Sheets) es la **única fuente** del catálogo físico: pestañas `Catalogo_fuerza` y `Catalogo_resist`. |
| D8 | `EJERCICIO_REFERENCIA` se descarta (columna sin uso). |
| D9 | Las jugadoras podrán cargar RM de **Arranque** y **Tirones de cargada** en su app. |
| D10 | Marca **"ya está en el GPS"** en cada sesión, para no contar dos veces las pasadas hechas con el chaleco. |

## 3. Qué ya existe (inventario al 2026-11-02)

**CN_HOCKEY (Streamlit)** — borrador guardado en la rama `fuerza-gym` (commit "wip: módulo de fuerza"):
- `pages/10_fuerza.py`: pestañas "Cargar sesión" (por jugadora) e "Historial".
- `src/loaders/fuerza_loader.py`, `src/metrics/fuerza.py` (RM vigente, Epley, tonelaje), `tests/test_fuerza.py`.
- `sql/`: esquema del borrador (ya aplicado en Supabase, ver abajo).
- `settings.py` apunta al Sheet `Ejercicios_fisico` (`FUERZA_SHEET_ID`). El GID de la pestaña `Fuerza_Plan` **ya no existe** en el Sheet y deja de usarse (D1).

**Supabase (proyecto wellness-hockey)**:
- `registros_rm`: 363 filas, 8 ejercicios (banco_plano, press_hombros, cargadas, hip_thrust, remo, peso_muerto, sentadilla_detras, sentadilla_delante).
- `fuerza_registro`: 0 filas (nunca usada). Rol `fuerza_writer` y vistas `jugadoras_rm_analitica` y `jugadoras_fuerza_analitica` ya creados. Desde la 0063 ya no tiene grants para `anon`/`authenticated`.
- `catalogo_ejercicios`: 15 filas. Los 8 de tipo `fisico` coinciden en nombre con parte de `Catalogo_resist` (Velocidad 30 a 70, Pasadas, Intermitentes, Otro) y tienen los parámetros vacíos; `Catalogo_resist` tiene 13 filas porque repite nombres. Ya tiene las columnas (largo, ancho, m², tiempos, series, reps, perfil, % partido, jugadores, día de microciclo).
- `registros_sesiones`: registro de sesiones del staff (6 filas, casi todas técnico-tácticas).

**APP_JUGADORAS_CV (Next.js)**:
- Las migraciones de la base viven en `supabase/migrations/` (hasta la 0060, más la 0061 de seguridad).
- `src/lib/sync-catalogo-ejercicios.ts` sincroniza `catalogo_ejercicios` desde **otra** planilla (la de wellness, pestaña `Catalogo_Ejercicios`).
- Catálogo de RM fijo en `src/lib/entrenamiento/ejercicios.ts`, reflejado en un check de `registros_rm`.
- `AGENTS.md`: esta versión de Next.js tiene cambios importantes; leer `node_modules/next/dist/docs/` antes de escribir código.

## 4. Seguridad (lección aprendida)

Las vistas `jugadoras_wellness_analitica`, `jugadoras_rm_analitica` y `jugadoras_fuerza_analitica` eran legibles por `anon` y `authenticated` vía la API pública. Corregido el 2026-11-02 con la migración **0061** (aplicada en producción; archivo en la rama `seguridad-vistas-analiticas` del repo de la app).

**Regla**: toda vista o tabla nueva para Streamlit se crea con RLS (tablas) y se cierra de inmediato con
`revoke all on <objeto> from anon, authenticated;` dejando SELECT solo a `streamlit_readonly` (lectura) o `fuerza_writer` (escritura).

Avisos menores pendientes (no urgentes): `es_staff()` y `jugadoras_activas_con_foto()` ejecutables por `anon`; `set_updated_at` sin `search_path` fijo; protección de contraseñas filtradas desactivada; (los grants de `fuerza_registro` para `anon`/`authenticated` se revocaron el 2026-11-03 con la 0063).

## 5. Modelo de datos (aplicado el 2026-11-03, migración 0063)

Todo aditivo. Archivo: `APP_JUGADORAS_CV/supabase/migrations/0063_fuerza_plan_semanal.sql` (rama `fuerza-plan-semanal`, commit 91041d7). Ya está aplicada en producción.

**Plan semanal separado por Match Day**: un plan = una semana (`semana_inicio` es un lunes, único). Cada ítem lleva su `match_day` (`MD-5`, `MD-4`, `MD-2`; el formato admite otros, p. ej. `MD-3` o `MD+1`) y un `orden` dentro del día.

**Permisos**: RLS activado y ningún permiso para `anon`/`authenticated`. `fuerza_writer` lee y escribe; `streamlit_readonly` solo lee.

| Tabla | Para qué | Columnas principales |
|---|---|---|
| `fuerza_planes` | Plan de una semana | id, semana_inicio, nombre, estado (borrador/publicado) |
| `fuerza_plan_items` | Lo **prescrito** | plan_id, match_day, orden, tipo (fuerza/pasada), ejercicio_id (ID del Sheet) + ejercicio_nombre (foto del nombre), series, repeticiones (en pasadas: cantidad de pasadas), pct_rm, distancia_m, zona, pct_vmax, pausa_s, notas |
| `fuerza_sesiones` | Lo **ejecutado** (equipo) | fecha, match_day (único por fecha y MD), plan_id (opcional), duracion_min, rpe_sesion, ya_en_gps, notas |
| `fuerza_sesion_items` | Detalle ejecutado | sesion_id, plan_item_id (opcional), orden, tipo, ejercicio_id, ejercicio_nombre, series_hechas, reps_hechas, pct_rm_real, distancia_m, zona, pct_vmax, pausa_s |
| `fuerza_parametros` | Valores editables | clave, valor, descripcion. Cargados: `umbral_alta_intensidad_vmax`=85 e `intensidad_base_sin_rm`=50 (provisorios) |
| `zonas_velocidad` | Zonas de pasadas | nombre, orden, desde_pct_vmax, hasta_pct_vmax (**vacía: cortes por definir**) |

Los ejercicios se referencian por **ID de texto del Sheet** (no por clave foránea), porque el catálogo vive en el Sheet. La base valida el formato (`FZA-###` o `RES-###`) y que el prefijo coincida con el tipo (fuerza o pasada). El nombre se guarda aparte para que el historial no cambie si se renombra en el Sheet.
`fuerza_registro` (por jugadora, ya existe) queda para la etapa individual.

## 6. Pasadas: cálculo y puntos abiertos

Tiempo objetivo individual:

`tiempo (s) = distancia (m) ÷ (Vmáx (km/h) ÷ 3,6 × %Vmáx)`

Salir de parada en distancias cortas (30 m) hace que la jugadora no llegue a su Vmáx: el tiempo calculado así sale más rápido que el real. Opciones:
- **A)** Vmáx con un factor de corrección por distancia (más simple).
- **B)** Tiempo de referencia por distancia de cada jugadora (más preciso; requiere ese dato).

**Pendiente de Tomi**: elegir A o B y definir los cortes de las zonas de velocidad. Pendiente de Claude: confirmar dónde está la Vmáx por jugadora (posible fuente: `perfil_fisico_gps` o los exports de Catapult).

## 7. Métricas

- **UA de fuerza** = series × repeticiones × %RM / 100 (sin RM: intensidad base).
- **Pasadas**: metros totales y metros con %Vmáx ≥ umbral.
- **ACWR de fuerza**: reutilizar la lógica EWMA de `src/metrics/physical.py` sobre la UA diaria.
- **Carga total** (GPS + fuerza): vista combinada, etapa posterior.

## 8. Orden de trabajo

- [x] Borrador de fuerza guardado en rama `fuerza-gym`
- [x] Revisión de Supabase (solo lectura)
- [x] Corrección de seguridad 0061 (aplicada)
- [x] Este documento
- [x] Sheet `Ejercicios_fisico`: columna `ID` agregada al final de cada pestaña el 2026-11-03 (`FZA-001` a `FZA-013` en `Catalogo_fuerza`, columna F; `RES-001` a `RES-013` en `Catalogo_resist`, columna N). Los IDs no se cambian ni se reutilizan.
- [ ] Opcional: columnas `VARIANTE` e `INTENSIDAD_BASE`. Quitar `EJERCICIO_REFERENCIA` del Sheet solo después de sacarla del código (`fuerza_loader.py`, `pages/10_fuerza.py`)
- [~] Migración 0062 + app de jugadoras: RM de Arranque y Tirones de cargada. Escrita y commiteada en `APP_JUGADORAS_CV`, rama `rm-arranque-tirones` (commit 73a7440); slugs `arranque` y `tirones_cargada`. **0062 aplicada en producción el 2026-11-03. Falta pasar la rama a `master` y desplegar.** Del lado Streamlit, el mapeo de slugs ya está en `fuerza-gym` (commit 756c3e9). La 0061 de seguridad (ya aplicada en producción) está en la rama `seguridad-vistas-analiticas`, pendiente de pasar a `master`.
- [ ] Repuntar el sync de `catalogo_ejercicios` (tipo físico) al Sheet `Ejercicios_fisico`
- [x] Migración 0063: tablas de plan, ejecutado y parámetros (permisos cerrados). Aplicada el 2026-11-03; archivo en la rama `fuerza-plan-semanal` de `APP_JUGADORAS_CV` (parte de `rm-arranque-tirones`, así que se pasa a `master` después de esa)
- [x] Métricas del plan con tests: `src/metrics/fuerza_plan.py` (UA, metros, tiempo objetivo de pasadas, resumen por MD y semana, limpieza de lo cargado en el planificador)
- [x] Loader del plan: `src/loaders/fuerza_plan_loader.py` (leer planes, ítems, parámetros y zonas; guardar plan por upsert en una transacción). SQL probado contra la base con rollback; el loader en sí no se pudo ejecutar en el sandbox (falta `psycopg`), probarlo en tu entorno
- [x] Loader de lo ejecutado (`listar_sesiones`, `cargar_items_sesiones`, `cargar_todos_items_plan`, `guardar_sesion`); SQL probado contra la base con rollback
- [x] Página: pestaña **Planificación** en `pages/10_fuerza.py` (lógica en `src/ui/fuerza_planificador.py`): semana, una pestaña por MD con tabla de fuerza y de pasadas, KPIs y gráficos de carga prevista, guardado en Supabase, parámetros editables. Probada con Streamlit AppTest y base simulada (`tests/test_fuerza_planificador_ui.py`); **falta probarla en la app real**
- [x] Loader del catálogo: lee `EJERCICIOS` (plural) e `ID`, y el catálogo de pasadas (`Catalogo_resist`)
- [x] Página: pestañas **Sesión ejecutada** (precargada desde el plan, se corrige lo hecho; duración, RPE, marca "ya en GPS") e **Historial** (plan vs ejecutado por semana, ACWR de fuerza, detalle) en `src/ui/fuerza_ejecutado.py`. La carga individual por jugadora queda oculta tras `MOSTRAR_INDIVIDUAL = False` en `pages/10_fuerza.py` (etapa 2). **Falta probarla en la app real**
- [ ] Pasadas con zonas y tiempos por jugadora
- [x] ACWR de fuerza (equipo) en `src/metrics/fuerza_ejecutado.py`: EWMA 7/28 días **completando con 0 los días sin sesión** (el de GPS no lo hace); provisorio hasta tener 28 días de historia
- [ ] Vista combinada GPS + fuerza

## 9. Reglas de trabajo

1. Se trabaja en la rama `fuerza-gym` y se pasa a `main` con merge fast-forward cuando Tomi lo decide (Streamlit Cloud despliega desde `main`, así que cada merge a `main` publica el módulo). Decisión del 2026-11-03: el módulo ya estaba en `main` desde ese día y se aceptó; nada se mergea a `main` sin pedido explícito.
2. Una herramienta a la vez: antes de cambiar de herramienta, `git status` y commit.
3. Pasos chicos, un commit por paso.
4. La base se define en un solo lugar: `APP_JUGADORAS_CV/supabase/migrations/`. Lo de `sql/` en este repo es historial del borrador.
5. Todo cambio de base es aditivo; probar y revisar antes de aplicar en producción.
6. Lo puro (cálculos) va en `src/metrics/` con tests.
7. Nunca commitear claves ni leer `.env` / `secrets.toml`.

## 10. Pendientes abiertos

- Elegir A/B de pasadas y definir las zonas de velocidad.
- Lista definitiva de ejercicios y variantes (hoy hay nombres repetidos: "Pasadas" x4, "Intermitentes" x2).
- Confirmar que el catálogo técnico-táctico sigue sincronizándose desde la planilla de wellness.
- Peso muerto y Remo tienen RM en la app pero no están en `Catalogo_fuerza`; Remo TRX no tiene RM. Decidir si se agregan al catálogo.
- Completar los parámetros de `Catalogo_resist` (largo, ancho, tiempos, perfil, % partido, MD recomendado).

## Pasadas: tiempos objetivo por jugadora (opción A) — hecho

- **Vmáx de cada jugadora** (`src/metrics/fuerza_vmax.py`): promedio de sus N mejores días (por defecto 3) dentro de una ventana (por defecto 180 días hacia atrás desde el último dato de GPS). Velocidades por encima del tope (35 km/h) se descartan como error del chaleco y se cuentan.
- **Factor por distancia** (30/40/50/60/70 m, interpolado entre medio): corrige que al salir de parada no se llega a la Vmáx. Valores iniciales **estimados con un modelo (τ≈0,9 s), NO medidos**: 0,82 / 0,86 / 0,88 / 0,90 / 0,91. Se editan en *Parámetros de cálculo*.
- **Tiempo objetivo** = distancia ÷ (Vmáx ÷ 3,6 × %Vmáx × factor). Se muestra por jugadora dentro de cada Match Day del planificador.
- Todos los criterios son parámetros editables (`fuerza_parametros`, se crean al primer guardado).
- Pendiente: cortes de las zonas de velocidad (la zona sigue siendo texto libre); pasar a opción B (tiempos de referencia medidos por jugadora) cuando existan.
- Avisos conocidos: el GPS tiene al menos una lectura imposible (51 km/h) que conviene corregir en origen; el ACWR de fuerza completa los días de descanso con 0 y el de GPS no.
