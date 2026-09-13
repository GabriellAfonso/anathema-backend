# Feature Specification: Heartbeat de aplicação nos sockets

**Feature Branch**: `013-socket-heartbeat`

**Created**: 2026-09-13

**Status**: Draft

**Input**: User description: "Heartbeat de aplicação nos sockets: o cliente manda `ping`, o servidor responde `pong`."

> Nota de idioma: os títulos de seção ficam em inglês porque os comandos
> seguintes do Spec Kit (`/speckit-plan`, `/speckit-tasks`, `/speckit-analyze`)
> os localizam por esses nomes. O conteúdo segue em português, como o resto das
> notas do projeto.

O cliente Unity vai rodar em desktop, Android e iOS. No celular, conexão meio
aberta é rotina: troca de Wi-Fi para dados móveis, NAT que expira, túnel sem
sinal. Nenhum desses casos gera close. O socket fica pendurado em silêncio, o
cliente não percebe que caiu, e a reconexão nunca dispara. No meio da partida,
isso é o jogador perdendo a vez pelo relógio sem saber que está desconectado.

O cliente já tem o detector pronto: manda `{"type": "ping"}` a cada 10 s e
declara a conexão morta depois de 30 s sem receber nada. Ele só arma o timeout
depois do primeiro `pong`. Hoje o servidor não conhece `ping`: os dois sockets
respondem `message_refused` com `unknown_message_type`, a cada 10 s, e o
detector nunca liga.

O ping/pong do protocolo WebSocket, que o servidor já faz, não resolve o lado do
cliente: o `ClientWebSocket` do .NET responde sozinho e não expõe o pong para a
aplicação, então o cliente não tem como medir silêncio por ele. Ele protege o
servidor — socket morto fecha do lado de cá e o jogador sai da fila —, mas não
avisa o jogador.

Esta feature dá ao cliente o que medir: uma mensagem que o servidor sempre
responde, que não custa nada à partida nem à fila, e que existe igual nos dois
sockets.

## Vocabulário desta feature

- **Ping**: mensagem do cliente com `type` exatamente `ping`. `payload`
  opcional.
- **Pong**: a resposta do servidor ao ping, só para o socket que mandou, com
  `type` `pong`.
- **Eco**: o `payload` do ping devolvido no pong. Existe quando o `payload` do
  ping é um objeto JSON; em qualquer outro caso o pong leva `{}`.
- **Socket aceito**: socket que passou pelos gates — autenticação nos dois, e a
  partida no de partida. Um socket recusado por gate recebe o motivo e fecha;
  não é socket aceito.
- **Presença**: o registro "este usuário está online", com a chave
  `presence:user:<id>` no cache. Existe no código, ninguém grava, ninguém lê.
  Não é o heartbeat desta feature.

## Investigação

Os pontos que o pedido mandou investigar em vez de assumir.

### Onde o ping é tratado

Os dois sockets decodificam o frame no mesmo lugar: o `receive` do consumer
base, que já recusa frame binário, JSON inválido e JSON que não é objeto. Daí em
diante eles se separam. O socket de matchmaking segue o roteamento
`handle_<type>` do consumer base. O socket de partida o substitui inteiro: passa
tudo pelo parser do protocolo, que recusa o que não está no conjunto das jogadas,
e ignora mensagens quando o socket não entrou numa partida.

Consequência para a spec: o ping precisa ser reconhecido **antes** da separação,
no trecho que os dois percorrem, e responder dali. Pôr `ping` no parser de
jogadas o tornaria um comando de partida, que entraria na mutação e geraria
versão; pôr um `handle_ping` só no roteamento do base não alcançaria o socket de
partida; pôr um em cada socket duplicaria a regra. Nenhum dos três serve.

### A presença (`set_heartbeat`)

`set_heartbeat` grava `presence:user:<id>` com TTL, e ninguém a chama. O
consumer que a chamava saiu do código junto com `ws/connection/`. Como a chave
nunca é preenchida, a limpeza no `disconnect` é ramo morto. O
`Backend/TODO.md` do vault registra isso como adiado de propósito: presença é
feature de produto — "quem está online" —, não existe tela pedindo, e o caminho
já está escrito (um `PresenceStore` próprio quando houver tela).

**Decisão: o ping não renova presença.** Pelos motivos:

1. **Ninguém lê.** Gravar a cada 10 s, por socket, um dado que nada consulta é
   escrita de cache sem consumidor.
