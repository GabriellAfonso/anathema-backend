# Contrato — o aplicador de efeito, o dano e a vitória

**Feature**: `006-spell-stack-effects` | **Data**: 2026-09-10

`apps.game.engine.spell_effect`, `unit_vitals`, `unit_damage` e `victory`, mais
`apps.game.match.match_outcome`. Reexportados por `apps.game.engine` e
`apps.game.match`. Assinaturas são o contrato; corpos são da implementação.

Este é o módulo que a spec mandou olhar com atenção: o que sair daqui é o que a
feature de combate vai reusar sem reimplementar. A razão do desenho está em
[research.md](../research.md) D7, D8, D9, D13 e D14.

---

## 1. O aplicador

```python
def apply_spell_effect(
    match: Match,
    caster: PlayerState,
    effect: SpellEffect,
    target: BankUnit | None,
    *,
    catalog: CardCatalog,
) -> None:
    """Executa um dos cinco efeitos do MVP sobre a partida.

    **Não sabe de onde a chamada veio, e não existe parâmetro que diga.** Na Fase
    de Ação a Resolução de Pilha chama isto depois de revalidar o alvo; no
    combate da §7.2 o feitiço do defensor vai chamar o mesmo com o alvo que
    acabou de receber. É o mesmo efeito com o mesmo resultado, e um parâmetro de
    origem -- mesmo um booleano -- convidaria o primeiro `if` que faz os dois
    caminhos divergirem.

    `target` já vem revalidado. `None` significa que o efeito não mira nada,
    nunca que o alvo sumiu -- decidir isso é da pilha, e o fizzle nunca chega
    aqui.

    Termina verificando a morte das unidades (§7.4) e, quando um Nexus mudou, a
    vitória (§10). As duas checagens acontecem **assim que o efeito termina**, e
    não no fim da pilha: o feitiço seguinte precisa enxergar o alvo já morto.

    >>> apply_spell_effect(match, caster, DamageUnit(amount=3), unit,
    ...                    catalog=catalog)
    >>> unit.damage_taken
    3
    """
```

O despacho é um `match` exaustivo sobre `SpellEffect`, a união fechada que a
feature 001 escreveu com esta feature em mente. Um efeito novo sem braço é erro
de mypy, não comportamento ausente em produção (FR-032).

| Efeito | O que faz | Duração |
|---|---|---|
| `BuffUnitHealth(amount)` | `HealthModifier(amount, effect.duration)` no alvo | do efeito |
| `PreventUnitDamage()` | `DamageImmunity(effect.duration)` no alvo | do efeito |
| `DamageUnit(amount)` | `deal_damage_to_unit(alvo, amount)` | — |
| `RestoreNexus(amount)` | `change_nexus(match, caster, +amount)` | — |
| `SacrificeNexusForAttack(cost, bonus)` | `AttackModifier(bonus, effect.duration)` em **todo** o banco do lançador, **depois** `change_nexus(match, caster, -cost)` | do efeito |

**A duração vem sempre de `effect.duration`, nunca de um literal.** É o que faz
o Fim de Rodada varrer a imunidade e não varrer o buff de vida sem que o
aplicador saiba o que é varrido — a §8 continua sendo a única dona dessa regra
(FR-047, FR-062).

**SACRIFICIAL FIRE aplica o buff antes do custo.** A troca é indivisível
(FR-039), e nessa ordem ela é indivisível qualquer que seja o comportamento da
verificação de vitória. Um lançador sem nenhuma unidade em campo perde os 8 de
Nexus do mesmo jeito: o laço sobre um banco vazio não faz nada, e o custo vem
depois dele.

Um alvo obrigatório ausente levanta `SpellNeedsTargetError`, a mesma recusa da
§5B. É braço impossível — `cast_spell` já validou —, e a recusa nomeada está
ali em vez de `assert` ou `cast`, pelo mesmo argumento de
`round_end._swap_token`.

---

## 2. `unit_vitals` — as perguntas

