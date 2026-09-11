# Contrato — a Resolução de Pilha (§6) e a cascata

**Feature**: `006-spell-stack-effects` | **Data**: 2026-09-10

`apps.game.engine.stack_resolution` e as edições em
`apps.game.engine.round_cycle`. Assinaturas são o contrato; corpos são da
implementação.

A razão do desenho está em [research.md](../research.md) D6, D10, D11 e D12.

---

## 1. `resolve_stack` não é exportada pelo pacote

```python
def resolve_stack(match: Match, *, catalog: CardCatalog) -> None:
```

`apps.game.engine.__init__` **não** a reexporta, pelo mesmo argumento que a
feature 005 usou para `run_upkeep` e `end_round` e escreveu no `__all__`:
expô-la daria uma porta por onde executar meia rodada — o contrário do que a
cascata garante. Quem a chama é `round_cycle`; quem a testa importa do módulo.

---

## 2. A §6 inteira

```python
def resolve_stack(match: Match, *, catalog: CardCatalog) -> None:
    """A §6: a pilha inteira resolve, do topo para a base, numa passagem só.

    **A prioridade não é devolvida entre um feitiço e o seguinte.** Quem conhece
    outros jogos de carta espera que seja; aqui não é.

    Assume a pilha não vazia -- a saída da §5 que a dispara já verificou. Pilha
    vazia é bug de chamador, como a fase de entrada é para `run_upkeep`.

    >>> resolve_stack(match, catalog=catalog)
    >>> match.stack
    []
    """
    initiator_user_id = match.stack[0].caster_user_id

    while match.stack:
        _resolve_top(match, catalog=catalog)

    _reopen_action_phase(match, initiator_user_id)
```

O iniciador é lido **antes** do laço: a pilha esvazia durante a resolução, e
`match.stack[0]` depois dela é `IndexError`. Variável local e não campo do
estado — o valor só existe durante a resolução, e a resolução acontece inteira
dentro de uma chamada (research D12).

```python
def _resolve_top(match: Match, *, catalog: CardCatalog) -> None:
    """Uma entrada: aplica se couber, e manda a carta ao cemitério sempre.

    O `pop` acontece antes de qualquer decisão, e o cemitério depois de todos os
    caminhos. É isso que faz a pilha esvaziar mesmo quando a partida termina no
    meio, sem um segundo laço de limpeza.
    """
    entry = match.stack.pop()

    _apply_while_the_match_is_live(match, entry, catalog=catalog)

    match.player(entry.caster_user_id).graveyard.append(entry.card)
```

```python
def _apply_while_the_match_is_live(
    match: Match, entry: StackEntry, *, catalog: CardCatalog
) -> None:
    """Revalida o alvo (§6) e aplica, ou não faz nada.

    Três saídas sem efeito, e as três mandam a carta ao cemitério do mesmo
    jeito:

        1. a partida já acabou -- nada abaixo do feitiço que a encerrou resolve
        2. o feitiço mira e o alvo não está mais em campo -- **fizzle**
        3. (nenhuma outra)

    Feitiço sem alvo nunca cai no caso 2: `target_card_instance_id is None`
    significa "não mira nada", nunca "o alvo sumiu".
    """
```

```python
def _reopen_action_phase(match: Match, initiator_user_id: int) -> None:
    """Passo 3 da §6, e a saída para a Fase de Ação.

    O `return` da partida terminada não é defesa contra o impossível: sem ele, a
    resolução que encerrou a partida a devolveria a `ACTION` e apagaria
    `FINISHED` -- exatamente o estado que esta feature existe para não produzir.

    A rodada **não** fecha aqui. Os dois passes que dispararam a resolução foram
    consumidos por ela, e é a zeragem abaixo que os consome.
    """
    if match.is_over:
        return

    match.consecutive_passes = 0
    match.priority_user_id = initiator_user_id
    match.phase = MatchPhase.ACTION
```

---

## 3. A revalidação é `Match.bank_unit()`

Nenhuma busca nova. A feature 002 escreveu o método para isto, e o docstring
dela diz assim: *"É a revalidação de alvo da §6, e `None` não é erro: é a
resposta que autoriza o fizzle."*