2. **As unidades não batem.** Presença é por usuário; ping é por socket. O
   mesmo usuário tem socket de fila e de partida, às vezes dois de partida numa
   reconexão, e o `disconnect` de qualquer um apagaria a chave enquanto outro
   continua vivo. Ligar os dois exige decidir essa semântica, e isso é a feature
   de presença, não esta.
3. **O item é decisão registrada.** A constituição proíbe resolver em passagem
   um item do `TODO.md`. Ligar presença aqui seria exatamente isso.
4. **O ping precisa ser barato e sem efeito.** Uma resposta que não toca
   armazenamento nenhum não tem como falhar por armazenamento, e não tem como
   atrasar por ele.

As peças mortas (`set_heartbeat`, `heartbeat_key`, o ramo do `disconnect`)
também **não** são apagadas nesta feature, pelo motivo 3. O item do `TODO.md`
continua aberto para presença.

### Direção do heartbeat

O `TODO.md` cita um caso que o ping do protocolo não cobre: cliente vivo mas
travado, que responde pong sem processar nada, e que precisaria de ping da
aplicação **respondido pelo cliente**. Esta feature é o sentido inverso — o
cliente pergunta, o servidor responde — e resolve outra coisa: o cliente saber
que caiu. O servidor continua sem detectar cliente travado, e isso continua
fora do escopo.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - O cliente em partida sabe que a conexão está viva (Priority: P1)

O jogador está numa partida. O cliente manda ping a cada 10 s e recebe pong a
cada um. O detector arma no primeiro pong e, se a rede some sem close, dispara
depois de 30 s de silêncio e o cliente reconecta. Enquanto isso a partida não
sente nada: o ping não é jogada, não gera versão, não chega ao oponente, não
mexe no relógio.

**Why this priority**: é o caso que motiva a feature. Perder a vez pelo relógio
sem saber que caiu é o dano real, e ele só acontece no socket de partida.

**Independent Test**: abrir os dois sockets de uma partida, mandar ping por um
deles em cada fase — mulligan, ação, declaração, defesa, terminada — e conferir
que chega exatamente um pong só àquele socket, que o outro jogador não recebe
nada, e que a versão, o estado e os prazos do relógio lidos antes e depois são
idênticos.

**Acceptance Scenarios**:

1. **Given** um socket de partida aceito, **When** o cliente manda
   `{"type": "ping"}`, **Then** aquele socket recebe
   `{"type": "pong", "payload": {}}` e nenhuma recusa.
2. **Given** uma partida em qualquer fase, **When** um jogador manda ping,
   **Then** a versão da partida é a mesma de antes e nenhum dos dois jogadores
   recebe `match_update`.
3. **Given** a vez de um jogador correndo no relógio, **When** ele manda ping,
   **Then** o prazo da vez é o mesmo de antes — o ping não conta como ação nem
   estende o tempo — e a vez expira no mesmo instante em que expiraria sem ping.
4. **Given** a espera do mulligan, **When** um jogador manda ping, **Then** o
   prazo do mulligan é o mesmo de antes e o mulligan dele continua pendente.
5. **Given** uma partida terminada ainda no armazenamento, **When** um jogador
   manda ping, **Then** recebe pong, e não `match_is_over` nem outra recusa.
6. **Given** um jogador com o socket de partida aberto, **When** o oponente
   manda ping, **Then** o jogador não recebe pong nem qualquer outro frame.
7. **Given** o mesmo usuário com dois sockets de partida abertos (reconexão com
   o socket velho ainda vivo), **When** manda ping por um deles, **Then** só
   aquele recebe pong.

---

### User Story 2 - O cliente na fila sabe que a conexão está viva (Priority: P1)

O jogador abriu o socket de matchmaking. O cliente começa a mandar ping antes de
escolher o deck e continua enquanto espera na fila. Cada ping recebe pong. A
fila não sente nada: ninguém entra, ninguém sai, ninguém muda de lugar.

**Why this priority**: o detector do cliente é o mesmo nos dois sockets. Se o
socket de fila recusar ping, o cliente recebe uma recusa a cada 10 s durante
toda a espera e o detector nunca arma ali. Mesma prioridade da história 1 porque
o cliente não tem como ligar o detector num socket e não no outro.

**Independent Test**: com a fila substituída pelo fake nomeado, abrir o socket
de matchmaking, mandar ping antes do `join_queue`, depois do `join_queue` e
depois de um `join_queue` recusado, e conferir um pong por ping e o conteúdo e a
ordem da fila idênticos antes e depois de cada um.

