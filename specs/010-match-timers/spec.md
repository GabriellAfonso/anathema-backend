# Feature Specification: Relógio da vez, e a correção do SACRIFICIAL FIRE

**Feature Branch**: `010-match-timers`

**Created**: 2026-09-11

**Status**: Draft

**Input**: User description: "Relógio da vez (§15), e uma correção de regra no SACRIFICIAL FIRE (§14). Duas partes independentes na mesma feature: a correção é pequena e não depende do relógio; o relógio é a parte grande."

> Nota de idioma: os títulos de seção ficam em inglês porque os comandos
> seguintes do Spec Kit os localizam por esses nomes. O conteúdo segue em
> português, como o resto das notas do projeto.

Referência de domínio: `Game/Fluxo de Partida.md` no vault, na versão com as
duas correções de 2026-09-11. A §14 é a regra do SACRIFICIAL FIRE, a §15 é o
relógio, e a §12 tem as constantes: **30s + 15s** por vez, **30s** no mulligan.

O resto das duas correções já está no motor e bate com a nota: feitiço que
resolve na hora e não gasta a vez, energia acumulando, declaração como janela
com puxar de volta, MAGIC BARRIER absorvendo o próximo dano, fim do empate e
desistência a qualquer momento. Esta feature não mexe em nada disso.

**Parte 1.** O motor implementa uma versão do SACRIFICIAL FIRE que a §14 não
diz: hoje ele exige alvo — uma unidade própria na zona de ataque — e só ela
ganha +3. A §14 diz "sem alvo; **todas** as unidades do atacante que estão na
zona de ataque naquele instante ganham +3". O código está errado, e a
descrição da carta e os testes repetem o erro.

**Parte 2.** Nenhuma vez tem relógio hoje. Um jogador que fecha o jogo no meio
da vez congela a partida para o outro até ela expirar. O relógio é problema de
transporte, não de regra: o motor não lê tempo e não muda. Quando o relógio
estoura, a camada de transporte manda ao motor uma ação comum, pela mesma
porta, como se o jogador a tivesse mandado.

A spec nomeia peças existentes — a porta única de ação do motor, a gravação
atômica, a visão por jogador, a descrição pública, o catálogo de códigos de
recusa — só como **fronteira**, nunca como desenho novo. É a convenção das specs
005 a 009.

## Vocabulário desta feature

- **Vez**: o intervalo em que um jogador deve a jogada, na Fase de Ação, na
  Declaração (§7.1) ou na Defesa (§7.2). Mulligan não tem vez: tem um prazo por
  jogador.
- **Vez nova**: começa quando a partida passa a esperar um jogador **e** (a)
  esse jogador é outro que não o da vez anterior, ou (b) a rodada é outra.
  Nenhuma outra coisa começa vez nova. Ir da Fase de Ação para a Declaração, ou
  voltar dela puxando o último atacante, é a mesma vez.
- **Aviso**: o frame "seu tempo está acabando", 30s depois do início da vez.
- **Estouro**: 45s depois do início da vez. A ação automática da fase é
  aplicada em nome de quem deve a jogada.
- **Ação automática**: passar (Fase de Ação), **Atacar** (Declaração),
  **Resolver** (Defesa), ou confirmar o mulligan sem trocar nada.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - SACRIFICIAL FIRE sem alvo, para toda a zona de ataque (Priority: P1)

Na declaração, o atacante joga o SACRIFICIAL FIRE sem escolher alvo. Toda
unidade dele que está na zona de ataque naquele instante ganha +3 de ataque,
para sempre, e ele paga 8 de Nexus sem cair abaixo de 1. Uma unidade mandada
para a zona depois do lançamento não ganha nada.

Mandar o SACRIFICIAL FIRE com alvo passa a ser recusado como qualquer feitiço
sem alvo que recebe um. O resto da §14 não muda: só na declaração, só pelo
atacante.

**Why this priority**: é regra do jogo errada em produção, e o cliente
desenharia uma mira que a carta não tem. É pequena e não depende do relógio.

**Independent Test**: com a declaração aberta e duas unidades na zona, lançar o
FIRE sem alvo e conferir +3 nas duas e o custo em Nexus; mandar uma terceira
unidade e conferir que ela não tem +3; lançar outro FIRE com alvo e conferir a
recusa de feitiço sem alvo.

**Acceptance Scenarios**:

1. **Given** a declaração aberta com as unidades X e Y na zona de ataque e o
   FIRE na mão do atacante, **When** ele lança o FIRE sem alvo, **Then** X e Y
   ganham +3 de ataque cada, o Nexus dele cai 8 (sem ficar abaixo de 1), e a
   vez continua com ele.
2. **Given** o FIRE já lançado sobre X e Y, **When** o atacante manda Z para a
   zona, **Then** Z tem o ataque de base, sem +3.
3. **Given** a declaração aberta com X na zona, **When** o atacante lança o FIRE
   com X como alvo, **Then** recebe a recusa de feitiço que não aceita alvo, e a
   partida não muda.
