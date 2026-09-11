# Feature Specification: Combate

**Feature Branch**: `007-combat-phase`

**Created**: 2026-09-10

**Status**: Draft

**Input**: User description: "Combate: a §7 inteira. Declaração do atacante, a janela livre do defensor, o dano simultâneo e a limpeza. É a última feature do motor — fechada ela, o Fluxo de Partida está implementado de ponta a ponta."

> Nota de idioma: os títulos de seção ficam em inglês porque os comandos
> seguintes do Spec Kit (`/speckit-plan`, `/speckit-tasks`, `/speckit-analyze`)
> os localizam por esses nomes. O conteúdo segue em português, como o resto das
> notas do projeto.

Referência de domínio: `Game/Fluxo de Partida.md` no vault. A §7 inteira é o
contrato desta feature, e a §5C é a ação que a dispara. A §10 (vitória) é
consumida como a feature 006 a entregou. A §8 e a cascata de fases são
consumidas como a feature 005 as entregou. A §12 dá o pareamento 1:1 estrito e
o limite de um ataque por rodada.

Esta é a última feature do motor. Fechada ela, o Fluxo de Partida está
implementado de ponta a ponta: uma partida roda do setup da §3 à vitória da §10
sem tocar em websocket.

Três coisas escritas por features anteriores prevendo o combate passam a ter
consumidor: `MatchPhase.COMBAT`, que existe desde a feature 002 e nunca foi
alcançada; a varredura de morte que já percorre os dois bancos porque o dano da
§7.3 é simultâneo; e a apuração de vitória separada da alteração de Nexus, que
existe exatamente para o cálculo único do combate. O aplicador de efeito da
feature 006 é reusado como está, e é o mesmo argumento: nenhum dos cinco
efeitos ganha uma segunda implementação.

O combate é a **única** exceção à alternância da §5 em todo o jogo, e a exceção
não pode vazar para fora dele.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Declarar ataque (Priority: P1)

A quarta e última ação da Fase de Ação, ao lado de jogar unidade, lançar
feitiço e passar.

Quem tem a prioridade e o token de ataque pode declarar ataque. Exige que o
token ainda não tenha sido consumido nesta rodada, que a pilha esteja vazia, e
que o autor tenha ao menos uma unidade no banco. O autor seleciona quais
unidades do próprio banco atacam — de uma até todas — e confirma.

O que acontece: o token é consumido, os atacantes ficam registrados, a partida
entra em Combate, e a prioridade passa ao defensor. Nenhuma carta se move,
nenhuma energia é gasta, nenhum dano acontece ainda.

A partir daqui o atacante **não age mais até o combate terminar**. Não joga
feitiço, não bloqueia, não responde, não interfere. É espectador, e é a
prioridade parada no defensor que faz disso uma recusa e não uma convenção.

**Why this priority**: sem declaração não existe combate, e sem combate nenhuma
das outras histórias existe. É a quarta e última ação da §5 que o motor
entrega.

**Independent Test**: com o token na mão, a pilha vazia e três unidades no
banco, declarar ataque com duas delas e conferir token consumido, fase em
Combate, prioridade no defensor, as duas unidades registradas como atacantes,
e nenhuma energia, carta, Nexus ou dano alterado.

**Acceptance Scenarios**:

1. **Given** o dono do token com prioridade, pilha vazia e três unidades no
   banco, **When** ele declara ataque com duas delas, **Then** o token está
   consumido, a fase é Combate, a prioridade é do defensor e as duas unidades
   constam como atacantes.
2. **Given** um dono de token com uma unidade só no banco, **When** ele declara
   ataque com ela, **Then** a jogada é aceita.
3. **Given** um dono de token com seis unidades no banco, **When** ele declara
   ataque com todas, **Then** a jogada é aceita e as seis constam como
   atacantes.
4. **Given** uma declaração aceita, **When** eu leio o estado inteiro, **Then**
   nenhuma energia mudou, nenhuma carta se moveu, nenhum Nexus mudou e nenhum
   dano acumulou.
5. **Given** um jogador que não é o dono do token, **When** ele declara ataque,
   **Then** a jogada é recusada citando o motivo.
6. **Given** um dono de token com o token já consumido nesta rodada, **When**
   ele declara ataque, **Then** a jogada é recusada citando o motivo.
7. **Given** uma pilha não vazia, **When** o dono do token declara ataque,
   **Then** a jogada é recusada citando o motivo.
8. **Given** um dono de token com o banco vazio, **When** ele declara ataque,
   **Then** a jogada é recusada citando o motivo.
9. **Given** um dono de token com unidades no banco, **When** ele declara
   ataque com zero unidades selecionadas, **Then** a jogada é recusada.
10. **Given** um dono de token, **When** ele declara ataque citando uma unidade
    do banco do oponente, **Then** a jogada é recusada citando a unidade.
11. **Given** um dono de token, **When** ele declara ataque citando a mesma
    unidade duas vezes, **Then** a jogada é recusada citando a unidade.

---

### User Story 2 - A janela livre do defensor (Priority: P1)

Aqui o combate rompe com a regra central da Fase de Ação, e é o ponto mais
delicado da feature.

Na §5 quem age executa exatamente uma ação e a prioridade troca. Na janela do
defensor **a prioridade não troca**: ele age quantas vezes quiser, em qualquer
ordem, até decidir encerrar.

O defensor atribui bloqueadores. Uma unidade do próprio banco é posta na frente
de uma unidade atacante específica. O pareamento é 1 para 1 estrito: cada
bloqueador cobre exatamente um atacante, cada atacante recebe no máximo um
bloqueador. Atacante sem bloqueador passa direto. Se mudar de ideia, o defensor
remove um bloqueador já atribuído e as duas unidades ficam livres de novo.

O defensor encerra a janela explicitamente.

**Why this priority**: é a única exceção à alternância em todo o jogo, e o
bloqueio é o que dá ao defensor algo a decidir. Sem ela o combate é uma fórmula
sem jogador.

**Independent Test**: com dois atacantes declarados e duas unidades no banco do
defensor, atribuir um bloqueador, atribuir outro, remover o primeiro e
reatribuí-lo a outro atacante — quatro ações seguidas — e conferir que a
prioridade continuou no defensor nas quatro e que o pareamento final é o
esperado.

**Acceptance Scenarios**:

1. **Given** um combate declarado, **When** o defensor atribui um bloqueador,
   **Then** a prioridade continua sendo dele e a fase continua sendo Combate.
