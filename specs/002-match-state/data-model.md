# Fase 1 — Modelo de dados

**Feature**: Estado de Partida (`002-match-state`)
**Data**: 2026-09-09

Nada aqui vai para banco relacional. "Modelo" quer dizer os tipos em memória
que `apps.game.match` define, as invariantes que eles garantem, e a forma JSON
que o Redis guarda.

Duas camadas, e a separação é deliberada:

- **Tipos vivos** — dataclasses e enums. É o que o motor vai manipular.
- **Documentos** — `TypedDict` compatíveis com JSON. É o que o Redis guarda.
  Só `serialization.py` converte entre as duas.

---

## Tipos vivos

### `CardInstanceId` — `cards_in_play.py`

`NewType("CardInstanceId", int)`. Identidade de uma cópia concreta de carta
dentro de uma partida.

| Invariante | Origem |
|---|---|
| Único dentro da partida, nos dois jogadores e nas cinco zonas | FR-009 |
| Distinto de `card_id` e de `user_id`, e o mypy recusa a troca | FR-009, princípio II |
| Opaco: não codifica `card_id`, dono, zona nem ordinal de cópia | FR-011 |
| Nasce com a carta e não muda ao trocar de zona | FR-012 |

Cunhado só por `Match.mint_card_instance_id()`. Nenhum outro ponto do código
constrói um `CardInstanceId` do nada.

### `MatchCard` — `cards_in_play.py`

`@dataclass(slots=True)`. Uma carta que pertence a uma partida. É o que vive no
deck, na mão, no cemitério e dentro de uma entrada da pilha.

| Campo | Tipo | Notas |
|---|---|---|
| `card_instance_id` | `CardInstanceId` | A identidade |
| `card_id` | `CardId` | Aponta para o molde no catálogo |

Dois campos e mais nada. Nome, custo, ataque e vida ficam no catálogo (FR-017);
dano e modificadores só existem em campo (FR-018), e um `MatchCard` não tem
onde guardá-los.

### `BankUnit` — `cards_in_play.py`

`@dataclass(slots=True)`. Uma unidade em campo. Existe só enquanto está no
banco.

| Campo | Tipo | Notas |
|---|---|---|
| `card` | `MatchCard` | Composição, não cópia dos dois campos (research D2) |
| `damage_taken` | `int` | Dano acumulado, nunca vida atual (research D4) |
| `modifiers` | `list[UnitModifier]` | Ordem sem significado; a soma é comutativa |

Mudanças de zona, para referência de quem implementar o motor depois:

```python
bank.append(BankUnit(card=hand.pop(index), damage_taken=0, modifiers=[]))
graveyard.append(dead_unit.card)   # mesmo objeto, mesmo identificador
```

| Invariante | Origem |
|---|---|
| `card` é o mesmo objeto que estava na mão — identidade preservada por construção | FR-012 |
| Nada aqui altera o molde do catálogo | FR-019 |
| Ataque e vida efetivos não são campos; derivá-los é do motor | FR-017 |

### `ModifierKind` — `modifiers.py`

`StrEnum` fechado. Existe como discriminante da união no JSON (research D5).

| Membro | Valor |
|---|---|
| `ATTACK` | `"attack"` |
| `HEALTH` | `"health"` |
| `DAMAGE_IMMUNITY` | `"damage_immunity"` |

### `AttackModifier`, `HealthModifier`, `DamageImmunity` — `modifiers.py`

`@dataclass(frozen=True, slots=True)`. Congelados: um modificador é um valor.
Aplicar é acrescentar à lista, expirar é remover — nunca editar no lugar.

| Tipo | Campos | Produzido por (exemplo) |
|---|---|---|
| `AttackModifier` | `amount: int`, `duration: EffectDuration` | `SacrificeNexusForAttack` |
| `HealthModifier` | `amount: int`, `duration: EffectDuration` | `BuffUnitHealth` |
| `DamageImmunity` | `duration: EffectDuration` | `PreventUnitDamage` |

`amount` pode ser negativo — feitiço que reduz ataque é o mesmo tipo com sinal
trocado. `DamageImmunity` **não tem** `amount`: a mecânica é tudo ou nada, e um
campo anulável deixaria existir estado sem significado (FR-020). É o mesmo
argumento que `effects.py` usa para `requires_target` ser derivado.

