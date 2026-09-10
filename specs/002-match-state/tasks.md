---

description: "Task list for 002-match-state"
---

# Tasks: Estado de Partida

**Input**: Design documents from `specs/002-match-state/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md),
[research.md](./research.md), [data-model.md](./data-model.md),
[contracts/match_state.md](./contracts/match_state.md),
[quickstart.md](./quickstart.md)

**Tests**: incluídos e obrigatórios. Não é preferência de estilo — o princípio
V da constituição exige teste para toda função nova, e o SC-009 da spec põe
`pytest` como porta de conclusão.

**Organization**: agrupadas por história de usuário, na ordem de prioridade da
spec.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivo diferente, sem dependência pendente)
- **[Story]**: a que história pertence (US1 a US7)
- Todo caminho de arquivo é relativo à raiz do repositório

## Estratégia de corte

Esta feature substitui um módulo em uso por seis chamadores. A ordem abaixo é
**aditiva até a Fase 9**: todo módulo novo entra em arquivo novo, ninguém
importa dele ainda, e `models.py` continua de pé. A suíte fica verde do começo
ao fim de cada fase.

A troca acontece de uma vez na Fase 9 (US7), que é onde os imports viram,
`models.py` morre e `test_match_model.py` sai. É a única fase em que a suíte
fica vermelha no meio, e é curta de propósito.

Consequência prática: **não pule a Fase 9**. Parar antes dela deixa dois
modelos de partida no repositório.

---

## Phase 1: Setup

**Purpose**: linha de base e esqueleto de arquivos, para que as fases seguintes
sejam edição pura e o `[P]` seja seguro.

- [X] T001 Rodar as três portas e registrar a linha de base verde: `cd server && pytest`, `cd server && mypy`, `cd server && black --check .`
- [X] T002 Criar os oito módulos vazios em `server/apps/game/match/`: `cards_in_play.py`, `modifiers.py`, `spell_stack.py`, `player_state.py`, `match_state.py`, `documents.py`, `serialization.py`, `player_view.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: os tipos folha que toda história consome. Nada aqui é importado
por código existente, então a suíte continua verde.

**⚠️ CRITICAL**: nenhuma história começa antes desta fase fechar.

- [X] T003 [P] Implementar `ModifierKind`, `AttackModifier`, `HealthModifier`, `DamageImmunity` e a união `UnitModifier` em `server/apps/game/match/modifiers.py`, reaproveitando `EffectDuration` de `apps.game.cards` (data-model "Modificadores"; research D5)
- [X] T004 [P] Implementar `CardInstanceId` (`NewType` sobre `int`), `MatchCard` e `BankUnit` em `server/apps/game/match/cards_in_play.py`, com `BankUnit` **contendo** um `MatchCard` e não copiando seus campos (research D2)
- [X] T005 Implementar `StackEntry` em `server/apps/game/match/spell_stack.py`, com `target_card_instance_id: CardInstanceId | None` (depende de T004)
- [X] T006 Implementar `PlayerState` em `server/apps/game/match/player_state.py`, com `user_id` como propriedade derivada de `profile`, não campo próprio (depende de T004)
- [X] T007 Implementar `MatchPhase` (as cinco fases da §2), `NotAParticipantError` e o dataclass `Match` com todos os campos em `server/apps/game/match/match_state.py` — sem métodos ainda (depende de T005, T006)
- [X] T008 Escrever a superfície pública inicial em `server/apps/game/match/__init__.py`, com `__all__` explícito, exportando o que existe até aqui (necessário porque `mypy.ini` roda com `strict`, que liga `no_implicit_reexport`)

**Checkpoint**: os tipos existem e o `mypy` passa. Nada de comportamento ainda.

---

## Phase 3: User Story 1 — Representar uma partida viva completa (Priority: P1) 🎯 MVP

**Goal**: um `Match` que carrega todos os campos da §2 e sabe quem joga.

**Independent Test**: montar uma partida com dois jogadores e conferir, campo a
campo, que os campos da §2 estão lá com os valores iniciais corretos; buscar
cada jogador pelo `user_id` e conferir que um `user_id` de fora é recusado com
o valor na mensagem.

### Implementation for User Story 1

- [X] T009 [US1] Implementar `Match.start(player1, player2)` em `server/apps/game/match/match_state.py` com os valores iniciais de research D10, incluindo o comentário que aponta a §3 no dono do token determinístico
- [X] T010 [US1] Implementar `has_player`, `player` e `opponent_of` em `server/apps/game/match/match_state.py`, transplantando o docstring e o `>>>` de `has_player` do `models.py` antigo (research D9)
- [X] T011 [P] [US1] Criar `server/apps/game/tests/fake_match_state.py` com `fake_new_match()`, no formato de `fake_player_data.py`
- [X] T012 [US1] Escrever `server/apps/game/tests/test_match_state.py`: campos iniciais, as cinco fases, busca de jogador, recusa citando o `user_id`, `has_player(None)` é `False`