2. **Given** um defensor que acabou de bloquear, **When** ele bloqueia de novo
   com outra unidade, **Then** a jogada é aceita — não existe limite de ações
   na janela.
3. **Given** um bloqueador atribuído, **When** o defensor o remove, **Then** o
   pareamento some, e tanto o bloqueador quanto o atacante voltam a estar
   livres.
4. **Given** um bloqueador removido, **When** o defensor o atribui a outro
   atacante, **Then** a jogada é aceita.
5. **Given** uma unidade do defensor já bloqueando um atacante, **When** ele a
   usa para bloquear um segundo atacante, **Then** a jogada é recusada citando
   a unidade.
6. **Given** um atacante que já tem bloqueador, **When** o defensor atribui um
   segundo bloqueador a ele, **Then** a jogada é recusada citando o atacante.
7. **Given** um combate declarado, **When** o defensor bloqueia com uma unidade
   que não está no banco dele, **Then** a jogada é recusada citando a unidade.
8. **Given** um combate declarado, **When** o defensor aponta um bloqueador
   para uma unidade que não está atacando, **Then** a jogada é recusada citando
   a unidade.
9. **Given** nenhum bloqueador atribuído, **When** o defensor remove um
   bloqueador, **Then** a jogada é recusada.
10. **Given** um combate em curso, **When** o atacante tenta qualquer ação,
    **Then** a jogada é recusada citando que a prioridade é do defensor.
11. **Given** um combate em curso, **When** o defensor tenta jogar unidade,
    lançar feitiço pela pilha ou passar, **Then** a jogada é recusada citando a
    fase.
12. **Given** um defensor sem nenhuma unidade no banco, **When** ele encerra a
    janela, **Then** a jogada é aceita e nada bloqueia.

---

### User Story 3 - Feitiço imediato do defensor (Priority: P1)

Dentro da janela, o defensor pode lançar feitiço, limitado só pela energia
disponível e sem limite de quantidade.

O feitiço resolve **imediatamente**, na hora em que é lançado. Não vai para a
pilha, e o atacante não pode responder. É o mesmo efeito, com o mesmo
resultado, do caminho da §5B — por um caminho diferente. O aplicador de efeito
é o mesmo, e não ganha uma segunda implementação.

As guardas de lançamento são as mesmas: a carta está na mão do autor, a carta é
um feitiço, a energia cobre o custo, e o alvo casa com o que o efeito declara —
"aliado" e "inimigo" continuam relativos a quem lança.

**Why this priority**: é o que permite ao defensor mudar o resultado do combate
antes do dano, e é o caso que a feature 006 escreveu o aplicador para atender.

**Independent Test**: com o defensor bloqueando um atacante, lançar um feitiço
de dano no atacante e conferir que o efeito aconteceu na hora, que a pilha
continua vazia, que a prioridade continua no defensor, e que a carta já está no
cemitério dele.

**Acceptance Scenarios**:

1. **Given** um combate em curso, **When** o defensor lança um feitiço, **Then**
   o efeito já aconteceu, a pilha continua vazia e a carta está no cemitério do
   defensor.
2. **Given** um feitiço lançado pelo defensor, **When** a ação termina, **Then**
   a prioridade continua sendo do defensor e a fase continua sendo Combate.
3. **Given** um defensor com energia para dois feitiços, **When** ele lança os
   dois, **Then** as duas jogadas são aceitas e os dois efeitos aconteceram.
4. **Given** um defensor sem energia para o custo do feitiço, **When** ele o
   lança, **Then** a jogada é recusada citando o custo e a energia disponível.
5. **Given** um feitiço de dano do defensor que mata um atacante, **When** ele
   resolve, **Then** o atacante sai do banco e vai para o cemitério do dono
   dele.
6. **Given** um feitiço de buff do defensor sobre um bloqueador, **When** ele
   resolve, **Then** o bloqueador entra no dano com o valor já buffado.
7. **Given** o mesmo estado inicial, **When** um efeito é aplicado pelo caminho
   da pilha e pelo caminho do combate, **Then** o resultado é idêntico campo a
   campo.
8. **Given** um combate em curso, **When** o atacante tenta lançar feitiço,
   **Then** a jogada é recusada.
9. **Given** um combate em curso, **When** o defensor lança feitiço mirando uma
   unidade que não está em campo, **Then** a jogada é recusada citando o alvo.

---

### User Story 4 - Dano simultâneo (Priority: P1)

Encerrada a janela, o dano acontece. Automático, sem input, e **todo
simultâneo**: não existe ordem de precedência entre os pares, e nenhuma unidade
morre antes de ter causado o dano dela.

Para cada atacante: bloqueado, atacante e bloqueador causam um no outro dano
igual ao próprio ataque efetivo, e nenhum dano chega ao Nexus; não bloqueado,
causa dano igual ao próprio ataque efetivo no Nexus do defensor.

Bloqueador órfão — o atacante que ele ia bloquear morreu antes da resolução,
por um feitiço do próprio defensor — não troca dano com ninguém e volta ao
banco intacto.

Imunidade a dano continua valendo: uma unidade protegida ataca normalmente e
não recebe nada.

A apuração da vitória é o ponto perigoso. O dano de combate pode zerar os dois
Nexus no mesmo cálculo, e a §10 chama isso de empate. Os dois Nexus precisam
ser alterados antes de o resultado ser apurado, e a apuração acontece **uma vez
só** — apurar depois de cada alteração transformaria um empate em vitória do
segundo, porque a primeira apuração já encerraria a partida com um único
derrotado e a verificação é idempotente.

**Why this priority**: é o que o combate existe para fazer. Sem ele a
declaração e o bloqueio não produzem nada.

**Independent Test**: dois atacantes, um bloqueado por uma unidade de força
igual e outro livre, encerrar a janela e conferir que atacante e bloqueador
morreram os dois, que o atacante livre levou o ataque dele ao Nexus do
defensor, e que nenhum dano chegou ao Nexus pelo par bloqueado.

**Acceptance Scenarios**:

1. **Given** um atacante bloqueado, **When** a janela encerra, **Then** atacante
   e bloqueador acumulam, cada um, dano igual ao ataque efetivo do outro, e o
   Nexus do defensor não mudou por esse par.
2. **Given** um atacante não bloqueado, **When** a janela encerra, **Then** o
   Nexus do defensor cai pelo ataque efetivo dele.
3. **Given** um atacante e um bloqueador que se matam, **When** a janela
   encerra, **Then** os dois vão para os cemitérios dos respectivos donos.
