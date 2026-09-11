# Specification Quality Checklist: Feitiço imediato

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-11
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

- A regra vem da nota do Fluxo de Partida corrigida em 2026-09-11, depois de o
  dono do produto apontar, durante a spec da feature 009, que feitiço sempre
  resolveu na hora e que "Resolver" é só do combate.
- Correção do dono do produto, depois da primeira versão: jogar feitiço **não**
  passa a vez, em nenhuma fase — o jogador joga quantos feitiços a energia
  pagar, e a vez só passa com unidade, ataque ou passe. A nota foi corrigida de
  novo.
- Uma decisão foi tomada por default e fica explícita em Assumptions: jogar
  feitiço vira **uma** ação só. Com a correção acima ela fica trivial — as duas
  ações de hoje passam a ter o mesmo campo, o mesmo efeito e a mesma
  prioridade. O `keeps_priority` do commit 7239e48 continua servindo: a ação
  única declara `True`, e as outras três da §5 continuam `False` (FR-008a).
- A spec nomeia peças existentes (aplicador de efeito, guardas de lançamento,
  varredura de morte, apuração de vitória) só como **fronteira**, pela
  convenção das specs 005 a 007.
- FR-021 cobre comentário e teste porque a pilha está descrita como regra em
  docstrings de módulos que não mudam de comportamento (`play_unit`,
  `round_end`, `card_draw`, `combat_state`, `cards_in_play`, `spell_effect`).
  A constituição manda preservar comentários, mas um comentário que afirma
  regra removida é o erro que esta feature corrige.