**Acceptance Scenarios**:

1. **Given** um socket de matchmaking aceito que ainda não mandou `join_queue`,
   **When** o cliente manda ping, **Then** recebe pong, e o jogador continua fora
   da fila.
2. **Given** um jogador na fila, **When** ele manda ping, **Then** recebe pong,
   continua na fila, na mesma posição, com o mesmo deck.
3. **Given** um jogador cujo `join_queue` foi recusado, **When** ele manda ping,
   **Then** recebe pong, e continua fora da fila.
4. **Given** um jogador sozinho na fila, **When** ele manda ping, **Then** nenhum
   `match_found` é emitido e nenhum deck é consultado.
5. **Given** um socket de matchmaking que já recebeu `match_found` e ainda não
   fechou, **When** o cliente manda ping, **Then** recebe pong.

---

### User Story 3 - O cliente mede a latência pelo eco (Priority: P2)

O cliente põe um marcador no ping — por exemplo o instante em que mandou — e
recebe o mesmo marcador no pong. Com isso mede o tempo de ida e volta sem que o
servidor precise saber o que o marcador significa.

**Why this priority**: o detector de queda funciona só com `{}`. O eco é o que
permite mostrar latência ao jogador e diagnosticar rede ruim, e custa pouco
porque a regra é devolver o que chegou.

**Independent Test**: nos dois sockets, mandar ping com objeto aninhado e
conferir que o pong traz o mesmo objeto; mandar ping com `payload` ausente,
`null`, número, texto, booleano e lista, e conferir `{}` em todos, sem recusa.

**Acceptance Scenarios**:

1. **Given** um socket aceito, **When** o cliente manda
   `{"type": "ping", "payload": {"sent_at_ms": 1726000000000}}`, **Then** recebe
   `{"type": "pong", "payload": {"sent_at_ms": 1726000000000}}`.
2. **Given** um socket aceito, **When** o `payload` do ping é um objeto com
   objetos e listas dentro, **Then** o pong devolve o mesmo objeto JSON: mesmas
   chaves, mesmos valores, nos mesmos níveis.
3. **Given** um socket aceito, **When** o ping vem sem `payload`, ou com
   `payload` `null`, número, texto, booleano ou lista, **Then** o pong traz
   `{}` e nenhuma recusa é emitida.
4. **Given** um socket aceito, **When** o ping traz campos além de `type` e
   `payload`, **Then** os campos a mais são ignorados e o pong segue a regra do
   `payload`.

---

### Edge Cases

- **Ping num socket recusado pelo gate de autenticação**: o socket recebe
  `auth_denied` e fecha com 4001, como hoje. Nenhum pong.
- **Ping num socket recusado pelo gate da partida** (sem `matchId`, partida
  inexistente, jogador que não joga a partida): o socket recebe `match_denied` e
  fecha com 4400, 4404 ou 4403, como hoje. Nenhum pong.
- **Ping numa partida que expirou do armazenamento** com o socket ainda aberto:
  recebe pong. O ping não consulta a partida, então não descobre que ela
  expirou; a próxima jogada descobre, com `match_not_found`, como hoje.
- **`pong` mandado pelo cliente**: recusado com `unknown_message_type` nos dois
  sockets, como qualquer tipo desconhecido.
- **`Ping`, `PING`, `" ping"`**: não são ping. Recusados com
  `unknown_message_type`.
- **Frame que não é JSON, frame binário, JSON que não é objeto**: continuam
  recusados com `malformed_message`, mesmo que o texto contenha "ping". O ping é
  reconhecido depois da decodificação, nunca antes.
- **Rajada de pings**: cada um recebe exatamente um pong, na ordem em que
  chegaram. Sem limite de taxa nesta feature.
- **Ping chegando enquanto uma jogada do mesmo socket é processada**: o socket
  atende as mensagens em ordem, então o pong sai depois do resultado da jogada.
  A latência medida inclui essa espera, e isso é correto — é o tempo que o
  servidor levou para responder àquele socket.
- **Ping de quem não tem a vez**: pong. Prioridade não se aplica ao ping.
- **Ping entre o fim da partida e o fechamento do socket**: pong. Não gera
  registro de partida nem mexe em estatística.
- **Payload grande**: devolvido inteiro. O limite é o do tamanho de frame que o
  transporte já impõe; esta feature não acrescenta outro.