4. **Given** um bloqueador cujo atacante morreu por feitiço antes da resolução,
   **When** a janela encerra, **Then** o bloqueador não acumula dano nenhum e
   continua no banco.
5. **Given** um atacante que morreu por feitiço antes da resolução, **When** a
   janela encerra, **Then** ele não causa dano a ninguém nem ao Nexus.
6. **Given** um defensor que matou todos os atacantes com feitiço, **When** a
   janela encerra, **Then** o combate resolve sem dano nenhum e o Nexus do
   defensor não mudou.
7. **Given** um atacante com imunidade a dano, bloqueado, **When** a janela
   encerra, **Then** o bloqueador acumula o dano do atacante e o atacante não
   acumula nada.
8. **Given** um bloqueador com imunidade a dano, **When** a janela encerra,
   **Then** o bloqueador não acumula nada e o atacante acumula o dano do
   bloqueador.
9. **Given** um atacante com bônus de ataque ativo, **When** a janela encerra,
   **Then** o dano causado é o do molde mais o bônus.
10. **Given** um bloqueador que só sobrevive por um buff de vida lançado na
    janela, **When** a janela encerra, **Then** ele sobrevive — o buff conta.
11. **Given** três atacantes não bloqueados, **When** a janela encerra, **Then**
    o Nexus do defensor cai pela soma dos três ataques efetivos, e a §10 é
    apurada uma vez só.
12. **Given** o Nexus do defensor indo a 0 ou menos pelo dano não bloqueado,
    **When** a janela encerra, **Then** o defensor perde.
13. **Given** os dois Nexus em 0 ou menos no mesmo cálculo de dano, **When** a
    §10 é apurada, **Then** o resultado é empate, com os dois entre os
    derrotados — nunca uma vitória de um só.
14. **Given** um combate qualquer, **When** o dano resolve, **Then** o Nexus do
    atacante não mudou.

---

### User Story 5 - Limpeza e volta à Fase de Ação (Priority: P1)

Toda unidade cuja vida efetiva foi alcançada pelo dano acumulado sai e vai para
o cemitério do dono — dos dois lados, numa varredura só, que é a mesma que o
motor já tem. Sobreviventes, atacantes e bloqueadores, estão no banco do dono.
A vitória é apurada.

A contagem de passes zera, a prioridade volta para o dono do token, e a partida
volta para a Fase de Ação. O estado de combate desaparece.

O Combate é um sub-estado atravessado pela mesma cascata que já leva a partida
por Upkeep, Resolução de Pilha e Fim de Rodada: quando a ação que encerra a
janela retorna, a partida está de volta esperando ação, nunca parada em
Combate.

**Why this priority**: sem a volta, o combate trava a partida na fase em que
entrou. É o que fecha o ciclo.

**Independent Test**: encerrar a janela de um combate com mortes dos dois lados
e conferir, na mesma resposta, que os mortos estão nos cemitérios certos, que
os sobreviventes estão nos bancos, que o estado de combate sumiu, que os passes
estão em 0, que a prioridade é do dono do token e que a fase é a Fase de Ação.

**Acceptance Scenarios**:

1. **Given** um combate com mortes dos dois lados, **When** a janela encerra,
   **Then** cada unidade morta está no cemitério do dono dela.
2. **Given** um combate com sobreviventes dos dois lados, **When** a janela
   encerra, **Then** cada sobrevivente está no banco do dono dele.
3. **Given** uma unidade morta no combate, **When** eu leio a carta no
   cemitério, **Then** o dano e os modificadores dela ficaram para trás.
4. **Given** a janela encerrada, **When** a operação retorna, **Then** a fase é
   a Fase de Ação, a prioridade é do dono do token e a contagem de passes é 0.
5. **Given** a janela encerrada, **When** eu leio o estado, **Then** o estado de
   combate não existe mais.
6. **Given** a janela encerrada, **When** a operação retorna, **Then** o número
   da rodada é o mesmo de antes do combate.
7. **Given** a janela encerrada, **When** a operação retorna, **Then** nenhuma
   energia mudou e ninguém comprou carta.
8. **Given** qualquer ação do combate, **When** a operação retorna, **Then** a
   partida nunca está parada numa fase automática — ou está em Combate
   esperando o defensor, ou já voltou para a Fase de Ação.
9. **Given** um combate que encerra a partida pelo dano, **When** a operação
   retorna, **Then** a partida está no estado terminal e não volta para a Fase
   de Ação.

---

### User Story 6 - A rodada continua depois do combate (Priority: P2)

A rodada **não** acaba com o combate. Os dois seguem alternando ações com a
energia que sobrou, jogando unidade, lançando feitiço e respondendo pela pilha
normalmente. O que mudou é só que o token está consumido: declarar ataque deixa
de ser ação legal pelo resto da rodada, e só volta no Upkeep seguinte, já com o
dono trocado.

A alternância volta ao normal assim que o combate termina. A exceção da janela
não vaza.

**Why this priority**: garante que o combate é um sub-estado e não um fim de
rodada disfarçado. Depende das histórias P1, mas é o que prova que elas não
quebraram a §5.

**Independent Test**: depois de um combate, jogar uma unidade, passar, e ver a
prioridade trocar nas duas — e tentar declarar ataque de novo e ser recusado.

**Acceptance Scenarios**:

1. **Given** um combate terminado, **When** o dono do token joga uma unidade,
   **Then** a jogada é aceita e a prioridade troca.
2. **Given** um combate terminado, **When** o defensor lança um feitiço,
   **Then** ele vai para a pilha e a prioridade troca — o caminho da §5B voltou
   a valer.
3. **Given** um combate terminado, **When** o dono do token declara ataque de
   novo, **Then** a jogada é recusada porque o token está consumido.
4. **Given** um combate terminado, **When** os dois passam com a pilha vazia,
   **Then** a rodada fecha normalmente.
5. **Given** a rodada seguinte iniciada, **When** o novo dono do token declara
   ataque, **Then** a jogada é aceita — o token voltou com o dono trocado.
6. **Given** um combate terminado, **When** o defensor do combate declara ataque
   na mesma rodada, **Then** a jogada é recusada: ele não é o dono do token.

---

### User Story 7 - O estado de combate sobrevive ao Redis (Priority: P2)

As duas conexões podem estar em workers diferentes, então o estado de combate —
quais unidades atacam e qual bloqueador está pareado com qual atacante —
precisa sobreviver à ida e à volta pela forma gravada, como todo o resto do
estado da partida.

