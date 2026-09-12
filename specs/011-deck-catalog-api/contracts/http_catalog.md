# Contrato: o catálogo pelo HTTP

**Feature**: `011-deck-catalog-api`

Somente leitura, igual para todo mundo, imutável durante a partida.

## `GET /game/cards/`

**Autenticação**: `Authorization: Bearer <access token>`. Sem token: `401`.

**Resposta `200`**

```json
{
  "cards": [
    {
      "card_id": 1,
      "card_type": "unit",
      "name": "JOHN COPPER",
      "energy": 5,
      "image": "john_card",
      "attack": 7,
      "health": 5
    },
    {
      "card_id": 1004,
      "card_type": "spell",
      "name": "LIFE POTION",
      "energy": 4,
      "image": "life_potion",
      "description": "Você recupera 5 de Nexus.",
      "effect": {
        "requires_target": false,
        "target_kind": "none",
        "duration": "permanent",
        "declaration_only": false
      }
    }
  ]
}
```

- 29 cartas: 24 unidades e 5 feitiços.
- Ordenadas por `card_id`, crescente.
- A resposta é idêntica para qualquer requisitante autenticado e não depende de
  partida em curso.
- Nenhum campo se chama `id`.

## Campos

### Comuns

| Campo | Tipo | Nota |
|---|---|---|
| `card_id` | int | único em todo o catálogo |
| `card_type` | `"unit"` \| `"spell"` | conjunto fechado |
| `name` | str | |
| `energy` | int | custo |
| `image` | str | chave da arte, resolvida pelo cliente |

### Só unidade

| Campo | Tipo |
|---|---|
| `attack` | int |
| `health` | int |

### Só feitiço

| Campo | Tipo | Nota |
|---|---|---|
| `description` | str | português, **para o jogador ler** |
| `effect` | objeto | **para o cliente decidir**, ver abaixo |

O cliente MUST decidir a mira pelos campos de `effect`. Decisão de regra tomada
lendo `description` é bug — é a mesma regra que o motor segue.

### `effect`

| Campo | Tipo | Valores |
|---|---|---|
| `requires_target` | bool | `target_kind != "none"` |
| `target_kind` | str | `"none"`, `"allied_unit"`, `"enemy_unit"` |
| `duration` | str | `"permanent"`, `"until_end_of_round"` |
| `declaration_only` | bool | `true` = só na declaração de ataque |

Os dois conjuntos são fechados e estáveis, e usam o mesmo texto que o motor.

**Como o cliente lê**:

| `requires_target` | `target_kind` | O que o cliente faz |
|---|---|---|
| `false` | `none` | manda a jogada sem alvo; **não** desenha mira |
| `true` | `allied_unit` | pede uma unidade do próprio banco |
| `true` | `enemy_unit` | pede uma unidade do banco do oponente |

`declaration_only: true` mantém a carta indisponível fora da declaração de
ataque.

Mandar alvo num feitiço `none`, ou omiti-lo num que exige, é recusado pelo
socket de partida com os códigos da feature 009 (`spell_takes_no_target`,
`spell_needs_target`, `wrong_spell_target_side`,
`spell_only_in_declaration`). O contrato acima existe para que isso não
aconteça.

## Estabilidade

- Acrescentar carta ao catálogo acrescenta um item à lista. Não é quebra.
- Acrescentar campo a uma carta não é quebra.
- Remover ou renomear campo, ou acrescentar valor a `card_type`, `target_kind`
  ou `duration`, **é** quebra: o cliente compara esses textos.
