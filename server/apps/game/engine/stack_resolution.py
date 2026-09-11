"""A Resolução de Pilha da §6: a pilha inteira resolve de uma vez.

Dispara quando os dois jogadores passam consecutivamente com a pilha não vazia,
e resolve **do topo para a base sem devolver prioridade entre um feitiço e o
seguinte**. Quem conhece outros jogos de carta espera que devolva; aqui não.

Para cada feitiço, antes de aplicar o efeito, o alvo é revalidado pelo
identificador que a entrada guardou. Alvo em campo, o efeito acontece; alvo
sumido, o feitiço **fizzla** e não faz nada. Nos dois casos a carta vai para o
cemitério do lançador.

Terminada a pilha, a prioridade volta para quem **iniciou** a pilha -- o
lançador do feitiço mais antigo dela, não o último. A rodada não acaba junto: os
dois passes que dispararam a resolução foram consumidos por ela.

`resolve_stack` não é reexportada pelo pacote, pela mesma razão que `run_upkeep`
e `end_round` não são: expô-la daria uma porta por onde executar meia rodada.
Quem a chama é a cascata de `round_cycle`.
"""

from apps.game.cards import CardCatalog, Spell

from apps.game.match import BankUnit, Match, MatchPhase, StackEntry

from .spell_cast_guards import CardIsNotASpellError
from .spell_effect import apply_spell_effect


def resolve_stack(match: Match, *, catalog: CardCatalog) -> None:
    """A §6 inteira, numa passagem só.

    Assume a pilha não vazia: a saída da §5 que a dispara já verificou. Pilha
    vazia é bug de chamador, como a fase de entrada é para `run_upkeep`.

    O iniciador é lido **antes** do laço. A pilha esvazia durante a resolução, e
    `match.stack[0]` depois dela é `IndexError` -- por isso o valor é lido cedo,
    e por isso ele é variável local em vez de campo do estado: só existe durante
    a resolução, que acontece inteira dentro desta chamada.

    >>> resolve_stack(match, catalog=catalog)
    >>> match.stack
    []
    """
    initiator_user_id = match.stack[0].caster_user_id

    while match.stack:
        _resolve_top(match, catalog=catalog)

    _reopen_action_phase(match, initiator_user_id)


def _resolve_top(match: Match, *, catalog: CardCatalog) -> None:
    """Uma entrada: aplica se couber, e manda a carta ao cemitério sempre.

    O `pop` acontece antes de qualquer decisão, e o cemitério depois de todos os
    caminhos. É isso que faz a pilha esvaziar mesmo quando a partida termina no
    meio, sem um segundo laço de limpeza -- e que dá a FR-023 um ponto de
    escrita só.
    """
    entry = match.stack.pop()

    _apply_while_the_match_is_live(match, entry, catalog=catalog)

    match.player(entry.caster_user_id).graveyard.append(entry.card)


def _apply_while_the_match_is_live(
    match: Match, entry: StackEntry, *, catalog: CardCatalog
) -> None:
    """Revalida o alvo (§6) e aplica, ou não faz nada.

    Duas saídas sem efeito, e as duas mandam a carta ao cemitério do mesmo jeito:

        1. a partida já acabou -- nada abaixo do feitiço que a encerrou resolve
        2. o feitiço mira e o alvo não está mais em campo -- **fizzle**

    Feitiço sem alvo nunca cai no caso 2: `target_card_instance_id is None`
    significa "não mira nada", nunca "o alvo sumiu", e o docstring de
    `StackEntry` já separa as duas perguntas.
    """
    if match.is_over:
        return

    target = _revalidated_target(match, entry)

    if entry.target_card_instance_id is not None and target is None:
        return

    apply_spell_effect(
        match,
        match.player(entry.caster_user_id),
        _spell_of(entry, catalog).effect,
        target,
        catalog=catalog,
    )


def _revalidated_target(match: Match, entry: StackEntry) -> BankUnit | None:
    """A revalidação da §6, por identificador.

    `Match.bank_unit` foi escrita para isto, e o docstring dela diz assim:
    "`None` não é erro: é a resposta que autoriza o fizzle". Nenhuma busca nova
    é escrita aqui.

    Não repete a checagem de lado da §5B: um alvo que era aliado no lançamento
    continua sendo o alvo, e ele não muda de banco durante uma resolução --
    ninguém age dentro dela.
    """
    if entry.target_card_instance_id is None:
        return None

    return match.bank_unit(entry.target_card_instance_id)


def _spell_of(entry: StackEntry, catalog: CardCatalog) -> Spell:
    """O molde da carta empilhada, estreitado para `Spell`.

    Braço impossível: `cast_spell` provou que a carta é feitiço antes de
    empilhá-la. A recusa nomeada está aqui em vez de `assert` -- que some com
    `-O` -- e de `cast`, que calaria o mypy sem responder a pergunta. É o mesmo
    tratamento que `round_end._swap_token` dá ao dono de token ausente.
    """
    template = catalog.card(entry.card.card_id)

    if not isinstance(template, Spell):
        raise CardIsNotASpellError(entry.card, template.card_type)

    return template


def _reopen_action_phase(match: Match, initiator_user_id: int) -> None:
    """Passo 3 da §6, e a saída para a Fase de Ação.

    O `return` da partida terminada não é defesa contra o impossível: sem ele, a
    resolução que encerrou a partida a devolveria a `ACTION` e apagaria
    `FINISHED` -- exatamente o estado que esta feature existe para não produzir.

    A rodada **não** fecha aqui, e é a zeragem abaixo que consome os dois passes
    que dispararam a resolução.
    """
    if match.is_over:
        return

    match.consecutive_passes = 0
    match.priority_user_id = initiator_user_id
    match.phase = MatchPhase.ACTION