O estado nasce na declaração, muda durante a janela do defensor e desaparece na
limpeza. A ausência dele fora do combate é distinguível de um combate sem
bloqueadores.

**Why this priority**: sem isso o combate só funciona com um worker, que não é
como o servidor roda. Mas a regra pode ser escrita e testada antes.

**Independent Test**: declarar ataque, atribuir um bloqueador, serializar a
partida, desserializar, e conferir igualdade campo a campo — incluindo os
atacantes e o pareamento — e então encerrar a janela pelo estado reconstruído e
obter o mesmo resultado.

**Acceptance Scenarios**:

1. **Given** um combate declarado com três atacantes, **When** a partida vai e
   volta pela forma gravada, **Then** os três atacantes voltam na mesma ordem.
2. **Given** um pareamento de bloqueadores, **When** a partida vai e volta,
   **Then** cada bloqueador continua pareado com o mesmo atacante.
3. **Given** uma partida fora do combate, **When** ela vai e volta, **Then** o
   estado de combate continua ausente, e a ausência é distinguível de um combate
   sem nenhum bloqueador.
4. **Given** uma partida reconstruída no meio do combate, **When** o defensor
   encerra a janela, **Then** o resultado é idêntico ao de encerrar sem ter
   passado pela forma gravada.

---

### User Story 8 - Uma partida completa, do setup à vitória (Priority: P3)

Com o combate fechado, o Fluxo de Partida está implementado de ponta a ponta.
Uma partida roda do setup da §3 até um Nexus chegar a 0, atravessando Upkeep,
Fase de Ação, pilha, combate e Fim de Rodada, sem tocar em websocket.

**Why this priority**: é a prova de que as sete features se costuram. Não
acrescenta regra nenhuma; verifica as que já existem.

**Independent Test**: montar uma partida, rodar rodadas alternando ações e
combates até um Nexus chegar a 0, e conferir que a partida terminou com o
desfecho certo sem que nenhuma fase automática tenha sido observada como
resultado.

**Acceptance Scenarios**:

1. **Given** uma partida montada pelo setup, **When** os dois jogam até um Nexus
   chegar a 0, **Then** a partida termina com o desfecho correto.
2. **Given** essa partida completa, **When** eu olho as fases observadas,
   **Then** nenhuma foi Upkeep, Resolução de Pilha ou Fim de Rodada — só Fase de
   Ação, Combate e o estado terminal.
3. **Given** essa partida completa, **When** ela termina, **Then** nada no
   caminho tocou websocket, Redis ou banco de dados.

---

### Edge Cases

**Declaração de ataque**

- **Autor não é o dono do token.** Recusa citando o motivo.
- **Token já consumido nesta rodada.** Recusa citando o motivo. É o caso do
  segundo ataque na mesma rodada.
- **Pilha não vazia.** Recusa citando o motivo. O combate não usa a pilha e não
  pode ser declarado com ela cheia.
- **Banco do autor vazio.** Recusa citando o motivo.
- **Zero unidades selecionadas.** Recusa. Ter unidade no banco e não escolher
  nenhuma é jogada mal formada, não um combate vazio.
- **Unidade selecionada que não está no banco do autor.** Recusa citando a
  unidade. Cobre a unidade do oponente, a carta na mão e a unidade que já
  morreu.
- **A mesma unidade selecionada duas vezes.** Recusa citando a unidade.
- **Declarar ataque fora da Fase de Ação.** Recusa citando a fase. Cobre o
  mulligan e a partida já em Combate.
- **Declarar ataque numa partida terminada.** Recusa citando que a partida
  acabou.
- **Duas guardas falhando ao mesmo tempo.** Vence a primeira da ordem:
  participante, prioridade, fase, e só então as regras da §5C.

**Janela do defensor**

- **Bloquear com unidade que já bloqueia outro atacante.** Recusa citando a
  unidade.
- **Bloquear um atacante que já tem bloqueador.** Recusa citando o atacante.
  Trocar de bloqueador exige remover antes.
- **Bloquear com unidade que não está no banco do defensor.** Recusa citando a
  unidade.
- **Apontar um bloqueador para uma unidade que não está atacando.** Recusa
  citando a unidade. Cobre a unidade do próprio defensor e a unidade do atacante
  que ficou fora da declaração.
- **Apontar um bloqueador para um atacante que já morreu na janela.** Recusa
  pela mesma regra: ele não está mais em campo.
- **Remover um bloqueador que não foi atribuído.** Recusa.
- **Atribuir, remover e reatribuir a mesma unidade.** Legal, quantas vezes
  quiser.
- **Bloquear com todas as unidades do banco.** Legal, se houver atacantes
  suficientes.
- **Mais atacantes que unidades no banco do defensor.** Legal: os que sobram
  passam direto.
- **Mais unidades no banco do defensor que atacantes.** Legal: as que sobram não
  bloqueiam nada.
- **Defensor sem nenhuma unidade no banco.** Legal. A janela existe do mesmo
  jeito, e ele encerra sem bloquear.
- **Defensor encerra sem bloquear nada.** Legal. Tudo passa para o Nexus.
- **O atacante tentando qualquer ação durante o combate.** Recusa. Ele é
  espectador, e a recusa cita que a prioridade é do defensor.
- **O defensor tentando jogar unidade, lançar feitiço pela pilha ou passar
  durante o combate.** Recusa citando a fase. São ações da §5, e o Combate não
  está entre as fases delas.
- **Bloquear ou encerrar a janela fora do Combate.** Recusa citando a fase.

**Feitiço imediato do defensor**

- **Feitiço sem energia suficiente.** Recusa citando o custo e a energia.
- **Carta que não está na mão do defensor.** Recusa citando a carta.
- **Carta de unidade na ação de lançar feitiço.** Recusa citando a carta e o
  tipo.
- **Alvo que não está em campo.** Recusa citando o alvo. Não é fizzle: fizzle é
  o alvo sumir entre o lançamento e a resolução, e aqui não existe esse
  intervalo.
- **Alvo no banco errado para o tipo de alvo do efeito.** Recusa citando o alvo.
- **Vários feitiços na mesma janela.** Legal, limitado só pela energia.
- **Feitiço que mata todos os atacantes.** Legal. O combate resolve sem dano
  nenhum.
- **Feitiço que buffa um bloqueador antes do dano.** O buff conta no cálculo do
  dano.
- **Feitiço que dá imunidade a um bloqueador.** Ele não recebe dano, e o
  atacante recebe o dele.
