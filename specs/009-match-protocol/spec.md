# Feature Specification: Protocolo de partida

**Feature Branch**: `009-match-protocol`

**Created**: 2026-09-11

**Status**: Draft — pausada até a feature 008 (feitiço imediato)

> [!warning] Pausada
> Escrita antes da correção de 2026-09-11 do Fluxo de Partida, que removeu a
> pilha: feitiço resolve na hora. Esta spec ainda cita pilha, fizzle e feitiço
> imediato do defensor como ação separada. Revisar depois que a feature 008
> tirar a pilha do motor.

**Input**: User description: "Protocolo de partida: ligar o motor ao websocket. Receber as jogadas do cliente, passá-las pelo motor, gravar, e mandar a cada jogador a partida como ele pode vê-la."

> Nota de idioma: os títulos de seção ficam em inglês porque os comandos
> seguintes do Spec Kit (`/speckit-plan`, `/speckit-tasks`, `/speckit-analyze`)
> os localizam por esses nomes. O conteúdo segue em português, como o resto das
> notas do projeto.

Referência de domínio: `Game/Fluxo de Partida.md` no vault. Esta feature não
acrescenta regra nenhuma: a §3 (mulligan), a §4 a §8 (rodada, pilha, combate) e
a §10 (vitória) são consumidas como as features 003 a 007 as entregaram. A §13
registra o timeout de jogada como "problema de transporte, não de regra" — ele
continua fora, e fica para a feature de timers.

Hoje o motor está completo e testado de ponta a ponta sem rede, e nenhum
cliente consegue jogar uma carta. O socket de partida autentica, confere o
participante, manda a visão ao conectar, e para por aí. Esta feature é a ponte:
receber a jogada, validar a forma, passar pelo motor, gravar pelo caminho
atômico que já existe, e entregar a cada jogador a partida como **ele** pode
vê-la.

A armadilha concreta desta feature é a ocultação. O grupo de partida já existe,
e o repasse de mensagem de grupo encaminha o payload do jeito que chegou:
mandar uma visão pronta para o grupo entrega a mão de um jogador ao outro. O
que atravessa os workers pode ser interno ao servidor; o que sai para cada
cliente é sempre montado para aquele cliente.

A spec nomeia peças existentes — o gate de entrada, o envelope `{type,
payload}`, a gravação atômica, a visão por jogador, a porta única de ação do
motor — só como **fronteira**, nunca como desenho novo. É a convenção das specs
005 a 007: o que não pode ganhar uma segunda versão precisa ser nomeável para
ser verificável.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Mulligan pelo socket, e a Rodada 1 começa sozinha (Priority: P1)

Dois jogadores acabaram de receber `match_found` e abriram o socket de partida.
Cada um recebe a própria mão inicial e escolhe quais cartas trocar — de nenhuma
a todas —, citando cada carta pelo identificador de instância da partida.

A primeira escolha a chegar é aplicada e os dois recebem a partida atualizada:
quem escolheu vê a mão nova; o oponente fica sabendo que ele já respondeu e
quantas cartas trocou, nunca quais.

Quando a segunda escolha chega, a partida sai da espera e entra na Fase de Ação
da Rodada 1 — com o sorteio do token, a compensação e o Upkeep já executados —
**no mesmo passo**. Nenhum cliente manda "começar". Se dependesse de uma
terceira mensagem, a partida travaria esperando algo que ninguém sabe que
precisa mandar.

**Why this priority**: é a primeira coisa que um jogador faz numa partida, e
sem ela nenhuma outra jogada é alcançável. A transição automática é o ponto em
que o protocolo pode travar a partida inteira.

**Independent Test**: com uma partida recém-criada e dois sockets conectados,
mandar o mulligan de um e conferir a atualização dos dois; mandar o do outro e
conferir que os dois recebem a partida em Fase de Ação da Rodada 1, com
energia 1, token sorteado e prioridade no dono do token, sem nenhuma mensagem
adicional.

**Acceptance Scenarios**:

1. **Given** uma partida esperando os dois mulligans, **When** o jogador A
   manda a escolha de trocar duas cartas, **Then** A recebe a própria visão com
   a mão nova e B recebe a própria visão, onde consta que A já respondeu, e a
   descrição pública informa só que A trocou duas cartas.
