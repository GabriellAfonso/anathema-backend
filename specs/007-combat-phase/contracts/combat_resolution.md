# Contrato: Dano, limpeza e volta (§7.3, §7.4, §7.5)

**Feature**: 007-combat-phase
**Módulos**: `apps/game/engine/combat_damage.py`,
`apps/game/engine/combat_cleanup.py`, `apps/game/engine/unit_vitals.py`,
`apps/game/engine/victory.py`

Tudo isto acontece dentro de **uma** ação: `EndDefenseWindowAction`. Quando ela
retorna, a partida está de volta esperando ação — ou terminada.

---

## 1. O ataque efetivo

`apps/game/engine/unit_vitals.py` (EDITADO)

```python
def unit_effective_attack(unit: BankUnit, *, catalog: CardCatalog) -> int:
    """O ataque do molde mais a soma dos modificadores de ataque, com piso em 0.

    É a quantidade que a §7.3 usa nos dois lados de um par e no dano ao Nexus.

    O piso existe porque `AttackModifier` aceita `amount` negativo por
    construção. Sem ele, um ataque negativo **curaria**: `deal_damage_to_unit`
    reduziria `damage_taken`, e o Nexus subiria. Nenhuma das duas é regra da §7.

    O piso mora aqui, e não em `deal_damage_to_unit`: aquele módulo também
    serve SUMMONED AX, cujo `amount` é positivo por construção, e pôr o piso lá
    escreveria uma regra da §7.3 no caminho da §5B.

    >>> unit_effective_attack(unit, catalog=catalog)   # molde 3, +3 do FIRE
    6
    """
```

Mora aqui porque o próprio módulo pediu: *"`unit_effective_attack` **não mora
aqui ainda** (...) Ela entra com o combate, junto das regras de bloqueio que só
ele conhece."* O texto sai; a função entra.

Reusa `_template_of`, que já está no módulo.

---

## 2. A alteração múltipla de Nexus

`apps/game/engine/victory.py` (EDITADO)

```python
def change_nexus(match: Match, player: PlayerState, amount: int) -> None:
    """Altera o Nexus de um jogador e apura a §10 em seguida. (inalterada)"""
    _add_to_nexus(player, amount)
    check_victory(match)


def change_nexus_simultaneously(
    match: Match, amount_by_player: Sequence[tuple[PlayerState, int]]
) -> None:
    """Altera vários Nexus e apura a §10 **uma vez**, depois de todos (§7.3).

    É a porta que o dano de combate usa, e a diferença entre ela e
    `change_nexus` é a razão de `check_victory` existir separada desde a
    feature 006: apurar depois de cada alteração transformaria o empate da §10
    em vitória do segundo, porque a primeira apuração já encerraria a partida e
    a verificação é idempotente.

    >>> change_nexus_simultaneously(match, ((defender, -7), (attacker, 0)))
    """
    for player, amount in amount_by_player:
        _add_to_nexus(player, amount)

    check_victory(match)


def _add_to_nexus(player: PlayerState, amount: int) -> None:
    """Único ponto do código que escreve Nexus. Sem teto e sem piso."""
    player.nexus += amount
```

`victory.py` continua sendo o único módulo que escreve Nexus, e agora com um
ponto só dentro dele — FR-061. Ver [research.md D15](../research.md).

---

## 3. O dano (§7.3)

`apps/game/engine/combat_damage.py` (NOVO)

```python
def resolve_combat_damage(match: Match, *, catalog: CardCatalog) -> None:
    """Todo o dano do combate, num evento só.

    Planeja antes de aplicar: o ataque efetivo de **todos** os participantes é
    lido antes da primeira escrita, e é isso que torna a simultaneidade da §7.3
    uma propriedade estrutural em vez de uma coincidência.
    """
    combat = match.ongoing_combat()
    attacker_player = _attacking_player(match)
    defender = match.opponent_of(attacker_player.user_id)

    strikes, nexus_damage = _plan_combat_damage(match, combat, catalog=catalog)

    for unit, amount in strikes:
        deal_damage_to_unit(unit, amount)

    change_nexus_simultaneously(
        match, ((defender, -nexus_damage), (attacker_player, 0))
    )
```

O atacante entra na chamada com 0 **sempre**, e não só quando há o que somar:
faz FR-058 valer literalmente e é o que torna o empate de FR-060 testável a
partir de um estado montado. Ver [research.md D16](../research.md).

`_attacking_player` estreita `match.token_holder_user_id` com recusa nomeada,
pelo precedente exato de `round_end._swap_token` — `assert` some com `-O`, e
`cast` calaria o mypy sem responder a pergunta.

### O plano, atacante por atacante

`_plan_combat_damage` percorre `combat.attacker_card_instance_ids` na ordem
declarada e acumula duas coisas: golpes em unidades e dano ao Nexus. A ordem não
influencia o resultado (FR-018), porque nada é escrito durante a leitura.

| Atacante em campo | Bloqueador declarado | Bloqueador em campo | Golpes | Nexus |
|---|---|---|---|---|
| não | — | — | nenhum | 0 |
| sim | não | — | nenhum | `+ ataque do atacante` |
| sim | sim | sim | atacante recebe o ataque do bloqueador, bloqueador recebe o do atacante | 0 |
| sim | sim | não | nenhum | 0 |

Linha 1 é FR-053. Linha 4 é o bloqueador órfão visto do outro lado, e não é
alcançável com as cinco cartas do MVP — a razão da resposta escolhida está em
[research.md D14](../research.md).

