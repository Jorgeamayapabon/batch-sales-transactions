# Parte 3: Azure Data Ecosystem

## Contexto del escenario

El volumen de datos ha crecido de forma que el microservicio Django ya no puede procesar directamente los archivos CSV de logs. Se requiere un flujo de datos en la nube que cubra: ingesta, transformación y almacenamiento analítico.

---

## Pregunta 1: ¿Cómo moverías los archivos del servidor local a ADLS Gen2?

### Opción recomendada: ADF con Self-Hosted Integration Runtime (SHIR)

```
Servidor local (CSV logs)
        │
        │  SHIR (agente instalado en el servidor)
        ▼
Azure Data Factory  ──────────────────────────►  ADLS Gen2
  (Copy Activity)                              /raw/logs/año=YYYY/mes=MM/día=DD/
```

**Pasos de configuración:**

1. **Instalar el Self-Hosted Integration Runtime** en el servidor local.
   - Descarga desde Azure Portal → Data Factory → Manage → Integration Runtimes.
   - El SHIR actúa como puente seguro sin exponer el servidor a internet.

2. **Crear un Linked Service** en ADF apuntando al sistema de archivos local (File System connector) usando el SHIR.

3. **Crear un Linked Service** hacia ADLS Gen2 con autenticación por **Managed Identity** (más seguro que access keys).

4. **Pipeline con Copy Activity:**
   - Source: File System (ruta local de los CSV)
   - Sink: ADLS Gen2 con estructura de particionamiento `año/mes/día`
   - Trigger: Schedule Trigger (ej. cada hora) o Storage Event Trigger

5. **Particionamiento en ADLS Gen2:**
   ```
   adls://datalake/
   └── raw/
       └── logs/
           └── año=2024/
               └── mes=03/
                   └── día=15/
                       └── logs_20240315_0800.csv
   ```
   > El particionamiento por fecha permite que Synapse y Databricks usen
   > *partition pruning*, leyendo solo los archivos del período relevante.

### Alternativa para volúmenes muy grandes: AzCopy

```bash
# Sincronización incremental desde servidor local a ADLS Gen2
azcopy sync \
  "/var/logs/sales/" \
  "https://<storage>.dfs.core.windows.net/raw/logs/" \
  --recursive \
  --delete-destination=false
```

> `azcopy sync` transfiere solo los archivos nuevos o modificados,
> ideal para automatizar con cron o Task Scheduler.

---

## Pregunta 2: Pipeline en Azure Data Factory para transformar y cargar en Synapse

### Arquitectura del pipeline (medallion architecture)

```
ADLS Gen2 /raw          ADLS Gen2 /silver         Azure Synapse Analytics
  (CSV crudo)    ──►      (Parquet limpio)   ──►    (Dedicated SQL Pool)
                  ADF Mapping Data Flow         ADF Copy Activity
```

### Diseño del pipeline en ADF

```
Pipeline: pl_logs_to_synapse
│
├── Activity 1: Get Metadata
│   └── Verifica que existan archivos nuevos en /raw/logs/
│
├── Activity 2: Data Flow — df_clean_logs
│   ├── Source:  ADLS Gen2 /raw (CSV)
│   ├── Transformaciones:
│   │   ├── Derived Column: normalizar fechas (string → timestamp)
│   │   ├── Filter: eliminar filas con monto NULL o negativo
│   │   ├── Derived Column: agregar columna high_risk (monto > 10000)
│   │   └── Select: proyectar solo columnas necesarias
│   └── Sink: ADLS Gen2 /silver (Parquet, particionado por año/mes)
│
├── Activity 3: Copy Activity — copy_silver_to_synapse
│   ├── Source:  ADLS Gen2 /silver (Parquet)
│   ├── Sink:    Synapse Analytics — tabla dbo.ventas_logs
│   └── Write behavior: Upsert (por transaction_id)
│
└── Activity 4: Stored Procedure (opcional)
    └── Ejecuta agregaciones o actualiza vistas materializadas en Synapse
```

### Tabla destino en Synapse (Dedicated SQL Pool)

