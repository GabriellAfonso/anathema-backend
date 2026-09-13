# Phase 0 — Research: Resultado de partida, registrado uma vez só

**Feature**: `012-match-result-history` | **Data**: 2026-09-12

Nenhum `NEEDS CLARIFICATION` sobrou da spec — a sessão de esclarecimento de
2026-09-12 fechou as duas decisões abertas. O que este documento resolve são as
escolhas técnicas que a spec deliberadamente não fixou, cada uma com o que foi
rejeitado e por quê.

---

## D1 — Onde a transição é detectada

**Decisão**: uma função pura `finished_match(before, after, ended_at)` num módulo
novo, `apps/game/history/finished_match.py`, que devolve o registro a gravar ou
`None`. A condição é a mesma que `protocol/match_events.py::_match_finished` já
usa: `before.outcome is None and after.outcome is not None`.

**Razão**: a condição já está provada em produção e é a definição exata de
"transição, nunca observação" (FR-007). Uma função pura sobre dois estados não
tem como registrar uma leitura — não existe leitura para ela olhar.

**Alternativas rejeitadas**:

- *Reusar `_match_finished` do pacote `protocol`*: ele devolve o evento de
  protocolo (`MatchFinishedEvent`, um `TypedDict` do frame do cliente). Ligar a
  persistência ao formato do frame faria o contrato do cliente e o do banco
  mudarem juntos. A condição é copiada em uma linha; o tipo não.
- *Detectar dentro do motor*: o motor não conhece banco (FR-023) e `_finish_match`
  é privado de propósito.
- *Detectar dentro de `MatchStore.mutate`*: é exatamente o que a spec proíbe
  (FR-008) — o compare-and-swap reaplica a mudança numa retentativa.

---

## D2 — Onde a gravação é disparada

**Decisão**: nos dois pontos que já chamam `mutate` e já têm o antes e o depois:

- `apps/game/consumers/match.py::MatchConsumer.play`
- `apps/game/match_timers/ticker.py::MatchClockTicker._expire`

Uma linha em cada, **depois** de `deliver_match_update`, chamando um helper
compartilhado `record_finished_match(recorder, before, stored, ended_at)`.

**Razão**: são os dois únicos caminhos de escrita que podem terminar uma partida
— uma desistência ou uma jogada pelo socket, e a ação automática dos 45s pelo
ticker. `TurnWarningMark` não passa pelo motor e nunca termina partida; o
`connect` do socket só lê.

Entregar antes de gravar satisfaz FR-016 literalmente: se a gravação explodir, os
dois jogadores já receberam o estado final.

**Alternativas rejeitadas**:

- *Dentro de `deliver_match_update`*: a entrega endereça grupos de channel layer;
  persistir não é responsabilidade dela (SRP, princípio IV). Além disso ela não
  saberia dizer se foi transição sem receber mais um parâmetro.
- *Uma task de fundo varrendo partidas terminadas no Redis*: transformaria a
  observação em gatilho, que é o que a feature inteira existe para impedir, e
  ainda daria janela para uma partida expirar antes da varredura.

---

## D3 — Exatamente uma vez, entre workers

**Decisão**: `match_id` com `unique=True` no modelo. A gravação insere dentro de
um savepoint; `IntegrityError` significa "outro worker chegou primeiro" e a
função devolve `False` sem tocar em estatística e sem propagar exceção.

```
transaction.atomic():            # a transação da feature: registro + estatísticas
    transaction.atomic():        # savepoint só do INSERT
        MatchRecord.objects.create(...)
    # IntegrityError aqui: savepoint desfeito, transação externa ainda utilizável
    bump_stats(...)
```

**Razão**: o savepoint interno é obrigatório. Um `IntegrityError` levantado
diretamente dentro de um `atomic()` marca a transação para rollback, e qualquer
consulta seguinte levanta `TransactionManagementError`. O bloco aninhado é a
forma que o Django documenta para capturar erro de integridade e continuar.

**Alternativas rejeitadas**:

- *`get_or_create` / `exists()` antes de inserir*: a corrida cabe exatamente entre
  a leitura e a escrita. A unicidade no banco é o que decide, não a checagem.
- *Trava no Redis em torno do registro*: trava tem tempo de vida, e tempo de vida
  é uma segunda coisa a acertar — o mesmo argumento que `MatchStore.mutate` já
  escreve para recusar trava no compare-and-swap.
- *Marcar "registrado" dentro do estado da partida*: seria escrita de estado
  dentro do caminho de registro, e uma retentativa do compare-and-swap a
  reaplicaria.

---