**Checkpoint**: US1 funciona e é testável sozinha. `models.py` continua intacto.

---

## Phase 4: User Story 2 — Identidade própria de cada carta (Priority: P1)

**Goal**: cunhar identificadores únicos na partida, opacos, que atravessam
zona sem mudar.

**Independent Test**: duas cópias do mesmo `card_id` recebem números
diferentes; o número de uma delas é o mesmo depois de passar por deck, mão,
banco, pilha e cemitério; juntando os identificadores dos dois jogadores não há
repetição.

### Implementation for User Story 2

- [X] T013 [US2] Implementar `Match.mint_card_instance_id()` em `server/apps/game/match/match_state.py`, devolvendo `next_card_instance_id` e incrementando, com o comentário de por que o contador é campo do estado e não do processo (research D1)
- [X] T014 [US2] Escrever `server/apps/game/tests/test_card_instance_identity.py`: cópias distinguíveis, identificador estável nas cinco zonas, nenhuma repetição entre os dois jogadores, o contador avança

**Checkpoint**: US1 e US2 funcionam de forma independente.

---

## Phase 5: User Story 3 — Ida e volta pelo Redis (Priority: P1)

**Goal**: o estado inteiro vira JSON e volta idêntico, sem chave de objeto
indexada por `user_id`.

**Independent Test**: serializar um estado com todas as zonas cheias, dano,
modificadores das duas durações e pilha com dois feitiços; passar por
`json.dumps`/`json.loads`; desserializar e comparar com o original.

### Implementation for User Story 3

- [X] T015 [P] [US3] Declarar os `TypedDict` da forma gravada em `server/apps/game/match/documents.py`: `CardDocument`, `ModifierDocument`, `BankUnitDocument`, `StackEntryDocument`, `PlayerDocument`, `MatchDocument`, adaptando para cá o comentário do `MatchState` antigo sobre chave de objeto JSON ser sempre string (research D9)
- [X] T016 [US3] Implementar em `server/apps/game/match/serialization.py` a ida e volta de carta, modificador, unidade de banco e entrada de pilha, com `match`/`case` exaustivo sobre `modifier_kind` (depende de T015)
- [X] T017 [US3] Implementar `to_match_document` e `match_from_document` em `server/apps/game/match/serialization.py` e exportá-las em `server/apps/game/match/__init__.py` (depende de T016)
- [X] T018 [US3] Acrescentar `fake_match_in_progress()` a `server/apps/game/tests/fake_match_state.py`: zonas cheias, dano acumulado, modificadores das duas durações, pilha com dois feitiços
- [X] T019 [US3] Escrever `server/apps/game/tests/test_match_serialization.py`: ida e volta idêntica, ordem de deck e de pilha preservadas, zona vazia volta vazia, e a inspeção que afirma que nenhuma chave de objeto JSON é um `user_id` em nenhum nível

**Checkpoint**: as três histórias P1 estão de pé. `store.py` ainda usa o modelo
antigo — a troca é a Fase 9.

---

## Phase 6: User Story 4 — Dano e modificadores na unidade do banco (Priority: P2)

**Goal**: provar que a instância carrega o que diverge do molde e nada mais, e
que o molde nunca é tocado.

**Independent Test**: acumular dano numa das duas instâncias do mesmo `card_id`
e conferir que a outra e o molde do catálogo não mudam; adicionar modificadores
das duas durações e conferir que dá para separar os grupos.

### Implementation for User Story 4

- [X] T020 [US4] Documentar em `server/apps/game/match/cards_in_play.py` os movimentos de zona como exemplo no docstring de `BankUnit` (`bank.append(BankUnit(card=hand.pop(i), ...))` e `graveyard.append(unit.card)`), que é o que torna FR-012 verdade por construção
- [X] T021 [US4] Escrever `server/apps/game/tests/test_bank_unit.py`: dano isolado por instância, molde do catálogo intacto, separação por duração, modificadores de ataque de sinais opostos coexistindo, e a asserção de que `MatchCard` não tem onde guardar dano

**Checkpoint**: US4 funciona sozinha.

---

## Phase 7: User Story 5 — Pilha e revalidação de alvo (Priority: P2)

**Goal**: a pilha guarda o alvo como número e o estado responde se aquele
número ainda está em campo.

**Independent Test**: empilhar dois feitiços e conferir a ordem LIFO; consultar
um identificador presente no banco e outro ausente; mover a unidade alvo para o
cemitério e conferir que a resposta vira negativa.

### Implementation for User Story 5