- **Feitiço do defensor que encerra a partida.** É alcançável: o custo em Nexus
  de SACRIFICIAL FIRE pode derrotar o próprio defensor. A partida termina ali,
  nenhuma ação seguinte é aceita, e o dano do combate não chega a ser resolvido.

**Dano**

- **Atacante que morreu antes da resolução.** Não causa dano a ninguém.
- **Bloqueador órfão.** Não troca dano com ninguém e volta ao banco intacto.
- **Atacante e bloqueador se matando.** Os dois vão para os cemitérios dos
  respectivos donos.
- **Atacante com ataque efetivo 0.** Causa 0 de dano; o bloqueador ainda causa o
  dele.
- **Ataque efetivo negativo por modificador.** Tratado como 0. O dano de combate
  nunca cura Nexus nem remove dano acumulado.
- **Unidade imune atacando.** Ataca normalmente e não recebe nada.
- **Dano exatamente igual à vida efetiva.** A unidade morre — a regra é o dano
  **alcançar** a vida efetiva, e é a que o motor já aplica.
- **Vários atacantes não bloqueados.** O Nexus do defensor cai pela soma, e a
  §10 é apurada uma vez só.
- **O Nexus do atacante.** Nunca recebe dano de combate.

**Vitória**

- **Nexus do defensor em exatamente 0 pelo dano.** Derrota.
- **Dois Nexus em 0 ou menos no mesmo cálculo.** Empate, com os dois entre os
  derrotados. Não é alcançável pelas cinco cartas do MVP — nenhuma delas
  subtrai Nexus do oponente, e o dano de combate só chega ao Nexus do defensor
  —, e por isso a garantia é estrutural: a apuração acontece uma vez, depois
  das duas alterações, e o cenário é exercido a partir de um estado montado.
- **Partida terminada no meio da janela.** Nenhuma ação seguinte é aceita, o
  dano não resolve, e o estado continua íntegro e serializável.
- **Partida terminada pelo dano de combate.** A limpeza acontece, o estado
  terminal é registrado, e a partida não volta para a Fase de Ação.

**Depois do combate**

- **Segundo ataque na mesma rodada.** Recusado: o token está consumido.
- **O defensor do combate declarando ataque na mesma rodada.** Recusado: ele não
  é o dono do token.
- **Os dois passando com a pilha vazia depois do combate.** A rodada fecha
  normalmente, pela §8.
- **O novo dono do token declarando ataque na rodada seguinte.** Aceito.
- **Combate numa rodada e combate na rodada seguinte.** Legais, um por rodada.

## Requirements *(mandatory)*

### Functional Requirements

**Ação: declarar ataque (§5C, §7.1)**

- **FR-001**: O sistema MUST aceitar "declarar ataque" como a quarta ação da
  Fase de Ação, com a mesma forma de ação e as mesmas guardas comuns que a
  feature 005 entregou, na mesma ordem.
- **FR-002**: A ação MUST carregar o autor e o conjunto de unidades do próprio
  banco que atacam.
- **FR-003**: A ação MUST exigir que o autor seja o dono do token de ataque.
- **FR-004**: A ação MUST exigir que o token não tenha sido consumido nesta
  rodada.
- **FR-005**: A ação MUST exigir que a pilha esteja vazia.
- **FR-006**: A ação MUST exigir ao menos uma unidade no banco do autor.
- **FR-007**: A ação MUST exigir ao menos uma unidade selecionada. Seleção vazia
  MUST ser recusada.
- **FR-008**: Cada unidade citada MUST estar no banco do autor. Uma que não
  esteja MUST ser recusada citando a unidade.
- **FR-009**: A mesma unidade citada mais de uma vez MUST ser recusada citando a
  unidade.
- **FR-010**: Aceita, a ação MUST consumir o token, registrar os atacantes, pôr
  a partida em Combate e passar a prioridade ao defensor.
- **FR-011**: A ação MUST NOT gastar energia, mover carta, causar dano, alterar
  Nexus nem criar modificador.
- **FR-012**: Declarar ataque MUST deixar de ser ação legal pelo resto da rodada
  assim que o token é consumido.

**Estado de combate**

- **FR-013**: Enquanto o combate dura, a partida MUST lembrar quais unidades
  atacam e qual bloqueador está pareado com qual atacante.
- **FR-014**: O estado de combate MUST referenciar unidades por identificador,
  nunca por referência ao objeto — a mesma decisão, pela mesma razão, que a
  entrada da pilha da §6.
- **FR-015**: O estado de combate MUST nascer na declaração, MUST mudar durante
  a janela do defensor e MUST desaparecer na limpeza.
- **FR-016**: O estado de combate MUST sobreviver à ida e à volta pela forma
  gravada com igualdade campo a campo, incluindo a ordem dos atacantes e o
  pareamento.
- **FR-017**: Fora do combate o estado MUST estar ausente, e a ausência MUST ser
  distinguível de um combate declarado sem nenhum bloqueador.
- **FR-018**: A ordem dos atacantes MUST ser preservada, e MUST NOT influenciar
  o resultado do dano.

**A janela do defensor: prioridade (§7.2)**

- **FR-019**: Durante o Combate a prioridade MUST ser do defensor, e MUST NOT
  trocar depois de nenhuma ação da janela.
- **FR-020**: O defensor MUST poder agir quantas vezes quiser, em qualquer
  ordem, sem limite de quantidade além da energia disponível.
- **FR-021**: A exceção MUST NOT vazar para fora do combate: na Fase de Ação,
  toda ação MUST continuar trocando a prioridade, sem nenhuma mudança de
  comportamento.
- **FR-022**: Toda ação do atacante durante o combate MUST ser recusada, e a
  recusa MUST citar que a prioridade é do defensor.
- **FR-023**: As ações da Fase de Ação — jogar unidade, lançar feitiço pela
  pilha, passar e declarar ataque — MUST NOT ser legais durante o Combate, para
  nenhum dos dois jogadores.
- **FR-024**: As ações da janela — atribuir bloqueador, remover bloqueador,
  lançar feitiço imediato e encerrar a janela — MUST NOT ser legais fora do
  Combate.

**Bloqueio (§7.2)**

- **FR-025**: O defensor MUST poder pôr uma unidade do próprio banco na frente
  de uma unidade atacante específica.
- **FR-026**: O pareamento MUST ser 1 para 1 estrito: cada bloqueador cobre no
  máximo um atacante, e cada atacante recebe no máximo um bloqueador.
- **FR-027**: Bloquear com uma unidade que já bloqueia outro atacante MUST ser
  recusado citando a unidade.
