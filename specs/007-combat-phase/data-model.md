# Data Model: Combate

**Feature**: 007-combat-phase | **Data**: 2026-09-11 | **Fase**: 1

O que o estado da partida ganha, como ele viaja, quais transições existem e
quais invariantes valem. Só o que muda — o resto de `apps.game.match` fica como
as features 002 e 006 o deixaram.

---

## 1. Estado novo

### `CombatState` — `match/combat_state.py` (NOVO)

O combate em curso: quem ataca, e quem cobre quem.

```python
@dataclass(slots=True)
class BlockAssignment:
    blocker_card_instance_id: CardInstanceId
    attacker_card_instance_id: CardInstanceId


@dataclass(slots=True)
class CombatState:
    attacker_card_instance_ids: list[CardInstanceId]
    blocks: list[BlockAssignment] = field(default_factory=list)
```

| Campo | Tipo | Significado |
|---|---|---|
| `attacker_card_instance_ids` | `list[CardInstanceId]` | As unidades declaradas na §7.1, na ordem em que o atacante as citou. Nunca vazia. Pode conter identificador de unidade que já morreu. |
| `blocks` | `list[BlockAssignment]` | O pareamento da §7.2. Vazia é legal — o defensor pode não bloquear nada. |

**Por que lista de pares e não dicionário**: `match/documents.py` proíbe chave
de objeto JSON indexada por identificador, com a razão escrita. Ver
[research.md D2](./research.md).

**O que este módulo não tem**: quem ataca. O atacante é
`match.token_holder_user_id` e o defensor é o oponente dele — ver
[research.md D3](./research.md). Também não tem dano, ataque efetivo nem
resultado: tudo isso é conta do motor, feita na resolução.

Consultas que o `CombatState` responde (perguntas, não regras — o pacote
`match` continua sem decidir nada):

```python
def is_attacking(self, card_instance_id: CardInstanceId) -> bool: ...
def blocker_of(self, attacker_card_instance_id: CardInstanceId) -> CardInstanceId | None: ...
def attacker_blocked_by(self, blocker_card_instance_id: CardInstanceId) -> CardInstanceId | None: ...
```

As três devolvem `None`/`False` para o ausente, sem levantar: "este atacante tem
bloqueador?" é pergunta normal, não erro — a mesma escolha de
`Match.bank_unit()`.

Atribuir e remover **não** são métodos daqui: são regra, e regra é do motor.
Ele escreve `combat.blocks` direto, como `unit_damage` escreve `player.bank`.

### `Match.combat` — `match/match_state.py` (EDITADO)

```python
combat: CombatState | None = None
```

`None` é ausência de combate, não valor de espera — a mesma forma de
`token_holder_user_id` antes do sorteio e de `outcome` antes do fim.

### `Match.ongoing_combat()` — `match/match_state.py` (EDITADO)

```python
def ongoing_combat(self) -> CombatState:
    """O combate em curso, ou recusa citando a fase."""
```

Levanta `MatchIsNotInCombatError(phase, match_id)`, definida no mesmo módulo, ao
lado de `NotAParticipantError` e pela mesma razão de não herdar de
`IllegalActionError`. É o estreitamento que as três regras do combate precisam —
ver [research.md D9](./research.md).

---

## 2. Forma gravada

### `match/documents.py` (EDITADO)

```python
class BlockAssignmentDocument(TypedDict):
    blocker_card_instance_id: int
    attacker_card_instance_id: int


class CombatDocument(TypedDict):
    attacker_card_instance_ids: list[int]
    blocks: list[BlockAssignmentDocument]


class MatchDocument(TypedDict):
    ...
    combat: CombatDocument | None     # NOVO
```

Chave obrigatória com valor `None` fora do combate, e não `total=False`: é o
argumento que a feature 006 usou para `outcome` — opcionalidade parcial num
`TypedDict` deixa o resto do documento igualmente opcional.

Sem migration, sem número de versão de esquema. `MatchDocument` já diz por quê:
a partida vive no Redis como JSON, e a `version` do compare-and-swap de
`store.py` é versão de **escrita**, não de esquema.

### `match/serialization.py` (EDITADO)

Quatro funções novas, no formato das que já existem:

```python
def to_combat_document(combat: CombatState | None) -> CombatDocument | None
def combat_from_document(document: CombatDocument | None) -> CombatState | None
def to_block_assignment_document(block: BlockAssignment) -> BlockAssignmentDocument
def block_assignment_from_document(document: BlockAssignmentDocument) -> BlockAssignment
```

`None` atravessa como `None`, como `to_match_outcome_document` já faz. A volta
reembrulha os inteiros em `CardInstanceId`, como `card_from_document` e
`stack_entry_from_document` já fazem.

A garantia do módulo continua valendo, agora com o pareamento dentro:
`match_from_document(json.loads(json.dumps(to_match_document(match))))` é igual
ao original.

### `match/player_view.py` (EDITADO)

```python
class PlayerView(TypedDict):
    ...
    combat: CombatDocument | None     # NOVO
```

Aparece inteiro para os dois lados. O pareamento é informação revelada — é a
mesma decisão que pôs `stack` na visão, enquanto a mão do oponente vira
contagem.

---

## 3. Transições

```
                  declare_attack (§5C)
    ACTION ─────────────────────────────────> COMBAT
      ^                                         │  │
      │                                         │  │ assign_blocker
      │                                         │  │ remove_blocker
      │                                         │  │ cast_combat_spell
      │                                         │  └──┐ (a prioridade NÃO troca)
      │                                         │ <───┘
      │        end_defense_window (§7.3-§7.5)   │
      └─────────────────────────────────────────┘
                                                │
                                                │ o Nexus de alguém chega a 0
                                                v
                                            FINISHED
```

