# Specification Quality Checklist: Decks do jogador, e o catálogo servido ao cliente

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-12
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- As duas "decisões que faltam" do pedido foram resolvidas na sessão de
  2026-09-12 e estão registradas em *Clarifications*: teto de **20** decks por
  jogador (FR-020) e **sem rascunho** — as três regras valem no salvamento e na
  fila (FR-021).
- A escolha "sem rascunho" não enfraquece a validação da fila: FR-022 registra
  por que as duas continuam existindo (o catálogo pode mudar entre um
  salvamento e uma partida).
- "Salvar deck com nome vazio ou repetido" foi resolvido por padrão razoável em
  vez de virar pergunta: nome não vazio depois de remover espaços (FR-018) e
  nome repetido aceito, porque a identidade é o `deck_id` (FR-019).
- HTTP aparece em FR-001 porque o pedido do maintainer nomeia o transporte
  ("O catálogo pelo HTTP"); o restante da spec não nomeia framework, rota,
  verbo nem formato de payload.
- "Fila", "setup da §3", "protocolo", "relógio" e "as três regras da feature
  001" aparecem só como fronteira que não pode ganhar segunda versão, pela
  convenção das specs 005 a 010 — não como desenho.
