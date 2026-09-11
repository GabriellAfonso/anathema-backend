# Feature Specification: Feitiço imediato

**Feature Branch**: `008-instant-spells`

**Created**: 2026-09-11

**Status**: Draft

**Input**: User description: "Feitiço imediato: tirar a pilha do motor. O Fluxo de Partida estava errado e foi corrigido em 2026-09-11: não existe pilha, feitiço resolve na hora em que é jogado, em qualquer fase. O único \"Resolver\" do jogo é o do combate."

> Nota de idioma: os títulos de seção ficam em inglês porque os comandos
> seguintes do Spec Kit (`/speckit-plan`, `/speckit-tasks`, `/speckit-analyze`)
> os localizam por esses nomes. O conteúdo segue em português, como o resto das
> notas do projeto.

Referência de domínio: `Game/Fluxo de Partida.md` no vault, na versão corrigida
em 2026-09-11. A §5B, a §5C, a saída da §5 e a §7.2 são o contrato desta
feature. A §6 foi removida, e a numeração das outras seções foi mantida.

**Esta feature corrige um erro de regra, não acrescenta uma.** A nota antiga
descrevia uma pilha de feitiços: o feitiço lançado na Fase de Ação esperava, o
oponente podia responder, e tudo resolvia de trás para frente quando os dois
passavam, com fizzle para alvo que sumiu. A feature 006 implementou isso, e as
features 002, 003, 005 e 007 carregam pedaços: a fase de resolução de pilha, a
pilha no estado, na forma gravada e na visão do jogador, o ramo da saída da §5
que manda para a pilha, a exigência de pilha vazia para declarar ataque, e a
separação entre dois jeitos de lançar feitiço — um que empilhava e outro, na
janela do defensor, que resolvia na hora.

A regra certa é a que o feitiço do defensor já seguia: o efeito acontece no
momento em que o feitiço é jogado, e **a vez não passa**. Na Fase de Ação e na
janela do defensor, quem tem a prioridade joga quantos feitiços quiser; a vez só
passa com uma das outras ações.

A constituição diz que, quando código e nota discordam, o código está errado.
Esta feature é o código sendo corrigido.

A spec nomeia peças existentes — o aplicador único de efeito, as guardas de
lançamento, a varredura de morte, a apuração de vitória — só como **fronteira**,
nunca como desenho novo. É a convenção das specs 005 a 007: o que não pode
ganhar uma segunda versão precisa ser nomeável para ser verificável.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Feitiço na Fase de Ação resolve na hora e não gasta a vez (Priority: P1)

Quem tem a prioridade na Fase de Ação joga um feitiço da mão. Se a carta é
feitiço, a energia cobre o custo e o alvo está certo — presente e do lado
certo quando o feitiço pede alvo, ausente quando não pede —, o feitiço
acontece: a energia é descontada, a carta sai da mão, o efeito é aplicado, e a
carta vai para o cemitério. Tudo nessa jogada.

Não existe janela de resposta, e a vez não passa: quem jogou continua com a
prioridade e pode jogar outro feitiço, quantos a energia pagar. A vez só passa
quando ele joga unidade, declara ataque ou passa.

**Why this priority**: é a regra corrigida. Enquanto isto não vale, todo feitiço
lançado fora do combate joga um jogo que não é o Anathema.

**Independent Test**: com a partida na Fase de Ação, jogar SUMMONED AX (3 de
dano) numa unidade
inimiga de 3 de vida e conferir, logo depois da jogada e sem nenhum passe: a
unidade no cemitério do dono, o feitiço no cemitério de quem jogou, a energia
descontada, a prioridade ainda com quem jogou, a contagem de passes em 0, e nada
pendente em lugar nenhum da partida. Em seguida jogar um segundo feitiço e
conferir que é aceito.

**Acceptance Scenarios**:

1. **Given** A com prioridade na Fase de Ação e energia suficiente, **When** A
   joga um feitiço de dano numa unidade inimiga, **Then** o dano está na
   unidade imediatamente depois da jogada, sem que nenhum jogador tenha
   passado.
2. **Given** a mesma jogada, **When** eu leio a partida, **Then** a carta do
   feitiço está no cemitério de A, a energia de A caiu do custo, a prioridade
   continua com A, e a fase continua sendo a Fase de Ação.