2. **Given** A já respondeu, **When** B manda a escolha de trocar nenhuma
   carta, **Then** os dois recebem, numa mesma atualização, a partida na Fase
   de Ação da Rodada 1 com o Upkeep já executado.
3. **Given** a Rodada 1 começou, **When** eu conto as mensagens que os
   clientes mandaram, **Then** foram exatamente duas: um mulligan de cada.
4. **Given** A já respondeu, **When** A manda o mulligan de novo, **Then** só o
   socket que mandou recebe uma recusa com o código de mulligan repetido, e a
   partida não muda.
5. **Given** a partida já está na Rodada 1, **When** qualquer jogador manda um
   mulligan, **Then** recebe a mesma recusa de mulligan repetido.
6. **Given** a partida esperando mulligan, **When** um jogador manda uma ação
   de jogo (jogar unidade, passar, ...), **Then** recebe uma recusa com o
   código que o motor der, e a partida não muda.

---

### User Story 2 - Jogar a partida: cada jogada aceita chega aos dois, cada um a sua (Priority: P1)

Com a partida em andamento, quem tem a prioridade manda uma ação: jogar
unidade, lançar feitiço, passar ou declarar ataque; na janela do defensor,
atribuir bloqueador, remover bloqueador, lançar feitiço imediato ou encerrar a
janela.

O autor da jogada é **sempre** o usuário autenticado daquele socket. A mensagem
não diz quem age, e se disser, é ignorado.

Aceita a jogada, os dois jogadores recebem a partida atualizada — cada um a
própria visão — junto da descrição pública do que aconteceu. Uma cascata
inteira — os dois passam, a pilha resolve, a rodada vira, o Upkeep compra —
chega como **uma** atualização, com o estado já estabilizado.

**Why this priority**: é a feature. Sem isto o motor completo continua
inalcançável por qualquer cliente.

**Independent Test**: com uma partida na Fase de Ação, mandar pelo socket de
quem tem a prioridade uma unidade, depois um feitiço do oponente em resposta,
depois dois passes; conferir que cada jogada aceita produz exatamente uma
atualização em cada socket, que cada visão contém a mão do próprio dono e só o
tamanho da mão do outro, e que a última atualização já chega com a pilha
resolvida.

**Acceptance Scenarios**:

1. **Given** A com prioridade e energia suficiente, **When** A manda jogar a
   unidade de instância X, **Then** A e B recebem cada um a própria visão com X
   no banco de A, a prioridade em B, e a descrição pública informando que A
   jogou X.
2. **Given** a mesma jogada, **When** eu comparo as duas atualizações, **Then**
   a de A contém a mão de A e a de B não contém nenhuma carta da mão de A.
3. **Given** A com prioridade, **When** A manda uma jogada cujo payload traz o
   `user_id` de B como autor, **Then** a jogada é avaliada como de A.
4. **Given** B sem prioridade, **When** B manda uma jogada cujo payload traz o
   `user_id` de A como autor, **Then** B recebe a recusa de prioridade e a
   partida não muda.
5. **Given** A lançou um feitiço e B passou, **When** A passa, **Then** os dois
   recebem uma única atualização, com a pilha já resolvida e a partida de volta
   à Fase de Ação.
6. **Given** a pilha vazia e um passe já dado, **When** o segundo jogador
   passa, **Then** os dois recebem uma única atualização, já na Fase de Ação da
   rodada seguinte, com o Upkeep executado.
7. **Given** o dono do token declara ataque, **When** o defensor atribui dois
   bloqueadores, lança um feitiço imediato e encerra a janela, **Then** cada
   uma dessas quatro jogadas produz uma atualização nos dois sockets, e a
   última chega com o dano e a limpeza já feitos.
8. **Given** uma jogada que leva um Nexus a 0, **When** ela é aceita, **Then**
   os dois recebem a partida terminada com o resultado.

---

### User Story 3 - Recusa com código estável, só para quem mandou (Priority: P1)

O cliente não é confiável. Toda mensagem é validada na forma antes de chegar ao
motor: tipo conhecido, campos presentes, tipos certos. O motor valida a regra;
esta camada valida a forma. Mensagem malformada nunca chega ao motor.

Uma recusa — de forma ou de regra — vai só para o socket que mandou, carrega um
código estável que o cliente consegue comparar e uma mensagem legível, deixa a
partida exatamente como estava, e não fecha o socket.