```python
def unit_max_health(unit: BankUnit, *, catalog: CardCatalog) -> int:
    """Vida do molde mais a soma dos modificadores de vida.

    É esta a quantidade que a morte compara, e é o que a spec chama de "vida
    efetiva" em FR-044 e nos cenários de US5.

    >>> unit_max_health(unit, catalog=catalog)   # molde 4, +2 de SHIELD
    6
    """


def unit_remaining_health(unit: BankUnit, *, catalog: CardCatalog) -> int:
    """A máxima menos o dano acumulado. É o que a spec chama de "vida efetiva"
    em FR-034.

    Pode ser zero ou negativa: a unidade morta é removida pela varredura, não
    por esta conta.

    >>> unit_remaining_health(unit, catalog=catalog)  # máxima 6, 3 de dano
    3
    """


def unit_is_dead(unit: BankUnit, *, catalog: CardCatalog) -> bool:
    """`unit_remaining_health(...) <= 0`.

    As duas formulações da spec são a mesma desigualdade:

        dano >= máxima   <=>   máxima - dano <= 0   <=>   restante <= 0

    >>> unit_is_dead(unit, catalog=catalog)
    False
    """


def unit_has_damage_immunity(unit: BankUnit) -> bool:
    """Se há um `DamageImmunity` ativo na lista de modificadores.

    Sem `catalog`: imunidade é da instância, não do molde. Fica aqui e não em
    `unit_damage` porque é pergunta, e o combate a fará sem causar dano nenhum
    ao decidir bloqueio.

    >>> unit_has_damage_immunity(unit)
    True
    """
```

`unit_effective_attack` **não existe nesta feature**. SACRIFICIAL FIRE escreve o
`AttackModifier`, e quem lê ataque é a §7.3 — a spec não o pede em FR nenhum, e
o combate vai precisar dele junto das regras de bloqueio que só ele conhece
(research D9).

O prefixo `unit_` é a regra de nomes específicos: `health` sozinho aparece no
molde (`Unit.health`), no modificador (`HealthModifier.amount`) e aqui.

---

## 3. `unit_damage` — as alterações

```python
def deal_damage_to_unit(unit: BankUnit, amount: int) -> None:
    """Acumula dano na unidade. Imunidade ativa faz nada entrar.

    Dano **acumula**; ele não reduz vida diretamente. Guardar vida absoluta
    obrigaria a desfazer na mão a expiração de um buff temporário, e o resultado
    passaria a depender da ordem dos eventos -- o docstring de `BankUnit` já
    registra isso.

    Não remove a unidade morta: quem faz isso é `bury_dead_units`, sobre os dois
    bancos, porque `BankUnit` não sabe de quem é.

    >>> deal_damage_to_unit(unit, 3)
    >>> unit.damage_taken
    3
    """


def bury_dead_units(match: Match, *, catalog: CardCatalog) -> None:
    """Move para o cemitério do **dono** toda unidade morta dos dois bancos.

    Varredura e não checagem do alvo: descobrir o dono de um `BankUnit` exigiria
    varrer os jogadores de qualquer jeito, e o dano simultâneo da §7.3 vai matar
    várias unidades dos dois lados num evento só.

    Compara por `card_instance_id`, nunca por `==` entre `BankUnit`: a dataclass
    tem `__eq__` gerado, e duas cópias intactas da mesma carta são iguais por
    valor -- uma remoção por valor levaria as duas.

    O `MatchCard` que entra no cemitério não tem onde guardar dano nem
    modificador; eles ficam para trás por construção.

    >>> bury_dead_units(match, catalog=catalog)
    """
```

---

## 4. `victory` — a §10

```python
def change_nexus(match: Match, player: PlayerState, amount: int) -> None:
    """Único ponto do código que escreve `nexus`, e a §10 vem junto.

    `amount` é assinado: LIFE POTION soma, SACRIFICIAL FIRE subtrai, e o dano de
    combate da §7.3 vai subtrair pela mesma porta.

    **Sem teto e sem piso.** O Nexus sobe livre acima de 20 -- o 20 da §12 é
    valor inicial, não limite -- e o negativo é preservado como ficou: um
    `max(0, ...)` apagaria por quanto o jogador passou do ponto.

    >>> change_nexus(match, caster, -8)
    >>> caster.nexus
    12
    """


def check_victory(match: Match) -> None:
    """A §10: depois de qualquer evento que altere um Nexus.

    Nexus <= 0 derrota o jogador; os dois <= 0 no mesmo cálculo é empate.

    Idempotente: uma partida já terminada não muda de resultado, e chamar de
    novo não faz nada. É o que permite ao combate chamá-la depois do dano
    simultâneo sem se preocupar com quantas vezes já foi chamada.

    Pública porque a §7.3 vai precisar dela sem passar por `change_nexus` -- o
    dano de combate altera os dois Nexus antes de verificar uma vez.

    >>> check_victory(match)
    >>> match.is_over
    True
    """
```