- **FR-028**: Bloquear um atacante que já tem bloqueador MUST ser recusado
  citando o atacante.
- **FR-029**: Bloquear com uma unidade que não está no banco do defensor MUST
  ser recusado citando a unidade.
- **FR-030**: Apontar um bloqueador para uma unidade que não está atacando MUST
  ser recusado citando a unidade.
- **FR-031**: O defensor MUST poder remover um bloqueador já atribuído,
  liberando tanto o bloqueador quanto o atacante.
- **FR-032**: Remover um bloqueador que não foi atribuído MUST ser recusado.
- **FR-033**: Atribuir e remover bloqueador MUST NOT gastar energia, mover
  carta, causar dano nem alterar Nexus.
- **FR-034**: Um atacante sem bloqueador MUST passar direto.

**Feitiço imediato do defensor (§7.2)**

- **FR-035**: O defensor MUST poder lançar feitiço durante a janela, limitado só
  pela energia disponível e sem limite de quantidade.
- **FR-036**: O feitiço MUST resolver imediatamente, MUST NOT entrar na pilha, e
  o atacante MUST NOT poder responder.
- **FR-037**: A pilha MUST permanecer vazia durante todo o combate.
- **FR-038**: O efeito MUST ser aplicado pelo mesmo aplicador que a §5B usa.
  MUST NOT existir uma segunda implementação de nenhum dos cinco efeitos.
- **FR-039**: O aplicador de efeito MUST NOT receber nem inferir por qual
  caminho a chamada chegou.
- **FR-040**: As guardas do lançamento MUST ser as mesmas da §5B, na mesma
  ordem: carta na mão do autor, carta é feitiço, energia cobre o custo, alvo
  casa com o que o efeito declara.
- **FR-041**: "Aliado" e "inimigo" MUST continuar relativos a quem lança.
- **FR-042**: Aceito, o feitiço imediato MUST descontar a energia, tirar a carta
  da mão e pô-la no cemitério do lançador.
- **FR-043**: O feitiço imediato MUST NOT fizzlar nunca: o alvo é validado no
  lançamento e não existe intervalo entre validar e aplicar.
- **FR-044**: Um feitiço do defensor que mate uma unidade MUST removê-la pelo
  mesmo caminho de morte que o motor já tem.
- **FR-045**: Um feitiço do defensor que altere Nexus MUST apurar a §10 junto do
  evento, como a §10 manda e como o motor já faz.
- **FR-046**: O atacante MUST NOT poder lançar feitiço durante o combate, por
  nenhum dos dois caminhos.

**Dano (§7.3)**

- **FR-047**: O dano MUST ser automático, sem input de jogador, disparado por
  encerrar a janela.
- **FR-048**: O ataque efetivo de uma unidade MUST ser o valor do molde mais a
  soma dos modificadores de ataque dela, com piso em 0.
- **FR-049**: Atacante bloqueado: atacante e bloqueador MUST causar um no outro
  dano igual ao próprio ataque efetivo, e nenhum dano desse par MUST chegar ao
  Nexus.
- **FR-050**: Atacante não bloqueado: MUST causar dano igual ao próprio ataque
  efetivo no Nexus do defensor.
- **FR-051**: Todo o dano MUST ser simultâneo. Nenhuma unidade MUST morrer antes
  de ter causado o dano dela, e MUST NOT existir ordem de precedência entre os
  pares.
- **FR-052**: Um bloqueador cujo atacante não está mais em campo na resolução
  MUST NOT trocar dano com ninguém e MUST permanecer no banco intacto.
- **FR-053**: Um atacante que não está mais em campo na resolução MUST NOT
  causar dano a ninguém nem ao Nexus.
- **FR-054**: A lista de atacantes e o pareamento MUST ser revalidados por
  identificador no momento da resolução.
- **FR-055**: Imunidade a dano MUST continuar valendo: uma unidade imune ataca
  normalmente e MUST NOT acumular dano.
- **FR-056**: O dano de combate MUST acumular na unidade pelo mesmo caminho de
  dano que o motor já tem, e MUST NOT reduzir vida diretamente.
- **FR-057**: O Nexus do atacante MUST NOT receber dano de combate.

**Vitória no combate (§10)**

- **FR-058**: Os dois Nexus MUST ser alterados antes de a §10 ser apurada, e a
  apuração MUST acontecer **uma vez só** por combate.
- **FR-059**: A §10 MUST NOT ser apurada a cada alteração de Nexus durante a
  resolução do dano de combate.
- **FR-060**: Dois Nexus menores ou iguais a 0 no mesmo cálculo MUST resultar em
  empate, com os dois entre os derrotados — nunca em vitória de um só.
- **FR-061**: A alteração de Nexus por dano de combate MUST continuar passando
  pelo módulo que já é o único a escrever Nexus, sem que esse módulo ganhe uma
  segunda apuração de vitória.
- **FR-062**: Se a partida terminar durante a janela do defensor, nenhuma ação
  seguinte MUST ser aceita, o dano do combate MUST NOT ser resolvido, e o estado
  MUST continuar íntegro e serializável.

**Limpeza e volta (§7.4, §7.5)**

- **FR-063**: Toda unidade cujo dano acumulado alcance a vida máxima MUST ir
  para o cemitério do dono, dos dois lados, numa varredura só.
- **FR-064**: A varredura de morte MUST ser a que o motor já tem. MUST NOT
  ganhar uma segunda versão para o combate.
- **FR-065**: Os modificadores e o dano de uma unidade morta MUST ficar para
  trás quando a carta vai para o cemitério.
- **FR-066**: Sobreviventes — atacantes e bloqueadores — MUST estar no banco do
  dono ao fim do combate.
- **FR-067**: Terminado o combate, o estado de combate MUST desaparecer.
- **FR-068**: Terminado o combate, a contagem de passes MUST ser 0, a prioridade
  MUST ser do dono do token, e a fase MUST ser a Fase de Ação.
- **FR-069**: O combate MUST NOT fechar a rodada. O número da rodada MUST ser o
  mesmo antes e depois.
- **FR-070**: O Combate MUST ser atravessado pela mesma cascata que já leva a
  partida por Upkeep, Resolução de Pilha e Fim de Rodada: nenhuma ação MUST
  devolver a partida parada numa fase automática, e a ação que encerra a janela
  MUST devolver a partida esperando ação.
- **FR-071**: O combate MUST NOT alterar energia nem fazer ninguém comprar
  carta.
- **FR-072**: Um combate que encerre a partida MUST deixá-la no estado terminal,
  e MUST NOT devolvê-la à Fase de Ação.

