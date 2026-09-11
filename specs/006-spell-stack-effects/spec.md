# Feature Specification: Pilha de Feitiços e Efeitos

**Feature Branch**: `006-spell-stack-effects`

**Created**: 2026-09-10

**Status**: Draft

**Input**: User description: "Pilha de feitiços: lançar feitiço, empilhar, responder, e resolver em LIFO com revalidação de alvo. Mais os cinco efeitos do catálogo, que é onde o motor finalmente altera vida, ataque e Nexus."

> Nota de idioma: os títulos de seção ficam em inglês porque os comandos
> seguintes do Spec Kit (`/speckit-plan`, `/speckit-tasks`, `/speckit-analyze`)
> os localizam por esses nomes. O conteúdo segue em português, como o resto das
> notas do projeto.

Referência de domínio: `Game/Fluxo de Partida.md` no vault. A §5B (jogar
feitiço), a §6 (Resolução de Pilha) e a §10 (vitória) são o contrato desta
feature. A §8 é consumida como a feature 005 a entregou: a varredura de
modificadores temporários não muda, ela só passa a ter o que varrer. A §12 dá
o Nexus inicial de 20.

Esta é a feature em que o motor finalmente **altera** vida de unidade, ataque
de unidade e Nexus de jogador. Até aqui nenhuma regra escrita tocava nenhum dos
três. É também a primeira em que uma partida pode acabar.

Três coisas que a feature 005 deixou escritas e inalcançáveis passam a ser
alcançáveis por esta: a saída "os dois passaram com a pilha cheia leva à
Resolução de Pilha", a fase `STACK_RESOLUTION` na cascata, e a varredura de
modificadores temporários do Fim de Rodada.

## Clarifications

### Sessão 2026-09-10

- **P: LIFE POTION num jogador com o Nexus já em 20. O Fluxo de Partida diz que
  o Nexus começa em 20 e que zero encerra a partida, e não diz nada sobre teto.
  Cura pode ultrapassar o valor inicial?**
  R: **Não existe teto.** O Nexus sobe livre acima de 20, e LIFE POTION nunca é
  jogada morta. A §12 continua dizendo só "Nexus inicial: 20" — é valor de
  partida, não limite superior.

  A consequência é que o Nexus é o único recurso do jogo sem teto: mão tem 10,
  banco tem 6, energia tem 10. A assimetria é deliberada — os outros três tetos
  existem para limitar o que o jogador pode **fazer** numa rodada, e o Nexus não
  habilita nada, só adia a derrota.

  A alternativa de fixar teto em 20 foi recusada por criar uma constante que a
  nota de domínio não tem, e a de recusar a jogada com Nexus cheio, por
  acrescentar uma recusa a uma ação que não tem nada de ilegal.

- **P: Um Nexus que chega a 0 no meio da resolução da pilha. Os feitiços
  restantes ainda resolvem? Um LIFE POTION abaixo de um SACRIFICIAL FIRE na
  mesma pilha muda quem ganha.**
  R: **A resolução para ali.** Assim que a verificação da §10 encontra um Nexus
  em 0 ou menos, a partida está terminada e nenhum efeito seguinte é aplicado.
  As entradas restantes da pilha vão para os cemitérios dos respectivos
  lançadores sem efeito, e a pilha termina vazia.

  É a leitura literal da §10 — "verificado depois de **qualquer** evento que
  altere um Nexus" — e a única que nunca produz o estado que esta feature existe
  para não produzir: Nexus em zero e a partida seguindo.

  Um LIFE POTION lançado antes de um SACRIFICIAL FIRE que mata o próprio
  lançador, portanto, não o salva: ele está **abaixo** na pilha e resolve
  depois. Salvar-se exige lançar a cura por cima, o que é decisão de ordem de
  lançamento, não acidente de implementação.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Lançar um feitiço (Priority: P1)

A terceira ação da Fase de Ação, ao lado de jogar unidade e passar.

Quem tem a prioridade pode lançar um feitiço da mão. Exige energia atual maior
ou igual ao custo da carta, e um alvo válido quando o efeito do feitiço exigir
alvo.

O que acontece: desconta a energia, tira a carta da mão, e põe o feitiço no
topo da pilha. **O efeito ainda não acontece.** A contagem de passes zera. A
prioridade troca — que é justamente o que dá ao oponente a chance de responder.

A validação de alvo acontece no lançamento, e "aliado" e "inimigo" são
relativos a quem lança: um feitiço de alvo aliado só aceita unidade no banco do
próprio lançador; um de alvo inimigo só aceita unidade no banco do oponente. Um
feitiço que não aceita alvo recusa a jogada que manda um, e um que exige alvo
recusa a jogada que não manda.

O motor decide tudo isso pelos campos estruturados do catálogo da feature 001 —
o tipo de alvo e a duração declarados pelo efeito — e **nunca** pela descrição
em português da carta.

**Why this priority**: sem lançar não existe pilha, e sem pilha nenhuma das
outras histórias existe. É a terceira e última ação da §5 que esta feature
entrega.

**Independent Test**: com 5 de energia, um feitiço de custo 5 na mão e uma
unidade aliada no banco, lançar o feitiço mirando a unidade e conferir energia
em 0, mão com uma carta a menos, pilha com uma entrada no topo, nenhuma
alteração em vida, ataque ou Nexus, passes em 0 e prioridade no oponente.

**Acceptance Scenarios**:

1. **Given** um jogador com prioridade, 5 de energia e um feitiço de custo 5 na
   mão, **When** ele o lança, **Then** a energia atual dele é 0, a carta saiu da
   mão e a pilha tem uma entrada.
2. **Given** um feitiço recém-lançado, **When** eu leio o estado inteiro da
   partida, **Then** nenhum Nexus mudou, nenhuma unidade ganhou modificador,
   nenhum dano acumulou e nada foi para o cemitério — o efeito não aconteceu.
3. **Given** um lançamento aceito, **When** a operação termina, **Then** a
   contagem de passes é 0 e a prioridade é do oponente.
4. **Given** um oponente que já tinha passado uma vez, **When** o jogador com
   prioridade lança um feitiço, **Then** a contagem de passes volta a 0 e a
   rodada não fecha.
5. **Given** um feitiço de alvo aliado e uma unidade no banco do próprio
   lançador, **When** ele a mira, **Then** a jogada é aceita.
6. **Given** um feitiço de alvo inimigo e uma unidade no banco do oponente,
   **When** ele a mira, **Then** a jogada é aceita.
7. **Given** um feitiço sem alvo, **When** ele é lançado sem alvo, **Then** a
   jogada é aceita e a entrada da pilha registra que não há alvo.
8. **Given** um lançamento aceito, **When** eu leio a entrada da pilha, **Then**
   ela guarda o identificador do alvo, o lançador, e a carta — nunca uma
   referência à unidade alvo.
