# Feature Specification: Resultado de partida, registrado uma vez só

**Feature Branch**: `012-match-result-history`

**Created**: 2026-09-12

**Status**: Draft

**Input**: User description: "Resultado de partida: registrar o que aconteceu quando uma partida acaba."

> Nota de idioma: os títulos de seção ficam em inglês porque os comandos
> seguintes do Spec Kit (`/speckit-plan`, `/speckit-tasks`, `/speckit-analyze`)
> os localizam por esses nomes. O conteúdo segue em português, como o resto das
> notas do projeto.

Hoje a partida acaba e o desfecho morre com o TTL de 6 horas do Redis. Os dois
jogadores veem a tela de fim, e nada sobra. `PlayerStats` nasce com o perfil no
cadastro e nunca mais é escrito: `matches_played`, `wins`, `losses` e
`play_time` ficam em zero para sempre.

Esta feature dá uma segunda vida ao desfecho: a partida que acaba vira uma linha
no banco, ligada aos dois perfis, e as estatísticas dos dois sobem junto. O
jogador consulta depois o próprio histórico.

Nada da §10 é redecidido aqui. As duas saídas — Nexus a zero e desistência — e a
ausência de empate já existem no motor. Esta spec as **usa** como fronteira,
nunca as redesenha, pela convenção das specs 005 a 011.

O requisito que carrega a feature não é o registro: é o **exatamente uma vez**.
A mesma partida é observada pelos dois jogadores, em conexões que podem estar em
workers diferentes, os dois recebem o estado final, e reconectar devolve o
estado final de novo. Nada disso pode produzir um segundo registro nem uma
segunda vitória.

## Vocabulário desta feature

- **Registro de partida**: a linha persistida que sobrevive ao TTL do Redis.
  Uma por partida terminada, nunca mais de uma, nunca menos.
- **Transição para terminada**: a gravação de estado que fez a partida passar de
  em andamento para terminada. É um evento, acontece uma vez, e é o único fato
  que autoriza um registro.
- **Observação**: qualquer leitura de uma partida já terminada — a entrega do
  estado final aos dois jogadores, a reconexão, a consulta de estado. Observação
  nunca registra.
- **Instante de criação**: o momento em que a partida foi criada. Passa a fazer
  parte do estado da partida, como os prazos do relógio da §15 já fazem, e
  sobrevive à ida e à volta pelo Redis.
- **Duração da partida**: o instante do fim menos o instante de criação.
- **Rodada final**: o número da rodada em que a partida acabou.
- **Motivo do fim**: Nexus a zero ou desistência. Conjunto fechado, o mesmo da
  §10; não existe empate e não existe derrota por abandono.
- **Histórico**: a lista paginada das partidas registradas de um jogador, da
  mais recente para a mais antiga.
- **Partida abandonada**: partida que nunca chegou a terminar e expirou do
  Redis. Não é desfecho: não produz registro nem mexe em estatística.
- **Deck da partida**: a lista de cartas com que o jogador entrou na fila, mais
  o nome que o deck tinha naquele momento. Cópia congelada: não é referência ao
  deck guardado, e editar ou apagar o deck depois não a altera.
- **Nexus final**: o Nexus de cada jogador no instante do fim, como ficou
  congelado no estado terminal.

## Clarifications

### Sessão 2026-09-12

- **P: Guardar com que deck cada um jogou?**
  R: Sim, como cópia congelada — a lista de cartas da entrada na fila mais o
  nome do deck naquele momento. Referência ao deck guardado não serve: o deck
  editado muda o que ela significa e o apagado a esvazia, e o dado histórico
  ficaria falso exatamente quando fosse usado. A lista congelada já existe: a
  fila leva o deck validado junto da entrada e o pareamento não o relê. O nome
  **não** viaja hoje — só o `deck_id` chega ao socket da fila —, e passa a
  viajar.
- **P: Registrar mais alguma coisa da partida além do desfecho?**
  R: O Nexus final dos dois jogadores, e nada mais. É um número por jogador, já
  está no estado terminal, e separa vitória apertada de atropelo. Cartas jogadas
  e número de turnos ficam de fora: contá-las exigiria contador novo mantido
  pelo motor durante a partida, que hoje não existe.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A partida que acaba vira exatamente um registro (Priority: P1)

