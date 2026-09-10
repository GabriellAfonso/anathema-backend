# Contrato — as portas públicas e as três regras

**Feature**: `005-round-cycle` | **Data**: 2026-09-10

Quatro superfícies, todas reexportadas por `apps.game.engine`:
`round_cycle` (as portas), `upkeep` (§4), `play_unit` (§5A) e `round_end` (§8).
Assinaturas são o contrato; corpos são da implementação.

---

## 1. `apps.game.engine.round_cycle` — as duas portas

```python
# Fluxo de Partida §5, "Saída da fase".
CONSECUTIVE_PASSES_TO_EXIT = 2


class MatchNotAwaitingUpkeepError(Exception):
    """Pediram o primeiro empurrão numa partida que não está parada antes do
    Upkeep. Cita a fase atual.

    Cobre os dois casos: a partida ainda em mulligan, e a partida que já foi
    iniciada -- o Upkeep da Rodada 1 roda uma vez só.

    >>> raise MatchNotAwaitingUpkeepError(MatchPhase.ACTION, "m-1")
    MatchNotAwaitingUpkeepError: match 'm-1' is in phase 'action': expected
    'upkeep' to begin the round cycle
    """

    def __init__(self, phase: MatchPhase, match_id: str) -> None: ...

    phase: MatchPhase


def begin_round_cycle(match: Match, *, randomness: RandomSource) -> None:
    """O primeiro empurrão: o Upkeep da Rodada 1 que o setup deixou pendente.

    O setup da §3 entrega a partida montada e parada em `UPKEEP`, sem tê-lo
    executado -- posicionar não é executar. Isto executa, e a partida volta na
    Fase de Ação esperando a primeira jogada.

    Chamada uma vez por partida. Depois dela a cascata de `submit_action` cuida
    de todo Upkeep seguinte, e nenhum outro empurrão é necessário.

    Altera `match` no lugar, como `record_mulligan` e `finish_setup`. Quem grava
    é o chamador, pelo `MatchStore.mutate` da feature 003.

    >>> begin_round_cycle(match, randomness=source)
    >>> match.phase
    <MatchPhase.ACTION: 'action'>
    """


def submit_action(
    match: Match,
    action: PlayerAction,
    *,
    catalog: CardCatalog,
    randomness: RandomSource,
) -> None:
    """Uma ação de jogador, e a partida de volta ao ponto de esperar ação.

    Quatro passos, nesta ordem:

        1. as três guardas comuns da §5 (`ensure_action_allowed`)
        2. a regra específica da ação
        3. a prioridade passa ao oponente
        4. a saída da fase, e a cascata que a atravessa

    O passo 4 é o que faz um único "passar" virar a rodada inteira: fim de
    rodada, varredura, troca de token, rodada +1 e o Upkeep da rodada seguinte
    acontecem aqui dentro. Quando isto retorna, a fase é sempre a Fase de Ação
    -- nenhum estado intermediário atravessa a fronteira desta função.

    Recusa levanta e não muta: nenhuma regra escreve antes de todas as suas
    guardas passarem, então não há meia ação a desfazer. Ver
    `player_action.IllegalActionError`.

    `catalog` é exigido mesmo por um passe, que não o usa: a porta é uma só, e
    recebe o que a mais cara das ações precisa.

    >>> submit_action(match, PassAction(actor_user_id=7),
    ...               catalog=catalog, randomness=source)
    >>> match.consecutive_passes
    1
    """
```

### A cascata, por dentro

```python
def _exit_action_phase(match: Match) -> None:
    """A saída da §5, verificada depois de toda ação.

    Dois passes com a pilha vazia levam ao Fim de Rodada; dois com a pilha
    cheia, à Resolução de Pilha. A segunda condição é escrita como a §5 manda,
    e **não tem consumidor nesta feature** -- nada enche a pilha, e o corpo da
    resolução é a §6.

    Como a prioridade troca a cada ação, dois passes consecutivos significam
    sempre que os dois jogadores passaram, nunca que um passou duas vezes.
    """


def _settle(match: Match, randomness: RandomSource) -> None:
    """Atravessa toda fase automática até a partida voltar a esperar ação.

    Laço e não uma sequência fixa de chamadas, por dois motivos: a saída da §5
    não sabe qual fase vem -- ela decide --, e a feature de pilha acrescenta um
    braço aqui sem reescrever nada.

    Termina sempre, e em no máximo duas voltas: `ROUND_END` leva a `UPKEEP` e
    `UPKEEP` leva a `ACTION`. Nenhuma fase automática leva a outra que volte à
    primeira.
    """
```

---

## 2. `apps.game.engine.upkeep` — a §4

```python
# Fluxo de Partida §12.
MAX_ENERGY = 10
ENERGY_PER_ROUND = 1


def run_upkeep(match: Match, *, randomness: RandomSource) -> None:
    """A §4 inteira: recarga e compra dos dois, e a partida entra em Ação.

    Para cada jogador, na ordem do par: a energia máxima sobe 1 até o teto de
    10, a atual passa a ser a máxima -- recarga total, o que sobrou da rodada
    anterior é perdido --, e ele compra 1 carta pela regra da §9.

    A ordem do par é a garantia, não um acaso. O que a §4 promete é
    **independência**: nenhum passo do Upkeep de um jogador lê o estado do
    outro. A ordem existe, é sempre a mesma, e é o que torna reproduzível um
    Upkeep em que os dois jogadores resetam o deck -- os dois resets consomem o
    contador de sorteios da partida, e sem ordem fixa qual pega qual ponto da
    sequência dependeria de quem fosse resolvido primeiro. Ver a seção
    Clarifications da spec.

    Um jogador com a mão cheia não compra, e o Upkeep segue: `draw_card`
    devolve `None`, que não é erro (§9).

    Depois dos dois: o token volta a estar disponível, os passes zeram, a
    prioridade vai para o dono do token, e a fase é a Fase de Ação.

    Não valida a fase de entrada. Quem chama é `begin_round_cycle`, que valida,
    ou a cascata, que só chega aqui vinda do Fim de Rodada.

    >>> run_upkeep(match, randomness=source)
    >>> match.players[0].energy_current
    1
    """
```

