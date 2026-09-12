"""As recusas do socket de matchmaking, com códigos estáveis.

Mesma razão de `refusal_codes.py`, que faz isto para o socket de partida: o
cliente Unity casa recusa por texto estável, e a mensagem carrega os valores
ofensores -- o `deck_id` pedido, a carta que passou do limite --, então ela não
serve de chave. O código serve.

`DECK_NOT_FOUND` cobre **dois** casos de propósito: o deck não existe, e o deck
é de outro jogador. Um código próprio para cada um já responderia "esse deck
existe" a quem não deveria saber.

O contrato inteiro está em
`specs/011-deck-catalog-api/contracts/matchmaking_messages.md`.
"""

# `join_queue` sem `deck_id`, ou com um que não é inteiro.
DECK_NOT_SPECIFIED = "deck_not_specified"

# O deck não existe, **ou** é de outro jogador. Mesmo código, mesmo texto.
DECK_NOT_FOUND = "deck_not_found"

# O deck é do jogador e não passa nas três regras da feature 001. A recusa leva
# `deck_problems` ao lado do texto.
INVALID_DECK = "invalid_deck"