Hoje uma mensagem sem `type`, ou com um `type` sem tratamento, é ignorada em
silêncio. Isso muda.

**Why this priority**: o cliente Unity casa recusa por texto estável, e frase
em inglês com valores dentro não serve de chave. Sem código estável o cliente
não sabe por que a jogada falhou; sem recusa de forma, um cliente com bug trava
esperando resposta a uma mensagem que o servidor jogou fora.

**Independent Test**: mandar, por um socket, cada espécie de mensagem
malformada e uma jogada ilegal de cada espécie de recusa do motor; conferir
para cada uma: recusa só naquele socket, código esperado, partida inalterada,
socket aberto, e nenhum frame no socket do oponente.

**Acceptance Scenarios**:

1. **Given** um socket de partida aceito, **When** ele manda uma mensagem sem
   `type`, **Then** recebe uma recusa com o código de mensagem malformada, e o
   socket continua aberto.
2. **Given** um socket aceito, **When** ele manda um `type` que não existe,
   **Then** recebe uma recusa com o código de tipo desconhecido.
3. **Given** um socket aceito, **When** ele manda jogar unidade sem o
   identificador de carta, ou com o identificador em texto, fracionário,
   booleano ou nulo, **Then** recebe uma recusa de forma, e o motor não é
   consultado.
4. **Given** um socket aceito, **When** ele manda um frame que não é um objeto
   JSON válido, **Then** recebe uma recusa de forma e o socket continua aberto.
5. **Given** A sem energia para a carta, **When** A manda jogá-la, **Then** A
   recebe a recusa de energia com o código dela, B não recebe nada, e a partida
   é idêntica à anterior.
6. **Given** duas recusas diferentes do motor, **When** eu comparo os códigos,
   **Then** eles são diferentes.
7. **Given** a mesma recusa provocada duas vezes com valores diferentes (cartas,
   custos), **When** eu comparo os códigos, **Then** eles são iguais.
8. **Given** uma recusa qualquer, **When** o socket manda em seguida uma jogada
   legal, **Then** ela é aceita normalmente.

---

### User Story 4 - Nenhum frame entrega o que o jogador não pode ver (Priority: P1)

A ocultação da feature 002 vale para **todo** frame que sai para um cliente:
visão ao conectar, atualização, descrição do que aconteceu, e recusa. Nenhum
contém a mão do oponente, nem o conteúdo ou a ordem de nenhum deck.

A descrição pública segue a mesma fronteira: carta jogada, feitiço lançado,
bloqueio atribuído e ataque declarado são públicos; o mulligan do oponente
revela só quantas cartas ele trocou; uma compra do oponente revela só que ele
comprou.

**Why this priority**: é o requisito de segurança do jogo. Um vazamento aqui
não aparece em nenhum teste de regra, e entrega a partida a quem ler o tráfego.

**Independent Test**: jogar uma partida inteira por dois sockets registrando
todo frame recebido por cada um, e conferir que nenhum frame recebido por A
contém identificador de instância de carta que, naquele momento, estava na mão
ou no deck de B — nem o `card_id` correspondente —, e vice-versa.

**Acceptance Scenarios**:

1. **Given** uma partida jogada do mulligan ao fim, **When** eu varro todos os
   frames recebidos por A, **Then** nenhum contém carta que estava na mão ou no
   deck de B no momento do frame.
2. **Given** B trocou três cartas no mulligan, **When** A recebe a
   atualização, **Then** ela informa que B trocou três cartas e não identifica
   nenhuma delas, nem as compradas no lugar.
3. **Given** o Upkeep compra uma carta para cada jogador, **When** A recebe a
   atualização, **Then** ela identifica a carta que A comprou e informa de B só
   que ele comprou.
4. **Given** A cita numa jogada uma carta que está na mão de B, **When** A
   recebe a recusa, **Then** ela é indistinguível da recusa de uma carta que
   não existe.
5. **Given** A e B têm a mesma partida, **When** o servidor entrega uma
   atualização aos dois, **Then** o que sai para cada socket foi montado para o
   dono daquele socket.

---

### User Story 5 - Reconectar em qualquer ponto devolve o estado atual (Priority: P2)

Reconectar continua sendo conectar de novo e receber a visão atual, em qualquer
momento da partida: durante o mulligan, com a pilha cheia, com o combate
aberto, ou depois do fim.