```python
def _finish_match(match: Match, outcome: MatchOutcome) -> None:
    """Único ponto que escreve o par (resultado, fase terminal).

    Privado de propósito: é a existência de um ponto só que torna a invariante
    `outcome is not None <=> phase is FINISHED` afirmável em vez de esperançosa.
    """
    match.outcome = outcome
    match.phase = MatchPhase.FINISHED
```

---

## 5. `MatchOutcome` — o estado, em `apps.game.match`

```python
class InvalidMatchOutcomeError(Exception):
    """Construíram um resultado que não é resultado de partida nenhuma.

    >>> raise InvalidMatchOutcomeError(())
    InvalidMatchOutcomeError: defeated_user_ids is (): expected one or two
    distinct user_ids
    """


@dataclass(frozen=True, slots=True)
class MatchOutcome:
    """Como a partida acabou (§10). Quem perdeu, e nada mais.

    Um `user_id` é derrota do outro jogador; dois é empate. Não existe campo de
    vencedor: ele é `match.players` menos isto, e gravá-lo seria a segunda fonte
    que `PlayerState.user_id` e `Match.awaiting_mulligan_user_ids` já recusam
    pelo mesmo argumento.

    Valida na construção, alto e cedo, como `FrozenCardCatalog`: vazio, três ou
    repetido não são resultados -- são bug de quem construiu.

    >>> MatchOutcome(defeated_user_ids=(7,)).is_draw
    False
    """

    defeated_user_ids: tuple[int, ...]

    @property
    def is_draw(self) -> bool:
        """Derivada, nunca gravada.

        >>> MatchOutcome(defeated_user_ids=(7, 9)).is_draw
        True
        """
        return len(self.defeated_user_ids) == 2
```

```python
class MatchPhase(StrEnum):
    ...
    FINISHED = "finished"          # NOVO -- terminal, sem transição de saída


@dataclass(slots=True)
class Match:
    ...
    outcome: MatchOutcome | None = None      # NOVO

    @property
    def is_over(self) -> bool:
        """`outcome is not None`. Propriedade e não campo, pela razão de sempre:
        um booleano gravado pode divergir do que ele resume.

        >>> match.is_over
        False
        """
        return self.outcome is not None
```

---

## 6. A forma gravada

```python
class MatchOutcomeDocument(TypedDict):
    defeated_user_ids: list[int]


class MatchDocument(TypedDict):
    ...
    outcome: MatchOutcomeDocument | None     # NOVO


class PlayerView(TypedDict):
    ...
    outcome: MatchOutcomeDocument | None     # NOVO
```

Lista e não tupla porque JSON não tem tupla; a volta reembrulha, como `CardId`,
`CardInstanceId` e `RandomSeed` já fazem. `None` enquanto a partida corre, como
`token_holder_user_id` é `None` antes do sorteio da §3.

O resultado entra na visão do jogador porque não é segredo de ninguém: sem ele o
cliente teria o estado terminal e não teria o desfecho.

---

## 7. Garantias

- **Um caminho por efeito.** Existe exatamente um lugar no código onde cada um
  dos cinco é executado, e o aplicador é o mesmo para a pilha e para o combate.
- **A origem não é observável.** Não há parâmetro, campo ou global que diga por
  onde a chamada chegou.
- **A morte é imediata.** Verificada assim que o efeito termina, nunca no fim da
  pilha — é o que faz o exemplo canônico da §6 funcionar.
- **Somar vida não é curar.** `damage_taken` é o mesmo antes e depois de
  `BuffUnitHealth`.
- **Imunidade barra a entrada, não o efeito.** O feitiço não fizzla: o alvo
  estava em campo, o efeito foi aplicado, e aplicar 0 de dano é o resultado
  certo.
- **`outcome is not None` ⟺ `phase is FINISHED`.** Um ponto só escreve os dois.
- **A §10 é idempotente.** Uma partida terminada não muda de resultado.
- **Nenhuma constante de Nexus máximo existe**, e `STARTING_NEXUS` continua
  significando só o valor inicial.