4. **Given** a declaração aberta com X na zona, **When** o atacante lança o FIRE
   mirando uma unidade do defensor, ou uma unidade própria fora da zona,
   **Then** recebe a mesma recusa de feitiço que não aceita alvo.
5. **Given** o atacante com Nexus 1, **When** ele lança o FIRE sem alvo,
   **Then** as unidades da zona ganham +3 e o Nexus continua 1.
6. **Given** a Fase de Ação ou a Defesa, **When** qualquer jogador lança o FIRE
   sem alvo, **Then** recebe a recusa de feitiço só na declaração, como hoje.
7. **Given** X com +3 do FIRE, **When** o atacante puxa X de volta ao banco,
   **Then** X continua com +3 — a pergunta aberta da §13 fica como está.
8. **Given** o FIRE aceito pelo socket, **When** os dois jogadores recebem a
   atualização, **Then** a descrição pública informa o feitiço lançado sem
   alvo, e a visão de cada um mostra o +3 em cada unidade da zona.

---

### User Story 2 - A vez estoura sozinha: aviso aos 30s, ação automática aos 45s (Priority: P1)

Quem deve a jogada tem 45 segundos. Aos 30 recebe o aviso de que o tempo está
acabando. Aos 45, se a vez ainda é dele, o servidor faz a ação automática da
fase em nome dele: passar na Fase de Ação, **Atacar** com o que estiver na
zona na Declaração, **Resolver** com os bloqueadores já atribuídos na Defesa.

A ação automática passa pelo mesmo caminho de toda jogada — a mesma porta do
motor, a mesma gravação atômica — e os dois jogadores recebem a partida
atualizada, cada um a sua visão, com a descrição pública do que aconteceu. A
descrição diz que foi o relógio, para o cliente distinguir "o oponente passou"
de "o tempo do oponente acabou".

**Why this priority**: é a razão da feature. Sem estouro, um jogador que some
congela a partida do outro.

**Independent Test**: com tempo injetado, abrir uma vez em cada uma das três
fases, avançar o relógio para 30s e conferir o aviso, avançar para 45s e
conferir a ação automática, a atualização nos dois sockets e a marca de relógio
na descrição — sem esperar tempo real.

**Acceptance Scenarios**:

1. **Given** uma vez da Fase de Ação que começou há 29s, **When** o relógio
   chega a 30s, **Then** os sockets abertos de quem deve a jogada recebem o
   aviso, e o oponente não recebe frame nenhum.
2. **Given** a mesma vez, **When** o relógio chega a 45s, **Then** a partida
   registra um passe do dono da vez, a vez vai ao oponente com relógio novo, e
   os dois recebem uma atualização cuja descrição marca o passe como estouro.
3. **Given** a Declaração com duas unidades na zona de ataque, **When** a vez
   do atacante estoura, **Then** o ataque é confirmado com as duas, e a vez vai
   ao defensor com relógio novo.
4. **Given** a Defesa sem bloqueador atribuído, **When** a vez do defensor
   estoura, **Then** o combate resolve com todo atacante passando direto, e a
   vez vai ao dono do token com relógio novo.
5. **Given** a Defesa com um bloqueador atribuído, **When** a vez estoura,
   **Then** o combate resolve com aquele bloqueio.
6. **Given** um estouro que dá o segundo passe seguido, **When** ele é aplicado,
   **Then** os dois recebem **uma** atualização já na rodada seguinte, como
   receberiam com um passe mandado pelo socket.
7. **Given** um estouro que leva a partida ao fim — um **Resolver** automático
   que zera um Nexus —, **When** ele é aplicado, **Then** os dois recebem a
   partida terminada com resultado e motivo, e nenhum relógio segue correndo.
8. **Given** a vez terminou antes dos 30s, **When** o relógio passa dos 30s da
   vez antiga, **Then** ninguém recebe aviso dela.

---

### User Story 3 - O relógio é da vez, não da ação (Priority: P1)

Jogar feitiço, mandar atacante, puxar atacante de volta e atribuir ou remover
bloqueador **não** reiniciam o relógio. Ele reinicia quando começa vez nova: a
prioridade foi ao outro jogador, a Defesa começou, o combate acabou, ou a
rodada virou.

É o que impede enrolar a partida: sem isso, um atacante mandaria e puxaria a
mesma unidade para sempre, ou um jogador lançaria feitiço barato só para zerar
o relógio.

A virada de rodada merece nome próprio. Os dois passes seguidos sempre devolvem
a vez a **quem deu o segundo passe**: ele não tinha o token, recebe o token na
troca da §8, e o Upkeep da §4 dá a prioridade ao dono do token. A cascata
termina com a vez no mesmo jogador que acabou de passar — e isso é vez nova,
com relógio novo. Se não fosse, o passe por estouro abriria a rodada seguinte
com o prazo já vencido, e o mesmo jogador estouraria de novo na hora.

**Why this priority**: sem esta regra o relógio existe e não protege nada.

