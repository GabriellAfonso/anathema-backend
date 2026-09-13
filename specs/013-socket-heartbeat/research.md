# Research: Heartbeat de aplicação nos sockets

**Feature**: `013-socket-heartbeat` | **Date**: 2026-09-13

Decisões técnicas, cada uma com as alternativas rejeitadas. Os achados de código
que motivaram a spec estão na seção *Investigação* de [spec.md](spec.md) e não
são repetidos aqui.

---

## D1 — O ping é reconhecido no `BaseConsumer.receive`, depois da decodificação

**Decisão**: o `receive` do `BaseConsumer` decodifica o frame como hoje e, antes
de chamar `receive_json`, pergunta se o objeto é ping. Se for, responde e
retorna; `receive_json` nunca vê o ping.

**Rationale**: `receive` é o último trecho que os dois consumers percorrem juntos.
O `MatchConsumer` substitui `receive_json` inteiro, mas não `receive`. Ali o frame
já é um objeto JSON — a recusa de binário, JSON inválido e não-objeto continua
acontecendo antes, então FR-015 vale sem código novo.

Para o `receive` continuar dentro das 20 linhas (princípio IV), a decodificação
sai para um método próprio que devolve o objeto ou `None` depois de recusar.

**Alternativas rejeitadas**:

- **`ping` no `parse_client_message`**: viraria `ClientCommand`, entraria em
  `PlayerChange` e no `mutate`, e geraria versão e `match_update` — o oposto do
  FR-007.
- **`handle_ping` no roteamento do `BaseConsumer`**: o `MatchConsumer` não passa
  por esse roteamento. Não chega ao socket de partida.
- **Um tratamento em cada consumer**: duplica a regra (FR-016).
- **Sobrescrever `receive_json` no base e fazer o `MatchConsumer` chamar
  `super()`**: o `MatchConsumer` teria de lembrar de chamar o base antes de
  parsear, e esquecer isso seria regressão silenciosa. No `receive` não há o que
  lembrar.
- **Middleware ASGI**: decodificaria o JSON duas vezes, mandaria frame por fora
  do consumer e não saberia se o socket passou pelos gates.

---

## D2 — A regra é pura, em `apps/game/protocol/heartbeat.py`

**Decisão**: módulo novo no pacote `protocol`, sem I/O:

- `PING = "ping"` e `PONG = "pong"`;
- `is_ping(content) -> bool`: `type` exatamente igual a `"ping"`;
- `pong_payload(content) -> dict[str, object]`: o `payload` se for objeto; `{}`
  em qualquer outro caso.

O consumer só junta as duas funções com `send_event`.

**Rationale**: o pacote `protocol` já guarda a forma das mensagens dos dois
sockets, inclusive as recusas do matchmaking (`matchmaking_refusals.py`). Função
pura testa a matriz de payloads toda sem abrir socket, e o teste de socket fica
só com o que depende de socket.

Duas funções em vez de uma que devolva `None` para "não é ping": `None` teria
dois sentidos, e o chamador precisaria de um comentário para lembrar qual.

**Alternativas rejeitadas**:

- **Regra dentro do `BaseConsumer`**: funciona, mas mistura forma de protocolo
  com encanamento de socket, que é justamente o que a nota `BaseConsumer.md` do
  vault separa.
- **Reusar `_payload_of` de `client_messages.py`**: ele **recusa** payload que não
  é objeto. O ping nunca recusa (FR-005). A regra é outra, então a função é outra.

---

## D3 — Ping em socket recusado pelo gate é descartado, sem frame

**Decisão**: `BaseConsumer.passed_socket_gates() -> bool` devolve `self.accepted`.
O `MatchConsumer` sobrescreve para `super().passed_socket_gates() and
self.match_id is not None`. Ping que chega a um socket onde isso é falso não
recebe resposta nenhuma.

