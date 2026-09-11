"""O combate em curso: quais unidades atacam, e qual bloqueador cobre qual
atacante.

Nasce na declaração da §7.1, muda durante a janela do defensor da §7.2 e
desaparece na limpeza da §7.4. Quem escreve é o motor — aqui o combate só é
representado, como a pilha em `spell_stack.py`.

As unidades são guardadas por identificador, nunca por referência ao objeto. É
a mesma decisão de `StackEntry`, e pela mesma razão: entre a declaração e a
resolução um feitiço do defensor pode matar um atacante, e a revalidação por
identificador é o que torna o bloqueador órfão da §7.3 possível de perguntar.

O pareamento é uma **lista de pares**, e não um dicionário indexado por
identificador. `documents.py` já escreveu a razão: chave de objeto JSON é
sempre string, e um dicionário indexado por `CardInstanceId` precisaria de uma
conversão na leitura que alguém teria de lembrar — e cujo esquecimento não dá
erro, dá busca que não acha nada.

Quem ataca **não** mora aqui: é o dono do token, e só ele pode declarar ataque
(§5C). Um campo próprio seria a segunda fonte que `PlayerState.user_id` recusa
com a razão escrita no docstring dele.
"""

from dataclasses import dataclass, field

from .cards_in_play import CardInstanceId


@dataclass(slots=True)
class BlockAssignment:
    """Uma unidade do defensor posta na frente de um atacante específico.

    O pareamento da §7.2 é 1 para 1 estrito, e quem mantém a invariante é o
    motor: cada um dos dois identificadores aparece no máximo uma vez na lista
    inteira.

    >>> block = BlockAssignment(CardInstanceId(4), CardInstanceId(3))
    >>> block.attacker_card_instance_id
    3
    """

    blocker_card_instance_id: CardInstanceId
    attacker_card_instance_id: CardInstanceId


@dataclass(slots=True)
class CombatState:
    """O combate em curso. Existe só entre a declaração e a limpeza.

    `attacker_card_instance_ids` nunca é vazia: declarar ataque com zero
    unidades é recusado (§7.1). `blocks` pode ser — o defensor encerrar sem
    bloquear nada é jogada legal, e é essa a diferença entre "combate sem
    bloqueadores" e "sem combate", que é `Match.combat is None`.

    A ordem dos atacantes é a da declaração. Ela é preservada e **não**
    influencia o resultado: o dano da §7.3 é simultâneo.

    >>> combat = CombatState(attacker_card_instance_ids=[CardInstanceId(3)])
    >>> combat.is_attacking(CardInstanceId(3))
    True
    """

    attacker_card_instance_ids: list[CardInstanceId]
    blocks: list[BlockAssignment] = field(default_factory=list)

    def is_attacking(self, card_instance_id: CardInstanceId) -> bool:
        """Se a unidade foi declarada atacante nesta §7.1.

        Não diz se ela ainda está em campo — quem responde isso é
        `Match.bank_unit()`, e as duas perguntas são diferentes: um atacante
        morto por feitiço na janela continua declarado.

        >>> combat.is_attacking(CardInstanceId(3))
        True
        """
        return card_instance_id in self.attacker_card_instance_ids

    def blocker_of(
        self, attacker_card_instance_id: CardInstanceId
    ) -> CardInstanceId | None:
        """Quem cobre aquele atacante, ou `None` se ninguém cobre.

        `None` não é erro: atacante sem bloqueador passa direto (§7.3). Mesma
        escolha de `Match.bank_unit()`, e pela mesma razão.

        >>> combat.blocker_of(CardInstanceId(3)) is None
        True
        """
        for block in self.blocks:
            if block.attacker_card_instance_id == attacker_card_instance_id:
                return block.blocker_card_instance_id

        return None

    def attacker_blocked_by(
        self, blocker_card_instance_id: CardInstanceId
    ) -> CardInstanceId | None:
        """Quem aquele bloqueador cobre, ou `None` se ele não foi atribuído.

        É a pergunta que a remoção da §7.2 faz antes de recusar, e é a inversa
        de `blocker_of` — as duas existem porque as duas perguntas são feitas
        por regras diferentes.

        >>> combat.attacker_blocked_by(CardInstanceId(4))
        3
        """
        for block in self.blocks:
            if block.blocker_card_instance_id == blocker_card_instance_id:
                return block.attacker_card_instance_id

        return None
