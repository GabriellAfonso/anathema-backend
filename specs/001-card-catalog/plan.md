# Implementation Plan: Catálogo de Cartas do MVP

**Branch**: `001-card-catalog` | **Date**: 2026-09-09 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-card-catalog/spec.md`

## Summary

Um pacote Python somente leitura dentro de `apps/game/`, irmão de `match/` e
`matchmaking/`, que guarda as 29 cartas do MVP como dataclasses congeladas e
expõe quatro operações — buscar por `card_id`, listar tudo, listar por tipo e
validar deck — atrás de um `Protocol`. Sem banco, sem migration, sem app Django
novo: a persistência do catálogo está fora de escopo e nada aqui precisa de
tabela para funcionar.

O que sustenta a spec: o efeito de feitiço vira uma união fechada de dataclasses
que declaram `target_kind` e `duration` como campos, então o motor de regras
decide sem ler português (FR-013); a imutabilidade vem de `frozen=True`, então
buff em partida não tem como alcançar a carta (FR-026); e a validação de deck
devolve a lista completa de problemas em vez de estourar no primeiro (FR-025).

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: nenhuma nova. Só a biblioteca padrão —
`dataclasses`, `enum`, `typing`. Django 5.2 e DRF já estão no projeto mas não
são tocados por esta feature.

**Storage**: N/A. Catálogo em memória, definido em código. Persistir deck e
catálogo está fora de escopo por decisão da spec.

**Testing**: pytest 9.1 + pytest-django 4.14, rodando com `cd server && pytest`.

**Target Platform**: servidor Linux (container `python:3.14-alpine3.22`).

**Project Type**: pacote de domínio interno dentro do app Django `apps.game`.
Não expõe HTTP nem websocket nesta feature.

**Performance Goals**: busca por `card_id` em tempo constante. Com 29 cartas
carregadas uma vez no import, não há alvo de throughput a perseguir.

**Constraints**: `cd server && mypy` verde sob `strict = True` e
`warn_unreachable = True`; funções de 4 a 20 linhas; arquivos abaixo de 500
linhas; nenhum campo `id` nu em superfície pública.

**Scale/Scope**: 29 cartas (24 unidades, 5 feitiços), 5 tipos de efeito, 6
módulos novos, 5 arquivos de teste novos. Nenhum arquivo existente é alterado.

## Constitution Check

*GATE: verificado antes da Fase 0 e de novo depois da Fase 1.*

| Princípio | Veredito | Como o desenho atende |
|---|---|---|
| I. Notas de decisão são a fonte da verdade | ✅ PASS | O catálogo consome `Game/Fluxo de Partida.md` (deck de 40 §12, duração "até o fim da rodada" §8, revalidação de alvo §6) e não contradiz nenhuma. Ressalva registrada abaixo. |
| II. Identidade nomeada, nunca `id` nu | ✅ PASS | O identificador se chama `card_id` em todo lugar. O tipo é `CardId`, distinto de `user_id`. |
| III. Tipos explícitos sob mypy strict | ✅ PASS | Só stdlib tipada; nenhuma dependência sem stubs, então nenhuma relaxação nova em `mypy.ini`. Nenhum `Any`, nenhum genérico nu. |
| IV. Unidades pequenas, uma responsabilidade | ✅ PASS | 6 módulos separados por responsabilidade: tipo de carta, efeito, catálogo, dados do MVP, regras de deck, superfície pública. Maior arquivo é o de dados (~300 linhas). |
| V. Comportamento testado com fakes nomeados | ✅ PASS | `FakeCardCatalog` em `apps/game/tests/`, no mesmo formato de `FakeMatchStore`. Nenhum I/O externo a mockar — não há banco, rede nem arquivo. |
| Stack fixada | ✅ PASS | Nenhuma dependência nova, nenhum bump. |
| Estrutura Django previsível | ✅ PASS | Subpacote de app existente, como `match/` e `matchmaking/`. Sem `INSTALLED_APPS` novo, sem `models.py`, sem migration. |
| Injeção de dependência | ✅ PASS | Consumidores recebem `CardCatalog` por parâmetro, como `MatchStore` recebe `Redis`. |
| Portas de qualidade | ✅ PASS | `pytest`, `mypy`, `black` rodam sem configuração nova. |

### Reverificação depois da Fase 1

O desenho fechado não mudou nenhum veredito. Três pontos que a Fase 1 tornou
concretos e que valia conferir:

- **Princípio III**: o pacote usa só `dataclasses`, `enum` e `typing`, todos
  tipados na stdlib. Nenhuma relaxação nova em `mypy.ini` — a lista de exceções
  do arquivo continua sendo só Channels, DRF e `ModelAdmin`.
- **Princípio IV**: o maior arquivo previsto é `mvp_catalog.py`, com as 29
  cartas, na casa das 300 linhas. Dentro do teto de 500. As funções são
  construtores e filtros, todas na faixa de 4 a 20 linhas.
- **Princípio II**: `CardId` é `NewType` sobre `int`, distinto de `user_id` no
  mypy, e o campo se chama `card_id` em toda a superfície pública.

**Ressalva no princípio I**: duas regras desta feature não têm nota em
`Decisões/` — o limite de 3 cópias por deck e as faixas de `card_id` (unidade
1–1000, feitiço a partir de 1001). Ambas vieram do pedido, estão registradas em
*Assumptions* na spec, e a constituição só manda escrever nota de decisão
quando o maintainer pede. Fica como candidato a `Decisões/` depois do primeiro
playtest, não como bloqueio.

## Project Structure

### Documentation (this feature)

```text
specs/001-card-catalog/
├── plan.md              # Este arquivo
├── spec.md              # A especificação
├── research.md          # Fase 0 — decisões de desenho e alternativas
├── data-model.md        # Fase 1 — entidades, campos, invariantes
├── quickstart.md        # Fase 1 — como rodar e provar que funciona
├── contracts/
│   └── card_catalog.md  # Fase 1 — superfície pública do pacote
├── checklists/
│   └── requirements.md  # Checklist de qualidade da spec (16/16)
└── tasks.md             # Fase 2 — criado por /speckit-tasks, não por este comando
```

### Source Code (repository root)

```text
server/
├── apps/
│   └── game/
│       ├── cards/                  # NOVO — o catálogo
│       │   ├── __init__.py         # superfície pública, com __all__ explícito
│       │   ├── card.py             # CardId, CardType, Card/Unit/Spell, faixas
│       │   ├── effects.py          # TargetKind, EffectDuration, união SpellEffect
│       │   ├── catalog.py          # protocolo CardCatalog, FrozenCardCatalog, erros
│       │   ├── mvp_catalog.py      # as 29 cartas + fábrica do catálogo do MVP
│       │   └── deck_rules.py       # DECK_SIZE, MAX_COPIES, problemas, validação
│       ├── match/                  # existente — não alterado nesta feature
│       ├── matchmaking/            # existente — não alterado
│       ├── consumers/              # existente — não alterado
│       └── tests/
│           ├── fake_card_catalog.py    # NOVO — catálogo pequeno para injeção
│           ├── test_card_catalog.py    # NOVO — busca, listagem, erros de carga
│           ├── test_spell_effects.py   # NOVO — os 5 efeitos estruturados
│           ├── test_deck_rules.py      # NOVO — as 3 regras de deck
│           └── test_mvp_catalog.py     # NOVO — conferência contra os dados de origem
└── core/                           # não alterado
```

**Structure Decision**: `apps/game/cards/` como subpacote, não app Django novo.
O app `apps.game` já é organizado por subpacote de responsabilidade
(`match/`, `matchmaking/`, `consumers/`), e o catálogo é domínio de jogo. Um app
novo exigiria entrada em `INSTALLED_APPS` e um `AppConfig` para zero modelo e
zero migration — cerimônia sem contrapartida. Se o catálogo virar tabela depois,
a promoção a app é uma mudança contida, e `card_id` já está pronto para ser a
chave.

Testes ficam em `apps/game/tests/`, como manda a constituição ("game tests under
`apps/game/tests`"), no mesmo nível plano dos testes que já existem lá.

## Complexity Tracking

Nenhuma violação de princípio a justificar. Um conflito de nome herdado, que
esta feature não cria nem resolve, fica registrado aqui para não sumir:

| Ponto | O que é | Por que não é resolvido aqui |
|---|---|---|
| `CardId` duplicado | `apps/game/match/models.py` já define `CardId = str`, com o comentário "o baralho ainda não existe". Esta feature define `CardId` como inteiro em `apps/game/cards/card.py`. Ficam dois nomes iguais e tipos incompatíveis no mesmo app. | Estado de partida está explicitamente fora do escopo da spec. Trocar o alias do `match` mexe em `play_card`, `MatchState` e nos testes de partida, que hoje usam id de carta em string. A troca é a primeira tarefa da feature que ligar o motor ao catálogo — não uma edição de passagem nesta. |

**Encaminhamento**: registrar em `Backend/TODO.md` no vault que
`match/models.py` deve passar a importar `CardId` de `apps.game.cards.card`
quando o motor começar a consumir o catálogo, e que o placeholder de string sai
junto.