**Independent Test**: com tempo injetado, fazer em uma vez, espaçados, feitiço,
mandar e puxar atacante, atribuir e remover bloqueador; conferir que o estouro
cai aos 45s do início da vez, e que cada troca de mão e a virada de rodada
abrem prazo novo.

**Acceptance Scenarios**:

1. **Given** uma vez da Fase de Ação, **When** o dono lança um feitiço aos 40s,
   **Then** o relógio não reinicia, e a vez estoura aos 45s.
2. **Given** uma vez que começou na Fase de Ação, **When** o dono declara
   ataque aos 10s, puxa a unidade aos 20s, declara de novo aos 30s e puxa de
   novo aos 40s, **Then** a vez estoura aos 45s contados do início, e o aviso
   chegou uma vez só, aos 30s.
3. **Given** a Declaração, **When** o atacante confirma **Atacar** aos 20s,
   **Then** a Defesa começa com relógio novo de 45s para o defensor.
4. **Given** a Defesa, **When** o defensor atribui e remove bloqueadores aos
   10s, 25s e 40s, **Then** a vez estoura aos 45s do início da Defesa.
5. **Given** a Defesa, **When** o defensor resolve aos 15s, **Then** a vez do
   dono do token começa com relógio novo.
6. **Given** A passou e B deve a jogada há 44s, **When** B passa, **Then** a
   rodada vira, a vez volta a B, e o prazo dela é de 45s a partir da virada.
7. **Given** a vez de B estourou com o segundo passe, **When** a rodada
   seguinte começa com a vez em B, **Then** B tem 45s novos, e nenhum estouro
   imediato acontece.
8. **Given** A joga unidade aos 5s, **When** a vez vai a B, **Then** B tem 45s
   novos.

---

### User Story 4 - O relógio sobrevive a quem abandona, a workers e à corrida (Priority: P1)

O jogador que deve a jogada fecha o jogo. É o caso que justifica o relógio:
quem abandona é justamente quem não vai mandar mais nada, e um relógio que
morasse na conexão dele morreria com ela. O estouro acontece com o socket dele
fechado.

As duas conexões podem estar em workers diferentes, e um worker pode reiniciar
no meio de uma vez. O prazo é compartilhado entre workers e sobrevive a isso.

O jogador manda "passar" no último instante e o relógio estoura no mesmo
instante: só um dos dois vale, e nenhuma escrita se perde. Pior: se o estouro
chegar atrasado, depois de a vez ter ido e voltado ao mesmo jogador, ele não
pode passar a vez **nova** dele. Um estouro vale só para a vez em que foi
armado; para qualquer outra, não faz nada.

**Why this priority**: um relógio que falha nesses casos é pior que nenhum —
ou não pune o abandono, ou pune quem jogou.

**Independent Test**: com tempo injetado e workers simulados, fechar o socket
do dono da vez e conferir o estouro; derrubar o worker que armou o prazo e
conferir que outro o executa; disparar passe e estouro juntos repetidas vezes e
conferir um passe só; entregar um estouro velho a uma vez nova do mesmo
jogador e conferir que nada muda.

**Acceptance Scenarios**:

1. **Given** A deve a jogada e fechou todos os sockets aos 5s, **When** o
   relógio chega a 45s, **Then** o passe automático de A é gravado, e B recebe
   a atualização.
2. **Given** A e B em workers diferentes, e o worker onde a vez de A começou
   reiniciado aos 20s, **When** o relógio chega a 45s, **Then** o estouro
   acontece uma vez, e os dois recebem a atualização.
3. **Given** A deve a jogada aos 45s, **When** o passe de A pelo socket e o
   estouro chegam juntos, **Then** exatamente um passe é gravado; se o do
   socket venceu, o estouro não faz nada; se o estouro venceu, o passe do
   socket recebe a recusa de prioridade.
4. **Given** um estouro armado para a vez de B na rodada 3, que chega atrasado,
   **When** a vez de B na rodada 4 está aberta, **Then** o estouro não faz
   nada: nenhuma gravação, nenhum frame.
5. **Given** A deve a jogada na Declaração aos 45s, **When** A lança um feitiço
   e o estouro chega junto, **Then** os dois valem, na ordem em que chegaram à
   gravação: o feitiço não termina a vez, então o **Atacar** automático ainda é
   da mesma vez.
6. **Given** A deve a jogada na Declaração com uma unidade na zona, **When** A
   puxa a unidade de volta e o estouro chega junto, e o puxar vence, **Then** o
   estouro vê a Fase de Ação da mesma vez e passa, em vez de atacar.
7. **Given** o defensor atribui um bloqueador e o estouro da Defesa chega junto,
   **When** o bloqueio vence, **Then** o **Resolver** automático resolve com
   aquele bloqueio.
8. **Given** mais de um worker enxergando o mesmo prazo vencido, **When** todos
   tentam o estouro, **Then** um só é gravado, e os jogadores recebem uma
   atualização só.

