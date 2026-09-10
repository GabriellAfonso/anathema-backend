# Implementation Plan: Estado de Partida

**Branch**: `002-match-state` | **Date**: 2026-09-09 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/002-match-state/spec.md`

## Summary

`apps/game/match/models.py` — hoje um `Match` de brinquedo com `turn`,
`board_state`, `hands` de string e um `play_card` que é regra de jogo no lugar
errado — é apagado e substituído por oito módulos no mesmo pacote: os tipos de
carta em partida, os modificadores, a pilha, o estado do jogador, o agregado
`Match`, os `TypedDict` da forma gravada, a serialização e a visão do jogador.
Nenhuma regra entra junto: nada aqui decide se uma jogada é legal.

Três decisões sustentam a spec. **Identidade**: `CardInstanceId` é um
`NewType` sobre `int`, cunhado por um contador que mora no próprio `Match`, com
espaço único na partida — é o que torna o alvo da pilha um número solto e a
revalidação da §6 uma pergunta respondível (FR-009 a FR-015, FR-027).
**Composição em vez de cópia**: `BankUnit` contém um `MatchCard` em vez de
repetir seus dois campos, então mover uma unidade do banco para o cemitério é
`graveyard.append(unit.card)` e o identificador sobrevive por construção, não
por disciplina (FR-012, FR-016). **Dois tipos de visão**: `PlayerSideView` tem
`hand`, `OpponentSideView` não tem o campo — vazar a mão do oponente vira erro
de mypy em vez de achado de revisão (FR-035).

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: nenhuma nova. Biblioteca padrão (`dataclasses`,
`enum`, `typing`, `json`, `uuid`) mais dois tipos que já existem no projeto:
`CardId` e `EffectDuration`, de `apps.game.cards`. `redis.asyncio` continua
sendo tocado só por `store.py`.

**Storage**: Redis 8.6, pela `MatchStore` que já existe. Uma chave por
partida, valor JSON, TTL de 6 horas. Sem banco relacional: partida viva não
tem tabela e esta feature não cria migration.

**Testing**: pytest 9.1 + pytest-django 4.14 + pytest-asyncio 1.4 (modo auto),
com `cd server && pytest`. Os testes de serialização e de visão são síncronos
e sem I/O; os de store continuam contra um Redis real no banco 15.

**Target Platform**: servidor Linux (container `python:3.14-alpine3.22`),
uvicorn com múltiplos workers — a razão de a partida morar no Redis.

**Project Type**: pacote de domínio interno dentro do app Django `apps.game`.
Não expõe HTTP. O websocket consome o pacote, mas o envelope de mensagem está
fora de escopo.

**Performance Goals**: buscar o jogador por `user_id` e buscar a unidade alvo
por `card_instance_id` são varreduras de coleção pequena e limitada — 2
jogadores, no máximo 6 + 6 unidades no banco (§12). O que precisa ser barato é
a serialização, que roda a cada gravação: uma passada por estado, sem cópia
intermediária além do dicionário que vai para `json.dumps`.

**Constraints**: `cd server && mypy` verde sob `strict = True` e
`warn_unreachable = True`, sem relaxação nova em `mypy.ini`; funções de 4 a 20
linhas; arquivos abaixo de 500 linhas; nenhum campo `id` nu; nenhuma chave de
objeto JSON indexada por `user_id`.

**Scale/Scope**: 2 jogadores, 80 cartas por partida, no máximo 12 unidades em
banco, pilha de poucos feitiços. 8 módulos novos, 1 apagado, 3 editados, 6
arquivos de teste novos e 4 existentes atualizados.

## Constitution Check

*GATE: verificado antes da Fase 0 e de novo depois da Fase 1.*

| Princípio | Veredito | Como o desenho atende |
|---|---|---|
| I. Notas de decisão são a fonte da verdade | ✅ PASS | Os campos vêm da §2 de `Game/Fluxo de Partida.md`, um a um. O identificador de instância implementa a nota de implementação da §6 ("a pilha guarda IDs de alvo, nunca referência direta a objeto"). A duração dos modificadores existe por causa da §8. Nada contradiz uma nota. |
| II. Identidade nomeada, nunca `id` nu | ✅ PASS | Três espaços nomeados e distintos no mypy: `user_id` (int), `CardId` (NewType), `CardInstanceId` (NewType). Campos: `card_instance_id`, `card_id`, `user_id`, `match_id`, `token_holder_user_id`, `priority_user_id`, `caster_user_id`, `target_card_instance_id`. Nenhum `id`. |
| III. Tipos explícitos sob mypy strict | ✅ PASS | Só stdlib tipada. Uniões fechadas para modificador; `tuple[PlayerState, PlayerState]` dá a aridade de dois ao tipo. Nenhuma relaxação nova — a lista de exceções de `mypy.ini` continua sendo Channels, DRF, `ModelAdmin`, migrations e o driver de websocket de teste. |
| IV. Unidades pequenas, uma responsabilidade | ✅ PASS | 8 módulos separados por responsabilidade, nenhum passando de ~150 linhas. `models.py`, que hoje mistura estado, serialização, visão e regra, deixa de existir. Funções de serialização são uma por tipo. |
| V. Comportamento testado com fakes nomeados | ✅ PASS | `FakeMatchStore` acompanha a troca; `FakeCardCatalog` já existe para quem precisar de molde; `fake_match_state.py` novo entrega estados de partida montados para teste, no formato de `fake_player_data.py`. O único I/O é o Redis, que já tem fake e teste de contrato próprios. |
| Stack fixada | ✅ PASS | Nenhuma dependência nova, nenhum bump. |
| Estrutura Django previsível | ✅ PASS | Módulos dentro de `apps/game/match/`, o pacote que já é dono da partida. Sem app novo, sem `INSTALLED_APPS`, sem migration. |
| Injeção de dependência | ✅ PASS | O catálogo chega por parâmetro a quem precisar dele (FR-041). Esta feature importa de `apps.game.cards` só dois **tipos** — `CardId` e `EffectDuration` — nunca a fábrica `mvp_catalog()`. Importar um tipo não é alcançar uma dependência em tempo de chamada. |
| Portas de qualidade | ✅ PASS | `pytest`, `mypy`, `black` rodam sem configuração nova. |
| Comentários preservados no refactor | ⚠️ ATENÇÃO | `models.py` é apagado, não refatorado, mas três comentários dele carregam intenção que continua válida e MUST ser reaproveitada: por que a chave vira string no JSON, por que `has_player` mora no `Match`, e o `>>> match.has_player(7)`. O detalhe está em [research.md](./research.md) D9. |

### Reverificação depois da Fase 1

O desenho fechado não mudou nenhum veredito. Quatro pontos que a Fase 1 tornou
concretos:

- **Princípio II**: `CardInstanceId` é `NewType` sobre `int`, então passar um
  `card_id` onde se espera um `card_instance_id` é erro de mypy — que é
  exatamente o risco que o formato `15-A`, descartado nas *Clarifications*,
  não conseguia impedir.
- **Princípio III**: a união `UnitModifier` precisa de um discriminante no
  JSON para voltar ao tipo certo. O campo é `modifier_kind`, e o
  `match`/`case` que o lê é exaustivo — um modificador novo sem braço é erro
  de tipo. Detalhe em [research.md](./research.md) D5.
- **Princípio IV**: o maior módulo previsto é `serialization.py`, com um par
  de funções por tipo, na casa de 180 linhas. Dentro do teto.
- **Princípio V**: nenhum teste desta feature precisa de mock novo. Estado é
  memória pura; só `test_match_store.py` toca Redis, e já tem fixture.

## Project Structure

### Documentation (this feature)

```text
specs/002-match-state/
├── plan.md                    # Este arquivo
├── spec.md                    # A especificação
├── research.md                # Fase 0 — decisões de desenho e alternativas
├── data-model.md              # Fase 1 — tipos, campos, invariantes, forma JSON
├── quickstart.md              # Fase 1 — como rodar e provar que funciona
├── contracts/
│   └── match_state.md         # Fase 1 — superfície pública de apps.game.match
├── checklists/
│   └── requirements.md        # Checklist de qualidade da spec (16/16)
└── tasks.md                   # Fase 2 — criado por /speckit-tasks, não por este comando
```

### Source Code (repository root)

```text
server/
├── apps/
│   └── game/
│       ├── cards/                       # existente — consumido, não alterado
│       ├── match/
│       │   ├── __init__.py              # REESCRITO — superfície pública, __all__
│       │   ├── models.py                # APAGADO — Match de brinquedo + play_card
│       │   ├── cards_in_play.py         # NOVO — CardInstanceId, MatchCard, BankUnit
│       │   ├── modifiers.py             # NOVO — ModifierKind, os 3 tipos, união
│       │   ├── spell_stack.py           # NOVO — StackEntry
│       │   ├── player_state.py          # NOVO — PlayerState
│       │   ├── match_state.py           # NOVO — MatchPhase, Match, NotAParticipantError
│       │   ├── documents.py             # NOVO — TypedDicts da forma gravada
│       │   ├── serialization.py         # NOVO — to_/from_ de cada tipo
│       │   ├── player_view.py           # NOVO — PlayerSideView, OpponentSideView, build
│       │   ├── store.py                 # EDITADO — dois call sites de serialização
│       │   └── client.py                # existente — não alterado
│       ├── consumers/
│       │   ├── match.py                 # EDITADO — só o import
│       │   └── matchmaking.py           # EDITADO — só o import
│       └── tests/
│           ├── fake_match_state.py             # NOVO — estados montados para teste
│           ├── test_match_state.py             # NOVO — campos, fases, busca de jogador
│           ├── test_card_instance_identity.py  # NOVO — US2
│           ├── test_bank_unit.py               # NOVO — dano, modificadores, molde intacto
│           ├── test_spell_stack.py             # NOVO — LIFO, alvo, fizzle
│           ├── test_match_serialization.py     # NOVO — ida e volta, chaves, contador
│           ├── test_player_view.py             # NOVO — o que aparece e o que não
│           ├── test_match_model.py             # SUBSTITUÍDO por test_match_state.py
│           ├── test_match_store.py             # EDITADO — asserções do estado novo
│           ├── fake_match_store.py             # EDITADO — import
│           └── test_match_consumer_access.py   # EDITADO — import
└── core/                                       # não alterado
```

**Structure Decision**: módulos planos dentro de `apps/game/match/`, não um
subpacote `match/state/`. O pacote `match/` já é o dono da partida — hoje com
`client.py`, `models.py` e `store.py` — e o que esta feature entrega é
exatamente o conteúdo que `models.py` deveria ter tido. Um subpacote
acrescentaria um nível de import (`apps.game.match.state.Match`) para separar
o estado do seu próprio store, que é a única coisa que o lê. `cards/` já provou
o formato plano com 6 módulos; este fica com 10, ainda navegável, e cada nome
diz o que tem dentro.

`__init__.py` passa a ser superfície pública com `__all__` explícito, como
`cards/__init__.py`: `mypy.ini` roda com `strict`, que liga
`no_implicit_reexport`, então sem a lista ninguém importa do pacote.

Testes ficam em `apps/game/tests/`, no nível plano que já existe, como manda a
constituição.

## Complexity Tracking

Nenhuma violação de princípio a justificar. Três pontos herdados que esta
feature toca de raspão e resolve ou registra:

| Ponto | O que é | Encaminhamento |
|---|---|---|
| `CardId` duplicado | `models.py` define `CardId = str` com o comentário "o baralho ainda não existe", incompatível com o `CardId = NewType(..., int)` de `cards/card.py`. O plano 001 registrou isso como pendência da primeira feature que ligasse o motor ao catálogo. | **Resolvido aqui.** O alias de string morre com `models.py`; `cards_in_play.py` importa `CardId` de `apps.game.cards`. Fica um `CardId` só no projeto. |
| Roteamento de `play_card` no consumer | `consumers/base.py:155` roteia `{"type": "play_card"}` para `handle_play_card`, que `MatchConsumer` não implementa. Apagar `Match.play_card` não mexe nisso — o roteamento já apontava para o vazio. | Fora de escopo: jogar carta é regra. Fica como está, e a feature do motor implementa o handler. |
| `test_match_store.py` assere sobre `hands` e `get_state_for_player` | Duas asserções morrem com o modelo antigo. | Reescritas contra o estado novo (FR-043). A intenção de cada uma é preservada: "o tipo de `user_id` sobrevive" vira "nenhuma chave de objeto JSON é `user_id`". |

**Registro no vault**: o item de `Backend/TODO.md` sobre unificar `CardId`
pode ser fechado quando esta feature entrar.