**Depois do combate (§7.5)**

- **FR-073**: Depois do combate, os dois jogadores MUST seguir alternando ações
  com a energia que sobrou — jogando unidade, lançando feitiço e respondendo
  pela pilha normalmente.
- **FR-074**: Declarar ataque MUST continuar recusado pelo resto da rodada.
- **FR-075**: O token MUST voltar a ficar disponível no Upkeep seguinte, já com
  o dono trocado, pelo Fim de Rodada que a feature 005 entrega.

**Recusa**

- **FR-076**: Uma ação recusada MUST deixar o estado da partida exatamente como
  estava, campo a campo, em qualquer ponto de falha.
- **FR-077**: Uma ação recusada MUST NOT consumir o token, criar ou alterar o
  estado de combate, descontar energia, mover carta, trocar prioridade, alterar
  a contagem de passes nem mudar a fase.
- **FR-078**: Uma ação recusada MUST NOT avançar o contador de identidade de
  carta nem o contador de sorteios da partida.
- **FR-079**: Toda recusa MUST nomear o valor ofensor: a unidade citada, o
  atacante citado, o custo contra a energia disponível, a carta pedida, o
  identificador do alvo, ou quem tem a prioridade — conforme a guarda que
  falhou.
- **FR-080**: A recusa MUST identificar qual guarda falhou, de forma que o
  cliente possa distinguir os casos sem interpretar texto livre.

**Fronteiras**

- **FR-081**: Esta feature MUST NOT alterar a alternância da Fase de Ação, as
  guardas comuns nem a cascata de fases da feature 005 fora do combate.
- **FR-082**: Esta feature MUST NOT usar nem alterar a pilha da feature 006, e o
  combate MUST NOT ser declarado com ela cheia.
- **FR-083**: Esta feature MUST NOT reimplementar o aplicador de efeito, a
  acumulação de dano, a varredura de morte nem a apuração de vitória. Nenhum
  deles MUST ganhar uma segunda versão.
- **FR-084**: Esta feature MUST NOT quebrar a garantia de round-trip da feature
  002, que passa a incluir o estado de combate.
- **FR-085**: Esta feature MUST NOT tocar websocket: envelope de mensagem,
  broadcast e reconexão ficam fora.
- **FR-086**: Esta feature MUST NOT gravar no Redis. Quem grava é o chamador,
  pelo caminho atômico que a feature 003 entregou.
- **FR-087**: Esta feature MUST NOT implementar timeout da janela do defensor.

### Key Entities

- **Declaração de ataque**: a ação da §5C. Carrega o autor e as unidades do
  próprio banco que atacam. É o quarto e último braço da união de ações que a
  feature 005 definiu.
- **Estado de combate**: quais unidades atacam e qual bloqueador está pareado
  com qual atacante. Nasce na declaração, muda na janela do defensor, desaparece
  na limpeza, e sobrevive ao Redis. Referencia unidades por identificador, nunca
  por objeto.
- **Pareamento**: a relação 1 para 1 entre um bloqueador e um atacante. Cada
  lado aparece no máximo uma vez.
- **Atacante**: uma unidade do banco do dono do token citada na declaração. Pode
  já não estar em campo na hora da resolução.
- **Bloqueador**: uma unidade do banco do defensor pareada com um atacante.
- **Bloqueador órfão**: um bloqueador cujo atacante não está mais em campo na
  resolução. Não troca dano com ninguém e volta ao banco intacto.
- **Janela do defensor**: o intervalo em que o defensor age sem que a prioridade
  troque. É a única exceção à alternância da §5 em todo o jogo.
- **Ataque efetivo**: o ataque do molde mais a soma dos modificadores de ataque,
  com piso em 0. Não é campo; é conta — como a vida efetiva da feature 006.
- **Feitiço imediato**: um feitiço lançado dentro da janela, que resolve na
  hora, sem pilha e sem chance de resposta. É outro caminho para o mesmo
  aplicador de efeito, nunca um segundo aplicador.
- **Cálculo de dano de combate**: o evento único em que todo o dano dos pares e
  do Nexus é aplicado. É o que precisa alterar os dois Nexus antes de a §10 ser
  apurada uma vez só.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: O dono do token declara ataque com parte do banco, o token fica
  consumido, a partida entra em Combate e a prioridade vai para o defensor — sem
  que energia, carta, Nexus ou dano mudem.
- **SC-002**: Em 100% das declarações recusadas listadas nos Edge Cases, o
  estado da partida depois é idêntico ao estado antes, campo a campo, contadores
  inclusive.
- **SC-003**: O defensor executa quatro ações seguidas na janela — bloquear,
  bloquear, remover e reatribuir — e a prioridade continua sendo dele nas
  quatro.
- **SC-004**: Fora do combate, toda ação continua trocando a prioridade: a suíte
  da Fase de Ação da feature 005 passa sem nenhum teste de regra alterado.
- **SC-005**: Em 100% das tentativas do atacante durante o combate, a jogada é
  recusada.
- **SC-006**: O pareamento 1 para 1 é inviolável: nenhuma sequência de ações
  aceitas produz um bloqueador cobrindo dois atacantes ou um atacante com dois
  bloqueadores.
- **SC-007**: Um feitiço do defensor resolve na hora, a pilha continua vazia do
  começo ao fim do combate, e a carta termina no cemitério do lançador.
- **SC-008**: A partir do mesmo estado inicial, cada um dos cinco efeitos produz
  resultado idêntico campo a campo aplicado pela pilha e aplicado pelo combate.
- **SC-009**: Existe exatamente 1 lugar no código onde cada um dos cinco efeitos
  é executado, 1 onde o dano acumula na unidade, 1 onde a unidade morta é
  varrida, e 1 onde o Nexus é escrito.
- **SC-010**: Encerrar a janela mata, num único cálculo, quem tinha de morrer
  dos dois lados, devolve os sobreviventes aos bancos, e leva o dano dos não
  bloqueados ao Nexus do defensor.
- **SC-011**: Um bloqueador cujo atacante morreu antes da resolução termina o
  combate no banco com o mesmo dano acumulado de antes — zero a mais.
- **SC-012**: Um defensor que mata todos os atacantes com feitiço encerra a
  janela sem que nenhum Nexus mude e sem que nenhuma unidade acumule dano de
  combate.
- **SC-013**: Um combate com três atacantes não bloqueados derruba o Nexus do
  defensor pela soma exata dos três ataques efetivos, e a §10 é apurada uma vez
  só.
