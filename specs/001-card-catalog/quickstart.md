# Quickstart — validar o catálogo de cartas

**Feature**: Catálogo de Cartas do MVP (`001-card-catalog`)
**Data**: 2026-09-09

Como provar que a feature está de pé. Detalhe de campo em
[data-model.md](./data-model.md), assinaturas em
[contracts/card_catalog.md](./contracts/card_catalog.md).

## Pré-requisitos

- Ambiente de desenvolvimento instalado: `pip install -r server/requirements-dev.txt`
  (traz `requirements.txt` junto, mais pytest, mypy e black).
- Nenhuma dependência nova para a feature em si, nenhum serviço externo. O
  catálogo é memória pura: Redis e banco não precisam estar de pé para nada
  aqui.

Todos os comandos rodam de `server/`:

```bash
cd server
```

## Portas de qualidade

As três da constituição, na ordem em que falham mais barato:

```bash
mypy                       # strict + warn_unreachable, sem relaxação nova
pytest                     # a suíte inteira
black --check .            # limpo é a condição; sem --check ele reescreve
```

Só desta feature:

```bash
pytest apps/game/tests/test_card_catalog.py \
       apps/game/tests/test_spell_effects.py \
       apps/game/tests/test_deck_rules.py \
       apps/game/tests/test_mvp_catalog.py
```

## Cenários de validação

Cada um mapeia para uma user story da spec. Rodam no shell do Django
(`python manage.py shell`) ou como teste.

### 1. Buscar carta por identificador (US1)

```python
from apps.game.cards import mvp_catalog

catalog = mvp_catalog()

catalog.card(1).name        # 'JOHN COPPER'
catalog.card(1).health      # 5   -- era `defense` no jogo anterior
catalog.card(1001).name     # "SOMEONE'S SHIELD"
```

**Esperado**: unidade devolve `card_type` `unit`, nome, `energy`, `attack`,
`health`, `image`. Feitiço devolve `card_type` `spell`, `description` e
`effect`.

### 2. Identificador desconhecido nomeia o que foi pedido (US1)

```python
catalog.card(9999)
```

**Esperado**: `UnknownCardError`, e o texto da exceção contém `9999`. Mensagem
genérica é falha do cenário, não detalhe de estilo (FR-018).

### 3. Efeito estruturado, sem ler português (US2)

```python
effect = catalog.card(1005).effect        # SUMMONED AX

effect.requires_target      # True
effect.target_kind          # TargetKind.ENEMY_UNIT
effect.duration             # EffectDuration.PERMANENT
effect.amount               # 3
```

**Esperado**: os cinco feitiços batem com a tabela *Efeitos do MVP* da spec.
Confira em particular:

| `card_id` | Feitiço | `requires_target` | `target_kind` | `duration` |
|---|---|---|---|---|
| 1001 | SOMEONE'S SHIELD | `True` | `ALLIED_UNIT` | `PERMANENT` |
| 1002 | MAGIC BARRIER | `True` | `ALLIED_UNIT` | `UNTIL_END_OF_ROUND` |
| 1003 | SACRIFICIAL FIRE | `False` | `NONE` | `PERMANENT` |
| 1004 | LIFE POTION | `False` | `NONE` | `PERMANENT` |
| 1005 | SUMMONED AX | `True` | `ENEMY_UNIT` | `PERMANENT` |

Nenhuma dessas leituras toca `description`.

### 4. Listagem (US3)

```python
len(catalog.all_cards())    # 29
len(catalog.units())        # 24
len(catalog.spells())       # 5
```

**Esperado**: nenhum feitiço em `units()`, nenhuma unidade em `spells()`. Em um
catálogo sem feitiços, `spells()` devolve tupla vazia — não levanta.

### 5. Deck válido é aceito (US4)

```python
from apps.game.cards import deck_problems, DECK_SIZE

deck = [1, 1, 1, 2, 2, 2, 3, 3, 3, ...]     # 40 ids, no máximo 3 iguais
deck_problems(deck, catalog)                # ()
```

**Esperado**: tupla vazia.

### 6. Deck inválido nomeia o problema concreto (US4)

```python
problems = deck_problems([1] * 40, catalog)
[p.message for p in problems]
```

**Esperado**: a mensagem cita o `card_id` `1` e a contagem `40` contra o limite
`3`. Três violações a checar, uma por regra:

| Deck | Problema esperado | A mensagem contém |
|---|---|---|
| 39 ids válidos | `WrongDeckSize` | `39` e `40` |
| 40 ids, um repetido 4× | `TooManyCopies` | o `card_id` e `4` |
| 40 ids, um inexistente | `UnknownDeckCard` | o `card_id` desconhecido |

### 7. Todos os problemas em uma passada (US4)

```python
problems = deck_problems([9999] * 41, catalog)
```

**Esperado**: pelo menos dois problemas — tamanho errado **e** identificador
desconhecido **e** excesso de cópias. Parar no primeiro é falha (FR-025).

### 8. O catálogo não muda (FR-026)

```python
import dataclasses
card = catalog.card(1)
card.health = 99
```

**Esperado**: `dataclasses.FrozenInstanceError`. E `catalog.card(1).health`
continua `5`.

### 9. Catálogo pequeno injetado (FR-029, SC-007)

```python
from apps.game.tests.fake_card_catalog import FakeCardCatalog

small = FakeCardCatalog([sample_unit, sample_spell])
len(small.all_cards())      # 2
```

**Esperado**: qualquer consumidor que aceite `CardCatalog` funciona com este
sem nenhuma alteração de código.

### 10. Conferência contra os dados de origem (SC-001)

`test_mvp_catalog.py` compara as 29 cartas com o apêndice *Dados de Origem* da
spec: `card_id`, nome, `energy`, `attack`, `health`, `image`.

**Esperado**: 0 divergências. Confere também as faixas — as 24 unidades entre
1 e 1000, os 5 feitiços em 1001 ou acima (SC-008).

## Como saber que terminou

- `mypy` verde, sem relaxação nova em `mypy.ini`.
- `pytest` verde, a suíte inteira.
- Os 10 cenários acima batem com o esperado.
- Nenhum arquivo fora de `apps/game/cards/` e `apps/game/tests/` foi tocado.
