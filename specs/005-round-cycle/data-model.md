# Data Model — Ciclo de Rodada

**Feature**: `005-round-cycle` | **Data**: 2026-09-10

Fase 1. Esta feature **não cria estado de partida**. Ela cria um tipo de
entrada — a ação — e transforma campos que a feature 002 já modelou.

A consequência prática: `match/documents.py` e `match/serialization.py` não são
tocados, não há migration, e a garantia de round-trip da feature 002 (FR-056)
vale por construção, não por teste novo de serialização.

---

## 1. Entrada: a ação de jogador

Vive em `apps/game/engine/player_action.py`. Não é estado de partida, não vai ao
Redis, não é serializada por esta feature. É um valor que o transporte constrói e
entrega ao motor.

| Tipo | Campos | `action_kind` | `allowed_phases` |
|---|---|---|---|
| `PlayUnitAction` | `actor_user_id: int`, `card_instance_id: CardInstanceId` | `PLAY_UNIT` | `{ACTION}` |
| `PassAction` | `actor_user_id: int` | `PASS` | `{ACTION}` |

`PlayerAction = PlayUnitAction | PassAction` — união fechada. `action_kind` e
`allowed_phases` são `ClassVar`: pertencem à mecânica, não à instância, então
nenhum call site constrói um passe que se diz legal no Upkeep. Mesma disciplina
de `ModifierKind` em `match/modifiers.py`.

Os dois braços são `frozen=True, slots=True`. Uma ação é um valor; ninguém a
altera no meio do caminho.

**Regras de validação** (as três guardas comuns, nesta ordem — FR-044):

1. `match.has_player(action.actor_user_id)` — via `match.player(...)`, que já
   recusa citando o `user_id`.
2. `match.priority_user_id == action.actor_user_id`.
3. `match.phase in action.allowed_phases`.

Só depois disso a regra específica do braço é verificada.

---

## 2. Campos de partida que esta feature transforma

Todos já existem em `apps/game/match/`. Nenhum campo novo, nenhum tipo alterado.

### `Match`

| Campo | Tipo | Quem escreve | Transição |
|---|---|---|---|
| `phase` | `MatchPhase` | Upkeep, saída da §5, Fim de Rodada | `UPKEEP → ACTION` (Upkeep); `ACTION → ROUND_END` (saída, pilha vazia); `ACTION → STACK_RESOLUTION` (saída, pilha não vazia — sem consumidor nesta feature); `ROUND_END → UPKEEP` (Fim de Rodada) |
| `priority_user_id` | `int \| None` | Upkeep, toda ação aceita | Upkeep põe no dono do token; toda ação passa ao oponente do autor |
| `consecutive_passes` | `int` | Upkeep, as duas ações | Upkeep zera; `PassAction` soma 1; `PlayUnitAction` zera |
| `token_holder_user_id` | `int \| None` | Fim de Rodada | Passa ao outro jogador, uma vez por rodada |
| `token_consumed` | `bool` | Upkeep | Volta a `False` toda rodada. Nada nesta feature o põe em `True` |
| `round_number` | `int` | Fim de Rodada | `+1`, sem teto |
| `stack` | `list[StackEntry]` | ninguém | **Lida** pela saída da §5. Nenhum caminho desta feature escreve nela (FR-054) |
| `next_card_instance_id` | `int` | ninguém | Nenhum caminho desta feature cunha carta (FR-050) |
| `next_roll_ordinal` | `int` | indiretamente, pela compra | Avança só quando o Upkeep dispara um reset de deck, e a decisão é da §9 |

### `PlayerState`

| Campo | Tipo | Quem escreve | Transição |
|---|---|---|---|
| `energy_max` | `int` | Upkeep | `min(energy_max + 1, 10)` |
| `energy_current` | `int` | Upkeep, `play_unit` | Upkeep: `= energy_max` (recarga total, sem carryover). `play_unit`: `-= custo da carta` |
| `hand` | `list[MatchCard]` | Upkeep (via compra), `play_unit` | Upkeep acrescenta a carta comprada; `play_unit` remove a jogada |
| `bank` | `list[BankUnit]` | `play_unit` | Acrescenta `BankUnit(card=card)` no fim. Nada nesta feature remove |
| `deck` | `list[MatchCard]` | indiretamente, pela compra | Só pelo caminho da §9, que esta feature não reescreve |
| `graveyard` | `list[MatchCard]` | indiretamente, pela compra | Só esvaziado por um reset de deck da §9. Nenhum caminho desta feature põe carta nele (FR-055) |
| `nexus` | `int` | ninguém | **Intocado** (FR-053). Sem combate e sem feitiço, a §10 é inalcançável |
| `mulligan_taken` | `bool` | ninguém | Do setup |

### `BankUnit`

| Campo | Tipo | Quem escreve | Transição |
|---|---|---|---|
| `card` | `MatchCard` | `play_unit` | A mesma carta que estava na mão — mesma identidade (FR-023) |
| `damage_taken` | `int` | ninguém | Nasce em 0 e **não é tocado pelo Fim de Rodada** (FR-033). Dano não é modificador e não expira |
| `modifiers` | `list[UnitModifier]` | Fim de Rodada | Nasce vazio (FR-022). O Fim de Rodada remove os de `UNTIL_END_OF_ROUND` e deixa os `PERMANENT` |