---

### User Story 5 - Mulligan com relógio (Priority: P2)

Cada jogador tem 30 segundos para responder o mulligan, sem aviso, e os dois
relógios correm ao mesmo tempo. Estourou: aquele jogador confirma sem trocar
nenhuma carta. Quem já respondeu não é afetado. Se o estouro é a segunda
resposta, a partida segue para a Rodada 1 exatamente como seguiria com uma
resposta mandada pelo socket — no mesmo passo, com a primeira vez já com
relógio.

**Why this priority**: sem isto um jogador que nunca abre o socket prende o
outro no mulligan. É P2 porque o mulligan acontece uma vez só por partida.

**Independent Test**: com tempo injetado, criar a partida, deixar o relógio
chegar a 30s com nenhuma, uma e as duas respostas mandadas, e conferir a
confirmação sem troca, a Rodada 1 e o relógio da primeira vez.

**Acceptance Scenarios**:

1. **Given** uma partida criada há 30s em que A já respondeu e B não, **When**
   o mulligan de B estoura, **Then** B confirma sem trocar nada, a partida
   entra na Fase de Ação da Rodada 1, e a primeira vez começa com relógio novo.
2. **Given** nenhum dos dois respondeu, **When** os dois relógios estouram,
   **Then** os dois confirmam sem troca, e a partida entra na Rodada 1.
3. **Given** A respondeu aos 10s, **When** o relógio de mulligan de A chega a
   30s, **Then** nada acontece a A.
4. **Given** a partida recém-criada, **When** o relógio chega a 30s, **Then**
   nenhum aviso foi mandado antes.
5. **Given** o mulligan de B estourou, **When** os dois recebem a atualização,
   **Then** a descrição informa que B trocou zero cartas e que foi o relógio.
6. **Given** B manda o mulligan aos 30s e o estouro chega junto, **When** um
   dos dois é gravado, **Then** o outro não vale: o do socket recebe a recusa
   de mulligan repetido, ou o estouro não faz nada.
7. **Given** A desistiu no mulligan, **When** os relógios de mulligan chegam a
   30s, **Then** nada acontece.

---

### User Story 6 - O cliente vê o prazo, e a reconexão vê o prazo real (Priority: P2)

A visão de cada jogador diz de quem é a vez e quanto falta para ela estourar,
medido pelo servidor, de modo que o cliente desenhe o relógio certo mesmo com o
relógio do dispositivo errado. Uma reconexão no meio da vez mostra o tempo que
realmente resta, não um relógio recomeçado. No mulligan, cada jogador vê o
próprio prazo.

**Why this priority**: o relógio funciona sem isto; o que falta é o jogador
saber que ele existe. P2 pela mesma razão da reconexão na feature 009.

**Independent Test**: com tempo injetado, conectar aos 0s, aos 20s e aos 40s de
uma vez, e depois de um feitiço aos 25s; conferir em cada visão e atualização o
dono da vez e o tempo restante.

**Acceptance Scenarios**:

1. **Given** a vez de A começou há 20s, **When** B conecta, **Then** a visão de
   B diz que a vez é de A e que faltam 25s para o estouro.
2. **Given** a vez de A começou há 40s, **When** A reconecta, **Then** a visão
   diz que faltam 5s, e que o aviso já vale.
3. **Given** A lança um feitiço aos 25s, **When** os dois recebem a
   atualização, **Then** ela diz que faltam 20s — o feitiço não devolveu tempo.
4. **Given** o relógio do dispositivo do cliente adiantado uma hora, **When**
   ele recebe a visão, **Then** o tempo restante informado continua certo.
5. **Given** o mulligan aberto há 12s e A já respondeu, **When** B conecta,
   **Then** a visão de B diz que faltam 18s para o mulligan dele.
6. **Given** uma partida terminada, **When** um jogador reconecta, **Then** a
   visão não traz vez nem prazo.

---

### User Story 7 - O fim da partida para todo relógio, e a partida sem ninguém (Priority: P3)

Desistência ou Nexus a zero encerram a partida, e todo relógio dela para:
nenhum aviso e nenhum estouro depois do fim.

Com os dois jogadores desconectados, o relógio continua passando a vez de
cada um. Passar nunca tira Nexus de ninguém, então uma partida sem ninguém não
termina sozinha. Pior: toda gravação renova o prazo de expiração da partida no
armazenamento, então os estouros a manteriam viva **para sempre**.

Decidido em 2026-09-11: o relógio continua girando, mas **estouro não renova a
expiração**. Só jogada real — mensagem de cliente aceita — renova. Uma partida
em que ninguém joga some do armazenamento 6h depois da última jogada real, e
com ela todo relógio dela. Nenhuma regra de jogo nova: não existe derrota por
abandono. Se só um jogador abandonou, o outro continua jogando e renovando, e
termina a partida pelo Nexus — cada Defesa do ausente resolve sem bloqueio.

**Why this priority**: não afeta nenhuma partida jogada; afeta recurso do
servidor e o que acontece com uma partida abandonada pelos dois.