9. **Given** um jogador com energia atual exatamente igual ao custo do feitiço,
   **When** ele o lança, **Then** a jogada é aceita e a energia dele fica em 0 —
   a guarda é `energia >= custo`.
10. **Given** um lançamento aceito, **When** eu leio o estado do oponente,
    **Then** só a prioridade mudou.

---

### User Story 2 - Responder no topo (Priority: P1)

A prioridade que trocou no lançamento é o que permite a resposta. O oponente,
agora com a prioridade, pode lançar o próprio feitiço, e ele entra **acima** do
primeiro. As mesmas guardas, na mesma ordem: participante, prioridade, fase, e
só então a regra da §5B.

A pilha pode conter feitiços dos dois jogadores, em qualquer proporção. Nada
limita a altura dela além da energia e da mão dos jogadores.

Quem **iniciou** a pilha — o lançador do feitiço mais antigo dela — precisa ser
conhecido antes de a resolução começar, porque a pilha esvazia durante a
resolução e a informação some junto.

**Why this priority**: responder é o motivo de a pilha existir. Sem a resposta,
empilhar e resolver na hora seriam a mesma coisa.

**Independent Test**: A lança um feitiço, B responde com outro, e conferir que a
pilha tem duas entradas na ordem de lançamento, com o feitiço de B no topo, e
que o lançador registrado em cada entrada é o correto.

**Acceptance Scenarios**:

1. **Given** uma pilha com um feitiço de A, **When** B lança um feitiço, **Then**
   a pilha tem duas entradas e a de B é o topo.
2. **Given** uma pilha com feitiços dos dois jogadores, **When** eu leio as
   entradas, **Then** cada uma registra o `user_id` de quem a lançou.
3. **Given** uma pilha com um feitiço de A no fundo, **When** B responde e os
   dois passam, **Then** quem inicia a pilha é A, e continua sendo A mesmo
   depois de a pilha esvaziar.
4. **Given** um jogador sem prioridade, **When** ele tenta responder, **Then** a
   ação é recusada citando quem tem a prioridade, e a pilha fica como estava.
5. **Given** uma pilha não vazia, **When** um jogador com prioridade joga uma
   unidade em vez de responder, **Then** a jogada é aceita, os passes zeram e a
   pilha continua intacta — jogar unidade não usa a pilha e não a resolve.
6. **Given** três feitiços lançados alternadamente, **When** eu leio a pilha,
   **Then** a ordem preserva o lançamento, com o último no topo.

---

### User Story 3 - Resolver a pilha inteira em LIFO (Priority: P1)

Dispara quando os dois jogadores passam consecutivamente com a pilha não vazia.

A pilha **inteira** resolve de uma vez, do topo para a base, **sem devolver
prioridade entre um feitiço e o seguinte**. Quem conhece outros jogos de carta
espera prioridade entre cada resolução; aqui não existe.

Para cada feitiço, antes de aplicar o efeito, o alvo é revalidado pelo
identificador que a entrada da pilha guardou:

- Alvo ainda em campo → o efeito é aplicado.
- Alvo não está mais em campo → o feitiço **fizzla**: não faz nada.

Nos dois casos a carta vai para o cemitério **do lançador**, não do dono do
alvo.

Feitiço sem alvo nunca fizzla.

Terminada a pilha: a contagem de passes zera, a prioridade volta para o jogador
que **iniciou** a pilha — quem lançou o feitiço mais antigo dela, não o último —
e a partida volta para a Fase de Ação. A rodada **não** acaba junto: os dois
passes que dispararam a resolução foram consumidos por ela.

**Why this priority**: é a §6 inteira, e é o que torna a saída de fase que a
feature 005 escreveu alcançável. Sem ela, uma pilha cheia trava a partida.

**Independent Test**: com dois feitiços na pilha de jogadores diferentes, fazer
os dois passarem e conferir, numa única leitura do resultado, que a pilha está
vazia, que as duas cartas estão nos cemitérios dos respectivos lançadores, que
os efeitos foram aplicados na ordem inversa do lançamento, que os passes estão
em 0, que a prioridade é de quem lançou o feitiço mais antigo, e que a fase é a
Fase de Ação da mesma rodada.

**Acceptance Scenarios**:

1. **Given** uma pilha com um feitiço e passes em 1, **When** o jogador com
   prioridade passa, **Then** a pilha resolve e a partida volta à Fase de Ação
   com a pilha vazia.
2. **Given** uma pilha com feitiços dos dois jogadores, **When** os dois passam,
   **Then** a pilha inteira resolve numa única operação, na ordem inversa do
   lançamento.
3. **Given** uma resolução de pilha, **When** ela termina, **Then** o número da
   rodada é o mesmo de antes — a rodada não fechou.
4. **Given** uma resolução de pilha, **When** ela termina, **Then** a contagem de
   passes é 0 e a prioridade é do lançador do feitiço mais antigo da pilha.
5. **Given** uma pilha em que A lançou primeiro e B respondeu, **When** ela
   resolve, **Then** a prioridade volta para A, não para B.
6. **Given** uma pilha em que o mesmo jogador lançou os dois feitiços, **When**
   ela resolve, **Then** a prioridade volta para ele.
7. **Given** uma resolução de pilha, **When** ela termina, **Then** cada carta
   está no cemitério de quem a lançou.
8. **Given** um feitiço cujo alvo saiu de campo entre o lançamento e a
   resolução, **When** a pilha resolve, **Then** ele não faz nada e vai para o
   cemitério do lançador mesmo assim.
9. **Given** um feitiço sem alvo, **When** a pilha resolve, **Then** ele nunca
   fizzla.
10. **Given** uma resolução de pilha, **When** ela termina, **Then** o chamador
    nunca observou a partida na fase de Resolução de Pilha — ela é fase de
    passagem, como o Upkeep e o Fim de Rodada.
11. **Given** uma pilha resolvida e a partida de volta à Fase de Ação, **When**
    os dois jogadores passam de novo, **Then** aí sim a rodada fecha.
12. **Given** uma resolução de pilha, **When** ela termina, **Then** nenhuma
    energia mudou e ninguém comprou carta.

---

### User Story 4 - O exemplo canônico da §6: fizzle por alvo morto (Priority: P1)

O exemplo que a nota de domínio escreve, e que precisa funcionar exatamente
assim: A lança um buff de vida na unidade X. B responde com um feitiço de dano
mirando X. Os dois passam. A pilha resolve o dano primeiro, X morre, e o buff
fizzla porque X não existe mais.

Isso só funciona se a morte da unidade for verificada **assim que o efeito
termina**, e não no fim da pilha: o feitiço seguinte precisa enxergar o alvo já
morto.

**Why this priority**: é o teste que prova que a revalidação por identificador
é real, e não uma referência disfarçada. Se falhar, a pilha está aplicando
efeito em unidade removida do jogo.

