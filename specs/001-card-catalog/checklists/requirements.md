# Specification Quality Checklist: Catálogo de Cartas do MVP

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-09
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

Checklist completa: 16/16.

Três decisões estão registradas em *Assumptions* — a primeira veio do
maintainer, as outras duas são padrão razoável adotado sem pergunta. Se alguma
estiver errada, o conserto é local:

1. **Faixas de `card_id`.** Unidade de 1 a 1000 (as 24 mantêm o id herdado),
   feitiço a partir de 1001 (1001–1005). Escolha do maintainer. A faixa é
   convenção de leitura, não regra do motor: FR-005 proíbe decidir o tipo
   comparando o `card_id` com 1000 — quem quer o tipo lê o campo `type`.
2. **MAGIC BARRIER mira unidade aliada.** A descrição herdada não diz de quem é
   a unidade. Muda só a tabela *Efeitos do MVP*.
3. **SACRIFICIAL FIRE dá +3 de ataque permanente.** Nada na origem diz que
   expira. Muda só a tabela *Efeitos do MVP*.

Fora de escopo, mas nomeado para a próxima feature: a identidade de cada cópia
de carta (até 3 por `card_id` no deck) é atribuída pela camada de partida, não
pelo catálogo.

O limite de 3 cópias por deck ainda não tem nota de decisão no vault. Candidato
a `Decisões/` depois do primeiro playtest.
