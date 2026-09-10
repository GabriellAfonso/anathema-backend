# Quickstart — validar o estado de partida

**Feature**: Estado de Partida (`002-match-state`)
**Data**: 2026-09-09

Como provar que a feature está de pé. Detalhe de campo em
[data-model.md](./data-model.md), assinaturas em
[contracts/match_state.md](./contracts/match_state.md).

## Pré-requisitos

- Ambiente de desenvolvimento instalado:
  `pip install -r server/requirements-dev.txt` (traz `requirements.txt` junto,
  mais pytest, mypy e black).
- **Redis de pé** para `test_match_store.py`, que roda contra um Redis real no
  banco 15 — o resto da suíte desta feature é memória pura e não precisa de
  nada. `docker compose up redis` resolve.
- Nenhuma dependência nova, nenhuma migration, nenhuma variável de ambiente
  nova.

Todos os comandos rodam de `server/`:

```bash
cd server
```

## Portas de qualidade

As três da constituição, na ordem em que falham mais barato:

```bash
mypy                       # strict + warn_unreachable, sem relaxação nova
pytest                     # a suíte inteira
black --check .            # limpo é a condição; sem --check ele reescreve
```

Só desta feature:

```bash
pytest apps/game/tests/test_match_state.py \
       apps/game/tests/test_card_instance_identity.py \
       apps/game/tests/test_bank_unit.py \
       apps/game/tests/test_spell_stack.py \
       apps/game/tests/test_match_serialization.py \
       apps/game/tests/test_player_view.py \
       apps/game/tests/test_match_store.py \
       apps/game/tests/test_match_consumer_access.py
```

## Cenários de validação

Os cinco que a spec lista em *Pronto quando*. Cada um mapeia para um arquivo de
teste; o que está abaixo é o roteiro de conferência manual, para quando a
suíte passar e você quiser ver funcionando.

Abra um shell com o projeto no path:

```bash
python -c "import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','core.settings'); django.setup()" && python
```

Ou, mais simples, rode os trechos abaixo dentro de um teste temporário.

---

### 1. Montar um estado completo

```python
from apps.game.match import Match
from apps.game.tests.fake_player_data import fake_player_data

match = Match.start(fake_player_data(7, "one"), fake_player_data(9, "two"))

match.round_number          # 1
match.phase                 # MatchPhase.UPKEEP
match.token_holder_user_id  # 7
match.priority_user_id      # 7
match.token_consumed        # False
match.consecutive_passes    # 0
match.next_card_instance_id # 1
match.player(7).nexus       # 20
match.player(7).hand        # []
```

**Esperado**: todos os campos da §2 presentes. Partida válida, não jogável —
as zonas estão vazias porque o setup da §3 é da próxima feature.

Estado mais rico, com as zonas preenchidas, sai pronto de
`apps/game/tests/fake_match_state.py`:

```python
from apps.game.tests.fake_match_state import fake_match_in_progress

match = fake_match_in_progress()   # zonas cheias, dano, modificadores, pilha
```

**Cobre**: US1, FR-001 a FR-008, FR-040.

---

### 2. Distinguir duas cópias da mesma carta

```python
from apps.game.cards import CardId
from apps.game.match import MatchCard

first  = MatchCard(match.mint_card_instance_id(), CardId(15))
second = MatchCard(match.mint_card_instance_id(), CardId(15))

first.card_instance_id != second.card_instance_id   # True
first.card_id == second.card_id                     # True — mesmo molde
match.next_card_instance_id                         # 3
```

E o identificador atravessando zonas:

```python
from apps.game.match import BankUnit

player = match.player(7)
player.hand.append(first)

player.bank.append(BankUnit(card=player.hand.pop(), damage_taken=0, modifiers=[]))
player.bank[0].card.card_instance_id    # o mesmo número de antes

player.graveyard.append(player.bank.pop().card)
player.graveyard[0].card_instance_id    # ainda o mesmo
```

**Esperado**: números diferentes para cópias do mesmo `card_id`; o mesmo número
nas cinco zonas.

**Cobre**: US2, FR-009 a FR-015.

---

### 3. Ida e volta sem perda

```python
import json
from apps.game.match import to_match_document, match_from_document
from apps.game.tests.fake_match_state import fake_match_in_progress

match = fake_match_in_progress()

document = to_match_document(match)
rebuilt  = match_from_document(json.loads(json.dumps(document)))

to_match_document(rebuilt) == document   # True
```

E a garantia de forma, que é inspeção e não comportamento:

```python
raw = json.loads(json.dumps(to_match_document(match)))

isinstance(raw["players"], list)                  # True — lista, não mapa
[p["profile"]["user_id"] for p in raw["players"]] # [7, 9] — inteiros, valores
"7" in raw                                        # False, em nenhum nível
```