Uma partida chega ao fim — por Nexus a zero ou por desistência — e o desfecho
deixa de ser efêmero. A jogada que levou a partida ao fim produz uma linha ligada
aos dois perfis, com o `match_id`, quem venceu, quem perdeu, o motivo, quando
começou, quando acabou, quanto durou e em que rodada acabou.

Os dois jogadores recebem o estado final como recebem hoje. A partida terminada
continua no Redis até expirar, e quem reconecta continua recebendo a visão final.
Nenhuma dessas leituras registra coisa alguma — só a transição registra.

**Why this priority**: é a feature. Sem ela nada do resto existe, e o desfecho
continua morrendo com o TTL.

**Independent Test**: rodar uma partida até o Nexus de um jogador chegar a zero
e conferir que existe uma linha com os seis campos; repetir com desistência;
entregar o estado final aos dois jogadores e reconectar várias vezes, conferindo
que a contagem de linhas daquele `match_id` continua em um.

**Acceptance Scenarios**:

1. **Given** uma partida em andamento, **When** o Nexus de um jogador chega a
   zero, **Then** existe exatamente um registro daquele `match_id`, com o
   vencedor, o derrotado e o motivo Nexus a zero.
2. **Given** uma partida em andamento, **When** um jogador desiste, **Then**
   existe exatamente um registro, com derrota para quem desistiu, vitória para o
   outro, e o motivo desistência.
3. **Given** uma partida que acabou de terminar, **When** os dois jogadores
   recebem o estado final, **Then** a contagem de registros daquele `match_id`
   continua em um.
4. **Given** uma partida terminada ainda viva no Redis, **When** um jogador
   reconecta e recebe a visão final, quantas vezes for, **Then** nenhum registro
   novo aparece e nenhuma estatística muda.
5. **Given** uma partida terminada, **When** o registro é lido, **Then** ele traz
   o instante de criação, o instante do fim, a duração entre os dois e a rodada
   final.
6. **Given** uma partida criada num worker e terminada em outro, **When** o
   registro é lido, **Then** o instante de criação é o da criação de verdade, e
   não o da última gravação.
7. **Given** o registro de uma partida, **When** alguém procura um campo chamado
   `id`, **Then** não existe nenhum: o espaço de identidade é nomeado
   (`match_id`, `user_id`, `profile_id`).
8. **Given** uma partida terminada, **When** o registro é lido, **Then** ele traz,
   para cada jogador, a lista de cartas com que ele entrou na fila e o nome que o
   deck tinha naquele momento.
9. **Given** uma partida registrada, **When** o jogador edita ou apaga o deck com
   que jogou, **Then** o registro continua com a lista e o nome de quando a
   partida aconteceu.
10. **Given** uma partida terminada, **When** o registro é lido, **Then** ele traz
    o Nexus final dos dois jogadores.

---

### User Story 2 - As estatísticas dos dois jogadores sobem junto com o registro (Priority: P1)

Registrada a partida, as estatísticas dos dois jogadores deixam de ser zero para
sempre: partidas jogadas sobe para os dois, vitória para um, derrota para o
outro, e a duração entra no tempo de jogo dos dois.

As duas escritas — registro e estatísticas — acontecem juntas ou não acontecem.
Uma falha no meio não pode deixar vitória contada sem partida registrada, nem
partida registrada sem vitória contada.

**Why this priority**: `PlayerStats` existe desde o cadastro e nunca foi escrito.
Sem esta história a feature registra partidas que ninguém consegue somar.

**Independent Test**: partir de dois jogadores com estatísticas zeradas, rodar
uma partida até o fim, e conferir os quatro contadores dos dois lados; forçar a
falha da escrita de estatísticas e conferir que o registro também não ficou.

**Acceptance Scenarios**:

1. **Given** dois jogadores com estatísticas zeradas, **When** uma partida entre
   eles termina, **Then** partidas jogadas é 1 para os dois, vitórias é 1 para o
   vencedor e 0 para o derrotado, e derrotas é 1 para o derrotado e 0 para o
   vencedor.