**Independent Test**: montar exatamente o cenário do exemplo, executar os dois
passes, e conferir que X está no cemitério do dono, que o buff não deixou
modificador nenhum em lugar nenhum, e que as duas cartas de feitiço estão nos
cemitérios dos respectivos lançadores.

**Acceptance Scenarios**:

1. **Given** o cenário do exemplo, **When** os dois passam, **Then** X está no
   cemitério do dono dela e não está mais no banco.
2. **Given** o cenário do exemplo, **When** os dois passam, **Then** o buff de
   vida não aplicou modificador nenhum a nenhuma unidade.
3. **Given** o cenário do exemplo, **When** os dois passam, **Then** as duas
   cartas de feitiço estão nos cemitérios dos lançadores.
4. **Given** dois feitiços de dano mirando a mesma unidade, e o de cima já
   bastando para matá-la, **When** a pilha resolve, **Then** o de baixo fizzla.
5. **Given** uma unidade que sobrevive ao feitiço de dano de cima, **When** o
   feitiço de baixo mirando ela resolve, **Then** ele **não** fizzla e o efeito
   é aplicado.
6. **Given** uma unidade morta durante a resolução, **When** eu leio o
   cemitério, **Then** a carta dela foi para o cemitério do **dono da unidade**,
   e não do lançador do feitiço que a matou.

---

### User Story 5 - Os cinco efeitos do MVP (Priority: P1)

O catálogo da feature 001 já declara os cinco, cada um com o tipo de alvo que
aceita e a duração que tem. Esta feature os **executa**; não os redesenha.

**SOMEONE'S SHIELD** — soma 2 à vida da unidade aliada alvo, permanente. Vida
efetiva é o valor do molde mais os modificadores de vida, menos o dano
acumulado. Somar vida **não é curar**: uma unidade danificada fica com mais
vida efetiva, e o dano acumulado continua exatamente onde estava.

**MAGIC BARRIER** — a unidade aliada alvo não recebe nenhum dano até o fim da
rodada. É o primeiro modificador temporário do jogo a existir de verdade: o Fim
de Rodada da feature 005 é quem o remove, e essa varredura passa a ter caso
real.

**SACRIFICIAL FIRE** — o lançador perde 8 de Nexus e todas as unidades dele em
campo ganham 3 de ataque, permanente. A troca é indivisível: o custo em Nexus
acontece mesmo que ele não tenha unidade nenhuma em campo.

**LIFE POTION** — o lançador recupera 5 de Nexus.

**SUMMONED AX** — causa 3 de dano à unidade inimiga alvo. Dano **acumula** na
unidade; ele não reduz vida diretamente. Uma unidade cujo dano acumulado alcança
a vida efetiva morre e vai para o cemitério do dono, verificado assim que o
efeito termina.

Dano em unidade com imunidade ativa não entra.

**Why this priority**: é onde o motor finalmente altera vida, ataque e Nexus.
Sem os efeitos, a pilha resolve o nada.

**Independent Test**: para cada um dos cinco, montar o estado mínimo, resolver
uma pilha com só aquele feitiço, e conferir campo a campo o que a carta
descreve — e conferir também que nada além disso mudou.

**Acceptance Scenarios**:

1. **Given** uma unidade aliada intacta, **When** SOMEONE'S SHIELD resolve nela,
   **Then** a vida efetiva dela sobe 2 e o dano acumulado continua 0.
2. **Given** uma unidade aliada com dano acumulado, **When** SOMEONE'S SHIELD
   resolve nela, **Then** a vida efetiva sobe 2 e o dano acumulado **não** muda —
   somar vida não é curar.
3. **Given** o modificador de vida aplicado, **When** a rodada fecha, **Then**
   ele continua lá — é permanente.
4. **Given** uma unidade aliada, **When** MAGIC BARRIER resolve nela, **Then**
   ela passa a ter imunidade a dano até o fim da rodada.
5. **Given** uma unidade com imunidade ativa, **When** um feitiço de dano
   resolve nela, **Then** o dano acumulado dela não muda e ela não morre.
6. **Given** uma unidade com imunidade ativa, **When** a rodada fecha, **Then**
   a imunidade não está mais lá — a varredura da §8 a removeu.
7. **Given** um lançador com 20 de Nexus e três unidades no banco, **When**
   SACRIFICIAL FIRE resolve, **Then** o Nexus dele é 12 e as três unidades
   ganharam 3 de ataque cada.
8. **Given** um lançador sem nenhuma unidade em campo, **When** SACRIFICIAL FIRE
   resolve, **Then** o Nexus dele cai 8 mesmo assim — a troca é indivisível.
9. **Given** SACRIFICIAL FIRE resolvido, **When** eu leio o banco do oponente,
   **Then** nenhuma unidade dele ganhou ataque.
10. **Given** o bônus de ataque aplicado, **When** a rodada fecha, **Then** ele
    continua lá — é permanente.
11. **Given** um lançador com 10 de Nexus, **When** LIFE POTION resolve, **Then**
    o Nexus dele é 15.
12. **Given** LIFE POTION resolvido, **When** eu leio o Nexus do oponente,
    **Then** ele não mudou.
13. **Given** um lançador com 20 de Nexus, **When** LIFE POTION resolve,
    **Then** o Nexus dele é 25 — o Nexus não tem teto.
14. **Given** um lançador com 18 de Nexus, **When** LIFE POTION resolve,
    **Then** o Nexus dele é 23, e a jogada não foi recusada em nenhum momento
    por o Nexus estar quase cheio.
15. **Given** uma unidade inimiga de vida efetiva 5 e sem dano, **When**
    SUMMONED AX resolve nela, **Then** o dano acumulado dela é 3 e ela continua
    no banco.
16. **Given** uma unidade inimiga de vida efetiva 3, **When** SUMMONED AX resolve
    nela, **Then** o dano acumulado alcança a vida efetiva, ela morre e a carta
    vai para o cemitério do dono.
17. **Given** uma unidade inimiga de vida efetiva 4 já com 2 de dano, **When**
    SUMMONED AX resolve nela, **Then** o dano acumulado é 5, maior que a vida
    efetiva, e ela morre.
18. **Given** uma unidade que recebeu SOMEONE'S SHIELD e depois dano igual à
    vida do molde, **When** o efeito termina, **Then** ela **não** morre — a
    vida efetiva inclui o modificador.

---

### User Story 6 - Aplicar efeito e empilhar são coisas separadas (Priority: P1)

Na Fase de Ação o feitiço é empilhado e só resolve depois. Durante o combate
(§7.2, feature seguinte) o feitiço do defensor resolve **imediatamente**, sem
pilha e sem chance de resposta. É o mesmo efeito, com o mesmo resultado, por um
caminho diferente.

Quem aplica o efeito **não pode saber** de qual dos dois caminhos veio. Se
souber, a feature de combate precisa de uma segunda implementação de cada
efeito — e duas implementações do mesmo efeito divergem.

