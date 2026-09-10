# Quickstart — Ciclo de Rodada

**Feature**: `005-round-cycle` | **Data**: 2026-09-10

Como rodar a suíte e como provar, à mão, que uma partida gira de ponta a ponta.
Detalhe de assinatura está em [contracts/](./contracts/); detalhe de campo está
em [data-model.md](./data-model.md).

---

## 1. Pré-requisitos

O container de desenvolvimento, como nas features anteriores:

```bash
docker compose up -d
```

Nada novo é instalado. Esta feature não acrescenta dependência, não cria
migration e não toca em Redis — todo o teste dela é síncrono e sem I/O.

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
cd server && pytest apps/game/tests/test_upkeep.py \
                    apps/game/tests/test_play_unit.py \
                    apps/game/tests/test_action_phase.py \
                    apps/game/tests/test_round_end.py \
                    apps/game/tests/test_round_cycle.py \
                    apps/game/tests/test_player_action.py
```

O que **não** pode ter mudado (US8, SC-012):

```bash
cd server && pytest apps/game/tests/test_match_setup.py \
                    apps/game/tests/test_mulligan.py \
                    apps/game/tests/test_setup_randomness.py \
                    apps/game/tests/test_card_draw.py \
                    apps/game/tests/test_deck_reset.py \
                    apps/game/tests/test_match_serialization.py
```

Nenhum desses arquivos foi alterado. Se algum deles falhar, a feature quebrou
uma anterior.

---

## 3. Uma partida girando, no shell

```bash
cd server && python manage.py shell
```

```python
from apps.game.engine import (
    PassAction,
    PlayUnitAction,
    begin_round_cycle,
    submit_action,
)
from apps.game.cards import mvp_catalog
from apps.game.randomness import SeededRandomSource
from apps.game.tests.fake_setup import fake_match_ready_for_upkeep

catalog = mvp_catalog()
source = SeededRandomSource()

# O setup entrega a partida parada antes do Upkeep da Rodada 1.
match = fake_match_ready_for_upkeep()
match.phase, match.round_number
# (<MatchPhase.UPKEEP: 'upkeep'>, 1)

# O primeiro empurrão. (US1, SC-001)
begin_round_cycle(match, randomness=source)
match.phase, match.round_number
# (<MatchPhase.ACTION: 'action'>, 1)
[(p.energy_max, p.energy_current, len(p.hand)) for p in match.players]
# rodada 1 com 1 de energia dos dois lados, e uma carta a mais em cada mão

# Quem tem a vez é o dono do token.
match.priority_user_id == match.token_holder_user_id
# True
```

### O passe que vira a rodada inteira (US6, SC-003)

```python
first = match.priority_user_id
submit_action(match, PassAction(actor_user_id=first),
              catalog=catalog, randomness=source)
match.consecutive_passes, match.phase
# (1, <MatchPhase.ACTION: 'action'>)

second = match.priority_user_id
token_before = match.token_holder_user_id

submit_action(match, PassAction(actor_user_id=second),
              catalog=catalog, randomness=source)

# Uma chamada só, e a partida já está na rodada 2 esperando ação.
match.round_number, match.phase, match.consecutive_passes
# (2, <MatchPhase.ACTION: 'action'>, 0)
match.token_holder_user_id != token_before
# True
[p.energy_current for p in match.players]
# [2, 2]
```

Em nenhum momento a partida ficou em `ROUND_END` ou `UPKEEP` do lado de fora da
chamada. Esse é o ponto inteiro da cascata.

### Jogar uma unidade (US3)

Na rodada 1 ninguém tem energia para nada: a unidade mais barata do catálogo do
MVP custa mais de 1. Passe rodadas até aparecer uma pagável — com a semente
fixa do `fake_setup`, isso acontece na rodada 3.

```python
from apps.game.cards import CardType

def playable(actor):
    for card in actor.hand:
        template = catalog.card(card.card_id)
        if (
            template.card_type is CardType.UNIT
            and template.energy <= actor.energy_current
        ):
            return card
    return None

def advance(match):
    submit_action(match, PassAction(actor_user_id=match.priority_user_id),
                  catalog=catalog, randomness=source)

while playable(match.player(match.priority_user_id)) is None:
    advance(match)