A visão passa a bastar para o jogador saber o que se espera dele. Hoje ela não
diz se o mulligan **daquele** jogador já foi enviado: quem reconecta durante a
espera não sabe se deve escolher ou aguardar o oponente. Isso entra, e do
oponente a visão revela só se ele já respondeu ou não.

**Why this priority**: a reconexão já funciona e não pode quebrar; o que falta
é um campo sem o qual o cliente fica sem saber o que desenhar durante a espera
do mulligan. É P2 porque o fluxo feliz não depende dela.

**Independent Test**: em cada um dos pontos — nenhum mulligan enviado, só o
próprio enviado, só o do oponente enviado, pilha com feitiço, combate aberto,
partida terminada — derrubar o socket, reconectar, e conferir que a visão
recebida é a do estado gravado e diz corretamente o que se espera do jogador.

**Acceptance Scenarios**:

1. **Given** A já mandou o mulligan e B não, **When** A reconecta, **Then** a
   visão de A diz que o mulligan dele foi enviado e que o oponente ainda não
   respondeu.
2. **Given** a mesma partida, **When** B reconecta, **Then** a visão de B diz
   que o mulligan dele não foi enviado e que o oponente já respondeu, sem dizer
   quantas nem quais cartas A trocou.
3. **Given** um feitiço na pilha, **When** um jogador reconecta, **Then** a
   visão traz a pilha e a prioridade atuais.
4. **Given** um combate aberto, **When** o defensor reconecta, **Then** a visão
   traz os atacantes e os bloqueios atribuídos até ali.
5. **Given** uma partida terminada, **When** um jogador reconecta, **Then** a
   visão traz o resultado.

---

### User Story 6 - Concorrência: workers diferentes e sockets repetidos (Priority: P2)

Os dois jogadores podem estar conectados a workers diferentes e agir ao mesmo
tempo — o mulligan é simultâneo por regra, e fora dele o jogador sem prioridade
pode mandar uma jogada que chega junto da do outro. Nenhuma escrita se perde:
quem perdeu a disputa é avaliado contra o estado que a outra jogada deixou, e é
aceito ou recusado por ele.

O mesmo usuário pode ter dois sockets abertos na mesma partida. Os dois recebem
as atualizações dele, e jogar por qualquer um vale.

**Why this priority**: a gravação atômica já resolve a disputa na camada de
estado; o que esta feature precisa garantir é que o protocolo a use sempre e
não reintroduza a perda por outro caminho — em especial, avaliando jogada
contra um estado guardado pela conexão.

**Independent Test**: com dois sockets em workers simulados distintos, mandar
os dois mulligans ao mesmo tempo repetidas vezes e conferir que a partida
sempre chega à Rodada 1 com os dois mulligans aplicados; abrir dois sockets do
mesmo jogador, jogar por um, e conferir a atualização nos dois.

**Acceptance Scenarios**:

1. **Given** A e B em workers diferentes esperando mulligan, **When** os dois
   mandam a escolha ao mesmo tempo, **Then** as duas são aplicadas e a partida
   entra na Rodada 1.
2. **Given** A com prioridade e B sem, **When** os dois mandam jogadas ao mesmo
   tempo, **Then** a de A é aceita e a de B é recusada contra o estado que a de
   A deixou — ou, se B ganhou a prioridade com a jogada de A, avaliada como
   legal por esse estado.
3. **Given** um socket conectado há muito tempo, **When** ele manda uma jogada
   depois de várias outras aceitas pelos dois lados, **Then** ela é avaliada
   contra o estado gravado agora, nunca contra o que o socket recebeu ao
   conectar.
4. **Given** A com dois sockets na mesma partida, **When** A joga por um deles,
   **Then** os dois sockets de A recebem a atualização, e B recebe a dele.
5. **Given** A com dois sockets, **When** um deles manda uma jogada ilegal,
   **Then** só esse socket recebe a recusa.
6. **Given** duas atualizações da mesma partida que chegam a um socket fora da
   ordem em que foram gravadas, **When** o cliente compara as duas, **Then** ele
   consegue dizer qual é a mais recente.

---

### User Story 7 - Uma partida inteira pela rede, do pareamento ao resultado (Priority: P3)

Dois clientes autenticados saem do `match_found`, enviam o mulligan, entram na
Rodada 1 sem mensagem extra, alternam unidades, feitiços, respostas na pilha e
combates até um Nexus chegar a zero, e recebem o resultado. Dali em diante toda
jogada é recusada.

