# Quickstart — Pilha de Feitiços e Efeitos

**Feature**: `006-spell-stack-effects` | **Data**: 2026-09-10

Como rodar a suíte e como provar, à mão, que a pilha resolve em LIFO com fizzle
e que um Nexus em zero encerra a partida. Detalhe de assinatura está em
[contracts/](./contracts/); detalhe de campo está em
[data-model.md](./data-model.md).

---

## 1. Pré-requisitos

O container de desenvolvimento, como nas features anteriores:

```bash
docker compose up -d
```

Nada novo é instalado. Esta feature não acrescenta dependência, não cria
migration e não toca em Redis — todo o teste dela é síncrono e sem I/O,
inclusive o de round-trip, que passa por `to_match_document` /
`match_from_document` direto.

Sem container, um virtualenv com `server/requirements-dev.txt` basta.

---

## 2. As três portas de qualidade

```bash
cd server && pytest
cd server && mypy
cd server && black --check .
```

As três precisam estar verdes. `mypy` roda com `strict = True` e
`warn_unreachable = True`, e esta feature não acrescenta relaxação nenhuma em
`mypy.ini`.

Só o que a feature acrescentou:

```bash
cd server && pytest apps/game/tests/test_cast_spell.py \
                    apps/game/tests/test_stack_resolution.py \
                    apps/game/tests/test_spell_effect.py \
                    apps/game/tests/test_unit_damage.py \
                    apps/game/tests/test_victory.py \
                    apps/game/tests/test_match_outcome.py \
                    apps/game/tests/test_spell_state_round_trip.py
```

O que **não** pode ter mudado (US9, SC-017):

```bash
cd server && pytest apps/game/tests/test_card_catalog.py \
                    apps/game/tests/test_mvp_catalog.py \
                    apps/game/tests/test_spell_effects.py \
                    apps/game/tests/test_match_serialization.py \
                    apps/game/tests/test_player_view.py \
                    apps/game/tests/test_round_end.py \
                    apps/game/tests/test_play_unit.py \
                    apps/game/tests/test_player_action.py \
                    apps/game/tests/test_action_phase.py \
                    apps/game/tests/test_upkeep.py
```

Nenhum desses arquivos foi alterado. Se algum deles falhar, a feature quebrou
uma anterior.

**Dois arquivos de teste anteriores mudaram**, e os dois por serem inventários
que esta feature tornou desatualizados — não por regressão:

```bash
cd server && pytest apps/game/tests/test_match_state.py \
                    apps/game/tests/test_round_cycle.py
```

- `test_match_state.py::test_the_phase_set_is_closed` lista os valores de
  `MatchPhase` um a um. `FINISHED` entrou, e a lista ganhou uma linha. O teste
  existe justamente para forçar essa decisão a ser consciente — e forçou.
- `test_round_cycle.py::test_the_stack_branch_of_the_exit_is_wired` afirmava
  que a cascata **parava** em `STACK_RESOLUTION`, porque nada sabia esvaziá-la.
  Ele agora afirma o outro lado da mesma costura: a cascata atravessa a fase e
  devolve a partida à Fase de Ação, na mesma rodada.

A regra que os dois guardam não mudou. O que mudou foi o inventário.

> `test_spell_effects.py` é da feature 001 e continua sendo sobre a **forma** dos
> cinco efeitos no catálogo. O que esta feature acrescenta — a **execução** deles
> — é `test_spell_effect.py`, no singular. Os dois nomes convivem de propósito:
> um descreve o que o efeito declara, o outro o que o motor faz com a
> declaração.

---

## 3. O exemplo canônico da §6, no shell

```bash
cd server && python manage.py shell
```

