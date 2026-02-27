# Parte 2: Data Engineering & SQL Optimization

## Contexto del escenario

- Tabla `clientes` en **MS SQL Server** — 5 millones de registros
- Tabla `ventas` en **PostgreSQL**
- Objetivo: reporte mensual de ventas por categoría de producto

---

## Pregunta 1: Consulta SQL optimizada en PostgreSQL

### Esquema hipotético asumido

```sql
-- Tabla principal de ventas
CREATE TABLE ventas (
    id            BIGSERIAL PRIMARY KEY,
    cliente_id    BIGINT        NOT NULL,
    producto_id   BIGINT        NOT NULL,
    monto         NUMERIC(14,2) NOT NULL,
    fecha         DATE          NOT NULL
);

-- Tabla de productos con categoría
CREATE TABLE productos (
    id         BIGSERIAL PRIMARY KEY,
    nombre     VARCHAR(200) NOT NULL,
    categoria  VARCHAR(100) NOT NULL
);
```

### Índices hipotéticos

```sql
-- Cubre el filtro de rango de fechas (columna más selectiva primero)
CREATE INDEX idx_ventas_fecha
    ON ventas (fecha);

-- Índice compuesto: permite Index-Only Scan para la agregación
-- (producto_id para el JOIN, monto para el SUM, fecha para el WHERE)
CREATE INDEX idx_ventas_producto_fecha_monto
    ON ventas (producto_id, fecha, monto);

-- Cubre el GROUP BY en productos
CREATE INDEX idx_productos_categoria
    ON productos (categoria);
```

> **Por qué este orden en el índice compuesto:** PostgreSQL puede usar
> `idx_ventas_producto_fecha_monto` como *Index-Only Scan*, evitando
> acceder a la tabla heap para obtener `monto`. El optimizador filtra
> primero por `fecha` usando el índice simple, y luego hace el JOIN +
> agregación con el compuesto.

### Consulta optimizada

```sql
SELECT
    p.categoria,
    SUM(v.monto)    AS total_ventas,
    COUNT(v.id)     AS num_transacciones
FROM ventas v
INNER JOIN productos p ON v.producto_id = p.id
WHERE v.fecha >= date_trunc('month', CURRENT_DATE - INTERVAL '1 month')
  AND v.fecha <  date_trunc('month', CURRENT_DATE)
GROUP BY
    p.categoria
HAVING
    SUM(v.monto) > 50000
ORDER BY
    total_ventas DESC;
```

### Por qué esta forma y no otras

| Decisión | Justificación |
|---|---|
| `date_trunc` en lugar de `EXTRACT` | Permite que el optimizador use el índice en `fecha` con un *range scan* en vez de un *seq scan* con función |
| `HAVING` en lugar de subconsulta | Más legible; PostgreSQL lo optimiza igual que un filtro post-agregación |
| `INNER JOIN` en lugar de subquery correlacionada | Evita N ejecuciones de la subquery; el *Hash Join* es O(n+m) |
| `COUNT(v.id)` incluido | Aporta contexto al reporte sin coste significativo adicional |

### Verificación del plan de ejecución

```sql
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT
    p.categoria,
    SUM(v.monto) AS total_ventas
FROM ventas v
INNER JOIN productos p ON v.producto_id = p.id
WHERE v.fecha >= date_trunc('month', CURRENT_DATE - INTERVAL '1 month')
  AND v.fecha <  date_trunc('month', CURRENT_DATE)
GROUP BY p.categoria
HAVING SUM(v.monto) > 50000
ORDER BY total_ventas DESC;
```

Lo que esperamos ver en el plan:
- `Index Scan` o `Index Only Scan` sobre `idx_ventas_fecha`
- `Hash Join` para relacionar con `productos`
- `HashAggregate` para el `GROUP BY`
- Sin `Seq Scan` en la tabla `ventas`

---

## Pregunta 2: Estrategia de Upsert/Merge para evitar duplicidad de PKs

### El problema

Durante la sincronización en horas pico entre SQL Server (fuente) y PostgreSQL (destino), se producen errores de **violación de PK** porque:

1. El proceso de sincronización puede ejecutarse en paralelo (dos workers intentan insertar el mismo registro).
2. Reintentos automáticos insertan filas que ya fueron confirmadas.

### Estrategia propuesta: Staging Table + INSERT … ON CONFLICT

#### Paso 1 — Tabla de staging temporal

```sql
CREATE UNLOGGED TABLE ventas_staging (
    LIKE ventas INCLUDING ALL
);
```

> `UNLOGGED` elimina el overhead del WAL durante la carga masiva.
> Al finalizar el proceso se trunca, por lo que la durabilidad no importa aquí.

#### Paso 2 — Carga masiva al staging (sin riesgo de conflicto)

```sql
COPY ventas_staging (id, cliente_id, producto_id, monto, fecha)
FROM '/tmp/sync_batch.csv'
WITH (FORMAT csv, HEADER true);
```

#### Paso 3 — Upsert atómico desde staging a tabla final

```sql
INSERT INTO ventas (id, cliente_id, producto_id, monto, fecha)
SELECT id, cliente_id, producto_id, monto, fecha
FROM ventas_staging
ON CONFLICT (id) DO UPDATE
    SET cliente_id  = EXCLUDED.cliente_id,
        producto_id = EXCLUDED.producto_id,
        monto       = EXCLUDED.monto,
        fecha       = EXCLUDED.fecha
WHERE
    -- Solo actualiza si el registro realmente cambió (evita writes fantasma)
    ventas.monto    IS DISTINCT FROM EXCLUDED.monto
    OR ventas.fecha IS DISTINCT FROM EXCLUDED.fecha;

TRUNCATE ventas_staging;
```

#### Alternativa para actualizaciones parciales: columna `updated_at`

```sql
ALTER TABLE ventas ADD COLUMN updated_at TIMESTAMPTZ DEFAULT now();

-- En el upsert, solo propagar cambios más recientes:
ON CONFLICT (id) DO UPDATE
    SET monto      = EXCLUDED.monto,
        updated_at = EXCLUDED.updated_at
WHERE EXCLUDED.updated_at > ventas.updated_at;
```

### Comparativa de estrategias

| Estrategia | Ventaja | Desventaja |
|---|---|---|
| `INSERT … ON CONFLICT DO UPDATE` | Atómico, sin locks adicionales, nativo PostgreSQL | Solo aplica en PostgreSQL |
| `MERGE` (SQL estándar, PostgreSQL 15+) | Sintaxis estándar, más legible | Disponible desde PG 15, menos flexible para condiciones complejas |
| Delete + Insert en transacción | Simple de entender | Lock de fila elevado en horas pico; riesgo de deadlock |
| Staging + swap de partición | Ideal para cargas muy grandes (>10M filas) | Mayor complejidad operativa |

### Medidas adicionales para horas pico

1. **Ventanas de sincronización** desplazadas fuera del peak (ej. cada 15 min pero con backoff exponencial si hay contención).
2. **Deadlock timeout** reducido en PostgreSQL (`lock_timeout = '5s'`) para fallar rápido y reintentar.
3. **Particionamiento por `fecha`** en la tabla `ventas` para que el Upsert opere solo sobre la partición del mes activo, reduciendo el espacio de búsqueda del índice.
4. **CDC (Change Data Capture)** con Debezium sobre SQL Server para capturar solo los cambios reales (inserts/updates/deletes) en lugar de sincronizar toda la tabla.