---

## 3. `apps.game.engine.play_unit` — a §5A

```python
# Fluxo de Partida §12. Mora aqui, e não em `player_state.py`, porque aplicar o
# teto é regra -- e aquele arquivo diz isso de si mesmo, nomeando este ponto:
# "o de banco ao jogar unidade (§5A)".
MAX_BANK_SIZE = 6


class CardIsNotAUnitError(IllegalActionError):
    """Usaram a ação de jogar unidade com uma carta que é feitiço.

    Recusa e não roteamento: jogar feitiço é a ação B da §5, com pilha e alvo,
    e usar a ação errada não é atalho para ela.

    >>> raise CardIsNotAUnitError(CardInstanceId(3), CardId(1001), CardType.SPELL)
    CardIsNotAUnitError: card instance 3 (card 1001) is a spell: expected a unit
    """

    def __init__(
        self,
        card_instance_id: CardInstanceId,
        card_id: CardId,
        card_type: CardType,
    ) -> None: ...


class NotEnoughEnergyError(IllegalActionError):
    """Custo maior que a energia atual. Cita os dois números.

    >>> raise NotEnoughEnergyError(7, CardInstanceId(3), 3, 1)
    NotEnoughEnergyError: user 7 cannot pay card instance 3: costs 3 energy,
    has 1
    """

    def __init__(
        self, user_id: int, card_instance_id: CardInstanceId, cost: int, available: int
    ) -> None: ...

    cost: int
    available: int


class BankIsFullError(IllegalActionError):
    """O banco chegou ao teto da §12. Cita o limite.

    >>> raise BankIsFullError(7, 6)
    BankIsFullError: bank of user 7 holds 6 units: expected fewer than 6 to
    play another
    """

    def __init__(self, user_id: int, bank_size: int) -> None: ...

    user_id: int
    bank_size: int


def play_unit(
    match: Match,
    actor: PlayerState,
    action: PlayUnitAction,
    *,
    catalog: CardCatalog,
) -> None:
    """A §5A: desconta a energia, tira a carta da mão, põe a unidade no banco.

    As quatro perguntas acontecem **antes** da primeira atribuição, e a ordem
    entre elas é parte da regra: a carta está na mão, a carta é uma unidade, a
    energia cobre o custo, o banco tem espaço. A carta precisa ser resolvida
    antes de se poder citar o custo dela na recusa de energia.

    Valida tudo e muta depois: é a ordem que garante que uma recusa deixa o
    estado idêntico, e não um rollback que alguém teria de manter completo.

    A unidade entra pronta e sem dano -- `BankUnit(card=card)` já nasce assim,
    porque não existe doença de invocação (§5A). Não usa a pilha: resolve na
    hora.

    Zera a contagem de passes, inclusive quando o oponente já tinha passado uma
    vez.

    Recebe o `actor` que `ensure_action_allowed` já buscou, em vez de buscá-lo
    de novo.

    >>> play_unit(match, actor, PlayUnitAction(7, CardInstanceId(3)),
    ...           catalog=catalog)
    >>> actor.bank[-1].card.card_instance_id
    3
    """
```

---

## 4. `apps.game.engine.round_end` — a §8

```python
def end_round(match: Match) -> None:
    """A §8, na ordem dela: varre, troca o token, sobe a rodada, volta ao Upkeep.

    A varredura remove das unidades no banco dos **dois** jogadores todo
    modificador marcado como "até o fim da rodada". Os permanentes ficam, e o
    dano acumulado não é tocado -- dano não é modificador, não expira, e mora
    em `BankUnit.damage_taken`.

    Nenhum feitiço existe ainda para criar um modificador temporário. A
    varredura existe assim mesmo, e é testada com um modificador posto à mão,
    para que a feature de pilha não tenha de voltar aqui.

    Não existe descarte por excesso de mão: o teto de 10 é aplicado na compra
    (§9), não aqui.

    Termina pondo a partida em `UPKEEP`. Quem executa o Upkeep é a cascata de
    `round_cycle`, não esta função -- a §8 não é dona da §4.

    >>> end_round(match)
    >>> match.phase
    <MatchPhase.UPKEEP: 'upkeep'>
    """
```

---

## 5. O que `apps.game.engine` passa a exportar

Acrescentado ao `__all__` existente:

```python
    # Ciclo de rodada (§4, §5, §8)
    "begin_round_cycle",
    "submit_action",
    "MatchNotAwaitingUpkeepError",
    # A forma da ação (§5)
    "ActionKind",
    "PlayUnitAction",
    "PassAction",
    "PlayerAction",
    # Recusas (§5)
    "IllegalActionError",
    "NotYourPriorityError",
    "PhaseForbidsActionError",
    "CardIsNotAUnitError",
    "NotEnoughEnergyError",
    "BankIsFullError",
    # Constantes da §12 aplicadas aqui
    "MAX_ENERGY",
    "MAX_BANK_SIZE",
```

`CardNotInHandError` já estava na lista e continua, agora vinda de
`player_action` em vez de `mulligan`.

`run_upkeep` e `end_round` **não** entram no `__all__` do pacote: quem os chama é
`round_cycle`, e expô-los daria uma porta por onde executar meia rodada — o
contrário do que a cascata garante. Os testes deles importam do módulo.