`duration` reaproveita `EffectDuration` de `apps.game.cards.effects` —
`PERMANENT` e `UNTIL_END_OF_ROUND`, os dois que a §8 precisa. Enum paralelo
seria duplicação com risco de divergir.

```python
UnitModifier = AttackModifier | HealthModifier | DamageImmunity
```

União fechada: um `match` que esqueça um braço é erro de mypy (FR-020).

**O que não vira modificador**: dano direto (vai para `damage_taken`) e cura de
Nexus (não toca unidade). FR-022 proíbe criar tipo só para constar.

### `StackEntry` — `spell_stack.py`

`@dataclass(slots=True)`. Um feitiço lançado e ainda não resolvido.

| Campo | Tipo | Notas |
|---|---|---|
| `card` | `MatchCard` | A cópia do feitiço; vai para o cemitério ao resolver |
| `caster_user_id` | `int` | Quem lançou |
| `target_card_instance_id` | `CardInstanceId \| None` | `None` é ausência explícita de alvo (FR-024) |

| Invariante | Origem |
|---|---|
| O alvo é um identificador, nunca uma referência a `BankUnit` | FR-025 |
| `None` significa "este feitiço não mira nada", nunca "o alvo sumiu" | FR-024 |

A distinção do FR-024 é estrutural: um feitiço sem alvo tem
`target_card_instance_id is None` para sempre; um feitiço cujo alvo sumiu
continua com o número, e é `Match.bank_unit()` que devolve `None`. Duas
perguntas diferentes, dois lugares diferentes.

### `MatchPhase` — `match_state.py`

`StrEnum` fechado. As cinco fases da §2, sem sexto valor possível (FR-002).

| Membro | Valor | Fluxo de Partida |
|---|---|---|
| `UPKEEP` | `"upkeep"` | §4 |
| `ACTION` | `"action"` | §5 — Fase de Ação |
| `STACK_RESOLUTION` | `"stack_resolution"` | §6 — Resolução de Pilha |
| `COMBAT` | `"combat"` | §7 — o estado do pareamento entra na feature de combate |
| `ROUND_END` | `"round_end"` | §8 — Fim de Rodada |

### `PlayerState` — `player_state.py`

`@dataclass(slots=True)`. Um lado do tabuleiro.

| Campo | Tipo | Inicial | Fluxo de Partida |
|---|---|---|---|
| `profile` | `PlayerData` | do matchmaking | dados públicos: `user_id`, apelido, ícone, nível |
| `nexus` | `int` | 20 | §12 |
| `deck` | `list[MatchCard]` | `[]` | ordem = topo primeiro |
| `hand` | `list[MatchCard]` | `[]` | teto de 10, aplicado na compra (§9) |
| `bank` | `list[BankUnit]` | `[]` | teto de 6 (§12) |
| `graveyard` | `list[MatchCard]` | `[]` | alimenta o reset de deck (§9) |
| `energy_max` | `int` | 0 | §4 |
| `energy_current` | `int` | 0 | §4 |

`user_id` é propriedade derivada, `self.profile["user_id"]`, não campo próprio.
Duplicá-lo criaria duas fontes que podem divergir; a propriedade dá o nome
curto ao caminho quente sem o risco.

Os tetos de mão e banco **não** são validados aqui. Aplicá-los é regra (§5, §9),
e regra está fora de escopo.

### `Match` — `match_state.py`

`@dataclass(slots=True)`. O agregado. Endereçado por `match_id`.

| Campo | Tipo | Inicial | Fluxo de Partida |
|---|---|---|---|
| `match_id` | `str` | `uuid4()` | — |
| `players` | `tuple[PlayerState, PlayerState]` | os dois do par | §2 — aridade no tipo |
| `round_number` | `int` | 1 | §2 `rodadaAtual` |
| `token_holder_user_id` | `int` | primeiro do par | §2 `donoDoToken` |
| `token_consumed` | `bool` | `False` | §2, reset no Upkeep |
| `priority_user_id` | `int` | igual ao dono do token | §2 `prioridade` |
| `phase` | `MatchPhase` | `UPKEEP` | §2 `faseAtual` |
| `stack` | `list[StackEntry]` | `[]` | §2 — fim da lista = topo da pilha |
| `consecutive_passes` | `int` | 0 | §2 `passesConsecutivos` |
| `next_card_instance_id` | `int` | 1 | contador de identidade (research D1) |