3. **Given** A acabou de jogar um feitiço e ainda tem energia, **When** A joga
   outro feitiço, **Then** a jogada é aceita; e **When** A joga em seguida uma
   unidade, **Then** a prioridade passa a B.
4. **Given** um feitiço de dano que mata a unidade alvo, **When** A o joga,
   **Then** a unidade vai para o cemitério do dono **antes** da carta do
   feitiço ir para o cemitério de A.
5. **Given** B passou uma vez, **When** A joga um feitiço e depois passa,
   **Then** a contagem de passes está em 1 e a rodada **não** fecha: B recebe a
   vez e pode responder ao que o feitiço fez.
6. **Given** um feitiço sem alvo (LIFE POTION), **When** A o joga, **Then** o
   Nexus de A muda na mesma jogada.
7. **Given** um feitiço que dá vida permanente (SOMEONE'S SHIELD), **When** A o
   joga numa unidade própria, **Then** o modificador está na unidade
   imediatamente.
8. **Given** B sem prioridade, **When** B tenta jogar um feitiço, **Then** a
   jogada é recusada por prioridade e a partida não muda.

---

### User Story 2 - Feitiço do defensor é o mesmo feitiço (Priority: P1)

Na janela do defensor, o defensor joga feitiço com as mesmas guardas, o mesmo
resultado e a mesma prioridade da Fase de Ação: resolve na hora e a vez não
passa. Ele segue bloqueando, desbloqueando e jogando feitiço até encerrar a
janela com **Resolver**.

É o comportamento que o motor já tem hoje para o defensor. O que muda é que ele
deixa de ser uma ação separada: jogar feitiço é **uma** ação só, igual nas duas
fases. O que o combate tem de próprio é quem pode agir — só o defensor —, e não
como o feitiço funciona.

**Why this priority**: é a metade da regra corrigida que já estava certa, e é
ela que não pode quebrar ao juntar as duas.

**Independent Test**: com o combate aberto, o defensor joga dois feitiços
seguidos pela mesma ação de jogar feitiço usada na Fase de Ação, e depois
atribui um bloqueador; conferir que os dois efeitos aconteceram na hora e que a
prioridade continuou com ele o tempo todo.

**Acceptance Scenarios**:

1. **Given** um combate aberto, **When** o defensor joga um feitiço de dano num
   atacante, **Then** o dano acontece na hora e a prioridade continua com o
   defensor.
2. **Given** o mesmo combate, **When** o defensor joga um segundo feitiço logo
   em seguida, **Then** a jogada é aceita.
3. **Given** um feitiço do defensor que mata um atacante já bloqueado, **When**
   o combate resolve, **Then** o bloqueador fica órfão como a feature 007
   define.
4. **Given** um combate aberto, **When** o atacante tenta jogar feitiço,
   **Then** a jogada é recusada por prioridade.
5. **Given** a ação de jogar feitiço, **When** eu a uso na Fase de Ação e na
   janela do defensor, **Then** é a mesma ação nas duas, com os mesmos campos.

---

### User Story 3 - A rodada fecha com dois passes, e o ataque não espera nada (Priority: P1)

Dois passes seguidos na Fase de Ação levam ao Fim de Rodada. Não existe outro
destino: nunca há feitiço pendente para resolver antes.

Declarar ataque exige ser o dono do token, o token não consumido e ao menos uma
unidade no banco. Não existe mais a exigência de pilha vazia.

**Why this priority**: são as duas regras da §5 que dependiam da pilha. Sem
corrigi-las, a saída da fase e a declaração de ataque carregam ramos e recusas
de algo que não existe.

**Independent Test**: na Fase de Ação, A joga um feitiço e passa, B passa, e a
rodada fecha com o Upkeep da rodada seguinte executado. Em outra partida, o dono
do token joga um feitiço e, na mesma vez, declara ataque sem nenhuma condição a
mais.

**Acceptance Scenarios**:

1. **Given** a Fase de Ação com a contagem de passes em 1, **When** o outro
   jogador passa, **Then** a partida chega à Fase de Ação da rodada seguinte com
   o Upkeep executado.
2. **Given** A jogou um feitiço e passou, **When** B passa, **Then** a rodada
   fecha — não existe resolução no meio.
3. **Given** o dono do token com prioridade, token livre e unidades no banco,
   **When** ele declara ataque, **Then** a jogada é aceita, sem nenhuma guarda
   sobre feitiço pendente.
4. **Given** o dono do token com prioridade, **When** ele joga dois feitiços e
   declara ataque na mesma vez, **Then** as três jogadas são aceitas.

---

### User Story 4 - Nenhum resto de pilha na partida (Priority: P2)

A pilha deixa de existir em todo lugar: no estado da partida, na forma gravada
que atravessa os workers, na visão que cada jogador recebe, no conjunto de fases
e no conjunto de recusas. Também deixa de existir o fizzle, a devolução de
prioridade a quem iniciou a pilha, e a regra de que a partida encerrada no meio
da resolução não resolve o resto.

**Why this priority**: resto de pilha que sobra é campo sempre vazio, fase
inalcançável e recusa que nunca dispara — e a feature 009 publicaria tudo isso
para o cliente como se fosse parte do jogo. É P2 porque o jogo já joga certo com
as histórias P1; esta é a limpeza que impede o erro de voltar pela porta dos
fundos.

**Independent Test**: gravar e reler uma partida em cada fase, montar a visão
dos dois jogadores, e listar as fases e as recusas do motor; conferir que nenhum
deles tem pilha, entrada de pilha, fase de resolução ou recusa de pilha.

**Acceptance Scenarios**:

1. **Given** uma partida em qualquer fase, **When** ela é gravada e relida,
   **Then** a forma gravada não tem campo de pilha e a partida relida é igual à
   original.
2. **Given** uma partida em qualquer fase, **When** eu monto a visão de um
   jogador, **Then** ela não tem campo de pilha.
3. **Given** o conjunto de fases da partida, **When** eu o listo, **Then** não
   existe fase de resolução de pilha.
4. **Given** o conjunto de recusas do motor, **When** eu o listo, **Then** não
   existe recusa de pilha cheia, e as recusas das guardas de lançamento
   continuam todas lá.
5. **Given** o motor, **When** eu procuro o fizzle, **Then** ele não existe como
   caminho nem como regra descrita.

---

### User Story 5 - Uma partida inteira com feitiço imediato (Priority: P3)

Uma partida roda do setup à vitória com feitiços jogados na Fase de Ação e na
janela do defensor, todos resolvendo na hora.

**Why this priority**: é a prova de integração das outras histórias; não entrega
comportamento novo sozinha.

**Independent Test**: o roteiro de partida completa que o motor já tem, reescrito
para a regra corrigida, roda do setup à vitória com aleatoriedade determinística.

**Acceptance Scenarios**:

1. **Given** dois jogadores com o deck de andaime, **When** o roteiro alterna
   unidades, feitiços na Fase de Ação, combates com feitiço do defensor e passes
   até um Nexus chegar a 0, **Then** a partida termina com o resultado certo e
   recusa qualquer ação a mais.

---

### Edge Cases

- **Feitiço jogado depois de um passe do oponente**: zera a contagem; a rodada
  só fecha com dois passes seguidos depois dele, então o oponente sempre recebe
  a vez depois de um feitiço antes de a rodada acabar.
- **Vários feitiços seguidos na mesma vez**: todos aceitos enquanto a energia
  pagar; cada um resolve inteiro antes do próximo ser jogado.
- **Feitiço seguido de declarar ataque na mesma vez**: aceito — o feitiço não
  gastou a vez.
- **Feitiço que mata o próprio alvo**: a unidade morre na jogada, e vai ao
  cemitério antes da carta do feitiço.
- **SACRIFICIAL FIRE e MAGIC BARRIER**: a segunda correção da nota (§14) deu a
  eles regra própria — momento, alvo, Nexus mínimo 1, barreira de um dano só. É
  outra feature. Aqui eles continuam com o comportamento de hoje, e nenhum teste
  desta feature afirma sobre eles algo que a §14 mudou.
- **Feitiço que termina a partida**: pela nota corrigida nenhum feitiço derrota
  ninguém (§10). O motor de hoje ainda deixa o SACRIFICIAL FIRE fazer isso, e
  esta feature não mexe nisso nem acrescenta teste para isso.
- **Alvo que não está em campo no momento da jogada**: recusa, como já é hoje.
  Não existe fizzle: como não há intervalo entre validar e aplicar, alvo
  inválido é sempre recusa.
- **Alvo aliado para feitiço de inimigo, ou o contrário**: recusa de lado, como
  hoje.
- **Feitiço sem alvo recebendo alvo, ou com alvo chegando sem**: recusa, como
  hoje.
- **Atacante tentando jogar feitiço durante o combate**: recusa por prioridade,
  como hoje.
- **Jogar feitiço fora da Fase de Ação e da janela do defensor** — no
  mulligan, ou com a partida terminada: recusa, pelas mesmas guardas comuns de
  qualquer outra ação e na mesma ordem.
- **Partida gravada antes desta feature**: ver Assumptions.

## Requirements *(mandatory)*

### Functional Requirements

**Jogar feitiço**

- **FR-001**: Jogar feitiço MUST ser **uma** ação só, legal na Fase de Ação e
  na janela do defensor.
- **FR-002**: A ação MUST carregar o autor, a carta da mão e o alvo, quando o
  feitiço pede alvo.
- **FR-003**: As guardas de lançamento MUST continuar as mesmas e na mesma
  ordem: carta na mão do autor, carta é feitiço, energia cobre o custo, alvo
  casa com o que o efeito declara (exigido ou proibido, lado certo, em campo).
- **FR-004**: Aceita, a ação MUST descontar a energia, tirar a carta da mão,
  aplicar o efeito e mandar a carta ao cemitério de quem jogou, tudo na mesma
  jogada.
- **FR-005**: A carta do feitiço MUST ir ao cemitério **depois** do efeito, de
  modo que uma unidade morta pelo efeito entre no cemitério antes dela.
- **FR-006**: O efeito MUST ser aplicado pelo aplicador único que já existe, e
  MUST NOT ganhar um segundo caminho de aplicação por fase.
- **FR-007**: Na Fase de Ação, jogar feitiço MUST zerar a contagem de passes.
- **FR-008**: Jogar feitiço MUST NOT passar a prioridade, na Fase de Ação e na
  janela do defensor. Quem tem a prioridade MUST poder jogar quantos feitiços a
  energia pagar.
- **FR-008a**: Jogar unidade, declarar ataque e passar MUST continuar passando a
  prioridade ao oponente, como hoje. As ações da janela do defensor MUST
  continuar não passando.
- **FR-009**: Uma recusa MUST deixar a partida exatamente como estava.
- **FR-010**: O fizzle MUST NOT existir. Alvo que não está em campo no momento
  da jogada MUST ser recusa.
- **FR-011**: A morte por dano de feitiço MUST continuar sendo apurada assim que
  o efeito termina, pela varredura de morte que já existe.
- **FR-012**: A alteração de Nexus por feitiço MUST continuar passando pelo
  único escritor de Nexus, que apura a §10.

**Saída da Fase de Ação e declaração de ataque**

- **FR-013**: Dois passes seguidos na Fase de Ação MUST levar ao Fim de Rodada,
  sem nenhum outro ramo.
- **FR-014**: Declarar ataque MUST exigir só: ser o dono do token, o token não
  consumido, e ao menos uma unidade no banco — além das guardas de seleção que
  a feature 007 já define.

**Remoção da pilha**

- **FR-015**: O estado da partida MUST NOT ter pilha nem entrada de pilha.
- **FR-016**: A forma gravada da partida MUST NOT ter campo de pilha, e a ida e
  volta pela forma gravada MUST continuar produzindo uma partida igual à
  original.
- **FR-017**: A visão do jogador MUST NOT ter campo de pilha.
- **FR-018**: O conjunto de fases MUST NOT ter fase de resolução de pilha.
- **FR-019**: O conjunto de recusas MUST NOT ter recusa de pilha cheia.
- **FR-020**: A devolução de prioridade a quem iniciou a pilha e a regra de
  partida encerrada no meio da resolução MUST deixar de existir, junto com o
  caminho que as executava.
- **FR-021**: A descrição escrita do motor — o que cada módulo diz de si, e o
  que cada teste afirma — MUST NOT apresentar pilha, resposta a feitiço ou
  fizzle como regra vigente.

**O que não pode quebrar**

- **FR-022**: Os cinco efeitos do MVP MUST produzir, campo a campo, o mesmo
  resultado que produzem hoje no caminho do defensor.
- **FR-023**: O combate da feature 007 MUST continuar como está: declaração,
  janela do defensor com bloqueio 1:1, dano simultâneo, bloqueador órfão,
  limpeza e um ataque por rodada.
- **FR-024**: A cascata de Fim de Rodada e Upkeep MUST continuar como está,
  incluindo a varredura de efeitos "até o fim da rodada".
- **FR-025**: O setup, o mulligan, a compra com reset de deck e a condição de
  vitória MUST continuar como estão.
- **FR-026**: Nenhuma regra fora da alternância da §5, da §5B, da §5C, da saída
  da §5, da §6 removida e da §7.2 MUST mudar.

### Key Entities

- **Ação de jogar feitiço**: uma só, com autor, carta e alvo opcional. Legal na
  Fase de Ação e na janela do defensor, e nas duas não passa a prioridade.
- **Partida**: perde a pilha e a fase de resolução. Todo o resto do estado fica.
- **Visão do jogador**: perde o campo de pilha. Todo o resto fica.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% dos feitiços aceitos, na Fase de Ação e na janela do
  defensor, têm o efeito visível no estado imediatamente depois da jogada, antes
  de qualquer outra ação.
- **SC-002**: Uma partida inteira roda do setup à vitória com feitiços nas duas
  fases, sem nenhum passe usado para fazer um feitiço acontecer.
- **SC-003**: 0 ocorrências de pilha, entrada de pilha, fase de resolução ou
  recusa de pilha no estado, na forma gravada, na visão, no conjunto de fases e
  no conjunto de recusas.
- **SC-004**: O jogador tem exatamente 1 ação de jogar feitiço, contra as 2 de
  hoje.
- **SC-005**: 100% dos testes dos cinco efeitos, das guardas de lançamento, do
  combate, do Fim de Rodada, do Upkeep, do setup e da compra continuam passando;
  só mudam os que afirmavam pilha, resposta ou fizzle.

## Assumptions

- **Uma ação de feitiço, não duas.** A nota corrigida descreve um só "jogar
  feitiço", e a separação da feature 007 existia porque um caminho empilhava e
  o outro não. Sem pilha e sem troca de vez, os dois fazem exatamente a mesma
  coisa com os mesmos campos. Manter duas ações faria a feature 009 publicar
  para o cliente dois tipos de mensagem para o mesmo gesto.
- **Feitiço zera a contagem de passes**, como a §5B diz. Consequência: depois
  de um feitiço, o oponente sempre recebe a vez antes de a rodada fechar, e
  pode reagir ao que o feitiço fez.
- **Partidas gravadas antes desta feature não são migradas.** Nenhum cliente
  consegue jogar ainda — o protocolo é a feature 009 —, então uma partida no
  Redis só pode estar parada no mulligan, com a pilha vazia. Elas expiram em 6
  horas.
- **As specs 005 a 007 não são reescritas.** São registro do que foi entregue
  em cada feature; esta spec registra a correção. A nota do vault é a fonte da
  verdade, e já foi corrigida.
- **A spec da feature 009 (protocolo) está pausada** esperando esta, e é
  revisada depois dela para tirar pilha, fizzle e o feitiço do defensor como
  ação separada.
- **A segunda correção da nota (2026-09-11) fica para features próprias**, entre
  esta e o protocolo: energia que acumula (§4), a declaração de ataque como
  janela com desfazer e feitiço (§7.1), SACRIFICIAL FIRE e MAGIC BARRIER com
  regra própria (§14), sem empate e com desistência (§10), e o relógio da vez
  (§15). Esta feature só tira a pilha, que as duas correções pedem igual.
- **Fora de escopo**: o protocolo de websocket, as regras da segunda correção,
  cartas novas, palavras-chave, balanceamento, e a pergunta da §13 sobre feitiço
  do defensor invocar unidade que bloqueia.
- **Dependências**: o aplicador de efeito e as guardas de lançamento da feature
  006, a porta única de ação e a cascata da 005, o combate da 007, a forma
  gravada e a visão da 002, e a nota do Fluxo de Partida corrigida em
  2026-09-11.
