# Medicalka

Backend мини-социальной сети: пользователи, публикации, комментарии, лайки, JWT, верификация email, Celery-очистка неверифицированных пользователей.

## Стек

- Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL
- JWT: **PyJWT**, пароли: **bcrypt** (без passlib)
- Celery + Redis (worker + beat)
- Docker Compose

## Быстрый старт

```bash
docker compose up --build
```

Опционально: `cp .env.example .env` и правьте секреты; compose уже подхватывает `.env.example` и задаёт URL сервисов.

Сервисы:

| Сервис | Порт / роль |
| --- | --- |
| `api` | http://localhost:8000 |
| `db` | PostgreSQL 5432 |
| `db_test` | PostgreSQL 5433 (для pytest) |
| `redis` | 6379 |
| `worker` | Celery worker |
| `beat` | Celery beat (cleanup раз в час) |

Swagger UI: http://localhost:8000/docs  
Health: `GET /health`

## Примеры запросов

```bash
# Регистрация (при DEBUG=true в ответе будет verification_token)
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"a@example.com","username":"alice","full_name":"Alice","password":"password123"}'

# Верификация
curl "http://localhost:8000/auth/verify-email?token=<TOKEN>"

# Логин
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"a@example.com","password":"password123"}'

# Создать пост
curl -X POST http://localhost:8000/posts \
  -H "Authorization: Bearer <ACCESS>" \
  -H "Content-Type: application/json" \
  -d '{"title":"Hello world","content":"my first post"}'

# Feed
curl "http://localhost:8000/feed?page=1&page_size=20"

# Поставить задачу очистки (в очередь Celery)
curl -X POST http://localhost:8000/admin/cleanup-unverified
```

Верификация без SMTP: при `DEBUG=true` токен возвращается в `POST /auth/register` и пишется в лог API.

## Права доступа

| Действие | Неверифицированный | Верифицированный |
| --- | --- | --- |
| login / читать посты / лайки | да | да |
| создавать посты и комментарии | 403 | да |
| редактировать/удалять свои сущности | — | только автор (иначе 404) |

## Структура проекта

```text
Medicalka/
  app/
    api/          # роутеры
    core/         # settings, security, exceptions
    db/           # engine / session
    models/       # SQLAlchemy
    schemas/      # Pydantic
    services/     # бизнес-логика
    workers/      # Celery app + tasks
  alembic/        # миграции
  tests/          # pytest + db_test + savepoint
  Dockerfile
  docker-compose.yml
```

## Тесты

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest -q
```

Без Docker pytest сам поднимает embedded Postgres.
С Docker/`db_test`: задайте `TEST_DATABASE_URL` — тогда используется он.

Smoke-сценарий (register → verify → post → like → feed → cleanup):

```bash
python scripts/smoke_e2e.py
```

## Фоновые задачи

- Задача `cleanup_unverified_users_task` удаляет пользователей с `is_verified=false` старше `UNVERIFIED_USER_TTL_HOURS` (по умолчанию 48).
- Beat запускает её каждый час.
- `POST /admin/cleanup-unverified` только ставит задачу в Redis (не чистит синхронно).

## Линт

```bash
ruff check app tests
```