**Independent Test**: com tempo injetado, encerrar a partida por desistência e
por Nexus com vezes e mulligans pendentes, avançar o relógio e conferir que
nada acontece; deixar uma partida sem sockets correr várias rodadas só com
estouros e conferir que a expiração continua contando da última jogada real.

**Acceptance Scenarios**:

1. **Given** a vez de A aberta há 20s, **When** B desiste, **Then** os dois
   recebem a partida terminada, e aos 45s nada acontece.
2. **Given** um **Resolver** que zera o Nexus do defensor, **When** o relógio
   passa dos 45s da vez seguinte que existiria, **Then** nada acontece.
3. **Given** uma partida sem nenhum socket aberto, cuja última jogada real foi
   há 5h, **When** o relógio avança com estouros por mais de 1h, **Then** a
   partida some do armazenamento 6h depois da última jogada real, e nenhum
   estouro ou aviso dela é processado depois disso.
4. **Given** A abandonou e B continua conectado, **When** B joga e as vezes de A
   estouram, **Then** cada jogada de B renova a expiração, os estouros de A não
   renovam, e a partida segue até terminar pelo Nexus ou por desistência.
5. **Given** uma partida sem nenhuma jogada real desde a criação, **When** só
   estouros acontecem — mulligans e vezes —, **Then** ela some 6h depois da
   criação.

---

### Edge Cases

**SACRIFICIAL FIRE**

- **Zona de ataque vazia na declaração**: não existe — puxar a última unidade
  devolve a partida à Fase de Ação, onde o FIRE é recusado por momento.
- **FIRE com alvo inválido de qualquer tipo** — unidade na zona, unidade fora
  dela, unidade do oponente, carta inexistente: sempre a recusa de feitiço que
  não aceita alvo, antes de qualquer checagem do alvo.
- **Dois FIRE na mesma declaração**: cada um dá +3 a toda unidade que está na
  zona no instante dele, e cobra o Nexus dele, com o piso de 1.
- **Unidade puxada de volta e mandada de novo depois do FIRE**: fica com o +3
  que ganhou; não ganha outro.
- **FIRE pelo defensor**: recusa de momento, como hoje (§14).

**Vez e troca de mão**

- **Declarar ataque na Fase de Ação**: mesma vez. Puxar o último atacante:
  mesma vez.
- **Virada de rodada**: vez nova, mesmo que o dono seja o mesmo — e é sempre o
  mesmo (ver User Story 3).
- **Rodada 1 aberta pelo fim do mulligan**: a primeira vez começa no mesmo
  passo que grava a segunda resposta.
- **Combate que termina com a partida**: não abre vez.
- **Partida terminada**: nenhuma vez, nenhum prazo, nenhum aviso.

**Estouro**

- **Ação automática escolhida pelo estado de agora**: a ação é a da fase em que
  a partida está quando o estouro é aplicado, não quando foi armado — desde
  que a vez seja a mesma (User Story 4, cenário 6).
- **Estouro atrasado** — por fila, worker reiniciando, ou todos os workers
  fora do ar: se a vez ainda é a mesma, age assim que for processado; se não
  é, não faz nada.
- **Estouro repetido** para a mesma vez, por mais de um worker: um só é
  gravado; os outros não fazem nada.
- **Estouro que o motor recusaria**: não deveria existir, porque a ação
  automática é sempre legal na vez dela. Se acontecer, fica registrado em log
  estruturado, nenhum frame sai para ninguém, e a partida não muda.
- **Partida expirada do armazenamento** quando o estouro chega: não faz nada,
  e nenhum relógio dela continua.
- **Estouro não gera recusa**: não existe socket de origem. Recusa continua
  sendo só resposta a uma mensagem de cliente.

**Aviso**

- **Dono da vez desconectado aos 30s**: ninguém recebe o aviso; ele não é
  guardado para depois. A reconexão vê o tempo restante na visão.
- **Aviso repetido** para a mesma vez, por mais de um worker: tolerado — o aviso
  identifica a vez e não muda a partida.
- **Aviso de vez que já terminou**: não é mandado.
- **Oponente**: não recebe aviso; vê o tempo restante na visão.

**Corrida com jogada real**

- **Jogada que termina a vez** (jogar unidade, passar, **Atacar**, **Resolver**)
  contra o estouro: exatamente uma vale.
- **Jogada que não termina a vez** (feitiço, mandar ou puxar atacante, atribuir
  ou remover bloqueador) contra o estouro: as duas valem, na ordem da gravação.
- **Jogada real depois do estouro**: avaliada contra o estado que o estouro
  deixou, com as recusas de sempre.

**Mulligan**

- **Mulligan de zero cartas mandado pelo socket e estouro**: resultado igual na
  partida; a descrição distingue a origem.
- **Um jogador que nunca conectou**: o relógio do mulligan dele corre desde a
  criação da partida.

## Requirements *(mandatory)*