**Esperado**: documento idêntico depois da volta. Nenhuma chave de objeto JSON
é um `user_id`, então não existe conversão de chave a lembrar — o
`{int(k): v for k, v in ...}` do modelo antigo não tem equivalente aqui.

**Cobre**: US3, FR-028 a FR-031.

---

### 4. Perguntar se um alvo ainda está no banco

```python
from apps.game.match import CardInstanceId

match.bank_unit(CardInstanceId(3))     # BankUnit — está em campo
match.bank_unit(CardInstanceId(999))   # None — fizzla
```

Simulando a §6 inteira:

```python
entry  = match.stack[-1]                # topo da pilha: LIFO
target = match.bank_unit(entry.target_card_instance_id)

if target is None:
    ...  # fizzle
```

Depois de a unidade morrer:

```python
player = match.player(7)
player.graveyard.append(player.bank.pop(0).card)

match.bank_unit(CardInstanceId(1))     # None — saiu do banco
```

**Esperado**: positiva enquanto está em campo, negativa depois de sair. `None`
não é erro: é a resposta que autoriza o fizzle.

**Cobre**: US5, FR-023 a FR-027.

---

### 5. A visão de cada jogador

```python
from apps.game.match import build_player_view

view = build_player_view(match, 7)

view["you"]["hand"]              # a mão do 7, com card_instance_id
view["opponent"]["hand_size"]    # só a contagem
view["you"]["deck_size"]         # só a contagem
"hand" in view["opponent"]       # False — o campo não existe no tipo
"deck" in view["you"]            # False
```

A prova mais forte é negativa. Recolha todos os `card_instance_id` que
aparecem na visão e confira que nenhum vem de um deck ou da mão do oponente:

```python
import json

leaked = json.dumps(view)
opponent_hand_ids = [c.card_instance_id for c in match.player(9).hand]
deck_ids = [
    c.card_instance_id
    for player in match.players
    for c in player.deck
]

all(str(i) not in leaked for i in opponent_hand_ids + deck_ids)   # True
```

E a recusa:

```python
build_player_view(match, 99)   # NotAParticipantError, citando 99
```

**Esperado**: a mão do oponente e os dois decks não aparecem, nem em conteúdo
nem em ordem. Um `user_id` de fora é recusado com o valor na mensagem.

**Cobre**: US6, FR-032 a FR-037.

---

### 6. Nada quebrou

O gate de participante, que é o único consumidor real do `Match` hoje:

```python
match.has_player(7)      # True
match.has_player(99)     # False
match.has_player(None)   # False — socket sem usuário autenticado
```

E o caminho inteiro, do matchmaking ao Redis e de volta, é o que
`test_match_store.py` cobre:

```bash
pytest apps/game/tests/test_match_store.py -v
```

**Esperado**: partida criada pelo pareamento, gravada, relida em outro
processo, com os dois jogadores passando no gate e o terceiro recusado. Apelido,
ícone e nível continuam lá depois da volta.

**Cobre**: US7, FR-038 a FR-041, FR-043.

---

## Conferir o que foi removido

```bash
test ! -f apps/game/match/models.py && echo "models.py apagado"
grep -rn "play_card" apps/game/match/ apps/game/tests/   # sem resultado
grep -rn "CardId = str" apps/                            # sem resultado
grep -rn "match.models" apps/                            # sem resultado
```

**Esperado**: nenhuma ocorrência. `play_card` era regra no lugar errado
(FR-042), e o `CardId = str` fecha a pendência do `Backend/TODO.md` no vault.

O roteamento de `{"type": "play_card"}` em `consumers/base.py` **continua**
existindo e apontando para um handler que ninguém implementa. Isso é anterior
a esta feature e continua fora de escopo — jogar carta é regra.

## Se algo falhar

| Sintoma | Provável causa |
|---|---|
| `pytest` reclama de conexão recusada só em `test_match_store.py` | Redis não está de pé. `docker compose up redis`. |
| `mypy` acusa `Returning Any` na volta do documento | O `cast(MatchDocument, ...)` em `store.py` sumiu ou aponta para o tipo errado. |
| Um `match` sobre `UnitModifier` acusa braço faltando | União nova sem tratamento. É o comportamento desejado — trate o braço, não silencie. |
| Ida e volta falha só com modificadores | Discriminante `modifier_kind` ausente ou grafado diferente na ida e na volta. |
| Visão do oponente com a mão dentro | Alguém usou `PlayerSideView` para os dois lados. `OpponentSideView` é um tipo separado de propósito. |
