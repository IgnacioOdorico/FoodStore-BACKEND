# FoodStore — Backend

API REST del sistema FoodStore. Permite gestionar productos, categorías, pedidos, pagos con MercadoPago y usuarios con RBAC.

---

## Stack Tecnológico

| Herramienta | Versión | Propósito |
|---|---|---|
| FastAPI | 0.111+ | Framework REST + WebSocket + OpenAPI |
| Python | 3.10+ | Lenguaje principal |
| PostgreSQL | 15 | Base de datos relacional |
| SQLModel | 0.0.19+ | ORM + schemas Pydantic integrados |
| Passlib (bcrypt) | — | Hashing de contraseñas (cost ≥ 12) |
| mercadopago | 2.3.0+ | SDK oficial MercadoPago (Checkout PRO) |
| cloudinary | 1.x+ | SDK Python para upload y gestión de imágenes |
| Docker & Compose | — | Base de datos + ngrok en contenedor |
| Pytest | — | Pruebas unitarias e integración |

---

## Arquitectura de Capas

```
Router → Service → UoW → Repository → Model
```

- **Router**: HTTP puro. Parsea request, delega al Service.
- **Service**: Lógica de negocio. Stateless. Emite eventos WS post-commit.
- **Unit of Work (UoW)**: Gestión de transacciones atómicas.
- **Repository**: Acceso a BD. Sin lógica de negocio.
- **Model**: SQLModel tables.

---

## Requisitos Previos

- Python 3.10+
- Docker y Docker Compose
- (Opcional) ngrok para webhooks de MercadoPago en desarrollo

---

## Instalación y Ejecución

### 1. Clonar el repositorio

```bash
git clone <URL_DEL_REPO>
cd FoodStore-BACKEND
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
```

Editar `.env` con los valores reales. Las variables requeridas son:

| Variable | Descripción |
|---|---|
| `POSTGRES_USER` | Usuario de PostgreSQL |
| `POSTGRES_PASSWORD` | Contraseña de PostgreSQL |
| `POSTGRES_DB` | Nombre de la base de datos |
| `POSTGRES_HOST` | Host de PostgreSQL (default: `localhost`) |
| `POSTGRES_PORT` | Puerto de PostgreSQL (default: `5432`) |
| `SECRET_KEY` | Clave secreta JWT (mín. 32 chars) |
| `ALGORITHM` | Algoritmo JWT (default: `HS256`) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Expiración del access token (default: `30`) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Expiración del refresh token (default: `7`) |
| `CORS_ORIGINS` | Orígenes permitidos como JSON array |
| `MP_ACCESS_TOKEN` | Access Token de MercadoPago (backend) |
| `MP_PUBLIC_KEY` | Public Key de MercadoPago (frontend) |
| `MP_WEBHOOK_URL` | URL pública del webhook MP (ngrok en dev) |
| `NGROK_URL` | URL pública de ngrok |
| `NGROK_AUTHTOKEN` | Auth token de ngrok |
| `CLOUDINARY_CLOUD_NAME` | Cloud name de Cloudinary |
| `CLOUDINARY_API_KEY` | API Key de Cloudinary |
| `CLOUDINARY_API_SECRET` | API Secret de Cloudinary |
| `VITE_API_URL` | URL base del backend |
| `VITE_FRONTEND_URL` | URL del frontend Store |

### 3. Levantar la base de datos y ngrok con Docker

```bash
docker-compose up -d
```