**Why this priority**: é a prova de integração de todas as outras histórias; não
entrega comportamento novo sozinha.

**Independent Test**: roteiro fixo de jogadas, com aleatoriedade determinística,
executado por dois sockets do pareamento ao resultado, conferindo em cada passo
a visão de cada um e, no fim, o resultado e a recusa de uma jogada a mais.

**Acceptance Scenarios**:

1. **Given** dois jogadores pareados, **When** o roteiro roda até um Nexus
   chegar a 0, **Then** os dois recebem a partida terminada com o mesmo
   resultado.
2. **Given** a partida terminada, **When** qualquer jogador manda qualquer
   jogada, **Then** recebe a recusa de partida terminada, só ele.
3. **Given** a partida terminada, **When** qualquer jogador manda um mulligan,
   **Then** recebe uma recusa, e a partida não muda.

---

### Edge Cases

- **Autor forjado**: payload com `user_id`, `actor_user_id` ou qualquer campo
  de autor apontando para o oponente. O campo é ignorado; a jogada é avaliada
  como do dono do socket. Não é recusa de forma — um campo a mais não torna a
  mensagem malformada.
- **Campos a mais em geral**: ignorados, pela mesma razão. Só campos faltando
  ou de tipo errado são recusa de forma.
- **Mensagem sem `type`, `type` vazio, `type` que não é texto, `type`
  desconhecido**: recusa com código, só para quem mandou.
- **`payload` ausente ou que não é objeto** numa mensagem cujo tipo exige
  campos: recusa de forma. Num tipo sem campos (passar, encerrar a janela), a
  ausência de `payload` é aceita.
- **Frame que não é JSON, JSON que não é objeto, frame binário**: recusa de
  forma, socket aberto.
- **Identificador de carta em formato inválido** — texto, fracionário,
  booleano, nulo onde não pode, negativo, lista onde se espera um só: recusa de
  forma, sem chegar ao motor.
- **Lista vazia de atacantes**: não é recusa de forma — a lista está bem
  formada. Chega ao motor, que a recusa com o código dele.
- **Mulligan com carta repetida, ou com carta que não está na mão**: bem
  formado; recusa do motor.
- **Mulligan de nenhuma carta**: escolha válida e resposta completa, diferente
  de não ter respondido.
- **Mulligan pela segunda vez, ou depois do setup**: recusa com o código de
  mulligan repetido do motor.
- **Jogada durante o mulligan**: recusa com o código da recusa que o motor
  der. A ordem das guardas do motor é contrato da feature 005 e não muda para
  caber no protocolo.
- **Jogada sobre estado velho**: avaliada contra o estado gravado agora. Se
  continua legal, é aceita; se não, recusada como qualquer outra.
- **Disputa perdida na gravação**: a jogada é reavaliada contra o estado que a
  outra deixou. O que é entregue aos jogadores descreve a tentativa que foi
  gravada, nunca uma tentativa descartada.
- **Disputa que não converge** depois das tentativas que a gravação atômica
  permite: recusa com código próprio, só para quem mandou, partida sem a
  jogada.
- **Partida que expirou do armazenamento** entre a conexão e a jogada: recusa
  com código próprio, só para quem mandou, sem derrubar o processo nem o
  socket.
- **Falha inesperada do servidor ao processar uma jogada**: recusa com código
  genérico, só para quem mandou, partida sem gravação, socket aberto, e nenhum
  detalhe interno na mensagem.
- **Jogada depois do fim**: recusa de partida terminada.
- **Atualizações entregues fora de ordem** a um socket, porque duas gravações
  em workers diferentes foram repassadas em tempos diferentes: o cliente
  identifica a mais recente, e a visão ao conectar carrega a mesma indicação
  para ser comparada com atualizações em trânsito.
- **Recusa que citaria informação oculta**: citar uma carta da mão do oponente
  recebe a mesma recusa de uma carta inexistente. A mensagem legível da recusa
  nunca lista mão alheia nem conteúdo de deck.
- **Identificador de carta oculta**: o identificador de instância de uma carta
  enquanto ela está na mão ou no deck de alguém é informação oculta para o
  outro jogador, tanto quanto o `card_id` dela.