actor = match.player(match.priority_user_id)
unit_in_hand = playable(actor)
energy_before = actor.energy_current
cost = catalog.card(unit_in_hand.card_id).energy

submit_action(
    match,
    PlayUnitAction(actor_user_id=actor.user_id,
                   card_instance_id=unit_in_hand.card_instance_id),
    catalog=catalog,
    randomness=source,
)

actor.energy_current == energy_before - cost
# True
actor.bank[-1].card.card_instance_id == unit_in_hand.card_instance_id
# True — mesma identidade, a carta só trocou de zona
actor.bank[-1].damage_taken, actor.bank[-1].modifiers
# (0, []) — entra pronta, sem doença de invocação
match.consecutive_passes
# 0 — jogar unidade quebra a sequência de passes
```

### Uma recusa que não muda nada (US7, SC-007)

```python
from apps.game.engine import NotYourPriorityError
from apps.game.match import to_match_document

waiting = match.opponent_of(match.priority_user_id).user_id
before = to_match_document(match)

try:
    submit_action(match, PassAction(actor_user_id=waiting),
                  catalog=catalog, randomness=source)
except NotYourPriorityError as refused:
    print(refused)                      # cita quem tem a prioridade
    print(refused.priority_user_id)     # e como atributo, não só no texto

to_match_document(match) == before
# True — campo a campo, contadores inclusive
```

### Dez rodadas seguidas (SC-002, SC-005)

```python
start = match.round_number
for _ in range(20):   # 2 passes por rodada
    advance(match)

start, match.round_number, match.phase
# (3, 13, <MatchPhase.ACTION: 'action'>)
[p.energy_max for p in match.players]
# [10, 10] — o teto da §12 se mantém, não vira 11
match.stack
# [] — nada nesta feature empilha
```

---

## 4. O que cada arquivo de teste prova

| Arquivo | Histórias | O caso que justifica o arquivo |
|---|---|---|
| `test_upkeep.py` | US2 | A rodada 11 continua com 10 de energia; um jogador de mão cheia não trava o Upkeep; os dois resetando o deck no mesmo Upkeep dão o mesmo resultado duas vezes |
| `test_play_unit.py` | US3 | Energia exatamente igual ao custo é aceita; banco em 5 é aceito e em 6 é recusado; o feitiço na ação errada é recusado |
| `test_action_phase.py` | US4 | Passar–jogar–passar–passar fecha a rodada só no último passe |
| `test_round_end.py` | US5 | O temporário some, o permanente fica, e o dano não é tocado |
| `test_round_cycle.py` | US1, US6, US8 | O primeiro empurrão; um passe entrega a rodada seguinte inteira; dez rodadas sem travar; round-trip pelo Redis de uma partida com banco e modificadores |
| `test_player_action.py` | US7 | As guardas comuns na ordem — sem prioridade **e** sem energia dá a recusa de prioridade; e a foto do estado idêntica em cada recusa |

O auxiliar `tests/match_snapshot.py` é o que torna "idêntico campo a campo"
literal: ele fotografa a partida com `to_match_document`, o mesmo caminho que a
feature 002 usa para provar o round-trip, então nenhum campo fica de fora — os
dois contadores inclusive.

---

## 5. Costuras deixadas de propósito

Duas coisas nesta feature existem sem consumidor, e é assim que devem estar até
a próxima:

1. **O ramo `STACK_RESOLUTION`.** A saída da §5 decide por ele quando a pilha
   não está vazia, e a cascata não sabe atravessá-lo. Nada nesta feature enche a
   pilha, então ele é inalcançável. `test_round_cycle.py` tem os dois testes que
   o mantêm honesto: um põe um feitiço à mão e afirma que a partida chega a
   `STACK_RESOLUTION`, e outro afirma que a pilha continua vazia ao longo de dez
   rodadas. A razão longa está em [research.md](./research.md) D9.

2. **`token_consumed` voltando a `False` todo Upkeep.** Nada nesta feature o põe
   em `True` — quem o consome é o ataque da §7. O campo é reposto assim mesmo
   porque a §4 manda, e porque a feature de combate encontra o campo já correto.

E uma que continua pendente, como os planos das três features anteriores
registraram: `consumers/base.py:155` roteia `{"type": "play_card"}` para um
handler que `MatchConsumer` não implementa. Esta feature entrega a regra que esse
handler vai chamar. Ligar os dois é a feature de transporte.
