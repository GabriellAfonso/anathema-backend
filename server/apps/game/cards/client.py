"""Handle do catálogo para o processo inteiro.

Mesmo papel de `match/client.py` e `matchmaking/client.py`: o ponto de
composição da aplicação, e o único lugar que chama a fábrica. Todo o resto
recebe um `CardCatalog` por parâmetro.

Em cache porque `mvp_catalog()` constrói e **valida** um catálogo a cada
chamada -- duplicata, faixa de identificador, índice. O catálogo é imutável em
tempo de execução, então uma instância por processo é a resposta certa, e
também evita que dois consumidores comparem cartas de índices diferentes.
"""

from functools import cache

from .catalog import CardCatalog
from .mvp_catalog import mvp_catalog


@cache
def get_card_catalog() -> CardCatalog:
    """O catálogo do processo.

    Views e consumers recebem o catálogo por parâmetro, então testes injetam o
    deles em vez de alcançar isto.

    >>> get_card_catalog() is get_card_catalog()
    True
    """
    return mvp_catalog()