O que esta feature entrega, então, são duas coisas separáveis: o aplicador de
efeito, que recebe a partida, o lançador, o efeito e o alvo já revalidado; e a
pilha, que decide quando e em que ordem chamá-lo.

**Why this priority**: é a fronteira que decide se a feature de combate é
pequena ou se ela duplica os cinco efeitos. Errar aqui custa na feature
seguinte, não nesta.

**Independent Test**: aplicar cada um dos cinco efeitos diretamente, sem passar
pela pilha, e conferir que o resultado é idêntico ao de resolvê-los pela pilha.

**Acceptance Scenarios**:

1. **Given** um efeito qualquer dos cinco, **When** ele é aplicado direto e
   também via resolução de pilha a partir do mesmo estado inicial, **Then** os
   dois estados resultantes são iguais, exceto pelo que é da pilha — carta no
   cemitério, prioridade, passes e fase.
2. **Given** o aplicador de efeito, **When** eu leio a informação que ele
   recebe, **Then** não existe nada que diga se a chamada veio da pilha ou do
   combate.
3. **Given** a revalidação de alvo, **When** eu procuro onde ela acontece,
   **Then** ela é da pilha, não do aplicador — o aplicador recebe o alvo já
   resolvido.
4. **Given** os cinco efeitos, **When** eu procuro no código onde cada um é
   executado, **Then** existe exatamente um lugar para cada.

---

### User Story 7 - A partida acaba quando um Nexus chega a zero (Priority: P1)

SACRIFICIAL FIRE é o primeiro efeito do jogo que altera Nexus, e ele pode zerar
o Nexus do próprio lançador. Deixar a verificação de vitória para a feature de
combate criaria um estado que nenhuma regra sabe descrever: Nexus em zero e a
partida seguindo.

Então a §10 entra aqui: depois de qualquer evento que altere um Nexus, um
jogador com Nexus em 0 ou menos perde. Os dois em 0 ou menos no mesmo cálculo é
empate.

A partida terminada precisa ser um **estado reconhecível** — quem perdeu, ou que
foi empate — e nenhuma ação é aceita depois disso.

**Why this priority**: é a única saída da partida que existe, e ela passa a ser
alcançável nesta feature. Sem ela o motor produz estado sem regra.

**Independent Test**: com o lançador em 8 de Nexus, resolver SACRIFICIAL FIRE e
conferir que o Nexus dele é 0, que a partida está terminada com ele como
perdedor, e que qualquer ação subsequente dos dois jogadores é recusada.

**Acceptance Scenarios**:

1. **Given** um lançador com 8 de Nexus, **When** SACRIFICIAL FIRE resolve,
   **Then** o Nexus dele é 0 e a partida está terminada com ele derrotado.
2. **Given** um lançador com 5 de Nexus, **When** SACRIFICIAL FIRE resolve,
   **Then** o Nexus dele é -3 e a partida está terminada com ele derrotado.
3. **Given** um lançador com 9 de Nexus, **When** SACRIFICIAL FIRE resolve,
   **Then** o Nexus dele é 1 e a partida continua.
4. **Given** uma partida terminada, **When** qualquer jogador tenta qualquer
   ação, **Then** ela é recusada citando que a partida acabou, e o estado fica
   idêntico.
5. **Given** uma partida terminada, **When** eu leio o estado, **Then** dá para
   saber quem perdeu — ou que foi empate — sem interpretar texto livre.
6. **Given** uma partida terminada, **When** ela vai ao Redis e volta, **Then**
   o estado de partida terminada e o resultado sobrevivem campo a campo.
7. **Given** um efeito que não altera Nexus nenhum, **When** ele resolve,
   **Then** a verificação de vitória não muda nada.
8. **Given** LIFE POTION num jogador com Nexus positivo, **When** ele resolve,
   **Then** a partida continua.
9. **Given** uma pilha em que SACRIFICIAL FIRE está acima de outros feitiços e o
   lançador tem 8 de Nexus, **When** a pilha resolve, **Then** a partida termina
   ali e os feitiços de baixo não são aplicados.
10. **Given** essa mesma pilha, **When** ela para, **Then** as cartas dos
    feitiços não aplicados estão nos cemitérios dos respectivos lançadores e a
    pilha está vazia.
11. **Given** uma pilha com LIFE POTION **abaixo** de um SACRIFICIAL FIRE que
    mata o lançador, **When** ela resolve, **Then** a cura não acontece e o
    lançador continua derrotado — ordem de lançamento é decisão do jogador.
12. **Given** uma pilha com LIFE POTION **acima** de um SACRIFICIAL FIRE do
    mesmo lançador com 8 de Nexus, **When** ela resolve, **Then** a cura resolve
    primeiro, o Nexus fica em 13, o SACRIFICIAL FIRE o leva a 5, e a partida
    continua.

---

### User Story 8 - Recusas de lançamento que nomeiam o ofensor (Priority: P1)

Lançar feitiço é mais uma ação passando pelas **mesmas** guardas da feature
005, na mesma ordem: o autor joga esta partida, o autor tem a prioridade, a
fase atual permite esta ação. Só depois disso a regra específica da §5B.

**Uma jogada ilegal não muda nada.** A recusa deixa o estado exatamente como
estava — não desconta energia, não tira carta da mão, não empilha, não troca
prioridade, não mexe na contagem de passes.

**Toda recusa nomeia o valor ofensor**, e a guarda que falhou é distinguível
sem interpretar texto livre.

**Why this priority**: é a mesma disciplina da feature 005 aplicada a uma ação
com três parâmetros em vez de um. O alvo dobra a superfície de recusa.

**Independent Test**: para cada caso de recusa, capturar o estado inteiro da
partida antes, tentar o lançamento, e comparar campo a campo com o estado
depois; e conferir que a mensagem cita o valor ofensor.

**Acceptance Scenarios**:

1. **Given** um feitiço que não aceita alvo, **When** o jogador o lança com um
   alvo, **Then** a jogada é recusada, e o estado fica idêntico.
2. **Given** um feitiço que exige alvo, **When** o jogador o lança sem alvo,
   **Then** a jogada é recusada citando o tipo de alvo esperado, e o estado fica
   idêntico.
3. **Given** um feitiço de alvo aliado, **When** o jogador mira uma unidade do
   oponente, **Then** a jogada é recusada citando o tipo de alvo esperado, e o
   estado fica idêntico.
4. **Given** um feitiço de alvo inimigo, **When** o jogador mira uma unidade do
   próprio banco, **Then** a jogada é recusada citando o tipo de alvo esperado,
   e o estado fica idêntico.
5. **Given** um alvo que já não está em campo no momento do lançamento, **When**
   o jogador o mira, **Then** a jogada é recusada citando o identificador — isso
   é recusa, não fizzle.
6. **Given** um jogador com 3 de energia e um feitiço de custo 5 na mão, **When**
   ele o lança, **Then** a jogada é recusada citando o custo 5 e a energia 3, e
   o estado fica idêntico.