- **Dois sockets do mesmo jogador**: os dois recebem as atualizações; a recusa
  vai só para o socket que mandou.
- **Socket recusado pelos gates 44xx** que ainda manda mensagem antes do close:
  não chega ao motor.

## Requirements *(mandatory)*

### Functional Requirements

**Entrada**

- **FR-001**: O socket de partida MUST aceitar, do cliente, a escolha de
  mulligan: a lista das cartas da própria mão a trocar, de nenhuma a todas.
- **FR-002**: O socket de partida MUST aceitar, do cliente, cada uma das oito
  ações que o motor aceita: jogar unidade, lançar feitiço, passar, declarar
  ataque, atribuir bloqueador, remover bloqueador, lançar feitiço imediato e
  encerrar a janela do defensor. Nenhuma ação a mais, nenhuma a menos.
- **FR-003**: Toda carta citada numa mensagem MUST ser citada pelo
  identificador de instância da partida, nunca pelo `card_id` do catálogo.
- **FR-004**: O autor de toda jogada MUST ser o usuário autenticado do socket
  que a recebeu. Nenhum campo da mensagem MUST alterar quem age.
- **FR-005**: Toda mensagem MUST ser validada na forma — tipo conhecido, campos
  presentes, tipos certos — antes de chegar ao motor. Mensagem malformada MUST
  NOT chegar ao motor.
- **FR-006**: Campos que a mensagem não precisa MUST ser ignorados, não
  recusados.
- **FR-007**: Toda jogada MUST ser avaliada contra o estado da partida gravado
  no momento da avaliação, nunca contra um estado guardado pela conexão nem
  contra o que o cliente acredita ver.
- **FR-008**: Toda mutação de partida desta feature MUST passar pela gravação
  atômica existente, que não perde escrita entre workers.

**O fim do setup**

- **FR-009**: Quando o segundo mulligan é aceito, a partida MUST sair da espera
  e chegar à Fase de Ação da Rodada 1, com o sorteio do token, a compensação e
  o Upkeep executados, na **mesma** mutação gravada.
- **FR-010**: Nenhuma mensagem de cliente além dos dois mulligans MUST ser
  necessária para a Rodada 1 começar.

**Saída**

- **FR-011**: Depois de toda mudança aceita, todo socket aberto dos dois
  jogadores naquela partida MUST receber a partida atualizada, montada para o
  dono daquele socket.
- **FR-012**: O que é entregue a cada cliente MUST ser montado para aquele
  cliente. Uma visão montada para um jogador MUST NOT ser entregue a outro, nem
  por repasse de grupo.
- **FR-013**: Junto da partida atualizada, cada jogador MUST receber a
  descrição do que aconteceu, até onde ela é pública para ele, na mesma
  atualização.
- **FR-014**: A descrição do que aconteceu MUST cobrir a jogada aceita **e** o
  que ela causou em seguida — efeito de feitiço, unidades que morreram, dano
  de combate, virada de rodada, compras do Upkeep e da compensação, fim da
  partida —, cada item recortado pelo que aquele jogador pode ver.
- **FR-015**: Carta jogada, feitiço lançado (com o alvo), ataque declarado (com
  os atacantes), bloqueio atribuído e bloqueio removido MUST ser descritos aos
  dois jogadores por inteiro.
- **FR-016**: O mulligan do oponente MUST ser descrito só pela quantidade de
  cartas trocadas. O próprio mulligan MAY ser descrito por inteiro ao autor.
- **FR-017**: Uma compra do oponente MUST ser descrita só como o fato de que
  ele comprou. A própria compra MAY identificar a carta.
- **FR-018**: Uma cascata inteira MUST chegar a cada socket como **uma**
  atualização, com o estado já estabilizado. Nenhum estado intermediário da
  cascata MUST ser entregue.
- **FR-019**: Uma jogada que termina a partida MUST entregar aos dois a partida
  terminada com o resultado.
- **FR-020**: Cada atualização e a visão enviada ao conectar MUST carregar uma
  indicação de sua posição na sequência de mudanças gravadas da partida, de
  modo que o cliente identifique a mais recente entre duas.

**Recusa**

- **FR-021**: Mensagem malformada e jogada ilegal MUST ser respondidas com uma
  recusa, e MUST deixar a partida exatamente como estava.