"Em campo" é `match.bank_unit(card_instance_id) is not None` — a mesma
revalidação por identificador que a §6 faz na pilha, pela mesma razão escrita em
`spell_stack.py`.

### O que o dano herda sem uma linha nova

- **Imunidade** (FR-055): `deal_damage_to_unit` já devolve sem escrever quando
  `unit_has_damage_immunity` é verdadeiro. Uma unidade imune ataca normalmente —
  o golpe dela está no plano — e não recebe.
- **Acúmulo** (FR-056): `deal_damage_to_unit` soma em `damage_taken` e não toca
  vida. O docstring de `BankUnit.damage_taken` já explica por quê.
- **Morte**: não acontece aqui. `resolve_combat_damage` não remove ninguém, e é
  isso que faz "nenhuma unidade morre antes de ter causado o dano dela" valer
  por construção.

---

## 4. Limpeza e volta (§7.4, §7.5)

`apps/game/engine/combat_cleanup.py` (NOVO)

```python
def end_combat(match: Match, *, catalog: CardCatalog) -> None:
    """A §7.3 e a §7.4 inteiras, disparadas por `EndDefenseWindowAction`.

    A apuração da §10 acontece dentro de `resolve_combat_damage`, no fim da
    §7.3, e **não** de novo aqui. É a mesma resposta: entre o dano e o passo 3
    da §7.4 nada altera Nexus -- enterrar unidade não mexe em Nexus --, e uma
    segunda chamada seria a segunda apuração que FR-058 proíbe, ainda que
    idempotente.
    """
    resolve_combat_damage(match, catalog=catalog)   # §7.3
    bury_dead_units(match, catalog=catalog)          # §7.4.1
    _leave_combat(match)                             # §7.4.4, §7.5


def _leave_combat(match: Match) -> None:
    """Passo 4 da §7.4, e o único ponto que apaga o par (combat, phase).

    O `return` da partida terminada não é defesa contra o impossível: sem ele, o
    combate que encerrou a partida a devolveria a `ACTION` e apagaria
    `FINISHED`. É a mesma linha, pela mesma razão, de
    `stack_resolution._reopen_action_phase`.

    O `combat = None` fica **antes** do `return`: um combate que encerra a
    partida pelo próprio dano também terminou, e FR-067 vale para ele. O único
    `CombatState` que sobrevive é o do combate interrompido por um feitiço na
    janela (FR-062), e é ele que registra que o combate nunca resolveu.
    """
    match.combat = None

    if match.is_over:
        return

    match.consecutive_passes = 0
    match.priority_user_id = match.token_holder_user_id
    match.phase = MatchPhase.ACTION
```

`bury_dead_units` varre **os dois bancos** e é a que já existe — o docstring
dela diz que foi escrita assim prevendo este chamador. Sobreviventes não são
tocados por ninguém: eles nunca saíram do banco, que é o que faz FR-066 valer
sem código. Ver [data-model.md §5](../data-model.md).

`match.priority_user_id = match.token_holder_user_id` atribui `int | None` a
`int | None` — sem estreitamento e sem recusa, porque os dois campos têm o mesmo
tipo.

---

## 5. Depois da ação, dentro de `submit_action`

| Passo | Combate resolvido | Partida terminada pelo dano |
|---|---|---|
| `_apply_action` | `end_combat` deixa a partida em `ACTION` | `end_combat` deixa a partida em `FINISHED` |
| `_pass_priority` | não faz nada (`keeps_priority`) | não faz nada |
| `_exit_action_phase` | passes em 0, não faz nada | passes em 0, não faz nada |
| `_settle` | `ACTION` não é automática, laço não roda | `FINISHED` não é automática, laço não roda |

Nos dois casos a partida volta **estabilizada**, que é a promessa de
`submit_action` desde a feature 005. FR-070 e FR-072.

---

## 6. `round_cycle._apply_action` (EDITADO)

```python
match action:
    case PlayUnitAction():
        play_unit(match, actor, action, catalog=catalog)
    case CastSpellAction():
        cast_spell(match, actor, action, catalog=catalog)
    case DeclareAttackAction():
        declare_attack(match, actor, action)
    case AssignBlockerAction():
        assign_blocker(match, actor, action)
    case RemoveBlockerAction():
        remove_blocker(match, actor, action)
    case CastCombatSpellAction():
        cast_combat_spell(match, actor, action, catalog=catalog)
    case EndDefenseWindowAction():
        end_combat(match, catalog=catalog)
    case PassAction():
        _pass_turn(match)
```

Oito braços sobre a união fechada: um braço novo sem regra escrita é erro de
mypy, não jogada que some em produção. `_AUTOMATIC_PHASES`,
`_exit_action_phase` e `_settle` **não mudam** — ver
[research.md D6 e D7](../research.md).

---

## 7. `engine/__init__.py` (EDITADO)

Entram no `__all__`: os cinco braços novos, as doze recusas novas,
`unit_effective_attack` e `change_nexus_simultaneously`.

**Não** entram, pela razão que o próprio `__all__` já escreve para `run_upkeep`,
`end_round`, `cast_spell` e `resolve_stack` — expô-los daria uma porta por onde
executar meia rodada: `declare_attack`, `assign_blocker`, `remove_blocker`,
`cast_combat_spell`, `end_combat`, `resolve_combat_damage`,
`validated_spell_cast`. Quem os chama é `round_cycle`, e os testes deles
importam do módulo.

---

## Cenários de aceitação cobertos

US4 inteira (cenários 1 a 14), US5 inteira (1 a 9), US6 (1 a 6).

FRs: FR-047 a FR-075.
