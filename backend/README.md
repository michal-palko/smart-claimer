# Time Entry API Prototype

A simple Dockerized FastAPI + PostgreSQL backend with a plain HTML/Bootstrap frontend for time entry logging.

## Quick Start

```bash
git clone <repo>
cd vykazy_api2
docker compose up --build
```

- API docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Web form: [http://localhost:8000/frontend/index.html](http://localhost:8000/frontend/index.html)

## Database

- Table: `time_entry`
- Data is persisted in the `dbdata` Docker volume.

## Migrations

- Alembic folder is present for future migrations.
- Initial schema is created via `backend/sql/001_init.sql`.

## Next Steps

- Add more fields or validation.
- Connect the HTML form with JS fetch if needed.
- Add authentication and replace the hard-coded "autor".
