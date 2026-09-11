# Contract: frames do servidor

**Feature**: `009-match-protocol` | **Socket**: `ws/match/?matchId=<uuid>`

Todo frame é montado para o dono do socket. Nenhum contém carta da mão do
oponente, nem conteúdo ou ordem de deck, nem identificador de carta que esteja
na mão ou no deck do oponente.

## `match_start` — ao conectar e ao reconectar

```json
{"type": "match_start", "payload": {"version": 4, "view": { ...PlayerView... }}}
```

## `match_update` — depois de toda mudança aceita, a todo socket dos dois jogadores

```json
{"type": "match_update", "payload": {"version": 5, "view": { ...PlayerView... }, "events": [ ... ]}}
```

`version` cresce a cada escrita da partida. O cliente descarta atualização com
`version` menor ou igual à última que aplicou, inclusive a do `match_start`.

## `message_refused` — só ao socket que mandou

Ver [refusal_codes.md](./refusal_codes.md).

## `PlayerView`

A da feature 002, com as mudanças do motor corrigido (fase `declaration`,
`outcome` com `defeated_user_id` e `reason`, sem `energy_max`) e, desta feature:

- `you.mulligan_taken: bool` — o próprio mulligan já foi enviado
- `opponent.mulligan_taken: bool` — o oponente já respondeu

## Eventos

Lista ordenada: primeiro a jogada, depois as consequências. Formas em
[data-model.md](../data-model.md#eventos-protocolmatch_eventspy).

Exemplo, para A, depois de B passar e fechar a rodada:

```json
[
  {"kind": "passed", "user_id": 9},
  {"kind": "round_started", "round_number": 2, "token_holder_user_id": 9},
  {"kind": "cards_drawn", "user_id": 7, "count": 1, "cards": [{"card_instance_id": 31, "card_id": 5}]},
  {"kind": "cards_drawn", "user_id": 9, "count": 1, "cards": []}
]
```