### Functional Requirements

**Parte 1 — SACRIFICIAL FIRE (§14)**

- **FR-001**: O SACRIFICIAL FIRE MUST ser lançado sem alvo.
- **FR-002**: Lançado, ele MUST dar +3 de ataque permanente a **toda** unidade
  do lançador que está na zona de ataque no instante do lançamento, e a nenhuma
  outra.
- **FR-003**: Uma unidade mandada para a zona de ataque depois do lançamento
  MUST NOT receber o bônus daquele lançamento.
- **FR-004**: O SACRIFICIAL FIRE lançado com alvo MUST ser recusado com a mesma
  recusa, e o mesmo código, de qualquer feitiço sem alvo que recebe um, e a
  partida MUST ficar como estava.
- **FR-005**: Continuam valendo sem mudança: só na declaração, só pelo atacante,
  custo de energia do catálogo, custo em Nexus `max(nexus - 8, 1)`, bônus
  permanente, e a recusa de momento com o código atual.
- **FR-006**: O tipo de alvo "unidade aliada na zona de ataque", que existia só
  para este feitiço, MUST deixar de existir no conjunto de tipos de alvo.
- **FR-007**: A descrição da carta no catálogo MUST dizer o que a carta faz:
  sem alvo, toda unidade aliada na zona de ataque ganha 3 de ataque, só na
  declaração, e o custo em Nexus com o piso de 1.
- **FR-008**: Os testes que fixam a versão de alvo único MUST mudar junto, como
  correção de regra e não como regressão: `test_sacrificial_fire.py`,
  `test_spell_effect.py`, `test_spell_effects.py`, `test_mvp_catalog.py`,
  `fake_spell_board.py`, `test_full_match.py` e `test_spell_state_round_trip.py`
  (este lança o FIRE com alvo em `fire_on_an_attacker`). Nenhum outro teste
  MUST mudar de expectativa por causa desta parte.
- **FR-009**: O cliente MUST lançar o SACRIFICIAL FIRE pelo mesmo comando de
  lançar feitiço da feature 009, sem alvo.

**Parte 2 — A vez e o prazo**

- **FR-010**: Toda vez — Fase de Ação, Declaração e Defesa — MUST ter prazo: o
  aviso 30s depois do início da vez, e o estouro 45s depois do início.
- **FR-011**: Vez nova MUST começar quando a partida passa a esperar um jogador
  diferente do da vez anterior, ou quando a rodada muda, inclusive se o jogador
  é o mesmo. Nenhuma outra mudança MUST começar vez nova.
- **FR-012**: Jogar feitiço, mandar atacante (inclusive a declaração que abre a
  janela), puxar atacante de volta (inclusive o último), atribuir bloqueador e
  remover bloqueador MUST NOT reiniciar o prazo nem adiar o aviso.
- **FR-013**: Cada vez MUST ter identidade própria, distinta de toda outra vez
  da partida — inclusive de outra vez do mesmo jogador na mesma fase.

**O estouro**

- **FR-014**: No estouro, se a vez armada ainda é a vez atual, o sistema MUST
  aplicar em nome do dono da vez a ação automática da fase em que a partida
  está naquele instante: passar na Fase de Ação, **Atacar** na Declaração,
  **Resolver** na Defesa.
- **FR-015**: A ação automática MUST entrar pela mesma porta do motor e pela
  mesma gravação atômica de toda jogada, e produzir exatamente o mesmo estado
  que a mesma ação mandada pelo socket produziria.
- **FR-016**: Um estouro para uma vez que não é a atual MUST NOT gravar nada nem
  mandar frame nenhum.
- **FR-017**: Um estouro aplicado MUST entregar a cada socket aberto dos dois
  jogadores a atualização montada para o dono do socket, com a descrição
  pública, como a feature 009 entrega toda jogada aceita.
- **FR-018**: A descrição pública de uma ação automática MUST dizer que a
  origem foi o relógio, e a de uma jogada do socket MUST continuar sem essa
  marca.
- **FR-019**: A disputa entre um estouro e uma jogada real MUST NOT perder
  escrita. Se a jogada termina a vez, exatamente uma das duas MUST valer; se
  não termina, as duas MUST valer, na ordem em que foram gravadas.
- **FR-020**: Mais de uma tentativa de estouro para a mesma vez MUST resultar em
  no máximo uma gravação e uma atualização.
- **FR-021**: Um estouro que o motor recusar MUST ser registrado em log JSON
  estruturado com a partida, a vez e a recusa, MUST NOT mandar frame a
  ninguém, e MUST deixar a partida como estava.

**O aviso**

- **FR-022**: Aos 30s de uma vez que ainda é a atual, todo socket aberto do dono
  da vez naquela partida MUST receber o aviso, identificando a vez e o tempo
  restante. O oponente MUST NOT recebê-lo.
- **FR-023**: O aviso MUST NOT ser mandado para uma vez que já terminou, nem no
  mulligan. Um aviso repetido para a mesma vez MAY acontecer, e não muda a
  partida.