**Rationale**: os dois gates aceitam o socket antes de recusar, para o motivo
chegar ao cliente, e fecham logo depois. No uvicorn, um frame mandado depois do
close levanta `RuntimeError: Unexpected ASGI message 'websocket.send', after
sending 'websocket.close'` — o bug que o `test_base_consumer_lifecycle.py`
registra. Na prática um frame do cliente não chega depois do close, mas o driver
de teste entrega, e a spec (FR-012, SC-007) exige o mesmo motivo e o mesmo close
code, com ou sem ping.

Os dois estados de recusa já existem e já são lidos: `accepted` é falso no gate
de autenticação, e `match_id` é `None` no gate da partida (é o que o
`on_disconnect` e o `receive_json` do `MatchConsumer` já conferem).

**Alternativas rejeitadas**:

- **Responder pong mesmo assim**: frame depois do close.
- **Deixar cair no caminho de hoje**: no socket de matchmaking isso vira
  `unknown_message_type` depois do close — outra vez frame depois do close.
- **Flag nova marcada no `close`**: sobrescrever `close` do Channels para guardar
  estado que os dois consumers já expõem de outro jeito.

Mensagens que **não** são ping, em socket recusado, continuam no caminho de hoje.
Mudar isso está fora do escopo (FR-020).

---

## D4 — O pong sai pelo `send_event` do próprio socket, nunca pelo channel layer

**Decisão**: `await self.send_event(type=PONG, payload=pong_payload(content))`.

**Rationale**: `send_event` escreve só neste socket. `group_send` mandaria para
todos os sockets do usuário (`user_group`) ou da partida (`match_group`), e
FR-002 proíbe. De quebra, o channel layer — que em produção é Redis — fica fora
do caminho: o ping não tem como falhar ou atrasar por ele.

O objeto do `payload` é o que `json.loads` acabou de criar para esta mensagem, e
ninguém mais tem referência a ele. Devolvê-lo sem cópia é seguro.

---

## D5 — O ping não renova presença, e as peças mortas ficam

**Decisão**: nenhuma linha desta feature chama `set_heartbeat`, lê
`heartbeat_key` ou toca o cache. `set_heartbeat`, `heartbeat_key` e o ramo do
`disconnect` não são apagados.

**Rationale**: está na spec, seção *Investigação → A presença*. Em resumo:
ninguém lê presença; presença é por usuário e ping é por socket; o item é
decisão registrada no `Backend/TODO.md`, e a constituição proíbe resolvê-lo em
passagem.

**Alternativa rejeitada**: apagar as peças mortas aproveitando a mudança no
`BaseConsumer`. É o primeiro caminho que o próprio `TODO.md` descreve, e por isso
mesmo pertence ao item, não a esta feature.

---

## D6 — Ordem dos pongs: garantida pelo consumer, sem fila própria

**Decisão**: nenhum mecanismo de ordenação.

**Rationale**: o Channels despacha as mensagens de uma instância de consumer uma
por vez, esperando o handler terminar. Pings do mesmo socket saem em ordem, e um
ping que chega durante uma jogada espera por ela. Isso entra na latência medida,
e está certo (spec, *Edge Cases*). Frames do channel layer, como `match_update`
do oponente, podem aparecer entre um ping e o pong dele. O cliente casa pelo
`type`, não pela posição.

---

## D7 — Sem limite de taxa, sem limite de tamanho próprio, sem log

**Decisão**: nada disso é implementado.

**Rationale**:

- **Taxa**: o cliente manda um ping a cada 10 s. Proteção contra abuso é
  transversal a todas as mensagens e fica para outra feature.
- **Tamanho**: o uvicorn já limita o frame (`ws_max_size`, padrão de 16 MiB). O
  eco nunca passa do tamanho do frame que chegou.
- **Log**: um ping a cada 10 s por socket enche o log, e nenhum ping é falha.

O ping/pong do protocolo WebSocket continua nos padrões do uvicorn
(`ws_ping_interval` e `ws_ping_timeout` de 20 s; nem o `dockerfile` nem o
`docker-compose.yml` os sobrescrevem). FR-021 é cumprido não mexendo neles.