- **FR-022**: A recusa MUST ir só para o socket que mandou a mensagem. O
  oponente MUST NOT receber nada que revele a tentativa, e os outros sockets do
  mesmo jogador também não.
- **FR-023**: A recusa MUST NOT fechar o socket. Os códigos de fechamento 44xx
  continuam exclusivos dos gates de entrada.
- **FR-024**: A recusa MUST carregar um código estável e uma mensagem legível. O
  código MUST NOT conter valores variáveis da jogada.
- **FR-025**: Cada espécie de recusa do motor MUST ter o seu código, e duas
  espécies diferentes MUST NOT compartilhar código — incluindo espécies em que
  uma é caso particular da outra, como partida terminada e fase que proíbe a
  ação.
- **FR-026**: A recusa de forma MUST distinguir, por código, ao menos: tipo
  ausente ou desconhecido, e mensagem com campo faltando ou de tipo errado.
- **FR-027**: O protocolo MUST definir recusas próprias, com código, para:
  partida que não existe mais no armazenamento, disputa de gravação que não
  convergiu, e falha inesperada do servidor.
- **FR-028**: O conjunto de códigos de recusa MUST ser um contrato documentado,
  para o cliente casar com ele sem ler o servidor.
- **FR-029**: Nenhuma recusa MUST revelar informação oculta: citar carta da mão
  do oponente MUST produzir a mesma recusa que citar carta inexistente, e a
  mensagem legível MUST NOT listar mão alheia nem conteúdo ou ordem de deck.
- **FR-030**: Mensagem sem `type` ou com `type` sem tratamento MUST deixar de
  ser ignorada em silêncio e MUST receber recusa.

**Ocultação**

- **FR-031**: Nenhum frame enviado a um cliente — visão, atualização,
  descrição ou recusa — MUST conter carta da mão do oponente, nem conteúdo ou
  ordem de nenhum deck.
- **FR-032**: O identificador de instância de uma carta enquanto ela está na
  mão ou no deck de um jogador MUST NOT aparecer em nenhum frame enviado ao
  outro jogador.

**Reconexão**

- **FR-033**: Reconectar MUST continuar sendo conectar de novo e receber a visão
  atual, em qualquer fase da partida, inclusive depois do fim.
- **FR-034**: A visão MUST dizer se o mulligan do próprio jogador já foi
  enviado.
- **FR-035**: A visão MUST dizer se o oponente já respondeu o mulligan, e MUST
  NOT revelar mais nada do mulligan dele.

**Concorrência**

- **FR-036**: Duas jogadas simultâneas sobre a mesma partida, em workers
  diferentes, MUST NOT perder escrita. A que perder a disputa MUST ser avaliada
  contra o estado que a outra deixou.
- **FR-037**: O que é entregue aos jogadores MUST descrever a mutação que foi
  gravada, nunca uma tentativa descartada na disputa.
- **FR-038**: Um usuário com mais de um socket aberto na mesma partida MUST
  receber as atualizações em todos, e MUST poder jogar por qualquer um.

**O que não pode quebrar**

- **FR-039**: Os gates de entrada do socket de partida e seus códigos 44xx MUST
  continuar como estão.
- **FR-040**: O envio da visão ao conectar MUST continuar como o caminho da
  reconexão.
- **FR-041**: O `match_found` do matchmaking e o fluxo de o cliente abrir o
  socket de partida em seguida MUST continuar como estão.
- **FR-042**: Nenhuma regra do motor MUST mudar para caber no transporte. Se
  faltar uma porta pública ao motor, ela MUST ser acrescentada, não contornada.
- **FR-043**: A recusa de autenticação e o envelope `{type, payload}` MUST
  continuar como estão para os outros sockets.

### Key Entities

- **Mensagem de jogada**: o que o cliente manda. Uma espécie (mulligan ou uma
  das oito ações) e os campos daquela espécie — identificadores de instância de
  carta, e nada que diga quem age.
- **Recusa**: resposta a uma mensagem que não virou mudança. Código estável,
  mensagem legível, destinada a um socket só. Duas famílias: de forma e de
  regra, mais as três do próprio protocolo (partida expirada, disputa sem
  convergência, falha inesperada).
- **Catálogo de códigos de recusa**: o conjunto fechado e documentado de
  códigos, um por espécie de recusa. É contrato com o cliente.