---

## 3. A máquina de fases, como esta feature a percorre

```text
        (setup, feature 003)
                 │
                 ▼
            [ UPKEEP ] ◄──────────────┐
                 │                    │
      begin_round_cycle /             │  end_round
      cascata de submit_action        │  (§8: varre, troca token, rodada +1)
                 │                    │
                 ▼                    │
            [ ACTION ] ───────────► [ ROUND_END ]
              ▲    │      2 passes,
              │    │      pilha vazia
              │    │
              └────┘      2 passes,      ┌──────────────────────┐
        toda ação aceita  pilha cheia    │ [ STACK_RESOLUTION ] │
        que não fecha ────────────────►  │  sem consumidor      │
        a rodada                         │  nesta feature (D9)  │
                                         └──────────────────────┘
```

**Fases de passagem**: `UPKEEP` e `ROUND_END` existem no modelo e nenhuma ação
termina com a partida numa delas (FR-040, FR-041). O laço de `_settle` atravessa
as duas.

**Terminação**: `ROUND_END` sempre leva a `UPKEEP`, e `UPKEEP` sempre leva a
`ACTION`. Nenhuma fase automática leva a outra fase automática que volte à
primeira, então o laço roda no máximo duas voltas.

**`COMBAT` e `MULLIGAN`** não são alcançáveis por nenhum caminho desta feature.

---

## 4. Invariantes

Verdadeiros antes e depois de toda porta pública desta feature.

**I1 — Fase estabilizada.** Quando `begin_round_cycle` ou `submit_action`
retorna, `match.phase is MatchPhase.ACTION`. (FR-040)

**I2 — Prioridade existente.** `match.priority_user_id` é o `user_id` de um dos
dois jogadores, nunca `None` e nunca um terceiro. (FR-014)

**I3 — Passes limitados.** `0 <= match.consecutive_passes < 2` depois de toda
porta. O valor 2 existe só dentro da chamada, entre a ação e a saída da fase, e
o Upkeep o zera antes de a partida voltar a esperar. (FR-010, FR-016)

**I4 — Recusa é identidade.** Se uma porta levanta, `to_match_document(match)` é
igual ao que era antes da chamada — contadores inclusive. (FR-048, FR-050)

**I5 — Energia dentro dos limites.** `0 <= energy_current <= energy_max <= 10`
para os dois jogadores. A borda superior é o teto da §12; a inferior é a guarda
de `play_unit`, que só desconta depois de provar `energy_current >= custo`.
(FR-005, FR-019)

**I6 — Banco dentro do limite.** `len(player.bank) <= 6` para os dois jogadores.
`play_unit` é o único caminho que acrescenta, e só depois de provar
`len(bank) < 6`. (FR-020)

**I7 — Nexus intocado.** `player.nexus` é o mesmo antes e depois de qualquer
sequência de chamadas desta feature. (FR-053)

**I8 — Conservação de cartas.** A soma `len(deck) + len(hand) + len(bank) +
len(graveyard)` de um jogador é constante ao longo de toda esta feature: nada
sai do jogo, e o que entra no banco saiu da mão. A compra da §9 move entre deck e
mão; o reset move entre cemitério e deck. Nenhum caminho desta feature cria nem
destrói carta. (FR-023, FR-050, FR-055)

**I9 — Pilha vazia.** `match.stack == []` em toda partida que só passou por esta
feature. É o que torna I1 verdadeiro apesar do braço `STACK_RESOLUTION` existir.
(FR-054)

**I10 — Round-trip.** `match_from_document(to_match_document(match))` é igual a
`match`, campo a campo, para qualquer estado produzido aqui. Vale por construção,
porque nenhum campo novo foi criado. (FR-056)

---

## 5. Constantes

Cada uma mora junto da regra que a aplica (D11), como `MAX_HAND_SIZE` mora em
`card_draw.py` e `STARTING_NEXUS` em `player_state.py`.

| Constante | Valor | Módulo | Origem |
|---|---|---|---|
| `MAX_ENERGY` | 10 | `engine/upkeep.py` | §12, "Energia máxima" |
| `ENERGY_PER_ROUND` | 1 | `engine/upkeep.py` | §12, "Incremento de energia" |
| `MAX_BANK_SIZE` | 6 | `engine/play_unit.py` | §12, "Limite de banco" |
| `CONSECUTIVE_PASSES_TO_EXIT` | 2 | `engine/round_cycle.py` | §5, "Saída da fase" |

`MAX_HAND_SIZE` (10) **não** é redeclarada: o Upkeep chama a compra da §9, e a
guarda de mão é dela (FR-007).

---

## 6. O que esta feature deliberadamente não modela

- **Alvo, pilha e resolução LIFO.** `StackEntry` já existe (feature 002) e
  continua sem quem o crie.
- **Pareamento de bloqueadores.** A §7.2 precisa de estado que ninguém modelou
  ainda; a fase `COMBAT` existe no enum e continua sem corpo.
- **Vida efetiva de unidade.** O molde mais os modificadores de vida menos o
  dano. Nenhum caminho desta feature precisa desse número — ele entra com o
  combate.
- **Ataque efetivo.** Mesma razão.
- **Relógio de jogada.** Fora de escopo por decisão da spec; §13 do Fluxo de
  Partida o mantém em aberto.