- [X] T022 [US5] Implementar `Match.bank_unit(card_instance_id) -> BankUnit | None` em `server/apps/game/match/match_state.py`, varrendo os dois bancos, com o comentário de por que devolve `None` em vez de levantar, ao contrário de `player()` (research D6)
- [X] T023 [US5] Escrever `server/apps/game/tests/test_spell_stack.py`: ordem LIFO, entrada com alvo e sem alvo, alvo presente devolve a unidade, alvo ausente devolve `None`, alvo que foi para o cemitério devolve `None`, e a distinção entre `target_card_instance_id is None` e alvo que sumiu

**Checkpoint**: a pergunta que autoriza o fizzle da §6 está respondida.

---

## Phase 8: User Story 6 — Visão de cada jogador (Priority: P2)

**Goal**: o recorte que um `user_id` pode receber, com a ocultação imposta pelo
tipo e não por checagem.

**Independent Test**: montar um estado com mãos e decks conhecidos e distintos,
gerar a visão dos dois jogadores e conferir, em cada uma, o que aparece e o que
não aparece.

### Implementation for User Story 6

- [X] T024 [US6] Declarar `PlayerSideView`, `OpponentSideView` e `PlayerView` em `server/apps/game/match/player_view.py`, com `OpponentSideView` **sem** campo `hand` e nenhum dos dois com conteúdo de deck (research D8)
- [X] T025 [US6] Implementar `build_player_view(match, user_id)` em `server/apps/game/match/player_view.py`, reaproveitando `Match.player()` para a recusa, e exportá-la em `server/apps/game/match/__init__.py` (depende de T024)
- [X] T026 [US6] Escrever `server/apps/game/tests/test_player_view.py`: própria mão com identificadores, mão do oponente só como contagem, nenhum identificador de deck na estrutura serializada, todos os campos compartilhados presentes, e `NotAParticipantError` citando o `user_id` de fora

**Checkpoint**: todas as histórias P1 e P2 estão de pé.

---

## Phase 9: User Story 7 — Cutover: não quebrar quem já depende da partida (Priority: P3)

**Goal**: trocar o modelo antigo pelo novo em todos os chamadores e apagar
`models.py`.

**⚠️ Esta é a única fase em que a suíte fica vermelha no meio.** Faça T027 a
T033 como um bloco, sem parar no meio.

**Independent Test**: parear dois jogadores pelo caminho existente, gravar no
Redis, reler, e conferir que os dois passam no gate de participante, que um
terceiro `user_id` não passa, e que apelido, ícone e nível continuam lá.

### Implementation for User Story 7

- [X] T027 [US7] Trocar `server/apps/game/match/store.py` para `to_match_document(match)` e `match_from_document(...)`, mantendo o `cast` e as assinaturas de `create`, `get` e `save` inalteradas
- [X] T028 [P] [US7] Trocar o import em `server/apps/game/consumers/match.py` para `from apps.game.match import Match`
- [X] T029 [P] [US7] Trocar o import em `server/apps/game/consumers/matchmaking.py` para `from apps.game.match import Match`
- [X] T030 [P] [US7] Trocar o import em `server/apps/game/tests/fake_match_store.py` e conferir que a superfície continua igual à de `MatchStore`
- [X] T031 [P] [US7] Trocar o import em `server/apps/game/tests/test_match_consumer_access.py`
- [X] T032 [US7] Reescrever `server/apps/game/tests/test_match_store.py` contra o estado novo, preservando a intenção de cada asserção: `hands` com chave inteira vira "nenhuma chave de objeto JSON é `user_id`", e `get_state_for_player` vira `build_player_view`; acrescentar que apelido, ícone e nível sobrevivem à volta
- [X] T033 [US7] Apagar `server/apps/game/match/models.py` e `server/apps/game/tests/test_match_model.py` — `play_card` é apagado, não migrado (FR-042), e a cobertura do modelo antigo já foi substituída por `test_match_state.py`

**Checkpoint**: um único modelo de partida no repositório, suíte verde.

---

## Phase 10: Polish & Cross-Cutting Concerns

- [X] T034 Fechar `server/apps/game/match/__init__.py`: `__all__` completo, na ordem do contrato, com o docstring de pacote explicando por que a lista é explícita
- [X] T035 [P] Conferir que nada sobrou: `grep -rn "match.models\|play_card\|CardId = str\|board_state" server/apps/` sem resultado fora de `consumers/base.py` (o roteamento de `play_card` lá é anterior e fica)
- [X] T036 [P] Conferir os limites da constituição nos arquivos novos: funções de 4 a 20 linhas, arquivos abaixo de 500, nenhum campo `id` nu
- [X] T037 Rodar os seis cenários de [quickstart.md](./quickstart.md) e conferir os resultados esperados
- [ ] T038 Rodar as três portas: `cd server && pytest`, `cd server && mypy`, `cd server && black --check .`
  - `mypy` verde (93 arquivos) e `black --check` limpo (94 arquivos).
  - `pytest`: 165 passam, 20 dão erro de conexão com `anathema_redis:6379`.
    Os 20 são os de `test_match_store.py` e `test_matchmaking_queue.py`, que
    exigem Redis de pé; `REDIS_URL` aponta para o nome do container
    (`core/settings.py:66`) e o Docker Desktop não estava rodando. Sete deles
    já erravam antes desta feature. **Falta rodar com o Redis de pé.**
