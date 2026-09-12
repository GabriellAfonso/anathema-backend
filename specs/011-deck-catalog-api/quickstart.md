# Quickstart: Decks do jogador, e o catálogo servido ao cliente

**Feature**: `011-deck-catalog-api` | **Date**: 2026-09-12

Como provar que a feature funciona ponta a ponta. Os detalhes de payload estão
em [`contracts/`](./contracts/); os de desenho, em
[`data-model.md`](./data-model.md).

## Pré-requisitos

- `docker compose up` com o compose de desenvolvimento (traz Redis e
  `INSTALL_DEV=true`).
- Migração aplicada: `cd server && python manage.py migrate`.
- Uma conta registrada por `POST /accounts/register/` — é o registro que cria o
  perfil e, com esta feature, o deck inicial.
- Um access token de `POST /accounts/login/`, exportado como `$TOKEN`.

## Portas de qualidade

```bash
cd server && pytest
cd server && mypy
cd server && black --check .
```

As três limpas são a condição de pronto, como em toda feature.

## 1. O catálogo

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/game/cards/
```

**Esperado**: `200`, `cards` com 29 itens ordenados por `card_id`, 24 com
`card_type: "unit"` e 5 com `"spell"`.

Confira, em um feitiço, o objeto `effect` com `requires_target`, `target_kind`,
`duration` e `declaration_only`. Confira que nenhum objeto tem campo `id`.

Sem o header: `401`.

## 2. O deck inicial

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/players/decks/
```

**Esperado**: `200`, um deck, 40 entradas em `card_ids`. Conta nova já nasce
jogável.

## 3. Criar, renomear, editar, apagar

```bash
# criar
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name": "Agro", "card_ids": [...40 identificadores...]}' \
  http://localhost:8000/players/decks/

# renomear
curl -X PATCH -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name": "Agro v2"}' http://localhost:8000/players/decks/2/

# apagar
curl -X DELETE -H "Authorization: Bearer $TOKEN" http://localhost:8000/players/decks/2/
```

**Esperado**: `201`, `200`, `204`. Depois do `DELETE`, um `GET` no mesmo
`deck_id` responde `404`.

## 4. As recusas do salvamento

| Corpo | Esperado |
|---|---|
| `{"name": "  ", "card_ids": [...40...]}` | `400` com `name` |
| 12 identificadores | `400` com `wrong_deck_size {found: 12, required: 40}` |
| 40 entradas, uma carta 4 vezes | `400` com `too_many_copies {card_id, count: 4, limit: 3}` |
| 40 entradas com `9999` | `400` com `unknown_card {card_id: 9999}` |
| 39 entradas, uma 4 vezes, uma `9999` | `400` com **os três** problemas |
| vigésimo primeiro `POST` | `400` com `deck_limit` |

Depois de um `400` no `PATCH`, o `GET` mostra o deck **como estava**.

## 5. O isolamento

Com dois tokens, `$A` e `$B`, e um deck do jogador A:

```bash
curl -H "Authorization: Bearer $B" http://localhost:8000/players/decks/<deck de A>/
curl -X PATCH -H "Authorization: Bearer $B" -H "Content-Type: application/json" \
  -d '{"name": "meu agora"}' http://localhost:8000/players/decks/<deck de A>/
curl -X DELETE -H "Authorization: Bearer $B" http://localhost:8000/players/decks/<deck de A>/
```

**Esperado**: `404` nos três, com o **mesmo corpo** de um `deck_id` que não
existe para ninguém. Nada distingue os dois casos. E o deck de A continua lá.

## 6. Entrar na fila com deck

Abra `ws://localhost:8000/ws/matchmaking/?token=$TOKEN` e mande:

```json
{"type": "join_queue", "payload": {"deck_id": 1}}
```

**Esperado**: nada volta enquanto espera par; com dois clientes, os dois recebem
`match_found` e abrem `ws/match/` em seguida, como hoje.

### As quatro recusas

| Mensagem | Esperado |
|---|---|
| `{"type": "join_queue", "payload": {}}` | `message_refused` / `deck_not_specified` |
| `deck_id` de outro jogador | `message_refused` / `deck_not_found` |
| `deck_id` inexistente | `message_refused` / `deck_not_found`, **corpo idêntico ao anterior** |
| deck que deixou de ser válido | `message_refused` / `invalid_deck` com `deck_problems` |

Em todas: **o socket continua aberto**, e um `join_queue` seguinte com deck bom
é aceito.

## 7. O deck viaja com a entrada

O cenário que a feature existe para garantir:

1. Cliente A manda `join_queue` com um deck válido.
2. Antes de qualquer par, A troca todas as cartas desse deck pelo HTTP — ou o
   apaga.
3. Cliente B manda `join_queue` e fecha o par.

**Esperado**: a partida nasce, e usa a lista que A tinha **no passo 1**. Apagar
o deck no passo 2 não impede o par.

O mesmo vale no meio da partida: apagar o deck não muda nada do que está em
jogo.

## 8. O andaime saiu

```bash
cd server && grep -rn "def deck_for" apps/game/consumers/
```

**Esperado**: nada. O matchmaking não fabrica mais deck -- ele *pergunta* a
lista à porta injetada (`self.decks.deck_for(...)`), que é chamada, não
definição. `starter_deck` continua existindo, agora como conteúdo do deck
inicial.

## Regressões que precisam continuar passando

```bash
cd server && pytest apps/game/tests/test_match_setup.py \
                     apps/game/tests/test_full_match.py \
                     apps/game/tests/test_matchmaking_queue.py \
                     apps/game/tests/test_matchmaking_clock.py \
                     apps/game/tests/test_match_consumer_flow.py \
                     apps/players/tests/
```

O setup da §3, o protocolo da 009 e o relógio da 010 não mudam.
