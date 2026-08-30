# Stack
- Python 3.14 / Django 5.2 LTS
- Django REST Framework 3.18
- Simple JWT 5.5.1
- Django Channels 4.3 + Uvicorn 0.52 (standard)
- channels_redis 4.3 / Redis 8.6
- mypy 2.3 + django-stubs 6.1
- pytest 9.1 + pytest-django 4.14 / pytest-asyncio 1.4 / pytest-cov 7.1
- Docker: python:3.14-alpine3.22 / redis:8.6-alpine


# Project knowledge base

Design and product decisions live in the Obsidian vault, not in this repo:

    C:/Users/gabri/Obsidian/Projetos/Anathema/

Read `Decisões/` before writing domain code. If the code disagrees with a
decision note, the code is wrong. `Backend/` holds per-app design notes.
Notes are in Brazilian Portuguese; keep that, and keep them short.
Write a new decision note only when asked.

Decisions in force:
- One profile per user, permanent. `PlayerProfile.user` is the PK, so
  `profile.pk == user.id`.
- `User.id` is the identity across the websocket and match layers.
- Never expose a bare `id` field. Name the id space: `user_id`, `profile_id`.


## Code style

- Functions: 4-20 lines. Split if longer.
- Files: under 500 lines. Split by responsibility.
- One thing per function, one responsibility per module (SRP).
- Names: specific and unique. Avoid `data`, `handler`, `Manager`.
  Prefer names that return <5 grep hits in the codebase.
- Types: explicit. No `any`, no `Dict`, no untyped functions.
- No code duplication. Extract shared logic into a function/module.
- Early returns over nested ifs. Max 2 levels of indentation.
- Exception messages must include the offending value and expected shape.

## Comments

- Keep your own comments. Don't strip them on refactor — they carry
  intent and provenance.
- Write WHY, not WHAT. Skip `// increment counter` above `i++`.
- Docstrings on public functions: intent + one usage example.
- Reference issue numbers / commit SHAs when a line exists because
  of a specific bug or upstream constraint.

## Tests

- Tests run with a single command: `cd server && pytest`.
- Every new function gets a test. Bug fixes get a regression test.
- Mock external I/O (API, DB, filesystem) with named fake classes,
  not inline stubs.
- Tests must be F.I.R.S.T: fast, independent, repeatable,
  self-validating, timely.
- Each test lives inside its scope's folder. App tests go under
  that app (e.g. `accounts` tests in `apps/accounts`, `game` tests
  in `apps/game/tests`).

## Dependencies

- Inject dependencies through constructor/parameter, not global/import.
- Wrap third-party libs behind a thin interface owned by this project.

## Structure

- Follow the framework's convention (Django).
- Prefer small focused modules over god files.
- Predictable paths: controller/model/view, src/lib/test, etc.

## Formatting

- Use the language default formatter (`cargo fmt`, `gofmt`, `prettier`,
  `black`, `rubocop -A`). Don't discuss style beyond that.

## Logging

- Structured JSON when logging for debugging / observability.
- Plain text only for user-facing CLI output.