2. **Given** dois jogadores com estatísticas zeradas, **When** uma partida de
   duração conhecida termina, **Then** o tempo de jogo dos dois subiu daquela
   mesma duração.
3. **Given** um jogador com cinco partidas já registradas, **When** a sexta
   termina, **Then** os contadores sobem de um, sem recontar as anteriores.
4. **Given** a escrita das estatísticas falhando, **When** a partida termina,
   **Then** não existe registro daquela partida e nenhuma estatística mudou.
5. **Given** a escrita do registro falhando, **When** a partida termina, **Then**
   os dois jogadores continuam recebendo o estado final e a partida continua
   terminada no Redis.

---

### User Story 3 - O jogador consulta o próprio histórico (Priority: P2)

O jogador pede as próprias partidas e recebe uma página, da mais recente para a
mais antiga. Cada linha mostra o oponente, se venceu ou perdeu, o motivo, a
duração, a rodada final e a data.

Só as próprias. Não existe caminho para o histórico de outro jogador.

**Why this priority**: o registro tem valor assim que existe — ele alimenta as
estatísticas —, mas a consulta é o que o jogador enxerga. Depende das duas
histórias acima e não bloqueia nenhuma delas.

**Independent Test**: com registros semeados para dois jogadores, pedir o
histórico de um e conferir a ordem, o conteúdo das linhas, a paginação e que
nenhuma linha do outro jogador aparece; tentar alcançar o histórico do outro por
qualquer caminho e conferir a recusa.

**Acceptance Scenarios**:

1. **Given** um jogador com partidas registradas, **When** pede o próprio
   histórico, **Then** recebe as partidas da mais recente para a mais antiga.
2. **Given** uma linha do histórico, **When** o jogador a lê, **Then** encontra o
   oponente, se venceu ou perdeu, o motivo, a duração, a rodada final e a data do
   fim.
3. **Given** um jogador com mais partidas do que cabem numa página, **When** pede
   a página seguinte, **Then** recebe as partidas seguintes, sem repetir nem
   pular nenhuma.
4. **Given** um jogador sem nenhuma partida registrada, **When** pede o próprio
   histórico, **Then** recebe uma lista vazia, e não uma recusa.
5. **Given** dois jogadores com históricos diferentes, **When** um pede o
   próprio, **Then** nenhuma linha em que ele não jogou aparece.
6. **Given** um jogador autenticado, **When** tenta alcançar o histórico de
   outro, **Then** é recusado, e a recusa não revela se aquele histórico existe.
7. **Given** uma requisição sem autenticação, **When** pede qualquer histórico,
   **Then** é recusada.
8. **Given** um oponente cujo perfil foi apagado depois da partida, **When** o
   jogador lê o próprio histórico, **Then** a linha continua lá, com o desfecho
   intacto, e a leitura não quebra.

---

### Edge Cases

- **Desistência durante o mulligan, antes da Rodada 1**: registra como qualquer
  outra desistência, com a rodada final sendo a primeira.
- **Partida abandonada pelos dois, que nunca termina e expira do Redis**: não
  produz registro nenhum e não mexe em estatística de ninguém. Não existe derrota
  por abandono.
- **Os dois clientes recebendo o estado final ao mesmo tempo, em workers
  diferentes**: um registro só. A corrida perde, e perder não é erro que chegue
  ao cliente.
- **Reconectar depois do fim, quantas vezes for**: nenhum registro novo, nenhuma
  estatística mexida.
- **Retentativa do compare-and-swap**: a gravação de estado relê e reaplica a
  mudança quando a versão mudou. Uma retentativa é rotina, não exceção, e não
  pode produzir uma segunda escrita de banco.
- **Perfil apagado depois da partida**: o registro sobrevive e o histórico do
  outro jogador continua legível.
- **Deck editado ou apagado depois da partida**: o registro não muda. A lista e o
  nome guardados são os do momento da entrada na fila.
- **Desistência com Nexus cheio**: o Nexus final registrado é o que estava —
  quem desiste com 20 perdeu igual, e o registro mostra as duas coisas.