7. **Given** um jogador que cita uma carta que não está na mão dele, **When** ele
   tenta lançá-la, **Then** a jogada é recusada citando a carta, e o estado fica
   idêntico.
8. **Given** um jogador que cita uma carta de unidade, **When** ele usa a ação de
   lançar feitiço, **Then** a jogada é recusada citando a carta e o tipo dela, e
   o estado fica idêntico.
9. **Given** um jogador sem a prioridade, **When** ele tenta lançar um feitiço,
   **Then** a recusa é a de prioridade, mesmo que o alvo e a energia também
   estejam errados.
10. **Given** uma partida em fase que não é a Fase de Ação, **When** um jogador
    tenta lançar um feitiço, **Then** a jogada é recusada citando a fase.
11. **Given** um lançamento recusado, **When** eu leio o contador de identidade
    de carta e o contador de sorteios da partida, **Then** nenhum dos dois
    avançou.
12. **Given** um lançamento recusado, **When** eu leio a pilha, **Then** ela está
    exatamente como estava.

---

### User Story 9 - Não quebrar 001, 002 e 005 (Priority: P2)

Esta feature consome o que as anteriores entregaram e não as altera.

- **Feature 001.** Os efeitos são lidos do catálogo pelos campos estruturados —
  tipo de alvo, duração, classe do efeito —, nunca pela descrição em português.
- **Feature 002.** Todo estado produzido aqui sobrevive à ida e à volta pelo
  Redis, campo a campo: pilha cheia, modificadores de ataque, de vida e de
  imunidade, dano acumulado, cemitério povoado, e partida terminada.
- **Feature 005.** A alternância, as guardas comuns e a cascata de fases não
  mudam. Lançar feitiço é mais uma ação passando pelas mesmas guardas, na mesma
  ordem. A varredura de modificadores temporários no Fim de Rodada continua
  exatamente a mesma; ela só passa a ter o que varrer.

**Why this priority**: é continuidade, não capacidade nova. Vale como história
porque a regressão aqui é silenciosa.

**Independent Test**: rodar as suítes das features 001, 002 e 005 sem alteração
nenhuma nos testes delas, e conferir que passam.

**Acceptance Scenarios**:

1. **Given** uma partida com a pilha cheia, unidades com os três tipos de
   modificador, dano acumulado e cemitérios povoados, **When** ela vai ao Redis
   e volta, **Then** o estado reconstruído é igual ao original, campo a campo.
2. **Given** uma partida terminada, **When** ela vai ao Redis e volta, **Then**
   o resultado dela é o mesmo.
3. **Given** o código depois desta feature, **When** eu procuro onde a duração
   de um efeito é decidida, **Then** ela vem do campo estruturado do catálogo, e
   nenhuma decisão de regra lê a descrição da carta.
4. **Given** a varredura de modificadores do Fim de Rodada, **When** eu a comparo
   com a que a feature 005 entregou, **Then** a regra é a mesma.
5. **Given** as suítes das features 001, 002 e 005, **When** elas rodam, **Then**
   passam sem alteração.

---

### Edge Cases

**Lançamento**

- **Feitiço sem alvo recebendo um alvo.** Recusa. Um alvo que o efeito não sabe
  usar é jogada mal formada, não parâmetro ignorável.
- **Feitiço com alvo lançado sem alvo.** Recusa citando o tipo de alvo esperado.
- **Feitiço de alvo aliado mirando unidade do oponente, e vice-versa.** Recusa
  citando o tipo de alvo esperado. "Aliado" e "inimigo" são relativos a quem
  lança.
- **Alvo que já não está em campo no momento do lançamento.** Recusa. É
  diferente de fizzle: fizzle é o alvo sumir **entre** o lançamento e a
  resolução.
- **Alvo que é uma carta na mão, no deck ou no cemitério.** Recusa — só unidade
  em banco é alvo.
- **Energia insuficiente.** Recusa citando o custo e a energia disponível.
- **Carta que não está na mão.** Recusa citando a carta.
- **Carta de unidade na ação de lançar feitiço.** Recusa citando a carta e o
  tipo. É a simétrica da recusa que a feature 005 já entrega para a ação de
  jogar unidade com carta de feitiço.
- **Feitiço de custo 0.** Lançável com 0 de energia — a guarda é `>=`.
- **Lançar com a mão em 1 carta.** Aceito; a mão fica vazia e passar continua
  legal.
- **Duas guardas falhando ao mesmo tempo.** Vence a primeira da ordem:
  participante, prioridade, fase, e só então a regra da §5B.

**Pilha e resolução**

- **Pilha com feitiços dos dois jogadores.** Resolve inteira, na ordem inversa
  do lançamento.
- **Pilha com um feitiço só.** Resolve igual; a prioridade volta para o único
  lançador.
- **Pilha em que o mesmo jogador lançou tudo.** A prioridade volta para ele.
- **Dois feitiços mirando a mesma unidade, o de cima matando ela.** O de baixo
  fizzla e vai para o cemitério do lançador sem fazer nada.
- **Feitiço mirando unidade que morreu por um efeito de cima.** Não existe
  "depois" dentro da resolução — ninguém age entre um feitiço e o seguinte. O
  alvo continua sumido e o feitiço fizzla.
- **Todos os feitiços da pilha fizzlando.** A pilha esvazia, as cartas vão para
  os cemitérios, e a partida volta à Fase de Ação normalmente.
- **Resolução que não fecha a rodada.** Os dois passes que dispararam a
  resolução foram consumidos por ela: a contagem volta a 0 e a rodada segue.
- **Dois passes com a pilha vazia depois de uma resolução.** Aí sim a rodada
  fecha, pela §8 que a feature 005 entrega.
- **Prioridade após a resolução.** Vai para quem **iniciou** a pilha, que pode
  não ser quem tinha a prioridade antes do primeiro lançamento e quase nunca é
  quem lançou o último feitiço.

**Efeitos**

- **Dano em unidade protegida por MAGIC BARRIER.** Não entra, e ela não morre.
  O feitiço não fizzla: o alvo está em campo, o efeito foi aplicado, e aplicar
  0 de dano é o resultado correto.
- **MAGIC BARRIER expira no Fim de Rodada; o buff de vida do SOMEONE'S SHIELD
  não.** É a primeira vez que a varredura da §8 tem os dois casos.
- **MAGIC BARRIER numa unidade que já tem imunidade ativa.** Aceito; a unidade
  segue imune e a imunidade expira no mesmo Fim de Rodada.
- **SACRIFICIAL FIRE sem nenhuma unidade em campo.** Perde o Nexus mesmo assim.
- **SACRIFICIAL FIRE com o Nexus do lançador em 8 ou menos.** Ele se derrota.
- **Buff de vida em unidade já danificada.** A vida efetiva sobe, o dano
  acumulado não muda. Somar vida não é curar.
