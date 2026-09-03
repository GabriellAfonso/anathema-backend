<!--
Sync Impact Report
- Version change: (uninitialized template) → 1.0.0
- Bump rationale: first ratification; every placeholder replaced with concrete
  project rules derived from CLAUDE.md and the Obsidian decision notes.
- Modified principles: none (initial adoption). Placeholders resolved to:
  [PRINCIPLE_1_NAME] → I. Decision Notes Are The Source Of Truth
  [PRINCIPLE_2_NAME] → II. Named Identity, Never A Bare `id`
  [PRINCIPLE_3_NAME] → III. Explicit Types, Checked By mypy strict
  [PRINCIPLE_4_NAME] → IV. Small Units, One Responsibility Each
  [PRINCIPLE_5_NAME] → V. Tested Behavior With Named Fakes
  [SECTION_2_NAME]   → Technology And Structure Constraints
  [SECTION_3_NAME]   → Development Workflow And Quality Gates
- Added sections: Core Principles (5), Technology And Structure Constraints,
  Development Workflow And Quality Gates, Governance.
- Removed sections: none.
- Templates requiring updates:
  ✅ .specify/templates/plan-template.md — "Constitution Check" is generic and
     resolves against this file; no edit required.
  ✅ .specify/templates/spec-template.md — no constitution-dependent section.
  ✅ .specify/templates/tasks-template.md — task categories already cover the
     testing and typing gates this constitution mandates.
  ✅ .specify/templates/checklist-template.md — no constitution reference.
  ✅ CLAUDE.md — this constitution restates its rules; no divergence introduced.
- Follow-up TODOs: none.
-->

# Anathema Backend Constitution

## Core Principles

### I. Decision Notes Are The Source Of Truth

Product and domain decisions live in the Obsidian vault at
`C:/Users/gabri/Obsidian/Projetos/Anathema/`, not in this repository. `Decisões/`
MUST be read before writing domain code. When code and a decision note disagree,
the code is wrong and MUST be corrected — never the note. New decision notes are
written only when the maintainer asks for one; notes stay in Brazilian
Portuguese and stay short.

Decisions currently in force and binding on all code:

- One `PlayerProfile` per user, permanent. `PlayerProfile.user` is the primary
  key, so `profile.pk == user.id`.
- `User.id` is the identity across the websocket and match layers.

Rationale: a single external home for decisions prevents the same question from
being re-answered differently in each app.

### II. Named Identity, Never A Bare `id`

No serializer, payload, websocket message, or public function signature MAY
expose a field named `id`. The identity space MUST be named: `user_id`,
`profile_id`, `match_id`.

Rationale: the websocket and match layers pass identities between processes
where the owning model is no longer visible; an unqualified `id` becomes
ambiguous exactly where a mismatch is most expensive.

### III. Explicit Types, Checked By mypy strict

Every function MUST be annotated. `Any`, bare generics (`dict`, `list`), and
untyped definitions are forbidden. `cd server && mypy` MUST pass with the
configuration in `server/mypy.ini` (`strict = True`, `warn_unreachable = True`)
before work is considered done. Existing per-module relaxations in `mypy.ini`
exist for third-party gaps (Channels, DRF, `ModelAdmin`) and MUST carry the
comment explaining why; new relaxations require the same written justification.

Rationale: the strict configuration is already green — every ignore added
without a reason is a permanent hole nobody can later distinguish from a real
constraint.

### IV. Small Units, One Responsibility Each

- Functions: 4-20 lines. Longer MUST be split.
- Files: under 500 lines. Longer MUST be split by responsibility.
- One thing per function, one responsibility per module.
- Early returns over nested conditionals; maximum 2 levels of indentation.
- No duplicated logic — shared behavior MUST be extracted into a function or
  module.
- Names MUST be specific and unique. `data`, `handler`, and `Manager` are
  banned; prefer a name that returns fewer than 5 grep hits in the codebase.
- Exception messages MUST include the offending value and the expected shape.