- **SC-014**: Dois Nexus em 0 ou menos no mesmo cálculo de dano produzem empate
  — os dois entre os derrotados —, nunca vitória do segundo.
- **SC-015**: Encerrada a janela, a partida está na Fase de Ação com os passes
  em 0 e a prioridade no dono do token, e o estado de combate não existe mais.
- **SC-016**: Em 100% das ações do combate, o resultado observável nunca é a
  partida parada numa fase automática.
- **SC-017**: O número da rodada é o mesmo antes e depois do combate, e nenhuma
  energia mudou nem ninguém comprou carta por causa dele.
- **SC-018**: Depois do combate os dois jogam normalmente na mesma rodada, e
  declarar ataque é recusado até o Upkeep seguinte, quando volta com o dono
  trocado.
- **SC-019**: Todo estado produzido por esta feature volta idêntico da forma
  gravada, campo a campo, incluindo os atacantes, o pareamento e a partida
  terminada.
- **SC-020**: Uma partida reconstruída da forma gravada no meio do combate
  produz, ao encerrar a janela, o mesmo resultado de uma que nunca foi gravada.
- **SC-021**: Uma partida completa roda do setup à vitória sem tocar em
  websocket, Redis ou banco de dados.
- **SC-022**: Em 100% dos casos de recusa, a mensagem cita o valor ofensor, e a
  guarda que falhou é identificável sem interpretar texto livre.
- **SC-023**: As suítes das features 001 a 006 passam. Os únicos testes delas
  que podem mudar são os que **inventariam** o que o motor tem — a lista de
  ações da partida, a lista de fases e a costura da cascata —, porque esta
  feature acrescenta uma ação e dá corpo a uma fase. Nenhum teste de **regra**
  das seis features é alterado.
- **SC-024**: Nenhuma decisão de regra desta feature lê a descrição em português
  de uma carta.

## Assumptions

- **Declarar ataque entra como um braço novo** da união de ações da feature 005,
  sem que a guarda comum nem a porta de entrada mudem de forma — que é o que a
  feature 005 escreveu prevendo, e o que a feature 006 já confirmou ao entrar do
  mesmo jeito.
- **As ações da janela são ações próprias**, não as da §5 com uma fase a mais. O
  feitiço imediato em particular é uma ação distinta da §5B: a ação da §5B
  empilha e passa a prioridade, e o código do motor já registra por escrito que
  ela declara só a Fase de Ação por isso.
- **A recusa é levantada, não devolvida como valor**, como toda jogada ilegal do
  motor desde a feature 003.
- **A ordem das checagens específicas da declaração** é: dono do token → token
  não consumido → pilha vazia → banco não vazio → seleção não vazia → cada
  unidade citada está no banco do autor. As guardas mais baratas e mais gerais
  vêm antes, e a que cita uma unidade específica vem por último.
- **O atacante vira espectador pela prioridade parada no defensor**, não por uma
  guarda nova. A guarda de prioridade que já existe recusa toda ação dele e já
  cita de quem é a vez.
- **A prioridade que não troca é propriedade da ação**, como as fases em que ela
  é legal já são. É o que impede a exceção de virar uma condição dentro da troca
  comum e de vazar para a Fase de Ação.
- **O estado de combate é campo do estado da partida**, ausente fora do combate.
  Precisa sobreviver ao Redis e ser lido por qualquer worker, como todo o resto.
- **O ataque efetivo é conta, não campo**, pelo mesmo argumento que a vida
  efetiva da feature 006: guardar o valor absoluto obrigaria a desfazer na mão a
  expiração de um bônus temporário.
- **O dano de combate é um evento único.** Todos os pares e o Nexus são
  calculados e aplicados antes de qualquer varredura de morte, e a §10 é apurada
  uma vez depois. É a leitura literal de "todo o dano é simultâneo".
- **A apuração única da §10 usa a função que só verifica**, e não a que altera e
  verifica junto. As duas existem separadas desde a feature 006 exatamente por
  causa deste cálculo, e o módulo de vitória continua sendo o único lugar que
  escreve Nexus.
- **O empate por combate não é alcançável com as cinco cartas do MVP.** Nenhuma
  subtrai Nexus do oponente, e o dano de combate só chega ao Nexus do defensor.
  A garantia é estrutural — uma apuração, depois das duas alterações — e o
  cenário é exercido a partir de um estado montado, não de uma sequência de
  jogadas.
- **Uma partida que termina durante a janela não resolve o dano.** É a mesma
  decisão que a feature 006 tomou para a pilha: assim que a §10 encontra um
  Nexus em 0 ou menos, nada mais é aplicado. O estado de combate fica como está,
  íntegro e serializável, e nenhuma ação é aceita depois.
- **O Combate entra na cascata da feature 005** como o Upkeep, a Resolução de
  Pilha e o Fim de Rodada já entraram — exceto que o Combate espera ação do
  defensor, e por isso não é fase automática: é a ação que encerra a janela que
  dispara o dano, a limpeza e a volta, tudo dentro da mesma chamada.
- **A morte de unidade continua sendo verificada pela varredura que já existe**,
  sobre os dois bancos. Ela foi escrita com essa largura prevendo o dano
  simultâneo da §7.3, e o combate a usa como está.
- **O ataque efetivo tem piso em 0.** Nenhuma das cinco cartas do MVP produz
  bônus negativo, mas o modificador de ataque aceita valor negativo por
  construção, e dano negativo curaria Nexus e removeria dano acumulado — que não
  é regra nenhuma da §7.
- **A operação recebe a partida e devolve a partida.** Ela não lê nem grava no
  Redis; quem grava é o chamador.

## Out of Scope

- **Feitiço que invoque unidade capaz de bloquear no mesmo combate.** Nenhum dos
  cinco feitiços do MVP faz isso, e a §13 do Fluxo de Partida registra a
  pergunta como deliberadamente em aberto.
- **Palavras-chave de carta.** Continuam na §13.
- **Cartas e efeitos além dos cinco do MVP.**
- **Envelope de mensagem, broadcast e reconexão no websocket.** Esta feature
  recebe uma ação e devolve o estado novo; quem fala com o cliente é outra
  camada.
- **Timeout da janela do defensor.** A janela não tem relógio, e um defensor que
  nunca encerra trava a partida para sempre. É o mesmo problema de transporte
  que a §13 registra, e fica para a feature de timers.
- **Persistência.** Gravar a partida no Redis é do chamador.
- **O que acontece com a partida depois de terminada** — rematch, ranking,
  registro de resultado.