Esto levanta:
- **PostgreSQL 15** en `localhost:5432`
- **ngrok** en `localhost:4040` (panel de inspección en http://localhost:4040)

> Para que ngrok funcione, `NGROK_AUTHTOKEN` debe estar definido en `.env`.

### 4. Crear entorno virtual e instalar dependencias

```bash
python -m venv .venv
source .venv/bin/activate   

# Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

### 5. Inicializar la base de datos y cargar seed

```bash
# Crea las tablas y carga datos iniciales (roles, estados, formas de pago, admin)
python -m app.db.seed
```

El seed carga:
- **Roles**: ADMIN, STOCK, PEDIDOS, CLIENT
- **Estados de pedido**: PENDIENTE, CONFIRMADO, EN_PREP, ENTREGADO, CANCELADO
- **Formas de pago**: MERCADOPAGO, EFECTIVO, TRANSFERENCIA
- **Unidades de medida**: kg, g, L, mL, ud, porciones
- **Usuario admin**: `admin@foodstore.com` / `Admin1234!`

> Cambiar la contraseña del admin antes de usar en producción.

### 6. Levantar el servidor de desarrollo

```bash
uvicorn app.main:app --reload
```

La API queda disponible en:
- **API REST**: `http://localhost:8000`
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **WebSocket**: `ws://localhost:8000/ws/pedidos`

---

## Configuración de MercadoPago con ngrok

Para recibir webhooks de MercadoPago en desarrollo local se necesita una URL pública. ngrok ya está incluido en `docker-compose.yml`.

1. Obtener el `NGROK_AUTHTOKEN` en https://dashboard.ngrok.com
2. Agregar al `.env`: `NGROK_AUTHTOKEN=tu-token`
3. Levantar con `docker-compose up -d`
4. Ver la URL generada en http://localhost:4040 o con:
   ```bash
   curl http://localhost:4040/api/tunnels
   ```
5. Actualizar `NGROK_URL` en `.env` con la URL generada
6. La URL del webhook de MP quedará: `https://tu-url.ngrok-free.app/api/v1/pagos/webhook`

---

## Estructura del Proyecto

```
app/
├── core/
│   ├── config.py          # Variables de entorno (Settings)
│   ├── database.py        # Sesión de SQLModel
│   ├── deps.py            # Dependencias FastAPI (get_current_user, require_role)
│   ├── security.py        # JWT, hashing de contraseñas
│   ├── uow.py             # Unit of Work (gestión de transacciones)
│   ├── websocket.py       # WSManager: pool de conexiones WebSocket
│   ├── base_repository.py # BaseRepository[T] genérico
│   ├── middleware/        # CORS, logging
│   ├── rate_limit/        # Rate limiting (5 intentos / 15 min)
│   └── exceptions/        # Handlers de errores RFC 7807
├── modules/
│   ├── auth/              # Login, registro, refresh, logout. JWT + RBAC
│   ├── usuarios/          # CRUD usuarios + roles
│   ├── direcciones/       # CRUD DireccionEntrega
│   ├── categorias/        # Categorías jerárquicas + Cloudinary
│   ├── producto/          # Catálogo + ingredientes + stock
│   ├── pedidos/           # FSM + audit trail + WebSocket
│   ├── pagos/             # MercadoPago Checkout PRO + webhook IPN
│   ├── uploads/           # Upload/delete imágenes en Cloudinary
│   └── ingrediente/       # Gestión de ingredientes y alérgenos
├── db/
│   └── seed.py            # Datos iniciales obligatorios
└── main.py                # Punto de entrada FastAPI
```

---

## Módulos API

| Módulo | Prefijo | Descripción |
|---|---|---|
| Auth | `/api/v1/auth` | Login, register, refresh, logout, me |
| Usuarios | `/api/v1/usuarios` | CRUD + RBAC |
| Direcciones | `/api/v1/direcciones` | CRUD + dirección principal |
| Categorías | `/api/v1/categorias` | Jerárquicas + imagen Cloudinary |
| Productos | `/api/v1/productos` | Catálogo + ingredientes + stock |
| Pedidos | `/api/v1/pedidos` | FSM + historial + cancelación |
| Pagos | `/api/v1/pagos` | MercadoPago + webhook + redirect |
| Uploads | `/api/v1/uploads` | Cloudinary upload/delete |

---

## Ejecutar Tests

```bash

# Todos los tests
pytest

# Con reporte de cobertura
pytest --cov=app --cov-report=term-missing

# Solo tests de un módulo
pytest tests/unit/
pytest tests/integration/
```

---

## Roles del Sistema (RBAC)

| Rol | Código | Permisos |
|---|---|---|
| Administrador | `ADMIN` | CRUD completo sin restricciones |
| Gestor de Stock | `STOCK` | Actualizar stock y disponibilidad |
| Gestor de Pedidos | `PEDIDOS` | Ver y avanzar estados de pedidos |
| Cliente | `CLIENT` | Catálogo, carrito, sus propios pedidos |

---

## Demo en Video

[Ver Video de Demostración](https://www.youtube.com/watch?v=HCHS3oAsbC4)

---