- **Buff de vida em unidade cujo dano acumulado já igualaria a vida do molde.**
  A vida efetiva passa a ser maior que o dano, e ela continua viva.
- **Dano exatamente igual à vida efetiva.** A unidade morre — a regra é o dano
  **alcançar** a vida efetiva.
- **Unidade morta.** Vai para o cemitério do **dono**, com os modificadores e o
  dano dela ficando para trás.

**Vitória**

- **Nexus em exatamente 0.** Derrota. A regra é `<= 0`.
- **Nexus negativo.** Derrota, e o valor negativo é preservado como está.
- **Partida terminada.** Nenhuma ação é aceita, de nenhum dos dois jogadores.
- **Nexus acima de 20.** Estado normal. LIFE POTION não tem teto, e 20 é o valor
  inicial da §12, não um limite.
- **LIFE POTION num jogador já derrotado.** Inalcançável: a resolução para no
  primeiro Nexus a chegar a 0, e nenhuma ação é aceita depois.
- **Partida encerrada no meio da pilha.** Os feitiços restantes não são
  aplicados, as cartas deles vão para os cemitérios dos lançadores, e a pilha
  termina vazia.
- **LIFE POTION abaixo de um SACRIFICIAL FIRE letal na mesma pilha.** Não salva:
  ele resolve depois, e depois não existe. Salvar-se exige lançar a cura por
  cima.

## Requirements *(mandatory)*

### Functional Requirements

**Ação: lançar feitiço (§5B)**

- **FR-001**: O sistema MUST aceitar "lançar feitiço" como a terceira ação da
  Fase de Ação, com a mesma forma de ação e as mesmas guardas comuns que a
  feature 005 entregou, na mesma ordem.
- **FR-002**: A ação MUST carregar o autor, a carta citada, e o alvo — que MUST
  poder ser ausente.
- **FR-003**: A ação MUST exigir que a carta citada esteja na mão do autor.
- **FR-004**: A ação MUST exigir que a carta citada seja um feitiço.
- **FR-005**: A ação MUST exigir energia atual maior ou igual ao custo da carta.
- **FR-006**: A ação MUST exigir alvo quando o efeito declarar que exige, e MUST
  recusar alvo quando o efeito declarar que não aceita.
- **FR-007**: Um alvo de tipo "unidade aliada" MUST ser uma unidade no banco do
  **lançador**; um de tipo "unidade inimiga" MUST ser uma unidade no banco do
  **oponente do lançador**.
- **FR-008**: Um alvo que não está em campo no momento do lançamento MUST ser
  recusado. Essa recusa MUST ser distinguível do fizzle.
- **FR-009**: Aceita, a ação MUST descontar o custo da energia atual, tirar a
  carta da mão e pôr o feitiço no **topo** da pilha.
- **FR-010**: A ação MUST NOT aplicar o efeito. Nenhum Nexus, modificador, dano,
  banco ou cemitério MUST mudar no lançamento.
- **FR-011**: A ação MUST zerar a contagem de passes.
- **FR-012**: A ação MUST passar a prioridade ao oponente, como toda ação da §5.
- **FR-013**: A entrada da pilha MUST guardar o identificador do alvo, nunca uma
  referência à unidade.
- **FR-014**: A ordem da pilha MUST preservar a ordem de lançamento, com o
  último lançado no topo.
- **FR-015**: A decisão sobre exigência de alvo, tipo de alvo e duração MUST vir
  dos campos estruturados do catálogo. Nenhuma decisão de regra MUST ler a
  descrição em português da carta.

**Resolução da pilha (§6)**

- **FR-016**: A Resolução de Pilha MUST disparar quando os dois jogadores
  passarem consecutivamente com a pilha não vazia — a saída de fase que a
  feature 005 já escreveu.
- **FR-017**: A pilha **inteira** MUST resolver numa única passagem, do topo
  para a base.
- **FR-018**: A prioridade MUST NOT ser devolvida a ninguém entre a resolução de
  um feitiço e a do seguinte.
- **FR-019**: Antes de aplicar cada efeito, o alvo MUST ser revalidado pelo
  identificador guardado na entrada.
- **FR-020**: Alvo ainda em campo MUST levar à aplicação do efeito.
- **FR-021**: Alvo que não está mais em campo MUST fazer o feitiço fizzlar: nada
  é aplicado.
- **FR-022**: Feitiço sem alvo MUST NOT fizzlar nunca.
- **FR-023**: Resolvido ou fizzlado, o feitiço MUST ir para o cemitério do
  **lançador**.
- **FR-024**: Quem iniciou a pilha — o lançador do feitiço mais antigo — MUST ser
  conhecido antes de a primeira entrada sair, e MUST sobreviver ao esvaziamento.
- **FR-025**: Terminada a pilha, a contagem de passes MUST ser 0, a prioridade
  MUST ser de quem iniciou a pilha, e a fase MUST ser a Fase de Ação.
- **FR-026**: A resolução MUST NOT fechar a rodada. O número da rodada MUST ser
  o mesmo antes e depois.
- **FR-027**: A Resolução de Pilha MUST ser fase de passagem: o chamador MUST
  NOT observá-la como resultado de uma ação, pela mesma cascata da feature 005.
- **FR-028**: A resolução MUST NOT alterar energia nem fazer ninguém comprar
  carta.

**Aplicação de efeito**

- **FR-029**: O aplicador de efeito MUST receber a partida, o lançador, o efeito
  e o alvo já revalidado, e MUST NOT receber nem inferir por qual caminho a
  chamada chegou.
- **FR-030**: A revalidação de alvo MUST ser da pilha, não do aplicador.
- **FR-031**: Cada um dos cinco efeitos MUST ter exatamente uma implementação no
  código.
- **FR-032**: A união de efeitos MUST ser tratada de forma fechada: um efeito
  novo sem execução escrita MUST ser erro de tipagem, não comportamento ausente
  em produção.

**Os cinco efeitos**

- **FR-033**: SOMEONE'S SHIELD MUST somar 2 à vida da unidade aliada alvo, de
  forma permanente.
- **FR-034**: A vida de uma unidade MUST ser lida como duas quantidades
  nomeadas, para que "vida efetiva" não signifique duas coisas: a **vida
  máxima** é o valor do molde mais a soma dos modificadores de vida; a **vida
  restante** é a máxima menos o dano acumulado.
- **FR-035**: Somar vida MUST NOT alterar o dano acumulado. A máxima sobe, a
  restante sobe junto, e o dano fica onde estava.
- **FR-036**: MAGIC BARRIER MUST dar à unidade aliada alvo imunidade a dano até
  o fim da rodada.
- **FR-037**: Dano dirigido a uma unidade com imunidade ativa MUST NOT ser
  acumulado, e a unidade MUST NOT morrer por ele.
- **FR-038**: SACRIFICIAL FIRE MUST subtrair 8 do Nexus do lançador e somar 3 ao
  ataque de **todas** as unidades dele em campo, de forma permanente.
