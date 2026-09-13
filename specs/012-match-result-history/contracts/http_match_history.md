# Contrato HTTP — Histórico de partidas

**Feature**: `012-match-result-history`

Uma rota, um verbo. O jogador autenticado lê as próprias partidas registradas.
Não existe rota para o histórico de outro jogador — não existe caminho a recusar
(D11, FR-019).

---

## `GET /game/matches/`

Lista as partidas em que o autenticado jogou, da mais recente para a mais antiga.

**Autenticação**: obrigatória (`IsAuthenticated`, JWT). Sem ela, `401`.

### Parâmetros de consulta

| Parâmetro | Tipo | Padrão | Limite |
|---|---|---|---|
| `page` | inteiro ≥ 1 | `1` | página além do fim responde `404` (padrão do DRF) |
| `page_size` | inteiro ≥ 1 | `20` | teto `100`; acima disso, vale `100` |

### `200 OK`

```json
{
  "count": 37,
  "next": "http://host/game/matches/?page=2",
  "previous": null,
  "results": [
    {
      "match_id": "4f1c2a9e-8d3b-4c77-9a51-6b0e2f7d1c84",
      "won": true,
      "end_reason": "nexus_depleted",
      "opponent": {
        "user_id": 9,
        "nickname": "brenda",
        "icon": "default_icon",
        "level": 3
      },
      "duration_seconds": 742,
      "final_round": 8,
      "ended_at": "2026-09-12T18:03:11Z"
    },
    {
      "match_id": "c07b1d55-2e64-4f0a-b3aa-91d8e4c6f220",
      "won": false,
      "end_reason": "forfeit",
      "opponent": null,
      "duration_seconds": 63,
      "final_round": 1,
      "ended_at": "2026-09-11T22:47:02Z"
    }
  ]
}
```

### Campos de uma linha

| Campo | Tipo | Nota |
|---|---|---|
| `match_id` | string | O mesmo `match_id` que o cliente viu no socket da partida. |
| `won` | booleano | Do ponto de vista de quem pede. Derivado: o autenticado é o vencedor ou não. |
| `end_reason` | `"nexus_depleted"` \| `"forfeit"` | Conjunto fechado da §10. Não existe empate e não existe abandono. |
| `opponent` | objeto \| `null` | Os mesmos campos públicos de `PlayerData`. `null` quando o perfil do oponente foi apagado depois da partida — a linha continua, com o desfecho intacto (FR-022). |
| `duration_seconds` | inteiro ≥ 0 | Do começo da partida ao fim. `0` em partida anterior a esta feature. |
| `final_round` | inteiro ≥ 1 | Rodada em que acabou. Desistência no mulligan registra `1`. |
| `ended_at` | data-hora ISO 8601, UTC | O instante da transição, não o da gravação no banco. |

**Nenhum campo se chama `id`** (FR-021): a identidade é `match_id` e `user_id`.

**O que não é exposto**: o deck da partida e o Nexus final dos dois lados ficam no
registro para análise posterior, e nenhuma resposta desta feature os entrega
(spec, Assumptions). O deck do oponente é guardado na mesma linha e continua
invisível.

### `401 Unauthorized`

Requisição sem token, ou com token inválido. Corpo padrão do DRF.

### `404 Not Found`

Duas causas, com o mesmo corpo:

- O autenticado não tem `PlayerProfile` — conta criada fora do registro
  (`createsuperuser`, fixtures). Mesma recusa de `PlayerMeView` e das rotas de
  deck, e pela mesma razão: o recurso não existe para esse usuário.
- `page` além da última página (comportamento padrão da paginação do DRF).

### Lista vazia

Jogador sem nenhuma partida registrada recebe `200` com `"count": 0` e
`"results": []`. Não é recusa.

---

## Ordenação e paginação

- Ordem fixa: `-ended_at`. Não há parâmetro de ordenação.
- Página 1 traz as 20 mais recentes. Percorrer todas as páginas devolve cada
  partida uma vez, sem repetir e sem pular (SC-009).
- Uma partida nova registrada entre dois pedidos de página entra no topo e pode
  empurrar uma linha da página 1 para a 2. É o comportamento aceito da paginação
  por número de página (D10).

---

## Isolamento

O queryset parte do perfil autenticado:

```python
MatchRecord.objects.filter(Q(winner=profile) | Q(loser=profile))
```

Nenhuma linha em que o autenticado não jogou é alcançável por esta rota, e não
existe parâmetro que aponte para outro jogador. É a mesma forma de
`deck_queries.py`: o isolamento sai da consulta, não de uma checagem depois dela.