- **Atualização de partida**: o que cada socket recebe depois de uma mudança
  aceita. A visão do dono do socket, a descrição do que aconteceu recortada
  para ele, e a posição da mudança na sequência da partida.
- **Descrição do que aconteceu**: o relato público de uma mudança aceita,
  recortado por destinatário — por inteiro para o que é público, reduzido a
  contagem ou a fato para o que é oculto.
- **Visão do jogador**: a que já existe, acrescida de se o próprio mulligan foi
  enviado, se o oponente já respondeu, e da posição na sequência de mudanças.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Dois clientes pareados jogam uma partida inteira, do mulligan ao
  resultado, mandando só jogadas — zero mensagens de controle além delas.
- **SC-002**: Em uma partida inteira jogada pela rede, 100% das jogadas aceitas
  produzem exatamente uma atualização em cada socket aberto dos dois jogadores.
- **SC-003**: Numa varredura de todos os frames recebidos pelos dois jogadores
  numa partida inteira, 0 frames contêm carta da mão do oponente, ou conteúdo
  ou ordem de deck.
- **SC-004**: 100% das mensagens malformadas e jogadas ilegais testadas recebem
  recusa só no socket que mandou, com o socket aberto e a partida idêntica à
  anterior.
- **SC-005**: 100% das espécies de recusa do motor têm código próprio, e 0 pares
  de espécies diferentes compartilham código.
- **SC-006**: Reconectar em cada um dos seis pontos — nenhum mulligan enviado,
  só o próprio, só o do oponente, pilha com feitiço, combate aberto, partida
  terminada — devolve o estado gravado e o que se espera do jogador, em 100%
  das tentativas.
- **SC-007**: Em 100 repetições de mulligans simultâneos em workers diferentes,
  100 partidas chegam à Rodada 1 com os dois mulligans aplicados.
- **SC-008**: Em ambiente local, a atualização de uma jogada aceita chega aos
  dois jogadores em menos de 1 segundo.
- **SC-009**: 100% dos testes existentes dos gates de entrada, da visão ao
  conectar, do matchmaking e do motor continuam passando sem alteração de
  expectativa.

## Assumptions

- **Recusa por partida expirada não fecha o socket.** A regra geral da feature
  é que recusa não derruba conexão, e os 44xx são dos gates de entrada. O
  cliente decide o que fazer com um socket de partida que não existe mais.
- **A recusa vai só ao socket que mandou**, não aos outros sockets do mesmo
  jogador: "só para quem mandou" é lido como a conexão, e os outros sockets
  não têm contexto para interpretar uma recusa que não pediram.
- **Jogada durante o mulligan recebe a recusa que o motor der.** Hoje, pela
  ordem participante → prioridade → fase da feature 005, é a de prioridade,
  porque ninguém tem a vez antes do sorteio. O protocolo não reordena guardas
  do motor para escolher uma recusa mais bonita.
- **O mesmo motivo de recusa em lugares diferentes é o mesmo código.** Carta
  fora da mão no mulligan e na jogada é a mesma espécie, e o motor já a trata
  como uma só.
- **A recusa de tipo desconhecido vale para todo socket que usa o envelope
  comum**, não só o de partida: é o envelope que muda, e nenhum dos outros
  sockets aceita mensagem hoje, então nenhum comportamento deles se perde.
- **O identificador de instância de carta oculta é tratado como oculto** porque
  identificadores são cunhados em sequência a partir da lista do deck, e quem
  os visse poderia inferir cartas. O servidor já proíbe derivar fatos do valor;
  a proibição aqui é não entregá-lo.
- **Não há confirmação separada para o autor.** A atualização que o autor
  recebe, igual em forma à do oponente, é a confirmação de que a jogada foi
  aceita.
- **Decks continuam vindo do `starter_deck`.** Deck em banco e escolha de deck
  na fila ficam fora.
- **Fora de escopo**: timeout de jogada, jogador ausente, abandono, aviso de
  oponente desconectado (feature de timers); histórico, ranking, recompensa, e
  qualquer destino da partida terminada além de recusar jogadas até expirar;
  espectadores; código do cliente; limite de taxa de mensagens.
- **Dependências**: a gravação atômica de partida (feature 003), a visão por
  jogador com ocultação por tipo (feature 002), a porta única de ação e a
  cascata (feature 005), a pilha (006), o combate (007), e os gates de entrada
  e o envelope dos consumers existentes.
