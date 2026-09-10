# Contrato — a superfície pública do setup

**Feature**: `003-match-setup` | **Data**: 2026-09-10

Três superfícies: `apps.game.randomness` (nova), `apps.game.engine` (nova) e as
mudanças no que `apps.game.match` já exporta. Assinaturas são o contrato;
corpos são da implementação.

Todos os pacotes declaram `__all__` explícito — `mypy.ini` roda com `strict`,
que liga `no_implicit_reexport`, então sem a lista ninguém importa do pacote.

---

## 1. `apps.game.randomness`

```python
RandomSeed = NewType("RandomSeed", str)


def new_random_seed() -> RandomSeed:
    """Semente nova, de entropia do sistema. Chamada no ponto de composição.

    >>> match = start_match(..., seed=new_random_seed())
    """


@dataclass(frozen=True, slots=True)
class Roll:
    """Um sorteio identificado: onde, no espaço de aleatoriedade da partida.

    Cunhado só por `Match.mint_roll()`.

    >>> Roll(RandomSeed("abc"), 3).ordinal
    3
    """

    seed: RandomSeed
    ordinal: int


class RandomSource(Protocol):
    """Aleatoriedade atrás de uma interface do projeto, injetada por parâmetro.

    Duas chamadas com o mesmo `Roll` devolvem o mesmo resultado, em qualquer
    processo. Implementações não guardam estado entre chamadas.
    """

    def shuffled(self, items: Sequence[T], roll: Roll) -> list[T]:
        """Permutação de `items`. Lista nova; a original não é tocada.

        >>> source.shuffled(deck, match.mint_roll())
        """

    def choose(self, options: Sequence[T], roll: Roll) -> T:
        """Um dos `options`. Levanta se a sequência for vazia.

        >>> source.choose(match.players, match.mint_roll()).user_id
        9
        """


class SeededRandomSource:
    """`RandomSource` sobre `random.Random`, semeado por `(seed, ordinal)`.

    A única coisa do projeto que toca o módulo `random`.

    >>> SeededRandomSource().shuffled([1, 2, 3], Roll(RandomSeed("s"), 1))
    [3, 1, 2]
    """
```

---

## 2. `apps.game.engine`

### `match_setup.py`

```python
@dataclass(frozen=True, slots=True)
class MatchEntry:
    """Um jogador chegando à partida com o deck dele.

    Perfil e deck viajam juntos para que não possam ser trocados de par.

    >>> MatchEntry(profile=await get_player_public_data(7), deck=deck).deck[0]
    15
    """

    profile: PlayerData
    deck: Deck


class InvalidPlayerDeckError(Exception):
    """Deck recusado, dizendo de quem era e todos os problemas de uma vez.

    Envolve `deck_problems()` da feature 001; não reimplementa nenhuma regra.

    >>> raise InvalidPlayerDeckError(7, problems)
    InvalidPlayerDeckError: deck of user 7 was refused: deck has 39 cards,
    expected exactly 40; card_id 15 appears 4 times, limit is 3
    """

    user_id: int
    problems: tuple[DeckProblem, ...]


def start_match(
    first: MatchEntry,
    second: MatchEntry,
    *,
    catalog: CardCatalog,
    randomness: RandomSource,
    seed: RandomSeed,
) -> Match:
    """A §3 até a espera do mulligan: valida, materializa, embaralha, compra 4.

    Os dois decks são validados antes de qualquer outra coisa; deck recusado
    não deixa partida nenhuma nascer.

    A partida volta em `MatchPhase.MULLIGAN`, sem dono de token e sem
    prioridade — quem sorteia é `finish_setup`, quando os dois responderem.

    >>> match = start_match(one, two, catalog=catalog,
    ...                     randomness=SeededRandomSource(), seed=seed)
    >>> match.phase
    <MatchPhase.MULLIGAN: 'mulligan'>
    >>> len(match.players[0].hand), len(match.players[0].deck)
    (4, 36)
    """


def finish_setup(match: Match, *, randomness: RandomSource) -> None:
    """Sorteia o token, compensa quem não o recebeu, posiciona para o Upkeep.

    Chamada por `record_mulligan` quando o segundo jogador responde. Não faz
    nada se ainda houver mulligan pendente.

    >>> finish_setup(match, randomness=source)
    >>> match.phase, len(match.player(match.token_holder_user_id).hand)
    (<MatchPhase.UPKEEP: 'upkeep'>, 4)
    """
```

