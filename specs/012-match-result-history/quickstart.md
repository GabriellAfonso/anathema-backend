# Quickstart — Validar o registro de resultado

**Feature**: `012-match-result-history`

Como provar que a feature funciona, de ponta a ponta. Cada cenário aponta para o
critério de sucesso que ele fecha.

---

## Pré-requisitos

```bash
cd server
pip install -r requirements-dev.txt
```

Redis de pé (os testes de store e de socket usam o DB 15, descartável):

```bash
docker compose up -d redis
```

Migração nova do app `game`:

```bash
cd server && python manage.py makemigrations game && python manage.py migrate
```

---

## As três portas de qualidade

```bash
cd server && pytest
cd server && mypy
black --check server/
```

As três verdes é a condição de pronto (constituição, *Development Workflow*).

---

## Cenário 1 — Partida por Nexus vira um registro

**Fecha**: SC-001, SC-005, SC-011, SC-012

```bash
cd server && pytest apps/game/tests/test_finished_match_record.py -v
```

O teste roda uma partida até o Nexus de um jogador chegar a zero e afirma:

- existe uma linha com aquele `match_id`;
- vencedor e derrotado corretos, motivo `nexus_depleted`;
- `duration_seconds` bate com o intervalo do relógio falso;
- `final_round` é a rodada em que acabou;
- o Nexus final dos dois bate com o estado terminal;
- o deck da partida dos dois é a lista que entrou na fila, com o nome dela;
- os quatro contadores dos dois jogadores subiram.

---

## Cenário 2 — Desistência, inclusive no mulligan

**Fecha**: SC-001, SC-012

```bash
cd server && pytest apps/game/tests/test_finished_match_record.py -k forfeit -v
```

Duas partidas: desistência no meio do jogo, e desistência durante o mulligan
antes da Rodada 1. As duas registram, com motivo `forfeit`, derrota para quem
desistiu, e `final_round` igual a `1` na segunda. O Nexus final de quem desistiu
**não** é zero — é o que estava.

---

## Cenário 3 — Exatamente uma vez, sob corrida

**Fecha**: SC-002, SC-003

```bash
cd server && pytest apps/game/tests/test_finished_match_once.py -v
```

Três afirmações:

- duas gravações concorrentes do mesmo resultado, uma vencendo e a outra
  recebendo `False`, deixam uma linha só e um incremento só de estatística;
- reconectar à partida terminada 20 vezes não muda a contagem de nada;
- a mudança reaplicada pelo compare-and-swap (via `interleaved_match_store.py`,
  que já existe) não produz um segundo registro.

---

## Cenário 4 — Partida abandonada não registra

**Fecha**: SC-004

```bash
cd server && pytest apps/game/tests/test_finished_match_once.py -k abandoned -v
```

Partida criada, nunca terminada, chave removida do Redis: zero registros, zero
alterações de contador. Não existe derrota por abandono.

---

## Cenário 5 — Falha de escrita não derruba a partida

**Fecha**: SC-006, SC-007

```bash
cd server && pytest apps/game/tests/test_finished_match_record.py -k failure -v
```

- Gravação de estatística falhando: zero registros daquela partida e zero
  contadores mexidos (a transação inteira volta atrás).
- Gravação do registro falhando: os dois jogadores continuam recebendo o frame do
  estado final, e a partida continua terminada no Redis.

---

## Cenário 6 — O instante de criação atravessa o Redis

**Fecha**: SC-001 (a duração), FR-014

```bash
cd server && pytest apps/game/tests/test_match_serialization.py -k started_at -v
cd server && pytest apps/game/tests/test_matchmaking_clock.py -v
```

Serializar e desserializar devolve o mesmo instante. Um documento gravado **sem**
o campo — o caso da janela de implantação — desserializa com `None` e não quebra.

---

## Cenário 7 — O deck da partida sobrevive à edição

**Fecha**: SC-011

```bash
cd server && pytest apps/game/tests/test_queued_deck_is_frozen.py -v
cd server && pytest apps/game/tests/test_finished_match_record.py -k deck -v
```

O primeiro já existe e continua verde: a fila congela o deck. O segundo registra a
partida, edita o nome do deck e apaga o deck, e afirma que a linha ficou idêntica
campo a campo.

---

## Cenário 8 — O histórico pelo HTTP

**Fecha**: SC-008, SC-009, SC-010

```bash
cd server && pytest apps/game/tests/test_match_history_api.py -v
```

- Primeira página em ordem decrescente de `ended_at`;
- 50 partidas percorridas em páginas devolvem 50 linhas, sem repetir nem pular;
- nenhuma linha de outro jogador aparece, e não existe parâmetro que aponte para
  ele;
- sem autenticação, `401`;
- sem perfil, `404`;
- sem partidas, `200` com lista vazia;
- perfil do oponente apagado: a linha continua, `opponent` vem `null`, e o
  desfecho está intacto.

Contrato completo em [`contracts/http_match_history.md`](contracts/http_match_history.md).

---

## Conferência manual (opcional)

Com o servidor de pé e um token JWT na mão:

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/game/matches/
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8000/game/matches/?page=2&page_size=5"
```

As estatísticas **não** têm rota: `PlayerSerializer` expõe perfil, não
`PlayerStats`, e servi-las ao cliente é decisão de outra feature. Para conferir:

```bash
cd server && python manage.py shell -c \
  "from apps.players.models import PlayerStats; print(list(PlayerStats.objects.values()))"
```

`matches_played`, `wins`, `losses` e `play_time` deixam de ser zero depois da
primeira partida terminada.