## D4 — Estatísticas sem perder incremento concorrente

**Decisão**: `PlayerStats.objects.filter(profile_id=...).update(...)` com
expressões `F()`:

```python
matches_played=F("matches_played") + 1,
wins=F("wins") + 1,
play_time=F("play_time") + duration_seconds,
```

**Razão**: o incremento acontece no banco, numa instrução só. Duas partidas do
mesmo jogador terminando ao mesmo tempo em workers diferentes somam as duas
(FR-013). Um `obj.wins += 1; obj.save()` lê em Python e escreve de volta — a
segunda escrita apagaria a primeira.

**Alternativas rejeitadas**:

- *`select_for_update()` + save*: resolve, mas segura linha por mais tempo e não
  compra nada sobre `F()` para um incremento puro.
- *Recalcular a estatística a partir da contagem de registros*: recontar todo o
  histórico a cada partida (o que FR-013 proíbe), e `play_time` não bate quando
  há registros com duração desconhecida.

---

## D5 — Perfil apagado, sem duplicar identidade

**Decisão**: `winner` e `loser` são `ForeignKey(PlayerProfile,
on_delete=models.SET_NULL, null=True)`. **Não** existe coluna espelho
`winner_user_id`/`loser_user_id`.

**Razão**: `PlayerProfile.user` é a chave primária (decisão 0001 do vault), então
`winner_id` **é** o `user_id` — uma coluna espelho seria uma segunda fonte da
mesma verdade, que é o que `MatchOutcome` e `PlayerState.user_id` já recusam pelo
mesmo argumento: uma segunda fonte não dá erro quando diverge, dá estado errado
que passa despercebido.

Com `SET_NULL`, o lado sobrevivente continua sabendo o desfecho: se o meu lado é
`loser`, eu perdi; se é `winner`, eu venci. O que se perde é a identidade do
oponente apagado, e isso é inerente a apagar o perfil.

**Consequência**: o `CASCADE` do perfil apagado **não** pode levar o registro
junto — daí `SET_NULL`, e não o `CASCADE` que `PlayerDeck` usa. Deck apagado com o
dono é certo; histórico do adversário, não.

**Alternativas rejeitadas**:

- *`PROTECT`*: impediria apagar o perfil, e a decisão de produto não é essa.
- *`CASCADE`*: apagaria a linha do histórico do outro jogador — exatamente o que
  FR-022 proíbe.
- *Espelhar `user_id` em coluna própria*: segunda fonte, ver acima.

---

## D6 — Formato do deck da partida no registro

**Decisão**: quatro colunas simétricas na mesma linha —
`winner_deck_name`, `winner_deck_card_ids`, `loser_deck_name`,
`loser_deck_card_ids` — com as listas em `JSONField`, do mesmo jeito que
`PlayerDeck.card_ids` já guarda.

**Razão**: a lista é lida inteira e escrita inteira, repetição é esperada (até 3
do mesmo `card_id`) e a ordem é a que o jogador montou. É o argumento que
`PlayerDeck` já escreve para recusar tabela de junção, e vale igual aqui.

**Alternativas rejeitadas**:

- *Tabela filha `MatchRecordSide`, duas linhas por partida*: mais normalizada, mas
  acrescenta duas escritas à transação que precisa ser exatamente-uma-vez e um
  join em toda listagem, para um dado que nunca é consultado por si.
- *`ForeignKey` para `PlayerDeck`*: proibido por FR-028 — o deck editado muda o
  que a referência significa e o apagado a esvazia.

---

## D7 — Instante de criação no estado

**Decisão**: `Match.started_at: EpochMillis | None = None`, escrito por
`MatchmakingConsumer.open_match`, na mesma linha em que hoje ele escreve
`match.clock = opening_match_clock(self.clock.now_ms())`.

**Razão**: é estado de **transporte**, do mesmo tipo do relógio da §15 — nenhuma
regra o lê, nenhuma porta do motor o escreve, e `start_match` continua sem saber
que ele existe. Isso preserva `test_engine_reads_no_time.py`, que reprova
qualquer leitura de tempo dentro do motor.

`EpochMillis` e não `datetime`: é o que já atravessa o documento JSON e o score
do sorted set sem conversão.

**Alternativas rejeitadas**:

- *Passar `started_at` para `start_match`*: acrescenta um parâmetro de tempo à
  assinatura do motor. Mesmo sem ler relógio, é a porta errada.
- *Usar o TTL da chave no Redis para derivar o começo*: o TTL é renovado a cada
  jogada. Ele mede a última jogada, não o começo.

---

## D8 — Documento gravado antes desta feature

