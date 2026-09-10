# Contrato — a forma da ação e as recusas

**Feature**: `005-round-cycle` | **Data**: 2026-09-10

`apps.game.engine.player_action`, reexportado por `apps.game.engine`.
Assinaturas são o contrato; corpos são da implementação.

Este é o módulo que a spec mandou olhar com atenção: a forma que sair daqui vai
ser reusada por feitiço, ataque, bloqueio e mulligan. A razão do desenho está em
[research.md](../research.md) D1, D2, D3 e D4.

`__all__` é explícito porque `mypy.ini` roda com `strict`, que liga
`no_implicit_reexport` — sem a lista, ninguém importa do pacote.

---

## 1. A união fechada

```python
class ActionKind(StrEnum):
    """Discriminante da união, e o que o transporte vai pôr no envelope.

    Conjunto fechado. As duas ações que faltam da §5 -- jogar feitiço e
    declarar ataque -- entram aqui junto com os braços delas.
    """

    PLAY_UNIT = "play_unit"
    PASS = "pass"


@dataclass(frozen=True, slots=True)
class PlayUnitAction:
    """Jogar uma unidade da mão (§5A).

    `card_instance_id` e não `card_id`: a jogada é sobre **aquela** cópia na
    mão, e o `NewType` da feature 002 faz de trocar um pelo outro um erro de
    mypy.

    >>> PlayUnitAction(actor_user_id=7, card_instance_id=CardInstanceId(3))
    """

    # `ClassVar` porque a espécie pertence à mecânica, não à instância: nenhum
    # call site consegue construir um PlayUnitAction que se diz `pass`. Mesma
    # disciplina de `ModifierKind` em `match/modifiers.py`.
    action_kind: ClassVar[ActionKind] = ActionKind.PLAY_UNIT
    # As fases em que esta ação é legal. Mora na ação e não numa cadeia de `if`
    # na guarda comum porque a §5 escreve a pergunta como "a fase atual permite
    # **esta** ação". O bloqueio da §7.2 vai declarar `{COMBAT}` sem que a
    # guarda mude.
    allowed_phases: ClassVar[frozenset[MatchPhase]] = frozenset({MatchPhase.ACTION})

    actor_user_id: int
    card_instance_id: CardInstanceId


@dataclass(frozen=True, slots=True)
class PassAction:
    """Passar a vez (§5D). Sempre disponível para quem tem a prioridade.

    Sem campo além do autor, e é isso que a união compra: não existe um passe
    com `card_instance_id` a construir nem a validar.

    >>> PassAction(actor_user_id=7)
    """

    action_kind: ClassVar[ActionKind] = ActionKind.PASS
    allowed_phases: ClassVar[frozenset[MatchPhase]] = frozenset({MatchPhase.ACTION})

    actor_user_id: int


# União fechada: um `match` sobre `PlayerAction` que esqueça um braço é erro de
# mypy, não bug em produção. Mesma disciplina de `Card` em `cards/card.py` e de
# `UnitModifier` em `match/modifiers.py`.
PlayerAction = PlayUnitAction | PassAction
```

**O que todo braço, presente e futuro, precisa ter**: `action_kind`,
`allowed_phases` e `actor_user_id`. As guardas comuns leem só esses três, e é
por isso que elas não conhecem os braços.

---

## 2. As guardas comuns

```python
def ensure_action_allowed(match: Match, action: PlayerAction) -> PlayerState:
    """As três guardas da §5, nesta ordem, antes de qualquer regra específica.

    A ordem é parte do contrato (FR-044): o autor joga esta partida; o autor
    tem a prioridade; a fase atual permite esta ação. Um jogador sem prioridade
    **e** sem energia recebe a recusa de prioridade, nunca a de energia.

    Devolve o `PlayerState` do autor, que a guarda 1 já teve de buscar. Assim
    nenhuma regra específica repete a busca, e não sobra um segundo lugar de
    onde `NotAParticipantError` pudesse escapar.

    Levanta `NotAParticipantError` (de `apps.game.match`) na guarda 1,
    `NotYourPriorityError` na 2 e `PhaseForbidsActionError` na 3.

    >>> ensure_action_allowed(match, PassAction(actor_user_id=7)).user_id
    7
    """
```

---

## 3. As recusas