- **FR-039**: SACRIFICIAL FIRE MUST cobrar o Nexus mesmo quando o lançador não
  tem unidade nenhuma em campo. A troca MUST ser indivisível.
- **FR-040**: SACRIFICIAL FIRE MUST NOT alterar as unidades do oponente.
- **FR-041**: LIFE POTION MUST somar 5 ao Nexus do lançador.
- **FR-042**: SUMMONED AX MUST somar 3 ao dano acumulado da unidade inimiga
  alvo.
- **FR-043**: Dano MUST acumular na unidade e MUST NOT reduzir vida diretamente.
- **FR-044**: Uma unidade cujo dano acumulado alcança ou ultrapassa a vida
  **máxima** MUST morrer e ir para o cemitério do **dono** dela. É a mesma
  condição que "vida restante menor ou igual a 0" — as duas formas MUST
  concordar sempre.
- **FR-045**: A morte MUST ser verificada assim que o efeito termina, e MUST NOT
  ser adiada para o fim da pilha.
- **FR-046**: Os modificadores e o dano de uma unidade morta MUST ficar para
  trás quando a carta vai para o cemitério.
- **FR-047**: O bônus de ataque, o bônus de vida e a imunidade MUST ser criados
  com a duração que o efeito declara, para que a varredura da §8 os trate sem
  regra nova.

**Vitória (§10)**

- **FR-048**: Depois de qualquer evento que altere um Nexus, o sistema MUST
  verificar a condição de vitória.
- **FR-049**: Um jogador com Nexus menor ou igual a 0 MUST perder.
- **FR-050**: Os dois jogadores com Nexus menor ou igual a 0 no mesmo cálculo
  MUST resultar em empate.
- **FR-051**: A partida terminada MUST ser um estado reconhecível no próprio
  estado da partida, com o resultado — quem perdeu, ou empate — legível sem
  interpretar texto livre.
- **FR-052**: Nenhuma ação de jogador MUST ser aceita numa partida terminada. A
  recusa MUST citar que a partida acabou.
- **FR-053**: O valor do Nexus MUST ser preservado como ficou, inclusive
  negativo. Ele MUST NOT ser fixado em 0.
- **FR-054**: O Nexus MUST NOT ter teto superior. LIFE POTION MUST somar 5
  mesmo com o Nexus em 20 ou mais, e a jogada MUST NOT ser recusada por isso. O
  valor 20 da §12 é o Nexus **inicial**, não um limite.
- **FR-055**: Assim que a verificação da §10 encontrar um Nexus menor ou igual a
  0, a resolução da pilha MUST parar. Nenhum efeito restante MUST ser aplicado.
- **FR-055a**: As entradas restantes da pilha MUST ir para os cemitérios dos
  respectivos lançadores sem efeito, e a pilha MUST terminar vazia.
- **FR-055b**: Numa partida encerrada no meio da resolução, a prioridade e a
  contagem de passes MUST NOT ser relevantes para nenhuma ação futura, porque
  nenhuma ação é aceita — mas o estado MUST continuar íntegro e serializável.

**Recusa**

- **FR-056**: Um lançamento recusado MUST deixar o estado da partida exatamente
  como estava, campo a campo, em qualquer ponto de falha.
- **FR-057**: Um lançamento recusado MUST NOT descontar energia, mover carta,
  empilhar, trocar prioridade, alterar a contagem de passes nem mudar a fase.
- **FR-058**: Um lançamento recusado MUST NOT avançar o contador de identidade
  de carta nem o contador de sorteios da partida.
- **FR-059**: Toda recusa MUST nomear o valor ofensor: o custo contra a energia
  disponível, a carta pedida, o tipo de carta, o identificador do alvo, o tipo
  de alvo esperado, ou quem tem a prioridade — conforme a guarda que falhou.
- **FR-060**: A recusa MUST identificar qual guarda falhou, de forma que o
  cliente possa distinguir os casos sem interpretar texto livre.

**Fronteiras**

- **FR-061**: Esta feature MUST NOT alterar a alternância, as guardas comuns nem
  a cascata de fases da feature 005.
- **FR-062**: Esta feature MUST NOT alterar a varredura de modificadores
  temporários do Fim de Rodada.
- **FR-063**: Esta feature MUST NOT implementar declarar ataque, bloqueio nem
  dano de combate.
- **FR-064**: Esta feature MUST NOT implementar o caminho de feitiço imediato do
  combate, mas MUST entregar o aplicador de efeito que ele vai usar.
- **FR-065**: Qualquer estado produzido por esta feature MUST sobreviver à ida e
  à volta pelo Redis com igualdade campo a campo — pilha, modificadores, dano
  acumulado, cemitério e partida terminada inclusive.
- **FR-066**: Esta feature MUST NOT gravar no Redis. Quem grava é o chamador,
  pelo caminho que a feature 003 entregou.

### Key Entities

- **Lançamento de feitiço**: a ação da §5B. Carrega o autor, a carta da mão, e
  um alvo que pode ser ausente. É o terceiro braço da união de ações que a
  feature 005 definiu.
- **Entrada da pilha**: um feitiço lançado e ainda não resolvido. Guarda a
  carta, quem a lançou, e o **identificador** do alvo — nunca a unidade. Já
  existe no estado da feature 002; esta feature passa a produzi-la e consumi-la.
- **Iniciador da pilha**: o lançador do feitiço mais antigo da pilha. É para
  quem a prioridade volta ao fim da resolução, e precisa ser lido antes de a
  pilha esvaziar.
- **Fizzle**: a resolução de um feitiço cujo alvo não está mais em campo. Não
  aplica nada, e ainda assim manda a carta ao cemitério do lançador.
- **Aplicador de efeito**: executa um dos cinco efeitos sobre a partida. Não
  sabe se foi chamado pela pilha ou pelo combate, e é isso que impede a feature
  seguinte de reimplementar os cinco.
- **Vida efetiva**: o valor do molde mais os modificadores de vida, menos o dano
  acumulado. Não é campo; é conta.
- **Dano acumulado**: quanto a unidade já levou. Não é modificador: não expira,
  e a varredura da §8 não o toca.
- **Modificador de unidade**: alteração com duração — ataque, vida ou imunidade
  a dano. A feature 002 já os representa; esta é a primeira a criá-los.
- **Resultado da partida**: quem perdeu, ou empate. Só existe depois que um
  Nexus chega a 0, e sobrevive ao Redis.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Um feitiço lançado desconta a energia exata do custo, sai da mão,
  e fica na pilha sem ter alterado nenhum Nexus, nenhum modificador, nenhum dano
  e nenhum cemitério.
- **SC-002**: O oponente consegue responder no topo da pilha, e a pilha
  resultante tem as duas entradas na ordem de lançamento.
