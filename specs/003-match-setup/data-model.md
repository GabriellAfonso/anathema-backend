# Phase 1 — Modelo de dados: Setup de Partida

**Feature**: `003-match-setup` | **Data**: 2026-09-10 | **Spec**:
[spec.md](./spec.md) | **Decisões**: [research.md](./research.md)

Esta feature acrescenta três campos ao estado da feature 002, um valor a um
enum, e três tipos novos fora dele. Nada é redesenhado.

---

## 1. Tipos novos — `apps/game/randomness.py`

### `RandomSeed`

```python
RandomSeed = NewType("RandomSeed", str)
```

A semente de uma partida. Texto, não inteiro, por dois motivos: `random.Random`
semeia string por SHA-512, sem depender de `PYTHONHASHSEED`; e texto atravessa
o JSON sem conversão. Nasce em `new_random_seed()`, de `secrets.token_hex(16)`.

Um `NewType` pelo mesmo motivo de `CardId` e `CardInstanceId`: passar um
`match_id` onde se espera uma semente vira erro de mypy.

### `Roll`

```python
@dataclass(frozen=True, slots=True)
class Roll:
    seed: RandomSeed
    ordinal: int
```

Um sorteio identificado. Congelado: um `Roll` é um endereço no espaço de
aleatoriedade da partida, não um objeto com estado. Cunhado só por
`Match.mint_roll()`.

**Invariante**: dois sorteios da mesma partida nunca compartilham `ordinal`.
Garantido pelo contador do `Match`, do mesmo jeito que `CardInstanceId`.

### `RandomSource`

```python
class RandomSource(Protocol):
    def shuffled(self, items: Sequence[T], roll: Roll) -> list[T]: ...
    def choose(self, options: Sequence[T], roll: Roll) -> T: ...
```

A interface própria do projeto (FR-037). `Protocol` e não classe base, como
`CardCatalog`: um substituto de teste só precisa dos dois métodos.

`shuffled` devolve lista nova em vez de embaralhar no lugar — o chamador
atribui, e nenhuma função do engine altera a coleção de quem a passou.

### `SeededRandomSource`

Implementação sobre `random.Random(f"{roll.seed}:{roll.ordinal}")`, um gerador
por chamada. Sem estado próprio: a mesma instância pode ser usada por qualquer
worker, e duas chamadas com o mesmo `Roll` devolvem o mesmo resultado.

**Invariante**: `shuffled(items, roll)` é uma permutação exata de `items`
(FR-010) — nada duplicado, nada perdido.

---

## 2. Campos novos no estado — `apps/game/match/`

### `Match` (`match_state.py`)

| Campo | Tipo | Antes | Depois |
|---|---|---|---|
| `random_seed` | `RandomSeed` | — | **novo, obrigatório** |
| `next_roll_ordinal` | `int` | — | **novo**, começa em 1 |
| `token_holder_user_id` | `int \| None` | `int` obrigatório | `None` até o sorteio |
| `priority_user_id` | `int \| None` | `int` obrigatório | `None` até o sorteio |
| `phase` | `MatchPhase` | padrão `UPKEEP` | padrão `MULLIGAN` |

Métodos novos:

```python
def mint_roll(self) -> Roll                       # espelha mint_card_instance_id
@property
def awaiting_mulligan_user_ids(self) -> tuple[int, ...]   # derivado, nunca gravado
```

Removido: `Match.start` (D8). Quem cria partida é `engine.start_match`.

**Invariantes**:

- `random_seed` nasce na criação e nunca muda (FR-039).
- `token_holder_user_id` e `priority_user_id` são `None` juntos ou preenchidos
  juntos. Preenchidos, são iguais (FR-034: a prioridade nasce com o dono do
  token).
- `phase is MULLIGAN` ⟺ `awaiting_mulligan_user_ids` não é vazia ⟺
  `token_holder_user_id is None`.
- `awaiting_mulligan_user_ids` só encolhe. Caminho só de ida.

### `MatchPhase` (`match_state.py`)

```
MULLIGAN = "mulligan"      # NOVO — a espera do setup, antes da Rodada 1
UPKEEP = "upkeep"
ACTION = "action"
STACK_RESOLUTION = "stack_resolution"
COMBAT = "combat"
ROUND_END = "round_end"
```

Seis valores. O conjunto continua fechado; o docstring passa a explicar que a
§2 lista cinco porque descreve o ciclo da rodada, e o setup acontece antes da
primeira (FR-025).

### `PlayerState` (`player_state.py`)

| Campo | Tipo | Padrão |
|---|---|---|
| `mulligan_taken` | `bool` | `False` |

Um booleano por jogador, e "quem falta" derivado dele (D3). Nenhuma lista de
`user_id` pendentes é gravada.

**Invariante**: `mulligan_taken` só vai de `False` para `True`.

---

## 3. Forma gravada — `apps/game/match/documents.py`

Três campos a mais. Nenhuma chave de objeto JSON continua sendo `user_id`, em
nenhum nível — a garantia da feature 002 vale sem alteração.

```python
class PlayerDocument(TypedDict):
    ...                        # inalterado
    mulligan_taken: bool       # NOVO

class MatchDocument(TypedDict):
    ...                        # inalterado, exceto:
    token_holder_user_id: int | None    # era int
    priority_user_id: int | None        # era int
    random_seed: str                    # NOVO
    next_roll_ordinal: int              # NOVO
```

`RandomSeed` é `str` em tempo de execução, então o documento declara `str` e a
volta reembrulha em `RandomSeed`, como `CardId` e `CardInstanceId` já fazem.

**Nada de concorrência entra aqui.** A versão de escrita do CAS (D6) é um campo
do hash Redis, fora do documento: `documents.py` não sabe que concorrência
existe.