| # | Transição | Gatilho | Escreve |
|---|---|---|---|
| T1 | `ACTION → COMBAT` | `DeclareAttackAction` aceita | `token_consumed = True`, `combat = CombatState(...)`, `phase = COMBAT`, `consecutive_passes = 0`; depois `_pass_priority` põe a prioridade no defensor |
| T2 | `COMBAT → COMBAT` | `AssignBlockerAction` | `combat.blocks.append(...)` |
| T3 | `COMBAT → COMBAT` | `RemoveBlockerAction` | `combat.blocks = [...]` sem o par |
| T4 | `COMBAT → COMBAT` | `CastCombatSpellAction` | energia, mão, cemitério, e o que o efeito alterar |
| T5 | `COMBAT → ACTION` | `EndDefenseWindowAction` | dano, mortes, `combat = None`, `consecutive_passes = 0`, `priority = token_holder`, `phase = ACTION` |
| T6 | `COMBAT → FINISHED` | T4 ou T5 levando um Nexus a ≤ 0 | `outcome`, `phase = FINISHED` (por `_finish_match`) |

**T2, T3 e T4 não trocam a prioridade.** É `keeps_priority = True` nos quatro
braços da janela, lido por `round_cycle._pass_priority`. T1 troca, como toda
ação da §5.

**T5 por dentro**, na ordem da §7.3 e da §7.4:

1. planeja todo o dano (lê ataque efetivo de todos os participantes);
2. aplica o dano às unidades;
3. altera os **dois** Nexus e apura a §10 **uma vez**;
4. varre as unidades mortas dos **dois** bancos para os cemitérios dos donos;
5. `combat = None`;
6. se a partida acabou, para aqui; senão zera os passes, devolve a prioridade ao
   dono do token e volta para `ACTION`.

O passo 3 acontece antes do 4, e a apuração do 3 é a da §7.4.3: nada entre os
dois altera Nexus, então o resultado é o mesmo e a §10 é chamada uma vez só.

---

## 4. Invariantes

| # | Invariante | Quem a mantém |
|---|---|---|
| I1 | `phase is COMBAT ⟹ combat is not None` | `declare_attack._enter_combat` e `combat_cleanup._leave_combat`, os dois únicos pontos que escrevem o par |
| I2 | `combat is not None ⟹ combat.attacker_card_instance_ids != []` | FR-007 na declaração; nada depois remove atacante da lista |
| I3 | Cada `card_instance_id` aparece no máximo uma vez em `attacker_card_instance_ids` | a guarda de duplicata da declaração |
| I4 | Cada `blocker_card_instance_id` aparece no máximo uma vez em `blocks` | `BlockerAlreadyBlockingError` |
| I5 | Cada `attacker_card_instance_id` aparece no máximo uma vez em `blocks` | `AttackerAlreadyBlockedError` |
| I6 | Todo `attacker_card_instance_id` de `blocks` está em `attacker_card_instance_ids` | `UnitIsNotAttackingError` |
| I7 | `outcome is not None ⟺ phase is FINISHED` | `victory._finish_match` (feature 006, inalterado) |

**I1 é unidirecional de propósito.** A recíproca não vale: uma partida terminada
durante a janela (FR-062) fica em `FINISHED` com o `CombatState` intacto, e é
esse estado congelado que registra que o combate foi interrompido em vez de
resolvido. Ver [research.md D17](./research.md).

**O que I2–I6 não garantem**: que os identificadores ainda estejam em campo. Uma
unidade citada pode morrer por feitiço durante a janela, e o `CombatState` não é
atualizado — a revalidação acontece na resolução, por `Match.bank_unit()`,
exatamente como a §6 revalida o alvo da pilha. É a mesma razão escrita em
`spell_stack.py`: *"o alvo é guardado como identificador, nunca como referência
ao objeto."*

---

## 5. O que **não** muda

| Estrutura | Por quê |
|---|---|
| `BankUnit` | O combate não acrescenta campo nenhum: `damage_taken` já acumula, `modifiers` já carrega o bônus de ataque, e a unidade atacando ou bloqueando continua no banco do dono do começo ao fim. Não existe "zona de combate". |
| `StackEntry`, `Match.stack` | O combate não usa a pilha (FR-082) e não pode ser declarado com ela cheia (FR-005). |
| `MatchPhase` | `COMBAT` existe desde a feature 002. Nenhuma fase nova. |
| `MatchOutcome` | O empate já é `defeated_user_ids` com dois `user_id`; a validação de aridade da feature 006 já o aceita. |
| `PlayerState` | Nexus, zonas e energia bastam. |
| `UnitModifier` e os três tipos | `AttackModifier` já existe e já é escrito por SACRIFICIAL FIRE; esta feature é a primeira a **ler**. |

**Unidade que ataca ou bloqueia não sai do banco.** É a decisão que faz FR-066
("sobreviventes estão no banco do dono") valer sem uma linha escrita: ninguém
foi movido, então ninguém precisa voltar. Mover para uma zona intermediária
exigiria devolver na limpeza, e o campo que um retorno esquecesse não daria
erro — daria unidade sumida do jogo, que é o argumento que `play_unit.py` já faz
contra rollback parcial.

---

## 6. Identidade

Nenhum campo `id` nu entra no estado, no documento nem na visão. Os nomes novos:

- `attacker_card_instance_ids`
- `blocker_card_instance_id`
- `attacker_card_instance_id`

Todos nomeiam o espaço de identidade, e todos são `CardInstanceId` — o `NewType`
que a feature 002 criou justamente porque *"três inteiros viajam nos mesmos
payloads de websocket: `user_id`, `card_id` e este"*. Trocar um bloqueador por
um `card_id` é erro de mypy.
