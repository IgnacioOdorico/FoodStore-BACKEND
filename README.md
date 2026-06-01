# FoodStore BACKEND

API REST del sistema FoodStore. Permite gestionar productos, categorías, pedidos y usuarios.

---

## Tecnologías

| Herramienta | Propósito |
|---|---|
| FastAPI | Framework web |
| Python 3.10+ | Lenguaje |
| PostgreSQL | Base de datos |
| Docker & Compose | Contenedor de la DB |

---

## Requisitos previos

- Python 3.10+
- pip
- Docker y Docker Compose corriendo

---

## Instalación y ejecución

```bash
# 1. Clonar el repositorio
git clone <URL_DEL_REPO>
cd FoodStore-BACKEND

# 2. Levantar la base de datos con Docker
docker-compose up -d

# 3. Crear y activar entorno virtual
python -m venv .venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate

# 4. Instalar dependencias
pip install -r requirements.txt

# 5. Configurar base de datos inicial (seed)
python reset_db.py

# 6. Levantar el servidor de desarrollo
uvicorn app.main:app --reload
```

La API queda disponible en `http://localhost:8000`.
Swagger (Docs) disponible en `http://localhost:8000/docs`.

---

## Video del Parcial
[Ver Video en YouTube](https://www.youtube.com/watch?v=HCHS3oAsbC4)
Complemento del video: https://www.youtube.com/watch?v=xzheMmXe0Uc
