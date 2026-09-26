# Academy FastAPI Project

## Project Map

- `main.py` creates the FastAPI application and registers routers.
- `config/db.py` contains the in-memory stores.
- `models/schemas.py` contains Pydantic request and response models.
- `routers/` contains student, course, and enrollment endpoints.
- `utils/` contains helpers shared by the routers.

## Rules



- Keep `config/db.py` limited to typed dictionary variables. Do not add SQL, an ORM, database connections, file persistence, or external storage.
- Keep the API centered on students, courses, and enrollments.
- Validate student emails as Gmail addresses and validate strong passwords through Pydantic schemas.
- Never include student passwords in API responses.
- Preserve unique student emails, valid enrollment references, duplicate-enrollment protection, and protection against deleting records referenced by enrollments.
- Support full and partial updates as separate operations.
- Do not add authentication, pagination, search, or sorting unless explicitly requested.
- Put behavior shared by multiple routers in `utils/` instead of duplicating it in route handlers.

## Verification

After changes, verify imports and FastAPI startup, check `/docs`, and exercise the affected endpoints with focused requests. Since this project currently has no dependency manifest or test suite, inspect the active Python environment before adding commands or dependencies.
