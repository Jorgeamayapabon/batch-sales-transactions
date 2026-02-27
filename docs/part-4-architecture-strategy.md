# Parte 4: Arquitectura & Estrategia

## Pregunta

> "Estamos migrando de una arquitectura monolítica a microservicios. ¿Cómo manejarías la **consistencia de datos** entre microservicios si uno de ellos falla a mitad de una transacción que involucra a dos bases de datos distintas (SQL Server y PostgreSQL)?"

---

## El problema: la transacción distribuida

En un monolito, una sola transacción de base de datos garantiza atomicidad:

```
BEGIN TRANSACTION
  INSERT INTO sql_server.ventas (...)
  INSERT INTO postgres.analytics (...)
COMMIT  -- o ROLLBACK si algo falla
```

En microservicios esto **no existe**: cada servicio tiene su propia base de datos y no hay un coordinador de transacciones compartido. Si el Servicio A escribe en SQL Server y luego el Servicio B falla al escribir en PostgreSQL, los datos quedan inconsistentes.

---

## Solución principal: Patrón Saga

El patrón **Saga** descompone la transacción distribuida en una secuencia de transacciones locales, donde cada una publica un evento que dispara la siguiente. Si alguna falla, se ejecutan **transacciones compensatorias** (el equivalente a un ROLLBACK distribuido).

### Variante recomendada: Saga con Orquestador

```
Cliente
   │
   ▼
Orquestador (Django Microservice)
   │
   ├──► 1. Servicio Ventas (SQL Server)
   │         └── INSERT ventas → OK → evento: VentaCreada
   │
   ├──► 2. Servicio Analytics (PostgreSQL)
   │         └── INSERT analytics → FALLA
   │
   └──► 3. Compensación automática
             └── Servicio Ventas → DELETE ventas (rollback)
```

**Flujo de código (pseudocódigo del orquestador):**

```python
class ProcesarVentaSaga:
    def ejecutar(self, transaccion: dict) -> None:
        venta_id = None
        try:
            # Paso 1: persistir en SQL Server (Servicio Ventas)
            venta_id = servicio_ventas.crear(transaccion)

            # Paso 2: replicar en PostgreSQL (Servicio Analytics)
            servicio_analytics.registrar(transaccion)

        except AnalyticsServiceError:
            # Transacción compensatoria: revertir paso 1
            if venta_id:
                servicio_ventas.cancelar(venta_id)
            raise SagaFailedError("Analytics falló; venta revertida.")
```

### Ventajas del orquestador vs. coreografía

| Aspecto | Orquestador | Coreografía (eventos) |
|---|---|---|
| Visibilidad del flujo | Alta — está centralizado | Baja — distribuido en múltiples servicios |
| Debugging | Sencillo | Complejo (hay que seguir eventos) |
| Acoplamiento | Moderado (orquestador conoce a los servicios) | Bajo (servicios solo emiten/escuchan eventos) |
| Recomendado cuando | Flujos cortos (2-4 pasos) con lógica de negocio clara | Flujos largos, muchos servicios independientes |

---

## Patrón complementario: Outbox Pattern

El mayor riesgo en la saga es este escenario:

```
Servicio Ventas:
  1. INSERT ventas → OK
  2. Publicar evento "VentaCreada" → FALLA (red caída)
     → El evento nunca llega al Servicio Analytics
     → Inconsistencia silenciosa
```

El **Outbox Pattern** resuelve esto garantizando que el evento se persista **junto con la transacción de negocio** en la misma base de datos:

```
SQL Server — Servicio Ventas
┌──────────────────────────────────────┐
│  BEGIN TRANSACTION                   │
│    INSERT INTO ventas (...)          │
│    INSERT INTO outbox (              │
│      evento   = 'VentaCreada',       │
│      payload  = '{"id": 123, ...}',  │
│      enviado  = FALSE                │
│    )                                 │
│  COMMIT                              │
└──────────────────────────────────────┘
          │
          │  Relay process (polling o CDC)
          ▼
    Message Broker (Azure Service Bus / RabbitMQ)
          │
          ▼
    Servicio Analytics (PostgreSQL)
```

**Beneficio clave:** si la red falla después del `COMMIT`, el registro en `outbox` persiste. El relay process reintenta el envío hasta que el broker confirme la entrega (`enviado = TRUE`). Nunca se pierde un evento.

---

## Garantizar idempotencia en el receptor

Cuando el Servicio Analytics recibe el evento (posiblemente más de una vez por reintentos), debe ser **idempotente**:

```python
# PostgreSQL — Servicio Analytics
INSERT INTO analytics (transaction_id, monto, fecha, ...)
VALUES (%s, %s, %s, ...)
ON CONFLICT (transaction_id) DO NOTHING;
-- Si ya existe, no hace nada. El resultado es siempre el mismo.
```

---

## Estrategia completa ante un fallo

```
Escenario: Servicio Analytics falla después de que Ventas ya persistió

Paso 1: Servicio Ventas escribe en SQL Server + tabla outbox (atómico).

Paso 2: Relay detecta el evento pendiente en outbox y publica en el broker.

Paso 3: Servicio Analytics falla al consumir el evento.
        → El broker NO hace ACK del mensaje.
        → El mensaje queda en la cola con política de retry (ej. 3 reintentos con backoff).

Paso 4: Servicio Analytics se recupera.
        → Consume el mismo mensaje.
        → ON CONFLICT DO NOTHING garantiza que no se duplique el registro.
        → Hace ACK al broker.

Paso 5: Consistencia eventual alcanzada.
        → No se perdió ningún dato.
        → No hay duplicados.
```

---

## Resumen de patrones utilizados

| Patrón | Problema que resuelve |
|---|---|
| **Saga (Orquestador)** | Coordina la secuencia de pasos y ejecuta compensaciones si algo falla |
| **Outbox Pattern** | Garantiza que el evento de negocio se publique aunque la red falle entre el commit y el envío |
| **Idempotencia en receptor** | Permite reintentos seguros sin crear datos duplicados |
| **Dead Letter Queue (DLQ)** | Captura mensajes que fallaron todos los reintentos para revisión manual |

---

## Nota sobre 2-Phase Commit (2PC) — por qué NO se recomienda

El **Two-Phase Commit** es la solución "clásica" para transacciones distribuidas, pero en microservicios introduce:

- **Acoplamiento fuerte**: todos los participantes deben estar disponibles simultáneamente.
- **Lock de recursos durante la coordinación**: degrada el rendimiento bajo carga.
- **Single point of failure**: si el coordinador falla en fase 2, los participantes quedan bloqueados indefinidamente.

Para arquitecturas de microservicios orientadas a alta disponibilidad, la **consistencia eventual** con Saga + Outbox es el estándar de la industria.