---

## 4. Forma no Redis — `apps/game/match/store.py`

A chave de partida deixa de ser uma string e passa a ser um **hash** de dois
campos:

| Campo | Conteúdo |
|---|---|
| `state` | o `MatchDocument` serializado, exatamente como hoje |
| `version` | inteiro, quantas vezes esta partida foi escrita |

TTL de 6 horas na chave, renovado a cada escrita, como hoje.

`version` serve **só** ao compare-and-swap. Não é versão de esquema — aquela
continua não existindo, como a feature 002 decidiu (D6).

Superfície da `MatchStore`:

| Método | Antes | Depois |
|---|---|---|
| `create(player1, player2)` | cria e grava | **removido** (D8) |
| `get(match_id)` | `HGET state` | igual, lendo do hash |
| `save(match)` | grava | grava, incrementando a versão |
| `mutate(match_id, change)` | — | **novo**: lê, aplica, grava se a versão bater |

`mutate` devolve o `Match` já mutado. Uma exceção levantada de dentro de
`change` propaga sem escrever nada (FR-023). Versão divergente = relê e repete;
esgotadas as tentativas, levanta citando o `match_id`.

---

## 5. Tipos novos no motor — `apps/game/engine/`

### `MatchEntry` (`match_setup.py`)

```python
@dataclass(frozen=True, slots=True)
class MatchEntry:
    profile: PlayerData
    deck: Deck
```

Um jogador chegando à partida com o deck dele. Existe para que perfil e deck
viajem juntos e não possam ser trocados de par (D8).

### `MulliganSelection`

As cartas que um jogador quer trocar: `Sequence[CardInstanceId]`, de 0 a 4
(FR-015). Não é tipo próprio — é a entrada de `record_mulligan`, validada lá.

---

## 6. Transições de estado do setup

```
                    start_match(first, second, catalog=, randomness=, seed=)
                                      │
                                      ▼
                    ┌─────────────────────────────────────┐
                    │ phase = MULLIGAN                    │
                    │ awaiting = (user_a, user_b)         │
                    │ token_holder = None                 │
                    │ priority = None                     │
                    │ deck 36 / mão 4  ×2                 │
                    │ nexus 20, energia 0/0 ×2            │
                    └─────────────────────────────────────┘
                          │                        │
        record_mulligan(a)│                        │record_mulligan(b)
         (rolls: reshuffle)                        │ (em qualquer ordem)
                          ▼                        ▼
                    ┌─────────────────────────────────────┐
                    │ phase = MULLIGAN                    │
                    │ awaiting = (o outro,)               │
                    └─────────────────────────────────────┘
                                      │
                       o segundo responde → finish_setup
                                      │
                                      ▼
                    ┌─────────────────────────────────────┐
                    │ phase = UPKEEP                      │
                    │ awaiting = ()                       │
                    │ token_holder = sorteado             │
                    │ priority = token_holder             │
                    │ mão: dono 4, oponente 5             │
                    │ round 1, token_consumed False       │
                    └─────────────────────────────────────┘
                                      │
                              Upkeep da §4 — outra feature
```

**Ordem dos sorteios** (`ordinal` crescente, na ordem em que são cunhados):

1. embaralhar o deck do primeiro jogador
2. embaralhar o deck do segundo jogador
3. reembaralhar o deck de quem respondeu o mulligan primeiro
4. reembaralhar o deck de quem respondeu depois
5. sortear o dono do token

Os ordinais 3 e 4 seguem a **ordem de chegada**, e é daí que vem a dependência
declarada em FR-042 e nas *Assumptions* da spec: trocar a ordem de chegada
troca qual jogador recebe qual fluxo.

---

## 7. Regras de validação, por operação

### `start_match`

| Regra | Origem | Recusa |
|---|---|---|
| 40 cartas, ≤3 cópias, tudo no catálogo | `deck_problems()` da feature 001 | `InvalidPlayerDeckError(user_id, problems)` |
| Os dois decks antes de qualquer mutação | FR-002, FR-005 | nada é criado nem gravado |

### `record_mulligan`

Na ordem, e toda validação antes de qualquer mutação (FR-023):

| # | Regra | Recusa |
|---|---|---|
| 1 | O `user_id` joga esta partida | `NotAParticipantError` (reusada) |
| 2 | Este jogador ainda não respondeu | `MulliganAlreadyTakenError` |
| 3 | Cada identificador da seleção está na mão, e só conta uma vez | `CardNotInHandError` |

Só então: tira da mão → compra a mesma quantidade → devolve ao deck →
reembaralha (FR-016).

### `finish_setup` (interno, disparado pelo segundo mulligan)

| Regra | Origem |
|---|---|
| Só roda com `awaiting_mulligan_user_ids` vazia | FR-027 |
| Sorteia o dono do token | FR-031 |
| O outro compra 1 | FR-032 |
| `priority = token_holder`, `phase = UPKEEP` | FR-034, FR-035 |

---

## 8. Contagens, do começo ao fim

| Momento | Deck | Mão | Total |
|---|---|---|---|
| Materializado | 40 | 0 | 40 |
| Depois de comprar 4 | 36 | 4 | 40 |
| Mulligan de *n* cartas, meio do passo (b) | 36 − n | 4 − n → 4 | 40 |
| Depois do mulligan | 36 | 4 | 40 |
| Dono do token, fim do setup | 36 | 4 | 40 |
| Oponente, fim do setup | 35 | 5 | 40 |

Os 80 identificadores de instância continuam distintos em todos os momentos
(FR-009, SC-005). O contador `next_card_instance_id` para em 81 no fim da
materialização e **não avança** no mulligan (FR-018).
