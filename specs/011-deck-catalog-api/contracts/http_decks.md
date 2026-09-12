# Contrato: os decks do jogador pelo HTTP

**Feature**: `011-deck-catalog-api`

Toda rota exige `Authorization: Bearer <access token>`. Sem token: `401`.

Toda rota opera **só sobre os decks do autenticado**. Deck de outro jogador e
deck inexistente produzem a **mesma** resposta `404`, com o mesmo corpo.

## `GET /players/decks/`

Lista os decks do autenticado.

**`200`**

```json
{
  "decks": [
    {"deck_id": 1, "name": "Deck inicial", "card_ids": [1, 1, 1, 2, 2, 2]},
    {"deck_id": 4, "name": "Agro", "card_ids": [5, 5, 5, 7]}
  ]
}
```

Jogador sem deck nenhum recebe `{"decks": []}` — `200`, não `404`.

A listagem traz **só** os decks do autenticado. Não há parâmetro para listar os
de outro.

## `POST /players/decks/`

Cria um deck.

**Corpo**

```json
{"name": "Agro", "card_ids": [1, 1, 1, 2, 2, 2, "... 40 no total"]}
```

**`201`** — o deck criado, no formato de leitura.

**`400`** — nome inválido, lista inválida, teto atingido, ou um dos dois
campos faltando. Ver *Recusas*.

## `GET /players/decks/<deck_id>/`

**`200`** — `{"deck_id": 4, "name": "Agro", "card_ids": [...]}`

**`404`** — não existe, ou não é seu.

## `PATCH /players/decks/<deck_id>/`

Renomeia, troca a lista, ou as duas coisas.

**Corpo** — pelo menos um dos dois campos:

```json
{"name": "Agro v2"}
{"card_ids": [1, 1, 1, "... 40 no total"]}
{"name": "Agro v2", "card_ids": ["... 40 no total"]}
```

`card_ids` **substitui** a lista inteira; não há edição por carta.

**`200`** — o deck atualizado.

**`400`** — corpo vazio, nome inválido ou lista inválida. O deck guardado
**não** muda.

**`404`** — não existe, ou não é seu.

## `DELETE /players/decks/<deck_id>/`

**`204`** — apagado. Some da listagem; um `GET` seguinte responde `404`.

**`404`** — não existe, ou não é seu.

Apagar é permitido mesmo com o deck em uso: um deck apagado não muda partida em
andamento nem entrada na fila já validada.

## Recusas

### Nome

```json
{"name": ["name is '   ': expected a non-empty name of up to 50 characters"]}
```

`400`. Nome vazio, só espaços, ou acima de 50 caracteres. Nome **repetido** é
aceito: a identidade do deck é o `deck_id`.

### Lista de cartas

`400`, com todos os problemas de uma vez:

```json
{
  "deck_problems": [
    {
      "kind": "wrong_deck_size",
      "found": 39,
      "required": 40,
      "message": "deck has 39 cards, expected exactly 40"
    },
    {
      "kind": "too_many_copies",
      "card_id": 12,
      "count": 4,
      "limit": 3,
      "message": "card_id 12 appears 4 times, limit is 3"
    },
    {
      "kind": "unknown_card",
      "card_id": 9999,
      "message": "card_id 9999 is not in the catalog"
    }
  ]
}
```

- `kind` é a chave estável. `message` é o texto da feature 001, o mesmo no HTTP
  e no websocket.
- As três regras: exatamente 40 cartas, no máximo 3 cópias do mesmo
  identificador, toda carta no catálogo.
- Não existe rascunho: um deck de 12 cartas é recusado com
  `wrong_deck_size {found: 12, required: 40}`.

### Campo faltando na criação

```json
{"detail": "creating a deck needs both 'name' and 'card_ids'"}
```

`400`, só no `POST`. Criar exige `name` **e** `card_ids`: um deck sem lista não
existe, porque não há rascunho a guardar. O `PATCH` aceita um campo só.

### Teto de decks

```json
{"deck_limit": ["player already has 20 decks: the limit is 20"]}
```

`400`, só no `POST`. Renomear, editar e apagar continuam funcionando no teto.

### Não existe, ou não é seu

```json
{"detail": "Não encontrado."}
```

`404`. **O mesmo corpo nos dois casos**, nas cinco operações. Nada na resposta
distingue "esse deck não existe" de "esse deck é de outro jogador".

## Estabilidade

- Acrescentar campo a um deck não é quebra.
- Acrescentar `kind` novo a `deck_problems` não é quebra se o cliente tratar
  desconhecido pela `message`.
- Renomear `deck_id`, `card_ids`, `deck_problems` ou qualquer `kind` **é**
  quebra.