**A pilha resolve do fim da lista para o começo.** `append` empilha, o último
elemento é o primeiro a sair (FR-026). Fica registrado aqui porque é a única
convenção de ordem que não é óbvia da leitura do campo.

Operações:

| Operação | Assinatura | Contrato |
|---|---|---|
| Criar | `Match.start(player1: PlayerData, player2: PlayerData) -> Match` | Estado válido, não jogável (research D10) |
| Gate de participante | `has_player(user_id: int \| None) -> bool` | `None` é `False`, nunca erro (FR-038) |
| Buscar jogador | `player(user_id: int) -> PlayerState` | Levanta `NotAParticipantError` citando o `user_id` (FR-006) |
| Buscar oponente | `opponent_of(user_id: int) -> PlayerState` | Mesma recusa |
| Revalidar alvo | `bank_unit(card_instance_id: CardInstanceId) -> BankUnit \| None` | Varre os dois bancos; `None` é a resposta do fizzle (FR-027) |
| Cunhar identidade | `mint_card_instance_id() -> CardInstanceId` | Devolve o atual e incrementa (FR-010) |

`player()` levanta e `bank_unit()` devolve `None` de propósito — research D6
explica a assimetria.

### `NotAParticipantError` — `match_state.py`

Levantada por `player()` e `opponent_of()`. A mensagem cita o `user_id` pedido
e o `match_id`, como a constituição exige de toda exceção.

---

## Documentos — a forma gravada

`TypedDict` em `documents.py`. É o que `json.dumps` recebe e o que
`json.loads` devolve.

| Documento | Campos |
|---|---|
| `CardDocument` | `card_instance_id: int`, `card_id: int` |
| `ModifierDocument` | `modifier_kind: str`, `duration: str`, `amount: int` (ausente em `damage_immunity`) |
| `BankUnitDocument` | `card: CardDocument`, `damage_taken: int`, `modifiers: list[ModifierDocument]` |
| `StackEntryDocument` | `card: CardDocument`, `caster_user_id: int`, `target_card_instance_id: int \| None` |
| `PlayerDocument` | `profile: PlayerData`, `nexus`, `deck`, `hand`, `bank`, `graveyard`, `energy_max`, `energy_current` |
| `MatchDocument` | `match_id`, `players: list[PlayerDocument]`, `round_number`, `token_holder_user_id`, `token_consumed`, `priority_user_id`, `phase: str`, `stack`, `consecutive_passes`, `next_card_instance_id` |

`ModifierDocument` com `amount` presente em dois dos três tipos é a
consequência de a união ter um braço sem quantidade. Fica como `total=False`
no campo `amount`, e o `match` sobre `modifier_kind` decide se o lê.

### Exemplo completo

```json
{
  "match_id": "3f9a2c14-...",
  "round_number": 3,
  "phase": "action",
  "priority_user_id": 7,
  "token_holder_user_id": 9,
  "token_consumed": false,
  "consecutive_passes": 1,
  "next_card_instance_id": 81,
  "stack": [
    {
      "card": {"card_instance_id": 57, "card_id": 1002},
      "caster_user_id": 9,
      "target_card_instance_id": 3
    }
  ],
  "players": [
    {
      "profile": {"user_id": 7, "nickname": "one", "icon": "default", "level": 1},
      "nexus": 18,
      "energy_max": 3,
      "energy_current": 1,
      "deck": [{"card_instance_id": 8, "card_id": 31}],
      "hand": [{"card_instance_id": 12, "card_id": 22}],
      "bank": [
        {
          "card": {"card_instance_id": 1, "card_id": 15},
          "damage_taken": 0,
          "modifiers": []
        },
        {
          "card": {"card_instance_id": 3, "card_id": 15},
          "damage_taken": 3,
          "modifiers": [
            {"modifier_kind": "attack", "amount": 2, "duration": "permanent"},
            {"modifier_kind": "damage_immunity", "duration": "until_end_of_round"}
          ]
        }
      ],
      "graveyard": [{"card_instance_id": 22, "card_id": 1004}]
    },
    {
      "profile": {"user_id": 9, "nickname": "two", "icon": "default", "level": 1},
      "nexus": 20,
      "energy_max": 3,
      "energy_current": 0,
      "deck": [], "hand": [], "bank": [], "graveyard": []
    }
  ]
}
```

