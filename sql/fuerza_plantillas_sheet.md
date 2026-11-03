# Plantillas del Sheet para Fuerza

Crear dos pestañas NUEVAS en el mismo Google Sheet (WELLNESS_SHEET_ID). Pegar cada bloque
CSV en la celda A1. Después pasarme el GID de cada pestaña para cargarlo en `settings.py`.

## Pestaña `Catalogo_Fuerza` (catálogo CERRADO)

El formulario solo va a ofrecer estos ejercicios: sumar uno nuevo = sumar una fila acá.

- `ADMITE_RM`: `Sí` si tiene RM propio. `No` si se prescribe como % de otro ejercicio.
- `EJERCICIO_REFERENCIA`: solo si `ADMITE_RM = No`. Es el ejercicio cuyo RM se usa para calcular el %RM.

```csv
EJERCICIO,CATEGORIA,UNILATERAL,ADMITE_RM,EJERCICIO_REFERENCIA
Sentadilla frontal,Dominante de rodilla,No,Sí,
Sentadilla trasera,Dominante de rodilla,No,Sí,
Hip thrust,Cadera,No,Sí,
Press de hombros,Empuje,No,Sí,
Banco plano,Empuje,No,Sí,
Cargada,Olímpico,No,Sí,
Arranque,Olímpico,No,Sí,
Tirones de cargada,Olímpico,No,No,Cargada
```

> Decisión tuya (criterio de preparador físico): si los tirones se refieren al RM de la cargada
> o tienen RM propio. Lo dejé referenciado a la cargada por ser la práctica habitual.
> Si preferís RM propio, poné `Sí` y dejá la referencia vacía.

## Pestaña `Fuerza_Plan` (lo que se QUIERE que hagan)

Una fila por ejercicio por sesión planificada. `SEMANA` es una etiqueta libre del microciclo.

```csv
SEMANA,MATCH_DAY,EJERCICIO,ORDEN,SERIES,REPS,PCT_RM
EJEMPLO,MD-4,Sentadilla trasera,1,4,5,80
EJEMPLO,MD-4,Banco plano,2,4,6,75
EJEMPLO,MD-4,Hip thrust,3,3,8,70
```

> Las filas `EJEMPLO` son ilustrativas, NO son una prescripción: reemplazalas por tu plan real.
