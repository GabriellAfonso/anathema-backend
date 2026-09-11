# Specification Quality Checklist: Combate

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-10
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

- A spec nomeia módulos e funções existentes do motor apenas como **fronteira**
  ("o mesmo aplicador", "a varredura que já existe", "o único lugar que escreve
  Nexus"), nunca como desenho novo. É a mesma convenção das specs 005 e 006
  deste projeto: o que não pode ganhar uma segunda versão precisa ser
  nomeável para ser verificável.
- O empate por dano de combate não é alcançável com as cinco cartas do MVP —
  nenhuma subtrai Nexus do oponente, e o dano de combate só chega ao Nexus do
  defensor. A garantia continua sendo requisito (FR-058 a FR-060), e o cenário é
  exercido a partir de um estado montado. Está registrado nos Edge Cases e nas
  Assumptions para que `/speckit-plan` não o descubra tarde.
- Duas decisões foram tomadas por default razoável, e ficam explícitas em
  Assumptions caso o dono do produto discorde: o piso em 0 do ataque efetivo, e
  a partida que termina durante a janela do defensor não resolver o dano do
  combate (mesma decisão que a feature 006 tomou para a pilha).