```python
class IllegalActionError(Exception):
    """Raiz das recusas de jogada desta feature.

    Levantar deixa o estado da partida **exatamente** como estava: nenhuma
    regra muta antes de todas as suas guardas passarem, então não há meia ação
    a desfazer.

    Não é a raiz de tudo que o motor recusa: a guarda de participante levanta
    `NotAParticipantError`, que mora em `apps.game.match` e não pode herdar
    daqui sem inverter a dependência entre o pacote de estado e o de regra.
    Quem quiser pegar toda recusa pega as duas.
    """


class NotYourPriorityError(IllegalActionError):
    """Agiu quem não tem a vez. A mensagem diz quem tem.

    >>> raise NotYourPriorityError(9, 7, "m-1")
    NotYourPriorityError: user 9 cannot act in match 'm-1': priority is
    user 7's
    """

    def __init__(
        self, actor_user_id: int, priority_user_id: int | None, match_id: str
    ) -> None: ...

    actor_user_id: int
    priority_user_id: int | None


class PhaseForbidsActionError(IllegalActionError):
    """A fase atual não permite esta ação. Cita a fase e as permitidas.

    Cobre a partida em `MULLIGAN`, e cobriria uma fase automática se alguém
    conseguisse pegá-la no meio -- o que a cascata torna impossível de fora.

    >>> raise PhaseForbidsActionError(ActionKind.PASS, MatchPhase.UPKEEP, ...)
    PhaseForbidsActionError: action 'pass' is not allowed in phase 'upkeep':
    expected one of ['action']
    """

    def __init__(
        self,
        action_kind: ActionKind,
        phase: MatchPhase,
        allowed_phases: frozenset[MatchPhase],
        match_id: str,
    ) -> None: ...

    action_kind: ActionKind
    phase: MatchPhase


class CardNotInHandError(IllegalActionError):
    """A seleção cita uma carta que não está na mão daquele jogador.

    Cobre também o identificador repetido: a validação do mulligan consome a
    mão candidata ao casar, então a segunda ocorrência já não está entre as
    restantes.

    Veio de `mulligan.py`, onde nasceu na feature 003. Mora aqui porque a
    pergunta -- "a carta citada está na mão do autor?" -- é a mesma no mulligan
    da §3 e na jogada da §5A, e vai ser a mesma no feitiço da §6. A mensagem
    não muda.
    """

    def __init__(
        self, card_instance_id: CardInstanceId, user_id: int, in_hand: list[int]
    ) -> None: ...

    card_instance_id: CardInstanceId
    user_id: int
```

**Nota de migração**: `CardNotInHandError` passa a herdar de
`IllegalActionError`, o que ela não fazia antes. Nenhum chamador quebra —
`test_mulligan.py` a importa de `apps.game.engine` e a captura pelo próprio
nome.

Cada recusa carrega os valores ofensores como **atributos**, não só dentro da
mensagem (FR-052). É o que deixa o transporte montar um payload sem interpretar
texto livre.

---

## 4. Como a próxima feature acrescenta uma ação

Três passos, e nenhum deles toca as guardas nem a porta pública:

1. Um valor novo em `ActionKind`.
2. Um braço novo, `frozen=True, slots=True`, com `action_kind`,
   `allowed_phases`, `actor_user_id` e os campos que aquela ação exige.
3. O braço entra na união `PlayerAction`.

O despacho de `round_cycle.submit_action` é um `match` sobre a união, então
esquecer o passo seguinte — escrever a regra — é erro de mypy, não jogada que
some.

Exemplos do que já se sabe que vem:

```python
@dataclass(frozen=True, slots=True)
class CastSpellAction:
    action_kind: ClassVar[ActionKind] = ActionKind.CAST_SPELL
    allowed_phases: ClassVar[frozenset[MatchPhase]] = frozenset(
        {MatchPhase.ACTION, MatchPhase.COMBAT}   # §7.2: feitiço resolve na hora
    )

    actor_user_id: int
    card_instance_id: CardInstanceId
    target_card_instance_id: CardInstanceId | None = None


@dataclass(frozen=True, slots=True)
class DeclareAttackAction:
    action_kind: ClassVar[ActionKind] = ActionKind.DECLARE_ATTACK
    allowed_phases: ClassVar[frozenset[MatchPhase]] = frozenset({MatchPhase.ACTION})

    actor_user_id: int
    attacker_card_instance_ids: tuple[CardInstanceId, ...]
```

Nenhum dos dois está nesta feature. Estão aqui para mostrar que o formato os
comporta (FR-046).
