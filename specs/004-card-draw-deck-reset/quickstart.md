# Quickstart — provar que a compra funciona

**Feature**: `004-card-draw-deck-reset` | **Data**: 2026-09-10

Como rodar e como conferir, sem abrir o código. Detalhe de zonas e invariantes
está em [data-model.md](./data-model.md); assinaturas, em
[contracts/card_draw.md](./contracts/card_draw.md).

---

## Pré-requisitos

Dependências de desenvolvimento instaladas
(`pip install -r server/requirements-dev.txt`, ou o compose de desenvolvimento,
que passa `--build-arg INSTALL_DEV=true`).

**Redis não é necessário para os testes desta feature.** Nenhum deles toca
I/O — inclusive o de round-trip, que passa pela serialização direto. O Redis
continua sendo necessário para a suíte inteira, por causa dos testes de store
da feature 003.

---

## As três portas

```sh
cd server && pytest
cd server && mypy
black --check server/
```

As três precisam ficar limpas. São as portas da constituição, não uma escolha
desta feature.

---

## Rodar só o que esta feature acrescenta

```sh
cd server && pytest apps/game/tests/test_card_draw.py apps/game/tests/test_deck_reset.py -v
```

Sem Redis, sem banco, sem rede. Se algum desses testes precisar de uma fixture
de I/O, o desenho saiu do plano.

---

## Provar que o setup da 003 não quebrou

Este é o critério que separa "migrei os chamadores" de "mudei o jogo":

```sh
cd server && pytest apps/game/tests/test_match_setup.py apps/game/tests/test_mulligan.py apps/game/tests/test_setup_randomness.py
```

Os três arquivos passam **sem uma linha alterada** (SC-008). Se algum precisar
de edição, o comportamento observável do setup mudou e FR-030 falhou.

Confirmação rápida de que ninguém os tocou:

```sh
git diff --stat master -- server/apps/game/tests/test_match_setup.py \
                          server/apps/game/tests/test_mulligan.py \
                          server/apps/game/tests/test_setup_randomness.py
```

Saída vazia é o resultado esperado.

---

## Provar a porta única

```sh
cd server && grep -rn "draw_from_deck_top\|EmptyDeckError" apps/
```

Saída vazia (SC-010, FR-031). Os dois nomes deixam de existir: o movimento é
privado, e a exceção foi apagada porque a §9 passou a responder o caso dela.

Quem compra, compra por aqui:

```sh
cd server && grep -rn "draw_card\|draw_cards" apps/ --include=*.py | grep -v tests
```

Espera-se: as definições em `engine/card_draw.py`, a lista de
`engine/__init__.py`, e os três call sites do setup e do mulligan. Nada fora do
`engine/`.

---

## Conferir na mão

```sh
cd server && python -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from apps.game.engine import MAX_HAND_SIZE, draw_card, draw_cards
from apps.game.randomness import SeededRandomSource
from apps.game.tests.fake_match_state import fake_cards, fake_new_match

source = SeededRandomSource()

# Guarda de mão: 10 na mão, deck cheio, nada acontece.
match = fake_new_match()
player = match.players[0]
player.hand = fake_cards(match, list(range(1, 11)))
player.deck = fake_cards(match, [15, 22])
before = list(player.deck)
print('mão cheia devolve None:', draw_card(match, player.user_id, randomness=source) is None)
print('deck intacto:', player.deck == before)

# Reset: deck vazio, cemitério com 4, mão com 2.
match = fake_new_match()
player = match.players[0]
player.hand = fake_cards(match, [15, 22])
player.graveyard = fake_cards(match, [31, 32, 33, 34])
drawn = draw_card(match, player.user_id, randomness=source)
print('comprou depois do reset:', drawn is not None)
print('cemitério vazio:', player.graveyard == [])
print('deck com 3:', len(player.deck) == 3)

# Compra múltipla: 8 na mão, pedir 3, ficar em 10.
match = fake_new_match()
player = match.players[0]
player.hand = fake_cards(match, list(range(1, 9)))
player.deck = fake_cards(match, [15, 22, 31, 32])
got = draw_cards(match, player.user_id, 3, randomness=source)
print('entraram 2 de 3:', len(got) == 2)
print('mão no teto:', len(player.hand) == MAX_HAND_SIZE)
"
```

Sete `True`. Qualquer `False` aponta o FR que quebrou:

| Linha | FR |
|---|---|
| `mão cheia devolve None` | FR-005, FR-007 |
| `deck intacto` | FR-006 |
| `comprou depois do reset` | FR-013 |
| `cemitério vazio` | FR-011 |
| `deck com 3` | FR-010 |
| `entraram 2 de 3` | FR-026, FR-027 |
| `mão no teto` | FR-025 |

---

## Provar o determinismo do reset

```sh
cd server && python -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from apps.game.engine import reset_deck_from_graveyard
from apps.game.randomness import SeededRandomSource
from apps.game.tests.fake_match_state import fake_cards, fake_new_match

def resulting_deck():
    match = fake_new_match()
    player = match.players[0]
    player.graveyard = fake_cards(match, [15, 22, 31, 32, 33])
    reset_deck_from_graveyard(
        player, randomness=SeededRandomSource(), roll=match.mint_roll()
    )
    return [card.card_id for card in player.deck]

print('mesmo cemitério, mesmo sorteio, mesmo deck:', resulting_deck() == resulting_deck())
"
```

`True`, sempre (SC-005, FR-023). É a semente que decide, e ela é fixa em
`fake_match_state.py` justamente para isto.

---

## Checklist de aceitação

| Critério | Como conferir |
|---|---|
| SC-001 a SC-003, SC-007 | `pytest apps/game/tests/test_card_draw.py` |
| SC-004 a SC-006 | `pytest apps/game/tests/test_deck_reset.py` |
| SC-008 | os três arquivos do setup passam sem diff |
| SC-009 | o teste de round-trip em `test_deck_reset.py` |
| SC-010 | `grep` por `draw_from_deck_top` vazio |
| SC-011 | o teste de deck e cemitério vazios em `test_card_draw.py` |