**Mulligan**

- **FR-024**: Cada jogador MUST ter 30s para o mulligan, contados da criação da
  partida, correndo ao mesmo tempo para os dois, sem aviso.
- **FR-025**: No estouro do mulligan de um jogador que ainda não respondeu, o
  sistema MUST registrar a resposta dele sem troca de carta, pela mesma porta e
  gravação do mulligan mandado pelo socket.
- **FR-026**: Se o estouro é a segunda resposta, a partida MUST chegar à Fase
  de Ação da Rodada 1 na mesma mutação gravada, como na feature 009, e a
  primeira vez MUST começar com prazo novo.
- **FR-027**: O estouro do mulligan de quem já respondeu, ou de uma partida fora
  do mulligan, MUST NOT fazer nada.
- **FR-028**: A descrição do mulligan por estouro MUST dizer que o jogador trocou
  zero cartas e que a origem foi o relógio.

**O que o relógio aguenta**

- **FR-029**: O estouro e o aviso MUST acontecer independentemente de haver
  socket aberto do dono da vez, ou de qualquer jogador.
- **FR-030**: O prazo de cada vez e de cada mulligan MUST ser compartilhado entre
  todos os workers, e MUST sobreviver ao reinício do worker que o armou.
- **FR-031**: Um estouro atrasado MUST agir assim que processado se a vez ainda
  é a mesma, e MUST NOT agir se não é.
- **FR-032**: O tempo MUST chegar ao relógio como dependência injetável, como a
  aleatoriedade já chega, de modo que todo cenário desta spec rode nos testes
  sem esperar tempo real e com resultado repetível.

**Fim de partida**

- **FR-033**: Quando a partida termina — desistência ou Nexus a zero, por jogada
  real ou por estouro —, todo prazo dela MUST parar: nenhum aviso e nenhum
  estouro depois disso.
- **FR-034**: Uma gravação feita por estouro MUST NOT renovar a expiração da
  partida no armazenamento. A expiração MUST continuar contando da criação ou
  da última mensagem de cliente aceita — jogada, mulligan ou desistência —, a
  mais recente. Recusa MUST NOT renovar.
- **FR-034a**: Uma partida que expirou MUST NOT ter aviso nem estouro
  processado, e nenhum relógio dela MUST continuar.
- **FR-034b**: Estouros seguidos MUST NOT encerrar a partida por conta própria:
  não existe derrota por abandono.

**O que o cliente vê**

- **FR-035**: A visão ao conectar e toda atualização MUST dizer, enquanto há vez,
  de quem ela é, a identidade dela e quanto falta para o estouro.
- **FR-036**: O tempo restante MUST ser medido pelo servidor no momento em que o
  frame é montado, e MUST NOT depender do relógio do dispositivo do cliente.
- **FR-037**: Uma reconexão no meio de uma vez MUST mostrar o tempo que
  realmente resta daquela vez.
- **FR-038**: No mulligan, a visão de cada jogador MUST dizer quanto falta para
  o mulligan dele, enquanto ele não respondeu.
- **FR-039**: Numa partida terminada, a visão MUST NOT trazer vez nem prazo.

**O que não pode quebrar**

- **FR-040**: Nenhuma regra do motor MUST mudar por causa do relógio, e nenhuma
  porta do motor MUST receber ou ler tempo.
- **FR-041**: O protocolo da feature 009 MUST continuar como está: comandos,
  recusas com os códigos atuais, visão por jogador, descrição pública, e nenhum
  frame com a mão do oponente ou conteúdo de deck.
- **FR-042**: A reconexão MUST continuar sendo conectar de novo e receber a
  visão atual.
- **FR-043**: Toda mutação desta feature MUST passar pela gravação atômica
  existente, sem trava com tempo de vida e sem contornar o compare-and-swap.
- **FR-044**: Os gates de entrada do socket de partida e seus códigos 44xx MUST
  continuar como estão.

### Key Entities

- **Vez**: o intervalo em que um jogador deve a jogada. Identidade própria, dono,
  rodada, instante de início, instante do aviso e instante do estouro. Muda de
  identidade quando muda o dono ou a rodada; atravessa a ida e a volta da
  Declaração.
- **Prazo de mulligan**: um por jogador, com o instante do estouro. Deixa de
  valer quando aquele jogador responde ou a partida sai do mulligan.
- **Estouro**: o disparo ligado a uma vez ou a um prazo de mulligan. Só age se o
  que ele armou ainda é o atual.
- **Ação automática**: o comando que o estouro manda ao motor — passar,
  **Atacar**, **Resolver** ou mulligan sem troca —, com o dono da vez como autor.
- **Aviso**: o frame que o dono da vez recebe aos 30s. Identifica a vez e o
  tempo restante.
- **Origem da jogada**: se a mudança gravada veio de um socket ou do relógio.
  Aparece na descrição pública.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Todos os cenários de relógio desta spec rodam na suíte de testes
  sem esperar tempo real, cada um em menos de 1 segundo, com o mesmo resultado
  em 100% das execuções.