Duas cópias da carta 15 no banco do jogador 7, uma intacta e outra com 3 de
dano e dois modificadores. O feitiço na pilha mira o `3`. Se o `3` morrer antes
da resolução, `bank_unit(3)` devolve `None` e o feitiço fizzla (§6).

**Nenhuma chave de objeto é `user_id`** — em nenhum nível (FR-030). `players` é
lista, e o `user_id` mora dentro de `profile`, como valor. É por isso que o
`{int(k): v for k, v in ...}` do modelo antigo não tem equivalente aqui: não
sobrou o que converter.

---

## Visão do jogador — `player_view.py`

`TypedDict`, derivados, nunca armazenados. Construídos por
`build_player_view(match, user_id)`.

### `PlayerSideView` — o próprio jogador

| Campo | Tipo |
|---|---|
| `profile` | `PlayerData` |
| `nexus` | `int` |
| `energy_max`, `energy_current` | `int` |
| `hand` | `list[CardDocument]` |
| `bank` | `list[BankUnitDocument]` |
| `graveyard` | `list[CardDocument]` |
| `deck_size` | `int` |

### `OpponentSideView` — o oponente

| Campo | Tipo |
|---|---|
| `profile` | `PlayerData` |
| `nexus` | `int` |
| `energy_max`, `energy_current` | `int` |
| `hand_size` | `int` |
| `bank` | `list[BankUnitDocument]` |
| `graveyard` | `list[CardDocument]` |
| `deck_size` | `int` |

**Não existe campo `hand` neste tipo.** Vazar a mão do oponente não é um bug de
valor a ser pego em revisão — é erro de mypy (research D8, FR-035).

**Nenhum dos dois tem conteúdo de deck**, só `deck_size`. FR-034 fala dos dois
decks, inclusive o próprio.

### `PlayerView`

| Campo | Tipo |
|---|---|
| `match_id` | `str` |
| `round_number` | `int` |
| `phase` | `str` |
| `priority_user_id`, `token_holder_user_id` | `int` |
| `token_consumed` | `bool` |
| `consecutive_passes` | `int` |
| `stack` | `list[StackEntryDocument]` |
| `you` | `PlayerSideView` |
| `opponent` | `OpponentSideView` |

`build_player_view` levanta `NotAParticipantError` para um `user_id` que não
joga a partida (FR-037) — reaproveita `Match.player()`, então a recusa é uma
só.

As cartas visíveis chegam como `CardDocument`, com `card_instance_id` — é o que
permite ao cliente mirar uma cópia específica (FR-036). Nome, custo, ataque e
vida não vão: o cliente tem o catálogo.

---

## Rastreabilidade

| Requisito | Onde vive |
|---|---|
| FR-001 a FR-003 | `Match` |
| FR-004, FR-008 | `PlayerState` |
| FR-005, FR-006 | `Match.players` (tupla), `Match.player()`, `NotAParticipantError` |
| FR-007 | listas em `PlayerState` e `Match.stack` |
| FR-009 a FR-015 | `CardInstanceId`, `Match.mint_card_instance_id`, `next_card_instance_id` |
| FR-016 a FR-022 | `BankUnit`, `modifiers.py` |
| FR-023 a FR-027 | `StackEntry`, `Match.bank_unit()` |
| FR-028 a FR-031 | `documents.py`, `serialization.py` |
| FR-032 a FR-037 | `player_view.py` |
| FR-038 | `Match.has_player()` |
| FR-039 a FR-041 | `store.py`, `consumers/*`, `__init__.py` |
| FR-042 | `models.py` apagado |
| FR-043 | testes e fakes atualizados |
| FR-044 | o pareamento de combate cabe como `dict[CardInstanceId, CardInstanceId]` no `Match`, sem tocar em nada acima |