- **Partida viva gravada antes desta feature**, sem instante de criação no
  estado: termina normalmente e produz registro, com o instante de criação
  assumido igual ao do fim e duração zero. Situação de janela de implantação,
  limitada às 6 horas do TTL.
- **Partida terminada cujo registro falhou**: a partida continua terminada no
  Redis e os jogadores veem o fim. A falha é registrada em log estruturado e não
  vira recusa para o cliente.

## Requirements *(mandatory)*

### Functional Requirements

#### O registro

- **FR-001**: Toda partida que transita para terminada MUST produzir exatamente
  um registro persistido, que sobrevive à expiração da partida no Redis.
- **FR-002**: O registro MUST carregar o `match_id` da partida, o vencedor, o
  derrotado, o motivo do fim, o instante de criação, o instante do fim, a duração
  e a rodada final.
- **FR-003**: O registro MUST estar ligado aos perfis dos dois jogadores.
- **FR-004**: O `match_id` MUST ser único entre os registros. É ele que faz uma
  corrida perder em vez de duplicar.
- **FR-005**: O motivo do fim MUST ser um dos dois da §10 — Nexus a zero ou
  desistência. Não existe empate e não existe derrota por abandono.
- **FR-006**: O vencedor MUST ser o jogador que não é o derrotado, derivado do
  par de jogadores da partida. Nenhuma camada nova pode decidir quem venceu.

#### Exatamente uma vez

- **FR-007**: Só a transição para terminada pode registrar. Nenhuma observação de
  uma partida já terminada pode produzir registro ou alterar estatística.
- **FR-008**: O registro MUST acontecer fora da mutação do estado da partida,
  depois da gravação de estado bem-sucedida. Uma mutação que é reaplicada numa
  retentativa MUST NOT produzir escrita de banco nenhuma.
- **FR-009**: Quando duas tentativas concorrentes chegarem ao registro da mesma
  partida, exatamente uma MUST persistir; a outra MUST ser descartada sem
  duplicar dado, sem alterar estatística e sem virar recusa para o cliente.
- **FR-010**: Uma partida que expira do Redis sem ter terminado MUST NOT produzir
  registro nem alterar estatística de ninguém.

#### As estatísticas

- **FR-011**: O registro da partida e a atualização das estatísticas dos dois
  jogadores MUST ser atômicos entre si: ou os dois acontecem, ou nenhum.
- **FR-012**: Ao registrar, partidas jogadas MUST subir de um para os dois
  jogadores; vitórias MUST subir de um para o vencedor; derrotas MUST subir de um
  para o derrotado; o tempo de jogo MUST subir da duração da partida para os
  dois.
- **FR-013**: As estatísticas MUST ser somadas a partir do valor corrente, sem
  recontar partidas já registradas, e sem perder incrementos concorrentes de
  outra partida do mesmo jogador.

#### O estado da partida

- **FR-014**: O instante de criação MUST fazer parte do estado da partida e MUST
  sobreviver à ida e à volta pelo armazenamento — criada num worker, lida em
  outro, o instante é o mesmo.
- **FR-015**: A partida terminada MUST continuar disponível no armazenamento até
  expirar, e a reconexão MUST continuar entregando a visão final exatamente como
  hoje.
- **FR-016**: Uma falha ao registrar MUST NOT impedir a partida de terminar, MUST
  NOT impedir os jogadores de receberem o estado final, e MUST NOT virar recusa
  para o cliente; MUST ser registrada em log estruturado.

#### O histórico

- **FR-017**: O jogador autenticado MUST conseguir listar as próprias partidas
  registradas, da mais recente para a mais antiga, em páginas.
- **FR-018**: Cada linha do histórico MUST trazer o oponente, se o jogador venceu
  ou perdeu, o motivo do fim, a duração, a rodada final e a data do fim.
- **FR-019**: O histórico de um jogador MUST NOT ser alcançável por outro
  jogador, por nenhum caminho.
- **FR-020**: Uma requisição sem autenticação MUST ser recusada.
- **FR-021**: Nenhum campo exposto pode se chamar `id`: o espaço de identidade é
  nomeado (`match_id`, `user_id`, `profile_id`).