- **SC-003**: Dois passes consecutivos com a pilha não vazia resolvem a pilha
  inteira numa única resposta, de cima para baixo, sem que o chamador observe a
  fase de Resolução de Pilha.
- **SC-004**: O exemplo canônico da §6 — buff de vida em X, dano em X por cima,
  os dois passam — termina com X no cemitério do dono, o buff sem efeito nenhum,
  e as duas cartas nos cemitérios dos lançadores.
- **SC-005**: Em 100% das resoluções, cada carta de feitiço termina no cemitério
  do lançador, tenha ela resolvido ou fizzlado.
- **SC-006**: Terminada a resolução, a prioridade é de quem lançou o feitiço mais
  antigo da pilha, os passes estão em 0, a fase é a Fase de Ação, e o número da
  rodada é o mesmo de antes.
- **SC-007**: Os cinco efeitos produzem exatamente o que a carta descreve, e
  nada além disso: em cada teste, todo campo do estado que a carta não menciona
  está idêntico ao de antes.
- **SC-008**: Uma unidade protegida por MAGIC BARRIER não acumula dano nenhum e
  não morre, e no Fim de Rodada seguinte deixa de estar protegida.
- **SC-009**: Um modificador de vida de SOMEONE'S SHIELD e um bônus de ataque de
  SACRIFICIAL FIRE continuam na unidade depois do Fim de Rodada.
- **SC-010**: SACRIFICIAL FIRE lançado por um jogador sem nenhuma unidade em
  campo custa os 8 de Nexus mesmo assim.
- **SC-011**: Um Nexus que chega a 0 ou menos encerra a partida num estado
  reconhecível, e as ações seguintes dos **dois** jogadores são recusadas.
- **SC-011a**: Uma pilha em que a partida termina no meio para ali: nenhum
  efeito abaixo é aplicado, todas as cartas restantes vão para os cemitérios dos
  lançadores, e a pilha termina vazia.
- **SC-011b**: LIFE POTION resolvido num jogador com 20 de Nexus o leva a 25 —
  não existe teto.
- **SC-012**: Em 100% dos casos de recusa listados nos Edge Cases, o estado da
  partida depois é idêntico ao estado antes, campo a campo — contadores
  inclusive.
- **SC-013**: Em 100% dos casos de recusa, a mensagem cita o valor ofensor, e a
  guarda que falhou é identificável sem interpretar texto livre.
- **SC-014**: Cada um dos cinco efeitos produz o mesmo resultado aplicado direto
  e aplicado via pilha, a partir do mesmo estado inicial.
- **SC-015**: Existe exatamente 1 lugar no código onde cada um dos cinco efeitos
  é executado.
- **SC-016**: Qualquer estado produzido por esta feature volta idêntico do
  Redis, campo a campo, partida terminada inclusive.
- **SC-017**: As suítes das features 001, 002 e 005 passam. Os únicos testes
  delas que podem mudar são os que **inventariam** o que o motor tem — a lista
  de fases da partida e a costura da Resolução de Pilha —, porque esta feature
  acrescenta uma fase e dá corpo à outra. Nenhum teste de **regra** das três
  features é alterado.
- **SC-018**: Nenhuma decisão de regra desta feature lê a descrição em português
  de uma carta.

## Assumptions

- **A ação de lançar feitiço entra como um braço novo** da união de ações da
  feature 005, sem que a guarda comum nem a porta de entrada mudem de forma. Foi
  para isso que a feature 005 as escreveu como escreveu.
- **A recusa é levantada, não devolvida como valor**, como toda jogada ilegal do
  motor desde a feature 003.
- **A ordem das checagens específicas do lançamento** é: carta na mão → carta é
  feitiço → energia suficiente → alvo compatível com o efeito. A carta precisa
  ser resolvida antes de se poder citar o custo dela na recusa, e o efeito
  precisa ser conhecido antes de se poder validar o alvo.
- **A Resolução de Pilha entra na cascata da feature 005** como mais uma fase
  automática, do mesmo jeito que o Fim de Rodada e o Upkeep. A feature 005
  deixou a fase fora do conjunto de fases automáticas exatamente porque o corpo
  dela não existia; agora existe.
- **O estado de partida terminada é campo do estado da partida**, não exceção
  nem valor de retorno. Ele precisa sobreviver ao Redis e ser lido por qualquer
  worker, e a §10 o descreve como estado.
- **A verificação de vitória acontece dentro do aplicador de efeito**, junto do
  evento que alterou o Nexus, e não como um passo separado no fim da pilha. É o
  que a §10 pede — "depois de qualquer evento que altere um Nexus" — e é o que
  faz a feature de combate herdá-la de graça.
- **A morte de unidade é verificada dentro do aplicador de efeito**, pelo mesmo
  motivo: o feitiço seguinte da pilha precisa enxergar o alvo já morto.
- **A vida efetiva é conta, não campo.** Guardar vida absoluta obrigaria a
  desfazer na mão a expiração de um buff temporário, e o resultado passaria a
  depender da ordem dos eventos. O estado da feature 002 já registra essa
  decisão.
- **O alvo é sempre uma unidade em banco.** Nenhum dos cinco efeitos do MVP mira
  jogador, carta na mão ou carta no cemitério, e o conjunto de tipos de alvo do
  catálogo é fechado nesses três valores.
- **Um feitiço aplicado a alvo imune não fizzla.** O alvo está em campo, o
  efeito foi aplicado, e aplicar 0 de dano é o resultado correto. Fizzle é sobre
  o alvo existir, não sobre o efeito surtir.
- **O Nexus não tem teto superior**, e por isso não existe constante de "Nexus
  máximo". O 20 da §12 é valor inicial e mora onde já mora, com o estado do
  jogador.
- **A parada da resolução por partida terminada é da pilha, não do aplicador.**
  O aplicador aplica o efeito e verifica a §10; quem decide não chamar o
  próximo é o laço da pilha. Assim o caminho imediato do combate herda a
  verificação de vitória sem herdar uma regra de pilha que ele não tem.
- **A operação recebe a partida e devolve a partida.** Ela não lê nem grava no
  Redis; quem grava é o chamador.

## Out of Scope

- **Declarar ataque, bloqueio e dano de combate (§7).**
- **Feitiço resolvendo imediatamente dentro do combate.** O caminho é da feature
  de combate; o aplicador de efeito que ela vai usar é desta.
- **Cartas e efeitos além dos cinco do MVP.**
- **Envelope de mensagem e broadcast no websocket.** Esta feature recebe uma
  ação e devolve o estado novo; quem fala com o cliente é outra camada.
- **Timeout de jogada.** Continua em aberto na §13 do Fluxo de Partida, e
  continua sendo problema de transporte.
- **Persistência.** Gravar a partida no Redis é do chamador.
- **O que acontece com a partida depois de terminada** — rematch, ranking,
  registro de resultado. Esta feature entrega o estado terminal, não o que se
  faz com ele.