### `mulligan.py`

```python
class MulliganAlreadyTakenError(Exception):
    """Este jogador já respondeu. Uma vez por partida.

    Também é a recusa de um mulligan que chega depois do setup terminado: os
    dois jogadores estão marcados, então não existe janela aberta.

    >>> raise MulliganAlreadyTakenError(7, match_id)
    MulliganAlreadyTakenError: user 7 already took the mulligan in match
    '3f2a...': it is once per match
    """

    user_id: int
    match_id: str


class CardNotInHandError(Exception):
    """A seleção cita uma carta que não está na mão daquele jogador.

    Cobre também o identificador repetido: a segunda ocorrência já não está
    entre as cartas restantes.

    >>> raise CardNotInHandError(CardInstanceId(12), 7)
    CardNotInHandError: card instance 12 is not in the hand of user 7:
    expected one of [3, 4, 5, 6]
    """

    card_instance_id: CardInstanceId
    user_id: int


def record_mulligan(
    match: Match,
    user_id: int,
    selection: Sequence[CardInstanceId],
    *,
    randomness: RandomSource,
) -> None:
    """A escolha de um jogador, aplicada na ordem que a §3 exige.

    Valida tudo antes de mutar qualquer coisa: `user_id` que não joga,
    mulligan repetido e carta fora da mão deixam o estado como estava.

    Depois: as escolhidas saem da mão, o jogador compra a mesma quantidade,
    **só então** as devolvidas voltam ao deck, e o deck é reembaralhado. Uma
    carta devolvida não pode ser recomprada na reposição, e volta com o
    identificador que já tinha.

    Se este for o segundo mulligan, chama `finish_setup` e a partida sai da
    espera.

    >>> record_mulligan(match, 7, [], randomness=source)     # trocar 0 é válido
    >>> match.awaiting_mulligan_user_ids
    (9,)
    """
```

### `card_draw.py`

```python
class EmptyDeckError(Exception):
    """Compra de um deck vazio, citando o dono.

    Não acontece no setup — 40 cartas, 5 compras. A regra geral da §9 chama
    isto depois do reset de deck, então também não vê deck vazio: chegar aqui
    é bug, não fluxo.
    """

    user_id: int


def draw_from_deck_top(player: PlayerState) -> MatchCard:
    """Tira a carta do topo do deck e põe no fim da mão. Devolve a carta.

    O movimento compartilhado: o setup compra 4, o mulligan compra a
    reposição, a compensação compra 1, e o Upkeep da §9 vai comprar 1. O teto
    de mão e o reset de deck da §9 são checagens **em volta** desta função, não
    dentro dela.

    >>> draw_from_deck_top(player).card_instance_id
    3
    """
```

---

## 3. `apps.game.match` — o que muda