```sql
CREATE TABLE dbo.ventas_logs (
    transaction_id  NVARCHAR(100)   NOT NULL,
    cliente_id      NVARCHAR(100)   NOT NULL,
    monto           DECIMAL(14,2)   NOT NULL,
    fecha           DATE            NOT NULL,
    high_risk       BIT             NOT NULL DEFAULT 0,
    ingested_at     DATETIME2       DEFAULT GETUTCDATE()
)
WITH (
    DISTRIBUTION = HASH(cliente_id),  -- Distribuye carga en los 60 nodos
    CLUSTERED COLUMNSTORE INDEX       -- Óptimo para consultas analíticas
);
```

> **`DISTRIBUTION = HASH(cliente_id)`**: agrupa los datos del mismo cliente
> en el mismo nodo de distribución, evitando *data movement* en JOINs
> contra la tabla de clientes.
>
> **`CLUSTERED COLUMNSTORE INDEX`**: comprime por columna, reduciendo hasta
> un 90% el almacenamiento y acelerando agregaciones (SUM, COUNT, AVG).

---

## Pregunta 3: ¿Qué servicio usar para scripts Python pesados de Data Cleaning?

### Respuesta: **Azure Databricks**

### Comparativa de opciones

| Servicio | Memoria máx. | Escala | Caso de uso ideal |
|---|---|---|---|
| **Azure Functions** | ~1.5 GB (consumption) / ~14 GB (premium) | Horizontal (instancias) | Procesamiento ligero, event-driven, < 10 min |
| **Azure Batch** | Sin límite (VMs dedicadas) | Horizontal (pool de VMs) | Jobs batch paralelos sin Spark; control total de la VM |
| **Azure Databricks** | Sin límite (cluster auto-scaling) | Horizontal + vertical | ETL pesado con PySpark; ML; datos > 100 GB |

### Por qué Databricks en este contexto

El escenario describe archivos CSV de logs que **superan la memoria del servidor Django**, lo que implica datasets de potencialmente decenas o cientos de GB. Databricks es la elección correcta porque:

1. **Procesamiento distribuido con PySpark**: divide el dataset en particiones y las procesa en paralelo en múltiples nodos, sin que ningún nodo deba cargar todo en memoria.

2. **Auto-scaling**: agrega o elimina workers automáticamente según la carga, optimizando costos.

3. **Integración nativa con ADLS Gen2**: acceso directo a los archivos en `/silver` sin moverlos.

4. **Delta Lake**: soporte de ACID transactions, time travel y schema evolution sobre ADLS Gen2, crítico para pipelines de datos confiables.

### Ejemplo de script PySpark en Databricks

```python
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

spark = SparkSession.builder.appName("SalesLogCleaning").getOrCreate()

df = spark.read.parquet("abfss://silver@<storage>.dfs.core.windows.net/logs/")

df_clean = (
    df
    .filter(F.col("monto").isNotNull() & (F.col("monto") > 0))
    .withColumn("high_risk", F.col("monto") > 10_000)
    .withColumn("fecha", F.to_date(F.col("fecha"), "yyyy-MM-dd"))
    .dropDuplicates(["transaction_id"])
)

(
    df_clean
    .write
    .format("delta")
    .mode("overwrite")
    .partitionBy("fecha")
    .save("abfss://gold@<storage>.dfs.core.windows.net/ventas_clean/")
)
```

### Cuándo elegir Azure Batch en su lugar

Usar **Azure Batch** si:
- El script es Python puro (pandas, scikit-learn) sin necesidad de Spark.
- Se requiere control total sobre la VM (bibliotecas de sistema, GPU, etc.).
- El presupuesto es muy ajustado y Databricks resulta costoso para la frecuencia de ejecución.

### Cuándo elegir Azure Functions en su lugar

Usar **Azure Functions** si:
- El procesamiento es ligero (< 1 GB por archivo).
- Se necesita activación por eventos (nuevo archivo en ADLS → trigger automático).
- El tiempo de ejecución cabe en el límite del plan (10 min consumption, ilimitado premium).

---

## Flujo completo integrado

```
Servidor local
      │
      │  ADF + SHIR
      ▼
ADLS Gen2 /raw  (CSV originales)
      │
      │  ADF Mapping Data Flow
      ▼
ADLS Gen2 /silver  (Parquet particionado)
      │
      │  Azure Databricks (limpieza pesada)
      ▼
ADLS Gen2 /gold  (Delta Lake, datos limpios)
      │
      │  ADF Copy Activity
      ▼
Azure Synapse Analytics  (Dedicated SQL Pool)
      │
      │  Power BI / Reporting
      ▼
   Dashboard
```