## Requirements *(mandatory)*

### Functional Requirements

#### A resposta

- **FR-001**: Os dois sockets, `ws/matchmaking/` e `ws/match/`, MUST responder a
  toda mensagem com `type` exatamente `ping` com um frame
  `{"type": "pong", "payload": {...}}`.
- **FR-002**: O pong MUST ir só ao socket que mandou o ping — nem a outros
  sockets do mesmo usuário, nem ao oponente, nem a grupo nenhum.
- **FR-003**: Quando o `payload` do ping é um objeto JSON, o `payload` do pong
  MUST ser o mesmo objeto: mesmas chaves, mesmos valores, em todos os níveis.
- **FR-004**: Quando o `payload` do ping está ausente, é `null`, ou é qualquer
  valor que não seja objeto, o `payload` do pong MUST ser `{}`.
- **FR-005**: O ping MUST NOT ser recusado, por nenhum motivo ligado ao
  `payload` ou a campos a mais na mensagem. Cada ping MUST produzir exatamente um
  pong, e os pongs MUST sair na ordem dos pings.
- **FR-006**: O servidor MUST NOT acrescentar nada ao eco — nem instante do
  servidor, nem identificador. O pong carrega só o que o FR-003 e o FR-004
  dizem.

#### Sem efeito

- **FR-007**: No socket de partida, o ping MUST NOT ler nem gravar a partida,
  MUST NOT criar versão, MUST NOT gerar `match_update` para ninguém, e MUST NOT
  alterar o prazo da vez nem o prazo do mulligan.
- **FR-008**: No socket de matchmaking, o ping MUST NOT colocar, retirar ou
  reposicionar ninguém na fila, MUST NOT consultar deck, e MUST NOT gerar
  `match_found` nem `matchmaking_failed`.
- **FR-009**: O ping MUST NOT gerar `message_refused`, registro de partida,
  alteração de estatística, nem escrita em armazenamento compartilhado de
  qualquer tipo.