**Decisão**: `started_at` e o deck da partida entram no `MatchDocument` como
campos **opcionais**, via uma classe base `TypedDict(total=False)`. A
desserialização usa `.get(...)`, e a ausência vira `None`.

**Razão**: durante a implantação existem partidas vivas gravadas pelo código
anterior, e elas duram até 6 horas. Recusar a leitura derrubaria partidas em
curso. O `total=False` é o que deixa o `.get()` devolver `int | None` sob mypy
strict, em vez de exigir `cast`.

Uma partida sem `started_at` registra com duração 0 (spec, Assumptions); uma sem
deck da partida registra com lista vazia e nome vazio.

**Alternativas rejeitadas**:

- *Versão de esquema no documento*: `store.py` registra explicitamente que versão
  de esquema não existe e que a `version` do hash não é isso. Introduzi-la por
  causa de dois campos opcionais é caro demais.
- *Migração dos documentos vivos no Redis*: script que roda uma vez, para dado que
  expira sozinho em 6 horas.

---

## D9 — A porta de gravação e os testes de socket

**Decisão**: `FinishedMatchRecorder` é um `Protocol` com um método
(`async def record(finished) -> bool`), injetado no construtor do `MatchConsumer`
e do `MatchClockTicker`, com a implementação de banco como padrão. Os testes
passam um `FakeFinishedMatchRecorder`.

**Razão**: `apps/game/tests/conftest.py` registra que nenhum teste de websocket
toca o banco — o `no_connection_churn` existe por causa disso. Uma escrita de ORM
alcançável do consumer quebraria essa garantia em toda a suíte de socket. É a
mesma forma de `PlayerDeckSource`, e pelo mesmo motivo.

O retorno `bool` (gravou / já existia) é o que deixa o teste de corrida afirmar
qual tentativa venceu sem ler o banco duas vezes.

**Alternativas rejeitadas**:

- *Chamar o ORM direto do consumer*: quebra a garantia acima e o princípio de
  injeção de dependência da constituição.
- *Sinal do Django (`post_save`)*: gatilho implícito, invisível em quem chama, e o
  que dispararia seria a gravação — não a transição.

---

## D10 — Endereço e paginação do histórico

**Decisão**: `GET /game/matches/`, `ListAPIView` do DRF com uma
`PageNumberPagination` própria (`page_size=20`, `page_size_query_param=page_size`,
`max_page_size=100`), declarada na própria view — não em `REST_FRAMEWORK` global.

**Razão**: `/game/` é onde mora o que é de partida (`/game/cards/` já está lá), e o
modelo vive no app `game`. Paginação local e não global porque as rotas de deck
respondem lista inteira hoje, e ligar paginação global mudaria o corpo delas sem
que ninguém pedisse.

`ListAPIView` e não `APIView` porque paginação é exatamente o que ela traz pronto
— a constituição manda seguir a convenção do framework.

**Alternativas rejeitadas**:

- */players/matches/*: o modelo e o `MatchEndReason` são do app `game`; a rota
  seguir o app evita um import cruzado só para servir HTTP.
- *Cursor pagination*: mais robusta sob inserção concorrente, mas o histórico de
  um jogador cresce uma linha por partida jogada por ele — não há volume que
  justifique perder o "pular para a página 4".

---

## D11 — Isolamento do histórico

**Decisão**: o queryset parte sempre do perfil autenticado:
`MatchRecord.objects.filter(Q(winner=me) | Q(loser=me))`. Não existe rota que
receba `user_id` de outro jogador.

**Razão**: é o argumento que `deck_queries.py` já escreve — o isolamento sai da
consulta, não de uma checagem depois dela. Sem rota parametrizada, não existe
caminho a recusar, e não existe recusa que revele se o histórico do outro existe
(FR-019).

**Alternativas rejeitadas**:

- */game/matches/?user_id=9* com checagem de permissão: cria o caminho e depois o
  fecha. Confirmar "esse histórico existe, mas não é seu" já entrega informação.

---

## D12 — Unidade de `play_time`

**Decisão**: segundos inteiros, truncados de `(ended_at - started_at) // 1000`.

**Razão**: `PlayerStats.play_time` é `BigIntegerField` e nunca foi escrito — não há
valor legado a interpretar. A duração também vai para o registro em segundos, e
as duas ficam na mesma unidade.

**Alternativas rejeitadas**:

- *Milissegundos*: precisão que ninguém consome; o histórico mostra "12 min".
- *`DurationField` no registro*: obrigaria `timedelta` no serializer e uma segunda
  unidade no mesmo dado que `PlayerStats` guarda como inteiro.
