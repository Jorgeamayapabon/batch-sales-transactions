# Batch Sales Transactions

Microservicio Django REST Framework para procesamiento batch de transacciones de ventas con detección de alto riesgo.

## Arquitectura

```
batch-sales-transactions/
├── config/                     # Configuración Django
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── apps/
│   └── transactions/           # App principal
│       ├── models.py           # SalesTransaction
│       ├── serializers.py      # Validación + lógica de negocio
│       ├── views.py            # BatchTransactionView
│       ├── middleware.py       # ResponseTimeMiddleware + decorador
│       ├── urls.py
│       └── tests/
│           ├── factories.py
│           ├── test_models.py
│           ├── test_serializers.py
│           ├── test_views.py
│           └── test_middleware.py
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

## Endpoint

### `POST /api/transactions/batch/`

Recibe un lote de transacciones de ventas, valida y persiste en PostgreSQL.

**Request:**
```json
{
  "transactions": [
    {
      "transaction_id": "TXN-001",
      "amount": "250.00",
      "date": "2024-03-10",
      "customer_id": "CUST-001"
    },
    {
      "transaction_id": "TXN-002",
      "amount": "15000.00",
      "date": "2024-03-11",
      "customer_id": "CUST-002"
    }
  ]
}
```

**Response `201 Created`:**
```json
{
  "created": 2,
  "transactions": [
    {
      "id": 1,
      "transaction_id": "TXN-001",
      "amount": "250.00",
      "date": "2024-03-10",
      "customer_id": "CUST-001",
      "high_risk": false,
      "created_at": "2024-03-10T12:00:00Z"
    },
    {
      "id": 2,
      "transaction_id": "TXN-002",
      "amount": "15000.00",
      "date": "2024-03-11",
      "customer_id": "CUST-002",
      "high_risk": true,
      "created_at": "2024-03-10T12:00:01Z"
    }
  ]
}
```

**Reglas de negocio:**
- `high_risk = true` cuando `amount > $10,000 USD`
- Todos los campos (`transaction_id`, `amount`, `date`, `customer_id`) son obligatorios
- IDs duplicados dentro del mismo lote son rechazados
- El monto debe ser mayor a cero

## Levantar con Docker

```bash
# Copiar variables de entorno
cp .env.example .env

# Construir y levantar servicios
docker compose up --build

# La API estará disponible en http://localhost:8000
```

## Ejecutar tests con Docker

```bash
docker compose --profile test run --rm test
```

## Desarrollo local

```bash
# Instalar dependencias (incluye dev)
uv sync

# Ejecutar tests
uv run pytest -v

# Ejecutar tests con cobertura
uv run pytest --cov=apps --cov-report=html
```

## Colección Postman

El repositorio incluye el archivo `batch sales transactions.postman_collection.json` listo para importar en Postman.

Contiene el request `POST /api/transactions/batch/` con un payload de ejemplo que incluye una transacción normal y una de alto riesgo.

**Importar en Postman:**
1. Abrir Postman → **Import**
2. Seleccionar el archivo `batch sales transactions.postman_collection.json`
3. Asegurarse de que el servidor esté corriendo en `http://localhost:8000`

## Variables de entorno

| Variable       | Default        | Descripción                  |
|----------------|----------------|------------------------------|
| `SECRET_KEY`   | (insecure dev) | Django secret key            |
| `DEBUG`        | `False`        | Modo debug                   |
| `ALLOWED_HOSTS`| `*`            | Hosts permitidos             |
| `DB_NAME`      | `sales_db`     | Nombre de la base de datos   |
| `DB_USER`      | `sales_user`   | Usuario PostgreSQL           |
| `DB_PASSWORD`  | `sales_pass`   | Contraseña PostgreSQL        |
| `DB_HOST`      | `db`           | Host PostgreSQL              |
| `DB_PORT`      | `5432`         | Puerto PostgreSQL            |
