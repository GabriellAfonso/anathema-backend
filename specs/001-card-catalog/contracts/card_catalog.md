# Contrato — `apps.game.cards`

**Feature**: Catálogo de Cartas do MVP (`001-card-catalog`)
**Data**: 2026-09-09

Esta feature não expõe HTTP nem websocket. A interface pública é a de um pacote
Python consumido por outro código do backend — motor de partida, matchmaking, e
mais tarde a camada que servir a coleção ao cliente. O contrato abaixo é o que
esses consumidores podem depender; qualquer coisa fora daqui é interna e pode
mudar sem aviso.

Detalhes de campo estão em [data-model.md](../data-model.md); aqui ficam as
assinaturas, as pré e pós-condições, e o que quebra.

---

## Obter o catálogo

```python
from apps.game.cards import CardCatalog, mvp_catalog

catalog: CardCatalog = mvp_catalog()
```

`mvp_catalog()` devolve o catálogo das 29 cartas do MVP. Constrói e valida na
chamada; se os dados estiverem inconsistentes, levanta na hora
(`DuplicateCardIdError`, `CardIdOutOfRangeError`) em vez de entregar catálogo
torto.

**Consumidores recebem `CardCatalog` por parâmetro, nunca chamam
`mvp_catalog()` no meio da lógica.** Só o ponto de composição da aplicação
chama a fábrica. É a mesma regra que `MatchStore` segue com o cliente Redis.

```python
class SpellStack:
    def __init__(self, catalog: CardCatalog) -> None:
        self._catalog = catalog
```

---

## `CardCatalog`

`typing.Protocol`. Tipagem estrutural: um substituto de teste só precisa ter os
métodos, não herdar de nada.

### `card(card_id: CardId) -> Card`

Devolve a carta com aquele `card_id`.

- **Pré**: nenhuma.
- **Pós**: devolve `Unit` ou `Spell`. O objeto é congelado — escrever nele
  levanta `FrozenInstanceError`.
- **Erro**: `UnknownCardError` se o `card_id` não existe. A mensagem contém o
  `card_id` pedido (FR-018).
- **Nunca** devolve `None`. Ausência é erro, não valor.

### `all_cards() -> tuple[Card, ...]`

Todas as cartas, ordenadas por `card_id`.

- **Pós**: tupla, não lista — o chamador não tem como alterar a coleção do
  catálogo (FR-026).

### `units() -> tuple[Unit, ...]`

Só as unidades, ordenadas por `card_id`.

- **Pós**: filtra por `card_type is CardType.UNIT`. **Não** filtra por faixa de
  identificador (FR-005).

### `spells() -> tuple[Spell, ...]`

Só os feitiços, ordenados por `card_id`.

- **Pós**: mesma regra de filtro. Tupla vazia é resposta válida, não erro
  (Edge Case da spec).

---

## Ler o efeito de um feitiço

O motor de regras decide pelos campos, nunca pelo texto. `description` existe
para o cliente mostrar ao jogador; ler `description` no motor é violação de
FR-013.

```python
spell = catalog.card(card_id)          # -> Spell
effect = spell.effect

effect.requires_target                 # bool  — derivado de target_kind
effect.target_kind                     # TargetKind — NONE | ALLIED_UNIT | ENEMY_UNIT
effect.duration                        # EffectDuration — PERMANENT | UNTIL_END_OF_ROUND
```

As três propriedades são estáveis: lidas ao aceitar a jogada e de novo ao
resolver a pilha, dão o mesmo resultado (FR-016). São atributos de um objeto
congelado, então isso é garantido pela construção, não por disciplina.

Para saber **o que** o efeito faz, o consumidor casa sobre a classe. A união é
fechada, então o mypy cobra exaustividade:

```python
match effect:
    case BuffUnitHealth(amount=amount): ...
    case PreventUnitDamage(): ...
    case DamageUnit(amount=amount): ...
    case RestoreNexus(amount=amount): ...
    case SacrificeNexusForAttack(nexus_cost=cost, attack_bonus=bonus): ...
```

Aplicar o efeito é da feature da pilha de feitiços, não desta.

---

## Validar um deck

```python
from apps.game.cards import deck_problems, ensure_valid_deck

problems = deck_problems(deck, catalog)   # tuple[DeckProblem, ...]
if problems:
    for problem in problems:
        show(problem.message)

ensure_valid_deck(deck, catalog)          # ou levanta InvalidDeckError
```

### `deck_problems(deck: Deck, catalog: CardCatalog) -> tuple[DeckProblem, ...]`

- **Pré**: `deck` é uma sequência de `CardId`. Repetição é esperada.
- **Pós**: tupla vazia significa deck válido. Caso contrário, **todos** os
  problemas encontrados, em uma passada (FR-025) — não interrompe no primeiro.
- **Nunca levanta** por deck inválido. Deck ruim é valor de retorno, não
  exceção.

### `ensure_valid_deck(deck: Deck, catalog: CardCatalog) -> None`

- **Pós**: retorna silenciosamente se o deck é válido.
- **Erro**: `InvalidDeckError` com todas as mensagens no texto e a tupla
  estruturada em `.problems`.

### Regras aplicadas

| Regra | Constante | Problema gerado |
|---|---|---|
| Exatamente 40 cartas | `DECK_SIZE` | `WrongDeckSize(found, required)` |
| No máximo 3 cópias por `card_id` | `MAX_COPIES_PER_CARD` | `TooManyCopies(card_id, count, limit)` — um por identificador excedente |
| Todo `card_id` existe no catálogo | — | `UnknownDeckCard(card_id)` — um por identificador desconhecido |

Toda `DeckProblem` tem `.message`, e a mensagem contém o valor ofensor. Recusa
genérica não é resposta aceitável (SC-004).

---

## Substituir o catálogo em teste

`CardCatalog` é um `Protocol`, então o teste injeta o que quiser desde que tenha
os quatro métodos. O projeto oferece `FakeCardCatalog` em
`apps/game/tests/fake_card_catalog.py`, com um punhado de cartas, no mesmo
formato de `FakeMatchStore`.

```python
from apps.game.tests.fake_card_catalog import FakeCardCatalog

catalog = FakeCardCatalog([sample_unit, sample_spell])
```

Nenhum consumidor precisa mudar para aceitar o fake — é o mesmo parâmetro
`CardCatalog` de sempre (FR-029).

---

## O que este contrato **não** promete

- **Persistência.** Nada aqui grava ou lê banco. Se o catálogo virar tabela, o
  `card_id` está pronto para ser a chave, mas a migração é outra feature.
- **Identidade de cópia.** Um deck tem até 3 cópias do mesmo `card_id`; quem dá
  identidade a cada cópia na mão ou no banco é a camada de partida.
- **Aplicação de efeito.** O catálogo descreve; a pilha de feitiços executa.
- **Serialização.** Não existe serializer nem payload de websocket nesta
  feature. Quando existir, `card_type` sai no wire como `"type"`.
- **Estabilidade de `card_id` entre expansões.** Se a coleção de unidades passar
  de 1000, quem se move é a faixa de feitiços — `card_id` de unidade já estará
  gravado em deck de jogador.