```python
from apps.game.cards import mvp_catalog
from apps.game.engine import CastSpellAction, PassAction, submit_action
from apps.game.tests.fake_random_source import ScriptedRandomSource
from apps.game.tests.fake_spell_board import (
    FRAGILE_UNIT,
    SACRIFICIAL_FIRE,
    SOMEONES_SHIELD,
    SUMMONED_AX,
    bank_card,
    fake_spell_board,
    hand_card,
)

catalog = mvp_catalog()
source = ScriptedRandomSource()

# Partida na Fase de Ação: A com prioridade, uma unidade X frágil no banco de A,
# SOMEONE'S SHIELD (1001) na mão de A, SUMMONED AX (1005) na mão de B.
match = fake_spell_board(
    catalog=catalog,
    hand_one=(SOMEONES_SHIELD,),
    hand_two=(SUMMONED_AX,),
    bank_one=(FRAGILE_UNIT,),
)
a, b = match.players
x = bank_card(a)

# A lança o buff de vida em X. O efeito NÃO acontece.
submit_action(
    match,
    CastSpellAction(a.user_id, hand_card(a, SOMEONES_SHIELD), x),
    catalog=catalog,
    randomness=source,
)
len(match.stack), a.bank[0].modifiers        # (1, [])   -- empilhou, não aplicou

# B responde no topo, mirando o mesmo X.
submit_action(
    match,
    CastSpellAction(b.user_id, hand_card(b, SUMMONED_AX), x),
    catalog=catalog,
    randomness=source,
)
[e.caster_user_id for e in match.stack]      # [7, 9]    -- B é o topo

# Os dois passam: a pilha resolve inteira, de cima para baixo.
submit_action(match, PassAction(a.user_id), catalog=catalog, randomness=source)
submit_action(match, PassAction(b.user_id), catalog=catalog, randomness=source)
```

O que se lê depois:

```python
match.stack                    # []          -- a pilha esvaziou
a.bank                         # []          -- X morreu pelo AX, que resolveu primeiro
[c.card_instance_id for c in a.graveyard]    # [2, 1]  -- X e o SHIELD de A
[c.card_instance_id for c in b.graveyard]    # [3]     -- o AX de B
match.priority_user_id         # 7           -- quem ABRIU a pilha, não quem fechou
match.consecutive_passes       # 0
match.round_number             # 1           -- a rodada NÃO fechou
match.phase                    # <MatchPhase.ACTION: 'action'>
```

O buff fizzlou: X não existia mais quando ele resolveu, e a carta foi ao
cemitério sem aplicar nada. É a §6 ao pé da letra.

---

## 4. Um Nexus em zero, no shell

```python
from apps.game.engine import MatchIsOverError

# Partida nova, SACRIFICIAL FIRE na mão de A, e A com 8 de Nexus.
match = fake_spell_board(catalog=catalog, hand_one=(SACRIFICIAL_FIRE,))
a, b = match.players
a.nexus = 8

submit_action(
    match,
    CastSpellAction(a.user_id, hand_card(a, SACRIFICIAL_FIRE)),
    catalog=catalog,
    randomness=source,
)
submit_action(match, PassAction(b.user_id), catalog=catalog, randomness=source)
submit_action(match, PassAction(a.user_id), catalog=catalog, randomness=source)

a.nexus                          # 0
match.is_over                    # True
match.outcome.defeated_user_ids  # (7,)
match.outcome.is_draw            # False
match.phase                      # <MatchPhase.FINISHED: 'finished'>

# Nenhuma ação é aceita depois disso, de nenhum dos dois.
submit_action(match, PassAction(b.user_id), catalog=catalog, randomness=source)
# MatchIsOverError: action 'pass' is not allowed in match 'fake-match-0001':
# the match is over, defeated user_ids (7,)
```

E o estado terminal sobrevive ao Redis:

```python
from apps.game.match import match_from_document, to_match_document
import json

back = match_from_document(json.loads(json.dumps(to_match_document(match))))
back.outcome == match.outcome     # True
back.phase                        # <MatchPhase.FINISHED: 'finished'>
```

---

## 5. Os cinco efeitos, um a um