- **FR-022**: O registro MUST sobreviver à exclusão do perfil de um dos
  jogadores, e o histórico do outro MUST continuar legível, com o desfecho
  intacto.

#### O que não muda

- **FR-023**: O motor não conhece banco e MUST continuar sem conhecer.
- **FR-024**: O protocolo de partida, o relógio da vez e o compare-and-swap da
  gravação de estado MUST continuar funcionando como hoje, sem mudança de
  contrato.
- **FR-025**: O fluxo de matchmaking e o de decks MUST continuar com o mesmo
  comportamento observável — as mesmas regras de validação, as mesmas recusas, o
  mesmo pareamento. A única mudança permitida é o nome do deck passar a viajar
  junto da lista de cartas que a entrada na fila já carrega (FR-029); ela MUST
  NOT alterar quem é pareado com quem nem quando.
- **FR-026**: A criação de perfil e de estatísticas no cadastro MUST continuar
  inalterada.

#### O deck e o Nexus final

- **FR-027**: O registro MUST guardar, para cada jogador, o deck da partida:
  a lista de cartas com que ele entrou na fila e o nome que o deck tinha naquele
  momento.
- **FR-028**: O deck da partida MUST ser cópia congelada, não referência: editar
  ou apagar o deck guardado depois da partida MUST NOT alterar o registro.
- **FR-029**: O nome do deck escolhido na entrada da fila MUST viajar com a
  entrada até a partida, como a lista de cartas já viaja, e MUST NOT ser relido
  do deck guardado no momento do registro.
- **FR-030**: O registro MUST guardar o Nexus final dos dois jogadores, como
  ficou no estado terminal.
- **FR-031**: Nada além do desfecho, do deck da partida e do Nexus final entra no
  registro: cartas jogadas e número de turnos ficam de fora, e nenhum contador
  novo é mantido pelo motor durante a partida.
- **FR-032**: O deck da partida MUST fazer parte do estado da partida e MUST
  sobreviver à ida e à volta pelo armazenamento, como o instante de criação
  (FR-014). A lista registrada é a da entrada na fila, e MUST NOT ser
  reconstruída a partir das zonas de carta no fim da partida.

### Key Entities

- **Registro de Partida**: uma partida que acabou. Identificada pelo `match_id`,
  único entre os registros. Guarda vencedor, derrotado, motivo do fim, instante
  de criação, instante do fim, duração, rodada final, Nexus final dos dois e, por
  jogador, o deck da partida. Ligada aos perfis dos dois jogadores, e sobrevive à
  exclusão de qualquer um deles.
- **Deck da partida**: a lista de cartas da entrada na fila mais o nome do deck
  naquele momento, copiados para dentro do registro. Não aponta para o deck
  guardado do jogador e não muda quando ele muda.
- **Estatísticas do Jogador**: os contadores acumulados de um perfil — partidas
  jogadas, vitórias, derrotas, tempo de jogo. Já existem, criados junto com o
  perfil; esta feature passa a escrevê-los.
- **Perfil do Jogador**: o dono das estatísticas e a ponta dos registros. Um por
  usuário, permanente.
- **Partida viva**: o estado efêmero no armazenamento. Ganha o instante de
  criação e o deck da partida de cada jogador; nada mais muda nela.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Uma partida encerrada por Nexus a zero e uma encerrada por
  desistência produzem, cada uma, exatamente um registro com vencedor, derrotado,
  motivo, duração e rodada final corretos.
- **SC-002**: Os dois jogadores recebendo o estado final ao mesmo tempo, em
  processos diferentes, produzem um registro só — verificado com 100 execuções
  concorrentes, todas com contagem 1.
- **SC-003**: Reconectar a uma partida terminada 20 vezes seguidas não muda a
  contagem de registros nem nenhum contador de estatística.
- **SC-004**: Uma partida abandonada pelos dois que expira sem terminar produz
  zero registros e deixa as estatísticas dos dois exatamente como estavam.
- **SC-005**: Depois de uma partida terminada, os quatro contadores dos dois
  jogadores refletem o resultado: partidas jogadas +1 para ambos, vitória para
  um, derrota para o outro, tempo de jogo +duração para ambos.