- **FR-010**: O ping MUST NOT criar nem renovar a presença do usuário
  (`presence:user:<id>`). A decisão e os motivos estão em
  [Investigação](#a-presença-set_heartbeat).

#### Quando

- **FR-011**: O ping MUST funcionar em qualquer momento de um socket aceito: no
  de matchmaking, antes do `join_queue`, na fila, depois de uma recusa e depois
  do `match_found`; no de partida, em todas as fases, inclusive `finished`.
- **FR-012**: O gate de autenticação MUST continuar fechando como hoje, com
  `auth_denied` e 4001, e o gate da partida MUST continuar fechando com
  `match_denied` e 4400, 4403 ou 4404. O ping MUST NOT abrir exceção em nenhum
  dos dois.

#### O que continua recusado

- **FR-013**: `pong` recebido do cliente MUST ser recusado com
  `unknown_message_type`, nos dois sockets.
- **FR-014**: O reconhecimento do `type` MUST ser exato e sensível a
  maiúsculas: qualquer outro texto segue a regra de tipo desconhecido que já
  vale para aquele socket.
- **FR-015**: Frame binário, frame que não é JSON e JSON que não é objeto MUST
  continuar recusados com `malformed_message`, como hoje.

#### Uma regra só

- **FR-016**: A regra do ping — reconhecer, montar o eco, responder — MUST
  existir uma vez só, num ponto que os dois sockets percorrem. Nenhum dos dois
  sockets MUST ter cópia própria dela, e o ping MUST NOT entrar no conjunto de
  jogadas do protocolo de partida.

#### Contratos

- **FR-017**: A feature MUST ter contrato próprio em
  `specs/013-socket-heartbeat/contracts/`, com a forma do ping, a do pong, a
  regra do eco, e o que o ping não faz.
- **FR-018**: O contrato de mensagens do cliente da feature 009 e o contrato do
  socket de matchmaking da feature 011 MUST ganhar uma nota dizendo que `ping`
  existe nos dois sockets e não é recusado, apontando para o contrato desta
  feature.
- **FR-019**: O catálogo de códigos de recusa MUST continuar o mesmo: nenhum
  código novo, nenhum removido, nenhum com significado alterado.

#### O que não muda

- **FR-020**: O protocolo de partida (009), o relógio (010), o fluxo de
  matchmaking e de decks (011) e o registro de resultado (012) MUST continuar com
  o mesmo comportamento observável para toda mensagem que não seja ping.
- **FR-021**: O ping/pong do protocolo WebSocket, feito pelo servidor, MUST
  continuar configurado como hoje.

### Key Entities

- **Ping**: mensagem do cliente. `type` `ping`, `payload` opcional e de forma
  livre. Não é jogada, não é entrada de fila, não tem autor relevante.
- **Pong**: frame do servidor, só para o socket do ping. `type` `pong`,
  `payload` sempre objeto: o eco, ou `{}`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Nos dois sockets, 50 pings seguidos produzem exatamente 50 pongs,
  na mesma ordem, e zero `message_refused`.
- **SC-002**: Nos dois sockets, um ping com objeto aninhado volta idêntico campo
  a campo; pings com `payload` ausente, `null`, número, texto, booleano e lista —
  seis casos — voltam com `{}`, e nenhum é recusado.
- **SC-003**: No socket de partida, pings mandados em cada uma das fases
  (mulligan, ação, declaração, defesa, terminada) deixam a versão, o estado e os
  prazos do relógio idênticos aos de antes, e nenhum dos dois jogadores recebe
  `match_update`.
- **SC-004**: No socket de partida, ping num socket cuja partida terminou recebe
  pong; nenhum registro de partida novo aparece e nenhuma estatística muda.
- **SC-005**: No socket de matchmaking, pings antes do `join_queue`, na fila e
  depois de uma recusa deixam o conteúdo e a ordem da fila idênticos, e nenhum
  deck é consultado.
- **SC-006**: Pong nunca chega a outro socket: com dois jogadores numa partida e
  um segundo socket do mesmo usuário aberto, só o socket que mandou o ping recebe
  frame.
- **SC-007**: Socket recusado pelo gate de autenticação e pelos três gates da
  partida fecha com o mesmo motivo e o mesmo close code de hoje, com ou sem ping
  mandado.
- **SC-008**: `pong` mandado pelo cliente é recusado com `unknown_message_type`
  nos dois sockets.
- **SC-009**: A partida de fumaça contra o servidor local, com pings no meio da
  partida, termina com um desfecho e exatamente uma linha no histórico de cada
  jogador; cada ping recebe pong, nenhuma recusa é causada por ping, e a
  sequência de versões recebidas pelos bots não tem salto atribuível a ping.
- **SC-010**: Com o servidor local sem carga, o cliente recebe o pong em menos
  de 1 segundo — folga de sobra para um detector que arma no primeiro pong e
  declara queda depois de 30 s.
- **SC-011**: A suíte inteira (`cd server && pytest`) e a checagem de tipos
  continuam verdes, e nenhum teste existente de protocolo, relógio, matchmaking,
  decks ou histórico precisou ser alterado.

## Assumptions

- **O `type` é a única coisa que identifica o ping.** Campos a mais são
  ignorados, como em toda mensagem do protocolo desde a feature 009.
- **Sem limite de taxa.** O cliente manda um ping a cada 10 s; um cliente com
  bug que mande mais recebe mais pongs. Limitar taxa é outra feature, junto de
  qualquer outra proteção contra abuso dos sockets.
- **Sem limite de tamanho próprio para o eco.** Vale o limite de frame que o
  transporte já tem.
- **Sem log por ping.** Um ping a cada 10 s por socket encheria o log sem
  informar nada; nenhum ping é falha.
- **O ping não atesta que a partida existe.** Ele responde "o servidor recebeu
  este socket", não "sua partida está viva". Partida expirada aparece na próxima
  jogada, como hoje.
- **A presença continua adiada**, como o `Backend/TODO.md` já registra. As peças
  mortas ficam onde estão. Ao fim da feature, o item do `TODO.md` ganha uma linha
  dizendo que o ping de aplicação cliente→servidor existe e que presença e
  detecção de cliente travado continuam em aberto.
- **O roteiro de fumaça ganha pings no meio da partida.** É a prova contra o
  servidor de verdade; não entra na suíte, como o roteiro inteiro.

## Out of Scope

- O servidor fechar sockets ociosos por conta própria.
- O servidor detectar cliente vivo mas travado (ping servidor→cliente).
- Mudar intervalo ou timeout do detector do cliente.
- Heartbeat no protocolo WebSocket (`ws_ping_interval`, `ws_ping_timeout`).
- Presença de usuário, lista de online, e a limpeza das peças mortas de
  `set_heartbeat`.
- Limite de taxa ou de tamanho de mensagem.
- Aviso de oponente desconectado ou reconectado.
- Código do cliente.