---

## D8 — "Não lê a partida" é provado por um fake que conta acessos

**Decisão**: `AccessCountingMatchStore`, subclasse nomeada de `FakeMatchStore`
em `apps/game/tests/access_counting_match_store.py`. Conta as chamadas a `get`,
`get_stored`, `save` e `mutate`.

**Rationale**: o `FakeMatchStore` prova "não gravou": a versão não muda e
`expiry_renewals` não cresce. "Não leu" ele não prova. O teste abre o socket (o
gate lê uma vez), zera a contagem, manda pings e confere zero acessos. É o mesmo
movimento de `InterleavedMatchStore`: subclasse com nome, sem `monkeypatch`.

**Alternativa rejeitada**: só comparar `match_snapshot` antes e depois. Isso prova
que o estado não mudou, não que não foi lido. FR-007 pede as duas coisas.

---

## D9 — Os testes de matchmaking passam pelo socket de verdade, sem banco

**Decisão**: `WebsocketTestClient` sobre `MatchmakingConsumer.as_asgi(queue=
FakeMatchmakingQueue(), decks=FakePlayerDeckSource(...), matches=FakeMatchStore(),
...)`, e não o `RecordingConsumer` de `test_matchmaking_join.py`.

**Rationale**: o ping mora no `receive`. O `RecordingConsumer` chama
`handle_join_queue` direto, pula o `receive`, e nem passa pelo `connect` que
liga `accepted`. Testar o ping por ele seria testar outro caminho.

Cada momento sem banco:

- **Antes do `join_queue`**: socket recém-aberto.
- **Na fila**: um jogador sozinho entra com o próprio deck. Sem par, nenhum
  `profile_for`, nenhum banco.
- **Depois de uma recusa**: `join_queue` com `deck_id` inexistente.
- **Depois do `match_found`**: o frame chega por `group_send` ao `user_group`,
  como `test_base_consumer_lifecycle.py` já faz. O consumer de matchmaking não
  guarda estado ao receber `match_found`, então isso é equivalente ao pareamento
  real e dispensa o `profile_for`, que toca banco.

A fila é conferida por `queue.waiting` antes e depois; o deck, por `decks.asked`.

---

## D10 — A fumaça ganha pings num módulo irmão

**Decisão**: `scripts/smoke_heartbeat.py` guarda o que é ping: montar o ping com
marcador, conferir o eco, contar pings e pongs, relatar a latência. O
`smoke_match.py` importa esse módulo e:

- no socket de fila, manda um ping antes do `join_queue` e aceita o `pong` no
  laço que espera `match_found`;
- no socket de partida, manda ping com marcador no primeiro estado de cada fase
  nova, e um ping com payload inválido (`42`) uma vez;
- trata `pong` em `on_frame` sem chamar `act`;
- no fim, exige pongs igual a pings, eco correto em todos, e nenhuma recusa
  `unknown_message_type`.

**Rationale**: `smoke_match.py` tem 460 linhas, e os pings passariam o limite de
500 (princípio IV). O script roda como `python scripts/smoke_match.py`, então o
diretório `scripts/` já está no `sys.path` e o import de módulo irmão funciona
sem instalar nada.

**Alternativa rejeitada**: flag `--ping`. O cliente de verdade sempre manda ping,
então a fumaça deve mandar sempre também. Uma flag deixaria o caminho padrão sem
o que a feature quer provar.

---

## D11 — Contratos: um arquivo novo e duas notas

**Decisão**:

- `contracts/heartbeat_messages.md` — o contrato inteiro.
- Nota no fim de `specs/009-match-protocol/contracts/client_messages.md` e de
  `specs/011-deck-catalog-api/contracts/matchmaking_messages.md`, apontando para
  ele.
- `specs/009-match-protocol/contracts/refusal_codes.md` **não muda** (FR-019).

**Rationale**: quem lê o contrato de um socket precisa descobrir que `ping`
existe ali. A regra fica escrita num lugar só, pelo mesmo motivo que o código.