- **SC-006**: Uma falha simulada na escrita das estatísticas deixa zero registros
  daquela partida e zero alterações de contador.
- **SC-007**: Uma falha simulada na escrita do registro não impede nenhum dos
  dois jogadores de receber o estado final.
- **SC-008**: O jogador recebe a primeira página do próprio histórico em ordem
  decrescente de data, e nenhuma tentativa de alcançar o histórico de outro
  jogador tem sucesso.
- **SC-009**: Percorrer todas as páginas do histórico de um jogador com 50
  partidas devolve as 50 linhas, sem repetição e sem omissão.
- **SC-010**: Apagar o perfil de um oponente mantém o histórico do outro jogador
  legível, com a mesma quantidade de linhas e o desfecho preservado.
- **SC-011**: O registro de uma partida terminada traz, para cada jogador, a
  mesma lista de cartas validada na entrada da fila e o nome que o deck tinha
  naquele momento; editar o nome e apagar o deck depois deixa o registro
  idêntico, campo a campo.
- **SC-012**: O registro traz o Nexus final dos dois jogadores, batendo com o
  estado terminal — incluindo a desistência, em que o Nexus de quem desistiu não
  é zero.
- **SC-013**: A suíte inteira (`cd server && pytest`) e a checagem de tipos
  continuam verdes, e nenhum teste existente de motor, protocolo, relógio, decks
  ou cadastro precisou ser alterado. Em matchmaking, a única alteração aceitável
  é a construção da entrada da fila passar a levar o nome do deck; nenhum teste
  de pareamento, de validação ou de recusa muda.

## Assumptions

- **Tempo de jogo em segundos**: `PlayerStats.play_time` acumula a duração das
  partidas em segundos inteiros. O campo já existe e nunca foi escrito, então não
  há valor legado a interpretar.
- **Tamanho de página**: 20 linhas por página, com teto de 100 quando o
  requisitante pedir mais. O projeto não tem paginação configurada hoje; este é o
  padrão que esta feature estabelece.
- **Duração medida pelo relógio de parede**, do instante de criação da partida ao
  instante do fim. Inclui as esperas — mulligan, tempo pensando, reconexões —,
  porque é o tempo que o jogador passou na partida.
- **O instante do fim é o da transição**, não o do registro no banco. A janela
  entre os dois é curta e não conta como tempo de jogo.
- **Partida viva sem instante de criação** (gravada antes desta feature e ainda
  dentro do TTL de 6 horas) termina normalmente, com instante de criação igual ao
  do fim e duração zero. Alternativa seria recusar a leitura, que derrubaria
  partidas em curso numa implantação.
- **Sem histórico agregado por oponente, por deck ou por carta**: o histórico é a
  lista das partidas, e nada além dela é calculado.
- **O deck da partida é guardado, não exibido**: a linha do histórico mostra o
  que o pedido listou — oponente, resultado, motivo, duração, rodada final e
  data. O deck e o Nexus final ficam no registro para a análise de balanceamento
  posterior; expô-los ao cliente é decisão de outra feature.
- **O deck do oponente também é guardado**, porque o registro é um por partida e
  guarda os dois lados. Isso não o torna visível: nenhuma resposta desta feature
  o entrega.
- **Partida viva sem deck da partida** (gravada antes desta feature e ainda
  dentro do TTL) termina normalmente e registra com deck vazio e sem nome, pela
  mesma razão do instante de criação ausente.
- **O oponente aparece pelo perfil**: apelido e identificador de perfil, os mesmos
  dados públicos que as outras respostas do jogador já expõem.
- **A exclusão de perfil é rara** e não tem fluxo de produto hoje; o requisito é
  que ela não quebre o histórico alheio, não que exista uma tela para ela.

## Out of Scope

- Experiência, nível, moedas e recompensa por partida. A economia é outra
  feature.
- Ranking, elo, pareamento por habilidade.
- Replay ou log jogada a jogada.
- Estatística por carta ou por deck: o dado passa a ser guardado, mas nada é
  agregado nem exposto nesta feature.
- Histórico de outro jogador, público ou de amigo.
- Cliente.