Rationale: these are the limits the existing `apps/` layout already holds to;
stating them as thresholds makes a violation reviewable instead of arguable.

### V. Tested Behavior With Named Fakes

The whole suite MUST run with one command: `cd server && pytest`. Every new
function gets a test. Every bug fix gets a regression test that fails before
the fix. External I/O — HTTP, database, filesystem, Redis — MUST be replaced by
a named fake class (e.g. `FakeMatchStore`, `FakePlayerSettings`), never an
inline stub or an ad-hoc lambda. Tests MUST be F.I.R.S.T.: fast, independent,
repeatable, self-validating, timely. Each test lives inside its own scope's
folder — `accounts` tests under `apps/accounts`, `game` tests under
`apps/game/tests`.

Rationale: named fakes are greppable and reusable; inline stubs silently drift
from the interface they imitate.

## Technology And Structure Constraints

The stack is pinned and MUST NOT be changed without an amendment to this
constitution:

- Python 3.14 / Django 5.2 LTS / Django REST Framework 3.18
- Simple JWT 5.5.1
- Django Channels 4.3 + Uvicorn 0.52 (standard)
- channels_redis 4.3 / Redis 8.6
- mypy 2.3 + django-stubs 6.1
- pytest 9.1 + pytest-django 4.14 / pytest-asyncio 1.4 / pytest-cov 7.1
- Docker images: `python:3.14-alpine3.22` / `redis:8.6-alpine`

Structural rules:

- Follow Django's conventions. Paths MUST be predictable: models, views,
  serializers, services, per-app folders under `server/apps/`.
- Prefer small focused modules over god files.
- Dependencies MUST be injected through a constructor or parameter, never
  reached for through a global or a module-level import at call time.
- Third-party libraries MUST be wrapped behind a thin interface owned by this
  project (the `match/store.py`, `matchmaking/queue.py` shape), so the library
  never leaks into domain code.
- Formatting is delegated to `black`. Style beyond the formatter's output is
  not a review topic.
- Logging is structured JSON for debugging and observability; plain text only
  for user-facing CLI output.

## Development Workflow And Quality Gates

Before any change is considered complete:

1. `cd server && pytest` passes.
2. `cd server && mypy` passes.
3. `black` has been run over the changed files.

Comment discipline is part of review:

- Existing comments MUST be preserved through a refactor — they carry intent
  and provenance.
- Comments explain WHY, not WHAT. No `# increment counter` above `i += 1`.
- Public functions carry a docstring stating intent plus one usage example.
- A line that exists because of a specific bug or upstream constraint MUST
  reference the issue number or commit SHA.

Deliberately deferred work is recorded in `Backend/TODO.md` in the vault with
its diagnosis and its path forward. An item in that file is a decision, not an
unknown bug, and MUST NOT be silently "fixed" in passing during unrelated work.

## Governance

This constitution supersedes any other practice, habit, or convention in this
repository. Where `CLAUDE.md` and this document overlap they MUST agree; if
they diverge, this document governs and `CLAUDE.md` is corrected to match.

Amendments:

- Any change to this file MUST be a deliberate, standalone edit that states
  what changed and why in its commit message.
- Version numbering follows semantic versioning:
  - MAJOR — a principle is removed or redefined in a backward-incompatible way,
    or a governance rule is dropped.
  - MINOR — a principle or section is added, or existing guidance is materially
    expanded.
  - PATCH — clarifications, wording, and typo fixes that change no rule.
- A change to the pinned stack in *Technology And Structure Constraints* is at
  minimum a MINOR amendment and MUST be recorded here before the dependency is
  bumped.

Compliance:

- Every review verifies the three quality gates above and the Core Principles.
- Complexity that violates a principle MUST be justified in writing at the
  point of the exception, or removed.
- `CLAUDE.md` remains the runtime development guidance for coding agents; the
  Obsidian vault remains the source of truth for domain decisions.

**Version**: 1.0.0 | **Ratified**: 2026-09-03 | **Last Amended**: 2026-09-03
