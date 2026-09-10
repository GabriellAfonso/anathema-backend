# Quickstart — provar que o setup funciona

**Feature**: `003-match-setup` | **Data**: 2026-09-10

Como rodar e como conferir, sem abrir o código. Detalhe de tipos está em
[data-model.md](./data-model.md); assinaturas, em
[contracts/match_setup.md](./contracts/match_setup.md).

---

## Pré-requisitos

Um Redis alcançável em `settings.REDIS_URL` — os testes de store e de
concorrência usam o banco 15, que é descartável e é limpo na entrada e na
saída de cada teste.

```sh
docker compose up -d redis        # ou um Redis local na porta 8.6 padrão
```

Dependências de desenvolvimento instaladas
(`pip install -r server/requirements-dev.txt`, ou o compose de desenvolvimento,
que passa `--build-arg INSTALL_DEV=true`).

---

## As três portas

```sh
cd server && pytest
cd server && mypy
black --check server/
```

As três precisam ficar limpas (SC-011). São as portas da constituição, não uma
escolha desta feature.

---

## Rodar só o que esta feature acrescenta

```sh
cd server
pytest apps/game/tests/test_match_setup.py \
       apps/game/tests/test_mulligan.py \
       apps/game/tests/test_setup_randomness.py \
       apps/game/tests/test_card_draw.py \
       apps/game/tests/test_starter_deck.py
```

E a regressão que não pode quebrar (US6):

```sh
pytest apps/game/tests/test_match_serialization.py \
       apps/game/tests/test_match_store.py \
       apps/game/tests/test_match_state.py \
       apps/game/tests/test_match_consumer_access.py
```

---

## Cenário 1 — uma partida nasce pronta para o mulligan (US1)

```python
from apps.game.cards import mvp_catalog, starter_deck
from apps.game.engine import MatchEntry, start_match
from apps.game.randomness import SeededRandomSource, new_random_seed

catalog = mvp_catalog()
deck = starter_deck(catalog)

match = start_match(
    MatchEntry(profile=player_one, deck=deck),
    MatchEntry(profile=player_two, deck=deck),
    catalog=catalog,
    randomness=SeededRandomSource(),
    seed=new_random_seed(),
)
```

**Esperado**:

| Pergunta | Resposta |
|---|---|
| `match.phase` | `MatchPhase.MULLIGAN` |
| `match.awaiting_mulligan_user_ids` | os dois `user_id` |
| `match.token_holder_user_id` | `None` — ninguém sorteou ainda |
| `len(player.deck), len(player.hand)` | `(36, 4)` dos dois lados |
| `player.nexus` | `20` dos dois lados |
| `player.energy_max, player.energy_current` | `(0, 0)` dos dois lados |
| identificadores de instância, os dois lados juntos | 80 valores, nenhum repetido |

**Deck recusado** (SC-006):

```python
start_match(MatchEntry(profile=player_one, deck=deck[:39]), ..., seed=seed)
# InvalidPlayerDeckError: deck of user 7 was refused: deck has 39 cards,
# expected exactly 40
```

Nenhuma partida é devolvida e nada vai ao Redis.

---

## Cenário 2 — a carta descartada não volta na reposição (US2, SC-004)

O cenário que dá nome à feature. Com uma fonte controlada:

```python
from apps.game.tests.fake_random_source import ScriptedRandomSource

source = ScriptedRandomSource()
discarded = [card.card_instance_id for card in match.players[0].hand[:2]]

record_mulligan(match, match.players[0].user_id, discarded, randomness=source)
```

**Esperado**:

- `len(hand) == 4` e `len(deck) == 36` — a contagem volta ao que era.
- Nenhum dos dois identificadores em `discarded` está na mão nova.
- Os dois estão no deck, com os **mesmos** identificadores.
- `match.next_card_instance_id` não mudou — nenhuma carta nasceu.

Repetir com 0, 1, 3 e 4 cartas fecha as cinco quantidades possíveis.

**Trocar 0 é resposta completa**, não ausência de resposta:

```python
record_mulligan(match, user_id, [], randomness=source)
match.awaiting_mulligan_user_ids     # (o outro,) — este já respondeu
```

**As quatro recusas**, cada uma deixando o estado intacto:

```python
record_mulligan(match, 99, [], randomness=source)
# NotAParticipantError: user 99 does not play match '...'

record_mulligan(match, user_id, [], randomness=source)   # segunda vez
# MulliganAlreadyTakenError: user 7 already took the mulligan ...

record_mulligan(match, user_id, [card_from_the_deck], randomness=source)
# CardNotInHandError: card instance 31 is not in the hand of user 7 ...

record_mulligan(match, user_id, [same_card, same_card], randomness=source)
# CardNotInHandError — a segunda ocorrência já não está entre as restantes
```

---

## Cenário 3 — o setup fecha com o sorteio (US4)

Respondido o segundo mulligan, sem nenhuma chamada a mais:

**Esperado**:

| Pergunta | Resposta |
|---|---|
| `match.phase` | `MatchPhase.UPKEEP` |
| `match.awaiting_mulligan_user_ids` | `()` |
| `match.token_holder_user_id` | um dos dois, sorteado |
| `match.priority_user_id` | igual ao dono do token |
| mão do dono do token | 4 cartas |
| mão do oponente | 5 cartas |
| `round_number`, `token_consumed`, `consecutive_passes` | `1`, `False`, `0` |
| `energy_max`, `energy_current` | `0` e `0` — o Upkeep é outra feature |

Com uma fonte que force cada um dos dois resultados do sorteio, o dono do token
e a mão de 5 trocam de lado juntos.

---

## Cenário 4 — o mesmo setup duas vezes (US5, SC-003)

```python
seed = RandomSeed("fixed-for-this-test")

first  = run_whole_setup(seed=seed, choices=..., arrival=("a", "b"))
second = run_whole_setup(seed=seed, choices=..., arrival=("a", "b"))

assert first == second      # dataclasses comparam campo a campo
```

Trocando **só** a semente, as duas partidas diferem — a semente é o que decide,
e não uma ordem fixa escondida.

Trocando **só** a ordem de chegada, as duas também diferem. Isso é
comportamento definido, não corrida: está em FR-042 e nas *Assumptions* da
spec.

**Sobrevivendo à recarga** (SC-009): gravar depois do primeiro mulligan,
recarregar em outra instância de store e mandar o segundo mulligan produz a
mesma partida que o setup que nunca saiu da memória. É a semente mais o
ordinal do sorteio que garantem isso.

---

## Cenário 5 — ida e volta pelo Redis com o mulligan pendente (US3, SC-007)

```python
await store.save(match)                    # phase = MULLIGAN, um já respondeu
reloaded = await store.get(match.match_id)

assert reloaded == match
```

O que precisa voltar igual: a fase, `mulligan_taken` dos dois lados, as duas
mãos, as duas ordens de deck, os identificadores, o contador de instância, a
semente e o ordinal do próximo sorteio.

---

## Cenário 6 — dois mulligans ao mesmo tempo (SC-010)

O teste que justifica o CAS. Contra o Redis de verdade:

```python
await asyncio.gather(
    store.mutate(match_id, lambda m: record_mulligan(m, 7, [], randomness=src)),
    store.mutate(match_id, lambda m: record_mulligan(m, 9, [], randomness=src)),
)

final = await store.get(match_id)
assert final.awaiting_mulligan_user_ids == ()
assert final.phase is MatchPhase.UPKEEP
```

**Esperado**: as duas respostas registradas, em alguma ordem, e o setup
terminado. Sem o compare-and-swap, uma das duas gravações sobrescreve a outra e
a partida fica esperando para sempre um jogador que já respondeu.

---

## Cenário 7 — o matchmaking continua pareando (US6)

Sem código novo do lado do cliente: dois sockets entram na fila e recebem
`match_found`, como hoje. O que mudou é o que ficou gravado.

```sh
cd server && pytest apps/game/tests/test_match_consumer_access.py
```

**Esperado**: a partida anunciada já tem deck embaralhado e mão de 4 dos dois
lados, está em `MULLIGAN`, e os dois `user_id` passam no gate de participante —
um terceiro e um socket sem usuário autenticado continuam sendo recusados.

---

## O que este quickstart **não** prova

Porque está fora de escopo, e nenhuma dessas coisas existe ainda:

- Mandar um mulligan por websocket. `record_mulligan` é a operação; o envelope
  é da feature de transporte.
- O Upkeep da §4. O setup entrega a partida posicionada e para.
- Teto de mão e reset de deck da §9. Nenhum dos dois pode ocorrer no setup.
- Timeout de um jogador que nunca responde (§13).