| `entry.target_card_instance_id` | `match.bank_unit(...)` | resultado |
|---|---|---|
| `None` | — | aplica, com `target=None`. Nunca fizzla. |
| um identificador | um `BankUnit` | aplica, com aquele `BankUnit` |
| um identificador | `None` | **fizzle** — não aplica nada |

A revalidação **não** repete a checagem de lado da §5B. Um alvo que era aliado
no lançamento continua sendo o alvo; ele não muda de banco durante uma
resolução, porque ninguém age dentro dela.

---

## 4. O molde do feitiço vem do catálogo

`catalog.card(entry.card.card_id)` precisa ser estreitado para `Spell` antes de
ler `.effect`. O estreitamento é um `isinstance` que levanta
`CardIsNotASpellError` no braço impossível — nunca `assert`, que some com `-O`,
nem `cast`, que calaria o mypy sem responder a pergunta.

É o mesmo tratamento que `round_end._swap_token` dá ao `token_holder_user_id`
`None`: uma recusa nomeada para um estado que só existe se algo já estiver
corrompido. `cast_spell` já provou que a carta é feitiço antes de empilhá-la.

---

## 5. As edições em `round_cycle.py`

### 5.1 O braço novo do despacho de ação

```python
match action:
    case PlayUnitAction():
        play_unit(match, actor, action, catalog=catalog)
    case CastSpellAction():                       # NOVO
        cast_spell(match, actor, action, catalog=catalog)
    case PassAction():
        _pass_turn(match)
```

`_exit_action_phase` **não muda**. A condição da pilha cheia que a feature 005
escreveu sem consumidor passa a ter um.

### 5.2 A fase entra na cascata

```python
_AUTOMATIC_PHASES = frozenset(
    {MatchPhase.STACK_RESOLUTION, MatchPhase.ROUND_END, MatchPhase.UPKEEP}
)
```

O comentário da feature 005 que explicava a ausência sai daqui — a dívida que
ele registrava está paga.

```python
def _run_automatic_phase(
    match: Match, randomness: RandomSource, catalog: CardCatalog
) -> None:
    """Um passo da cascata. Cada fase automática sabe para onde vai."""
    if match.phase is MatchPhase.STACK_RESOLUTION:
        resolve_stack(match, catalog=catalog)
        return

    if match.phase is MatchPhase.ROUND_END:
        end_round(match)
        return

    run_upkeep(match, randomness=randomness)
```

`_settle` e `_run_automatic_phase` passam a receber `catalog`. `submit_action`
já o recebe, e já o exige até de um passe que não o usa — a razão está no
docstring dela: *"a porta é uma só, e recebe o que a mais cara das ações
precisa."*

### 5.3 A terminação continua provável, e mais curta

| De | Para | Volta |
|---|---|---|
| `STACK_RESOLUTION` | `ACTION` ou `FINISHED` | 1 |
| `ROUND_END` | `UPKEEP` | 1 |
| `UPKEEP` | `ACTION` | 2 |

Máximo de duas voltas, como antes. `STACK_RESOLUTION` nunca leva a `ROUND_END`
porque zera os passes antes de devolver `ACTION`, e `FINISHED` não está em
`_AUTOMATIC_PHASES` — a cascata para nele.

---

## 6. Garantias

- **A pilha esvazia sempre.** `match.stack == []` depois de `resolve_stack`,
  inclusive quando a partida terminou no meio.
- **Toda carta vai ao cemitério do lançador**, resolvida, fizzlada ou não
  aplicada. Um ponto de escrita só.
- **A prioridade volta para quem abriu a pilha** — `stack[0].caster_user_id` lido
  antes do primeiro `pop` —, que quase nunca é quem lançou o último feitiço.
- **A rodada não fecha.** `round_number` é o mesmo antes e depois.
- **Ninguém observa `STACK_RESOLUTION`.** É fase de passagem, como `UPKEEP` e
  `ROUND_END`: `submit_action` devolve a partida já estabilizada.
- **Nada de energia nem de compra.** A resolução não desconta energia e não faz
  ninguém comprar carta.
