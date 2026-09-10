"""Uma fotografia comparável do estado inteiro de uma partida.

Existe para os testes de recusa. A §5 exige que uma ação ilegal deixe a partida
**exatamente** como estava, e provar isso campo a campo à mão significaria a
mesma dúzia de comparações repetida em cada teste -- com a chance de cada cópia
esquecer um campo. Os dois contadores da partida são justamente os que mais
fácil se esquece, e são os que FR-050 quer conferir.

Passa por `to_match_document` em vez de comparar objetos: o documento é um
`TypedDict` de tipos primitivos, comparável por `==` até o fundo, e é o mesmo
caminho que a feature 002 usa para provar a ida e a volta pelo Redis. Nenhum
campo fica de fora, porque a serialização é a que já precisa conhecer todos.

`copy.deepcopy` mais `==` não serviria: `Match` e as dataclasses da árvore usam
`slots=True` sem `eq` em todos os níveis, e a comparação sairia por identidade
em alguns deles -- passando sem provar nada.

Não é um fake: não substitui I/O nenhum, e por isso é uma função e não uma
classe.

>>> before = match_snapshot(match)
>>> with pytest.raises(NotYourPriorityError):
...     submit_action(match, action, catalog=catalog, randomness=source)
>>> match_snapshot(match) == before
True
"""

from apps.game.match import Match, MatchDocument, to_match_document


def match_snapshot(match: Match) -> MatchDocument:
    """O estado inteiro da partida como um documento comparável.

    >>> match_snapshot(match)["round_number"]
    1
    """
    return to_match_document(match)
