# Specification Quality Checklist: Protocolo de partida

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

- **Spec revisada em 2026-09-11**, depois de o motor receber as duas correções
  da nota: sem pilha, com janela de declaração, desistência, resultado com
  motivo e energia que acumula. O relógio da vez (§15) ficou fora, e é a
  feature seguinte.
- FR-014 resolvido com o dono do produto: o relato inclui o que a jogada
  causou, cada item recortado por visibilidade. Exige que o motor relate o que
  fez, uma porta pública nova.
- A spec nomeia peças existentes (`{type, payload}`, os 44xx, `match_found`,
  `starter_deck`, a gravação atômica) só como **fronteira**, pela convenção das
  specs 005 a 007. "Frame JSON" aparece nos Edge Cases porque a forma da
  mensagem é o próprio objeto da validação desta feature.
- Três armadilhas encontradas lendo o código ficam explícitas para
  `/speckit-plan` não descobri-las tarde: o repasse de grupo encaminha payload
  pronto (FR-012); o socket guarda a partida lida ao conectar, e avaliar jogada
  contra ela perderia escrita (FR-007); e o fim do mulligan deixa a partida
  parada antes do Upkeep, que precisa rodar na mesma mutação (FR-009).
- FR-020 (posição na sequência de mudanças) não estava no texto de entrada: é
  consequência de duas gravações em workers diferentes poderem ser repassadas
  fora de ordem, o que deixaria o cliente desenhando um estado velho por cima de
  um novo — em especial no mulligan simultâneo.