- [X] T039 Fechar o item "`CardId` duplicado no app `game`" em `Backend/TODO.md` no vault — esta feature o resolve

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Fase 1)**: sem dependência
- **Foundational (Fase 2)**: depende da Fase 1 — **bloqueia todas as histórias**
- **US1 (Fase 3)**: depende da Fase 2
- **US2 (Fase 4)**: depende de US1 (`mint_card_instance_id` é método do `Match`)
- **US3 (Fase 5)**: depende de US1 e US2 (serializa o contador e os identificadores)
- **US4 (Fase 6)**: depende da Fase 2; independente de US3
- **US5 (Fase 7)**: depende de US1 (`bank_unit` é método do `Match`)
- **US6 (Fase 8)**: depende de US1 e US3 (a visão reaproveita os documentos)
- **US7 (Fase 9)**: depende de US1, US3 e US6 — é o cutover
- **Polish (Fase 10)**: depende da Fase 9

### Ordem real recomendada

Sequencial, na ordem numerada. As dependências acima quase encadeiam tudo:
`Match` é o agregado, e cinco das sete histórias acrescentam um método a ele.
Isso não é acoplamento acidental — é a natureza de uma feature cujo entregável
é um modelo de dados.

### Paralelismo de verdade

Existe, mas é curto. Onde vale:

- **Fase 2**: T003 e T004 são arquivos diferentes sem dependência entre si.
- **Fase 9**: T028 a T031 são quatro trocas de import em quatro arquivos.
- **Fase 10**: T035 e T036 são conferências que não escrevem nada.

Fora disso, dois pares independentes: US4 (Fase 6) pode rodar em paralelo com
US3 (Fase 5), e US5 (Fase 7) com US4 — ambos só dependem da Fase 2 e de US1.

```bash
# Fase 2, em paralelo:
Task: "Implementar modifiers.py em server/apps/game/match/modifiers.py"
Task: "Implementar cards_in_play.py em server/apps/game/match/cards_in_play.py"

# Fase 9, em paralelo:
Task: "Trocar o import em server/apps/game/consumers/match.py"
Task: "Trocar o import em server/apps/game/consumers/matchmaking.py"
Task: "Trocar o import em server/apps/game/tests/fake_match_store.py"
Task: "Trocar o import em server/apps/game/tests/test_match_consumer_access.py"
```

---

## Implementation Strategy

### MVP

O MVP desta feature são as **três histórias P1 juntas** — Fases 1 a 5. US1
sozinha entrega um `Match` que não persiste, e persistir é o motivo de a
partida existir no Redis. Parar em US1 ou US2 não entrega nada demonstrável.

Depois da Fase 5 dá para provar o essencial: montar um estado, distinguir duas
cópias da mesma carta e fazer a ida e volta sem perda.

### Entrega incremental

1. Fases 1–2 → os tipos existem, suíte verde
2. Fases 3–5 → **MVP**: estado, identidade, serialização
3. Fase 6 → dano e modificadores provados
4. Fase 7 → a pergunta do fizzle respondida
5. Fase 8 → visão do jogador com ocultação imposta pelo tipo
6. Fase 9 → **cutover**, o modelo antigo morre
7. Fase 10 → limpeza e portas

### O que não fazer

- **Não pule a Fase 9.** Parar antes deixa dois modelos de partida convivendo,
  e o novo sem nenhum chamador.
- **Não antecipe a Fase 9.** Trocar `store.py` antes de a serialização existir
  deixa a suíte vermelha por várias fases seguidas, sem ganho.
- **Não implemente regra.** Se uma tarefa te levar a escrever validação de
  jogada, cálculo de dano, troca de prioridade ou avanço de fase, pare — está
  fora de escopo, e é o defeito que `play_card` tinha.

---

## Notes

- `[P]` = arquivo diferente, sem dependência pendente
- Todo módulo novo entra em arquivo novo até a Fase 9; a suíte fica verde
- Comentários do `models.py` antigo são transplantados, não descartados
  (research D9) — a constituição manda preservar intenção num refactor, e
  apagar um arquivo não é licença para jogar fora o porquê
- Commit por tarefa ou por grupo lógico; a Fase 9 vale um commit só
- Rode `black` antes de cada commit: formatação não é assunto de revisão
