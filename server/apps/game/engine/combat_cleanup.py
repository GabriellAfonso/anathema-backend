"""A §7.4 e a §7.5: o que sobra do dano, e a volta para a Fase de Ação.

Disparada por `EndDefenseWindowAction`, e é **dentro desta chamada** que o
combate inteiro acontece: o dano da §7.3, a varredura da §7.4 e a devolução da
vez. Quando a ação retorna, a partida está esperando ação -- nunca parada em
Combate.

A §10 é apurada dentro de `resolve_combat_damage`, no fim da §7.3, e **não** de
novo aqui. O passo 3 da §7.4 manda verificar a vitória, e a resposta é a mesma:
entre o dano e ele nada altera Nexus -- enterrar unidade não mexe em Nexus --, e
uma segunda chamada seria a segunda apuração que a §7.3 existe para não ter,
ainda que idempotente.

Sobrevivente não é movido por ninguém. Unidade que ataca ou bloqueia nunca sai
do banco do dono, então "os sobreviventes voltam pro banco" vale por construção
-- não existe zona de combate, e `BankUnit` diz de si mesmo que existe só
enquanto está no banco.
"""

from apps.game.cards import CardCatalog
from apps.game.match import Match, MatchPhase

from .combat_damage import resolve_combat_damage
from .unit_damage import bury_dead_units


def end_combat(match: Match, *, catalog: CardCatalog) -> None:
    """A §7.3 e a §7.4 inteiras, na ordem da nota.

    Três passos e nenhuma condição: o dano, a varredura dos dois bancos, e a
    saída. A varredura é a que já existe, e o docstring dela diz que foi escrita
    com essa largura prevendo este chamador.

    >>> end_combat(match, catalog=catalog)
    >>> match.phase
    <MatchPhase.ACTION: 'action'>
    """
    resolve_combat_damage(match, catalog=catalog)
    bury_dead_units(match, catalog=catalog)
    _leave_combat(match)


def _leave_combat(match: Match) -> None:
    """Passo 4 da §7.4, e o único ponto que apaga o par `(combat, phase)`.

    O `combat = None` fica **antes** do `return`: um combate que encerra a
    partida pelo próprio dano também terminou, e o estado dele some junto. O
    único `CombatState` que sobrevive é o do combate interrompido por um feitiço
    dentro da janela, que nunca chega aqui -- e é ele que registra que o combate
    não resolveu.

    O `return` da partida terminada não é defesa contra o impossível: sem ele, o
    combate que encerrou a partida a devolveria a `ACTION` e apagaria
    `FINISHED`.

    `priority_user_id` recebe `token_holder_user_id` sem estreitamento: os dois
    campos são `int | None`, e a §7.4 manda devolver a vez a quem declarou.
    """
    match.combat = None

    if match.is_over:
        return

    match.consecutive_passes = 0
    match.priority_user_id = match.token_holder_user_id
    match.phase = MatchPhase.ACTION