Cada linha é uma afirmação que o teste correspondente faz. Os números são os do
catálogo do MVP, lidos dos campos estruturados — nunca da descrição.

| Carta | Estado antes | Estado depois |
|---|---|---|
| SOMEONE'S SHIELD | unidade aliada, molde 4 de vida, 3 de dano | `unit_max_health` 6, `damage_taken` **ainda 3** |
| MAGIC BARRIER | unidade aliada sem modificador | `DamageImmunity` até o fim da rodada; dano seguinte não entra |
| SACRIFICIAL FIRE | lançador com 20 de Nexus, 3 unidades | Nexus 12, as 3 com `AttackModifier(+3)` permanente |
| SACRIFICIAL FIRE | lançador com 20 de Nexus, **0 unidades** | Nexus 12 mesmo assim |
| LIFE POTION | lançador com 20 de Nexus | Nexus **25** — não existe teto |
| SUMMONED AX | unidade inimiga, `unit_max_health` 3 | `damage_taken` 3, unidade no cemitério do dono |
| SUMMONED AX | unidade inimiga com `DamageImmunity` | `damage_taken` inalterado, unidade viva, feitiço **não** fizzlou |

E a §8 continua a mesma, agora com o que varrer:

```python
# depois de dois passes com a pilha vazia
[type(m).__name__ for m in unit.modifiers]   # ['HealthModifier'] -- a imunidade sumiu
```

---

## 6. O que cada arquivo de teste prova

| Arquivo | Histórias | O que ele pinça |
|---|---|---|
| `test_cast_spell.py` | US1, US8 | Empilha sem aplicar; as 4 guardas na ordem; as 5 recusas com o valor ofensor; estado idêntico por `match_snapshot` em toda recusa. |
| `test_stack_resolution.py` | US2, US3, US4 | LIFO; sem prioridade entre resoluções; fizzle por alvo morto; cemitério do lançador; prioridade de volta ao iniciador; rodada não fecha; o exemplo canônico da §6. |
| `test_spell_effect.py` | US5, US6 | Os cinco efeitos; a duração vinda do catálogo; o mesmo resultado aplicado direto e via pilha. |
| `test_unit_damage.py` | US5 | Vida máxima contra restante; morte no limite exato; imunidade barrando a entrada; enterro no cemitério do dono. |
| `test_victory.py` | US7 | Nexus ≤ 0, empate, idempotência, `MatchIsOverError`, e a invariante `outcome ⟺ FINISHED`. |
| `test_match_outcome.py` | US7 | `is_draw` nos dois casos, e as três recusas de construção. |
| `test_spell_state_round_trip.py` | US9 | Pilha cheia, os três modificadores, dano, cemitério e partida terminada indo e voltando pelo documento. |

---

## 7. Costuras deixadas de propósito

Três, e todas registradas:

- **`unit_effective_attack` não existe.** SACRIFICIAL FIRE escreve o modificador
  de ataque, e nada nesta feature o lê — quem lê é a §7.3. Os testes afirmam o
  modificador na unidade: espécie, quantidade e duração. Research
  [D9](./research.md).
- **`apply_spell_effect` é exportado e não tem um segundo chamador.** É de
  propósito: FR-064 pede que o aplicador que o combate vai usar seja entregue
  aqui, e o teste de US6 o exercita pelos dois caminhos — direto e pela pilha —
  justamente para provar que os dois dão o mesmo resultado.
- **`resolve_stack` e `cast_spell` não são exportados pelo pacote.** Mesma razão
  que a feature 005 deu para `run_upkeep` e `end_round`: expô-los daria uma porta
  por onde executar meia rodada. Os testes deles importam do módulo.

E uma pendência que continua de fora: `consumers/base.py` roteia
`{"type": "play_card"}` para um handler que `MatchConsumer` não implementa.
Depois desta feature o pendente deixa de ser "faltam as regras" — falta só o
envelope, que é da feature de transporte.