- **SC-002**: Em ambiente local, com tempo real, o aviso chega ao dono da vez
  entre 30 e 32 segundos depois do início dela, e o estouro é gravado entre 45 e
  47 segundos.
- **SC-003**: Em uma vez com qualquer número de feitiços, atacantes mandados e
  puxados e bloqueadores atribuídos e removidos, o estouro acontece aos 45s do
  início da vez em 100% dos casos.
- **SC-004**: Em 100 repetições de passe real e estouro simultâneos, 100
  partidas gravam exatamente um passe, e nenhuma perde escrita.
- **SC-005**: Em 100% dos estouros entregues a uma vez que não é a deles, a
  partida fica idêntica e nenhum frame é enviado.
- **SC-006**: Com o dono da vez desconectado durante a vez inteira, o estouro
  acontece em 100% das tentativas, com os sockets em um worker ou em workers
  diferentes, e com o worker que armou o prazo reiniciado no meio.
- **SC-007**: Uma reconexão no meio da vez mostra tempo restante com no máximo 1
  segundo de diferença do real.
- **SC-008**: Um mulligan sem resposta é confirmado sem troca em 100% das
  partidas, e a partida chega à Rodada 1 quando o segundo mulligan é resolvido,
  por resposta ou por estouro.
- **SC-009**: Depois do fim da partida, 0 avisos e 0 estouros são processados.
- **SC-010**: O SACRIFICIAL FIRE lançado sem alvo na declaração dá +3 a 100% das
  unidades que estavam na zona no instante e a 0 das mandadas depois; lançado
  com alvo, é recusado em 100% dos casos.
- **SC-011**: Todos os testes existentes continuam passando sem mudança de
  expectativa, menos os listados no FR-008.
- **SC-012**: Uma partida sem jogada real some do armazenamento 6h depois da
  última jogada real em 100% dos casos, qualquer que seja o número de estouros
  nesse intervalo.

## Assumptions

- **A virada de rodada é vez nova, mesmo com o mesmo dono.** A descrição da
  feature fala de "uma cascata que termina com a vez em outro jogador". Pela
  §4 e pela §8, a cascata termina **sempre** com a vez em quem deu o segundo
  passe. Tratar a virada como a mesma vez faria o passe por estouro abrir a
  rodada seguinte já estourado, em laço. Por isso a identidade da vez inclui a
  rodada.
- **"Mora no consumer", na §15, é lido como "mora no transporte".** O texto da
  nota coloca o relógio no consumer, e a feature exige que ele não dependa do
  socket do dono da vez. A intenção da nota é "não no motor"; um relógio preso
  a uma conexão morreria com ela. Se a nota precisar dizer isso com outras
  palavras, é decisão do mantenedor.
- **O prazo do mulligan conta da criação da partida**, não da conexão do
  jogador: o relógio não pode depender de socket, e é na criação que o
  `match_found` sai para os dois.
- **O aviso não é guardado.** Quem está desconectado aos 30s não o recebe
  depois; a visão ao reconectar já traz o tempo restante, e o cliente desenha o
  aviso a partir dele.
- **O oponente não recebe aviso.** "Quem deve a jogada recebe o aviso"; o outro
  vê o tempo restante na visão.
- **A ação automática é escolhida pelo estado no instante em que é aplicada**,
  dentro da mesma vez. Um atacante que puxa a última unidade no instante do
  estouro é estourado na Fase de Ação, com passar.
- **Latência de rede não é compensada.** O tempo restante é o do servidor na
  montagem do frame; o que o frame leva para chegar é ruído aceito.
- **A pergunta aberta da §13** — o +3 do FIRE não expira e fica em unidade puxada
  de volta — continua aberta. A correção aplica o bônus a mais unidades e não
  responde a pergunta.
- **Partida abandonada pelos dois expira; não termina com derrota.** Decidido
  pelo mantenedor em 2026-09-11 (opção A da clarificação). As alternativas
  descartadas: derrota por abandono depois de estouros seguidos, que seria regra
  nova da §10/§15 e penalidade fora de escopo; e pausar o relógio sem ninguém
  conectado, que depende da presença adiada no `Backend/TODO.md`. O prazo de
  expiração continua o atual, 6h.
- **As constantes são as da §12**, fixas: 30s + 15s por vez, 30s no mulligan.
- **Fora de escopo**: relógio de partida inteira ou banco de tempo; aviso de
  oponente desconectado ou reconectado; configuração de tempo por partida ou
  modo; ranking e penalidade por abandono; presença de usuário (o item de
  heartbeat do `Backend/TODO.md` continua adiado); código do cliente.
- **Dependências**: a porta única de ação e a cascata (005), o feitiço imediato
  (008), a segunda correção da nota (declaração como janela, desistência), o
  protocolo de partida (009) com a descrição pública e a versão de escrita, e a
  gravação atômica com compare-and-swap (003).
