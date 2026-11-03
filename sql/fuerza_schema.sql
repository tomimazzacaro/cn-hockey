-- sql/fuerza_schema.sql
-- Módulo de Fuerza (CN Hockey). REVISAR antes de aplicar: es la MISMA base que usa
-- la app de las jugadoras (proyecto wellness-hockey). Todo es aditivo: no modifica
-- ni borra nada existente.
--
-- Contexto verificado:
--  * registros_rm (RM autorreportado por las jugadoras) YA existe -> se reusa, no se duplica.
--  * El dashboard lee con el rol streamlit_readonly, que hoy solo tiene SELECT sobre la vista
--    jugadoras_wellness_analitica. Se sigue el mismo patrón: vistas + GRANT SELECT.
--  * La identidad es jugadora_id (uuid, FK a jugadoras.id); el player_id del dashboard se
--    deriva del nombre_completo (normalizar_nombre), igual que con wellness.

-- ── 1. Vista de RM (lectura) ────────────────────────────────────────────────
-- Mismas exclusiones que jugadoras_wellness_analitica (STAFF y JUGADORA NAVAL).
create or replace view jugadoras_rm_analitica as
select j.id as jugadora_id,
       j.nombre_completo,
       r.ejercicio,
       r.rm_kg,
       r.fecha
from registros_rm r
join jugadoras j on j.id = r.jugadora_id
where j.posicion is distinct from 'STAFF'
  and j.nombre_completo is distinct from 'JUGADORA NAVAL';

grant select on jugadoras_rm_analitica to streamlit_readonly;

-- ── 2. Series realizadas (lo único nuevo) ───────────────────────────────────
create table if not exists fuerza_registro (
    id          bigint generated always as identity primary key,
    jugadora_id uuid         not null references jugadoras(id),
    fecha       date         not null,
    ejercicio   text         not null,   -- nombre del Catalogo_Fuerza (el catálogo vive en el Sheet)
    nro_serie   smallint     not null check (nro_serie >= 1),
    reps        smallint     not null check (reps >= 1),
    kg          numeric(6,2) not null check (kg >= 0),
    rir         smallint     check (rir between 0 and 10),  -- opcional
    creado_en   timestamptz  not null default now(),
    -- una serie existe una sola vez: protege contra doble clic en el formulario
    unique (jugadora_id, fecha, ejercicio, nro_serie)
);

create index if not exists idx_fuerza_registro_busqueda
    on fuerza_registro (jugadora_id, fecha, ejercicio);

-- RLS activado y SIN políticas para anon/authenticated: la API pública de Supabase
-- no puede leer ni escribir. Solo entran los roles de abajo (conexión directa).
alter table fuerza_registro enable row level security;

-- ── 3. Vista de series (lectura para el dashboard) ──────────────────────────
create or replace view jugadoras_fuerza_analitica as
select j.id as jugadora_id,
       j.nombre_completo,
       f.fecha, f.ejercicio, f.nro_serie, f.reps, f.kg, f.rir
from fuerza_registro f
join jugadoras j on j.id = f.jugadora_id
where j.posicion is distinct from 'STAFF'
  and j.nombre_completo is distinct from 'JUGADORA NAVAL';

grant select on jugadoras_fuerza_analitica to streamlit_readonly;

-- ── 4. Rol de ESCRITURA (para el formulario de carga) ───────────────────────
-- Rol propio, con permisos SOLO sobre fuerza_registro (+ lectura de jugadoras para
-- elegir a quién cargar). Poner la contraseña a mano; NO commitearla.
-- create role fuerza_writer login password '<<poner-acá>>';
-- grant usage on schema public to fuerza_writer;
-- grant select, insert, update, delete on fuerza_registro to fuerza_writer;
-- grant select (id, nombre_completo, posicion, activa) on jugadoras to fuerza_writer;
-- grant usage, select on sequence fuerza_registro_id_seq to fuerza_writer;
-- create policy fuerza_writer_all on fuerza_registro
--     for all to fuerza_writer using (true) with check (true);