```python
class MatchPhase(StrEnum):
    MULLIGAN = "mulligan"        # NOVO
    UPKEEP = "upkeep"
    ACTION = "action"
    STACK_RESOLUTION = "stack_resolution"
    COMBAT = "combat"
    ROUND_END = "round_end"


@dataclass(slots=True)
class Match:
    match_id: str
    players: tuple[PlayerState, PlayerState]
    random_seed: RandomSeed                       # NOVO, obrigatório
    token_holder_user_id: int | None = None       # era int obrigatório
    priority_user_id: int | None = None           # era int obrigatório
    phase: MatchPhase = MatchPhase.MULLIGAN       # era UPKEEP
    next_roll_ordinal: int = 1                    # NOVO
    ...                                           # o resto inalterado

    # start() REMOVIDO — quem cria partida é engine.start_match

    def mint_roll(self) -> Roll:
        """Cunha o próximo sorteio desta partida.

        Único ponto que produz um `Roll`, como `mint_card_instance_id` é o
        único que produz identidade de carta.

        >>> match.mint_roll().ordinal
        1
        """

    @property
    def awaiting_mulligan_user_ids(self) -> tuple[int, ...]:
        """De quem o setup ainda espera. Vazia = pronto para o sorteio.

        Derivada de `mulligan_taken`, nunca gravada: uma segunda lista a manter
        em sincronia daria espera eterna quando alguém esquecesse de atualizar.

        >>> match.awaiting_mulligan_user_ids
        (7, 9)
        """


@dataclass(slots=True)
class PlayerState:
    mulligan_taken: bool = False                  # NOVO
    ...                                           # o resto inalterado
```

### `store.py`

```python
class MatchStore:
    """Partidas endereçadas por `match_id`. Cliente Redis injetado.

    Cada partida é um hash de dois campos: `state`, o documento JSON, e
    `version`, quantas vezes a partida foi escrita. A versão existe só para o
    compare-and-swap de `mutate` — **não** é versão de esquema, que continua
    não existindo.

    >>> store = MatchStore(Redis.from_url("redis://localhost:6379/3"))
    >>> await store.save(match)
    >>> (await store.get(match.match_id)).phase
    <MatchPhase.MULLIGAN: 'mulligan'>
    """

    # create() REMOVIDO — quem cria partida é engine.start_match; quem grava
    # chama save().

    async def get(self, match_id: str) -> Match | None:
        """Partida pelo id, ou None se nunca existiu ou já expirou."""

    async def save(self, match: Match) -> None:
        """Grava o estado e renova o TTL, incondicionalmente.

        Para a criação, onde ninguém mais escreveu ainda. Mutação de partida
        viva usa `mutate`, que não sobrescreve escrita alheia.
        """

    async def mutate(
        self, match_id: str, change: Callable[[Match], None]
    ) -> Match:
        """Lê, aplica `change`, e grava só se ninguém escreveu no meio.

        A gravação é compare-and-swap sobre a versão lida. Versão divergente
        significa que outro worker escreveu: relê e aplica `change` de novo,
        sobre o estado fresco. Uma exceção levantada dentro de `change` aborta
        sem gravar nada.

        É o caminho que o mulligan simultâneo exige — duas conexões,
        possivelmente em workers diferentes, mutando a mesma partida.

        >>> await store.mutate(
        ...     match_id,
        ...     lambda match: record_mulligan(match, 7, cards, randomness=src),
        ... )
        """


class ConcurrentMatchWriteError(Exception):
    """A partida mudou debaixo de tantas tentativas seguidas que desistimos.

    Cita o `match_id` e quantas tentativas foram feitas.
    """
```

---

## 4. `apps.game.cards` — o que muda

```python
def starter_deck(catalog: CardCatalog) -> Deck:
    """Deck de andaime: 40 identificadores válidos, derivados do catálogo.

    Existe porque o matchmaking precisa entregar um deck e a origem real —
    deck de jogador guardado em banco — é outra feature. Não é escolha de
    balanceamento, não é contrato, e sai quando aquela feature entrar.

    Deriva do catálogo em vez de listar 40 números à mão para que continue
    válido quando o catálogo mudar.

    >>> len(starter_deck(mvp_catalog()))
    40
    >>> deck_problems(starter_deck(mvp_catalog()), mvp_catalog())
    ()
    """
```

---

## 5. Fora do contrato

Não entram nesta feature, e nenhum símbolo acima os pressupõe:

- `handle_mulligan` em `MatchConsumer`, e qualquer envelope de mensagem.
- O Upkeep da §4 — `finish_setup` para na porta dele.
- As duas condições da §9 (teto de mão, reset de deck) em volta de
  `draw_from_deck_top`.
- Timeout do mulligan (§13).
