---

description: "Task list for 004-card-draw-deck-reset"
---

# Tasks: Compra de Carta e Reset de Deck

**Input**: Design documents from `specs/004-card-draw-deck-reset/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md),
[research.md](./research.md), [data-model.md](./data-model.md),
[contracts/card_draw.md](./contracts/card_draw.md),
[quickstart.md](./quickstart.md)

**Tests**: incluídos e obrigatórios. Não é preferência de estilo — o princípio
V da constituição exige teste para toda função nova, e o quickstart põe
`pytest` como porta de conclusão.

**Organization**: agrupadas por história de usuário, na ordem que as
dependências permitem. Onde a ordem diverge da numeração da spec, a razão está
escrita na fase.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivo diferente, sem dependência pendente)
- **[Story]**: a que história pertence (US1 a US6)
- Todo caminho de arquivo é relativo à raiz do repositório

## Estratégia de corte

Esta feature troca a porta pública de um módulo que três chamadores já usam. A
tentação é fazer a troca de uma vez; o resultado seria uma janela vermelha
atravessando o setup inteiro, com `engine/__init__.py` sem importar.

O corte aqui evita o vermelho por inteiro, e não só o encurta:

- **Fases 2 e 3 são aditivas.** `deck_reset.py` nasce sem chamador;
  `draw_card` e `draw_cards` nascem ao lado de `draw_from_deck_top`, que
  continua público. Suíte verde do começo ao fim.
- **A Fase 4 migra os três call sites** para a regra nova, ainda com a porta
  velha aberta. Os testes do setup passam sem uma linha alterada — é aqui que
  SC-008 se prova.
- **A Fase 5 fecha a porta.** Os testes que afirmam a superfície removida saem
  **antes** da remoção (T027), e o rename mais o `__all__` acontecem na mesma
  edição (T028), porque separá-los deixaria `engine/__init__.py` importando um
  nome que não existe — e isso derruba a suíte inteira, não um arquivo.

A suíte fica verde em **todo checkpoint de fase e entre todas as tarefas**.
Se alguma tarefa deixar vermelho, o corte foi violado.

### Por que US3 e US5 vêm antes de US1

`draw_card` tem três braços, e um deles é o reset. Escrever a regra primeiro
obrigaria a deixar o braço do reset vazio ou duplicado durante uma fase
inteira. A Fase 2 entrega o reset como operação isolada — testável sozinha,
sem a regra em volta — e a Fase 3 só o chama.

US5 (determinismo) mora junto de US3 pela mesma razão: o embaralhamento do
reset é a única aleatoriedade que esta feature introduz, e prová-la fora do
módulo que a produz não acrescentaria nada.

### Por que US6 se divide em duas fases

US6 tem duas metades com riscos diferentes. Migrar os chamadores (Fase 4) é
aditivo e reversível. Apagar a porta velha (Fase 5) é a metade que quebra
compilação se feita fora de ordem. Separá-las deixa a Fase 4 servir de
checkpoint: se o setup passou com a regra nova e a porta velha ainda aberta,
FR-030 está provado antes de qualquer remoção.

---

## Phase 1: Setup

**Purpose**: linha de base e esqueleto de arquivos, para que as fases seguintes
sejam edição pura e o `[P]` seja seguro.

- [X] T001 Rodar as três portas e registrar a linha de base verde: `cd server && pytest`, `cd server && mypy`, `black --check server/`
- [X] T002 [P] Criar o módulo vazio `server/apps/game/engine/deck_reset.py`
- [X] T003 [P] Criar o arquivo de teste vazio `server/apps/game/tests/test_deck_reset.py`

**Checkpoint**: suíte verde, dois arquivos novos que ninguém importa.

---

## Phase 2: US3 + US5 — o reset de deck (Priority: P1)

**Goal**: todo o cemitério vira o deck embaralhado, sem tocar mão nem banco, de
forma repetível.

**Independent Test**: montar um jogador com deck vazio, 4 cartas no cemitério e
2 na mão; chamar o reset; conferir cemitério vazio, deck com 4, mão intacta, e
que os 4 identificadores são os mesmos.

**Aditiva**: nada importa `deck_reset` ainda. A suíte não pode ficar vermelha
nesta fase.

- [X] T004 [US3] Implementar `reset_deck_from_graveyard(player, *, randomness, roll)` em `server/apps/game/engine/deck_reset.py`, com docstring de intenção mais exemplo e a nota de que ela não decide se o reset acontece (contrato em `contracts/card_draw.md` §2)
- [X] T005 [US3] Exportar `reset_deck_from_graveyard` no `__all__` de `server/apps/game/engine/__init__.py`
- [X] T006 [US3] Testes do movimento em `server/apps/game/tests/test_deck_reset.py`: cemitério vira deck, cemitério fica vazio, e o deck é permutação exata das cartas que estavam no cemitério (FR-010, FR-011, FR-016)
- [X] T007 [US3] Testes do que o reset **não** toca em `server/apps/game/tests/test_deck_reset.py`: mão, banco, `nexus`, `energy_max`, `energy_current` e `match.next_card_instance_id` idênticos ao estado anterior (FR-012, FR-018, FR-019)
- [X] T008 [US5] Teste de ordem concreta em `server/apps/game/tests/test_deck_reset.py` com `ScriptedRandomSource`: o deck sai exatamente na ordem que a fonte ditou, e o `Roll` recebido é o que o chamador passou (FR-021)
- [X] T009 [US5] Testes de determinismo em `server/apps/game/tests/test_deck_reset.py` com `SeededRandomSource`: mesmo cemitério e mesmo `Roll` dão o mesmo deck; sementes diferentes dão decks diferentes (FR-023, SC-005)
- [X] T010 [US5] Teste de recarga em `server/apps/game/tests/test_deck_reset.py`: serializar a partida com `to_match_document`, reconstruir com `match_from_document`, provocar o segundo reset e conferir que a sequência continuou de onde parou em vez de recomeçar (US5 cenário 5)

**Checkpoint**: `pytest apps/game/tests/test_deck_reset.py` verde; suíte
inteira verde; nenhum arquivo existente alterado além do `__init__.py`.

---

## Phase 3: US1 + US2 + US4 — a regra da §9 (Priority: P1)

**Goal**: a porta única da compra, com as duas guardas na ordem que a §9 exige,
e a compra múltipla por cima dela.

**Independent Test**: com 3 cartas na mão e 5 no deck, comprar e conferir mão 4
/ deck 4; com 10 na mão, comprar e conferir que nada mudou em nenhuma zona.

**Aditiva**: `draw_from_deck_top` continua público e continua sendo o que o
setup chama. `draw_card` nasce ao lado, delegando a ele. A suíte fica verde
entre todas as tarefas.

- [X] T011 [US1] Acrescentar `MAX_HAND_SIZE = 10` e `draw_card(match, user_id, *, randomness)` a `server/apps/game/engine/card_draw.py`, com os três braços na ordem da §9 e docstring dizendo que `None` não é erro (contrato em `contracts/card_draw.md` §1)
- [X] T012 [US4] Acrescentar `NegativeDrawCountError` e `draw_cards(match, user_id, count, *, randomness)` a `server/apps/game/engine/card_draw.py`, parando na primeira compra que não acontece (research D7, D8)
- [X] T013 [US1] Exportar `draw_card`, `draw_cards`, `MAX_HAND_SIZE` e `NegativeDrawCountError` no `__all__` de `server/apps/game/engine/__init__.py`
- [X] T014 [US1] Testes da compra normal em `server/apps/game/tests/test_card_draw.py`: a carta vem do topo, vai para o fim da mão, o deck perde exatamente ela, o identificador não muda, o contador de identidade não avança, e cemitério e banco ficam intactos (FR-020, FR-019, FR-017)
- [X] T015 [US1] Testes de escopo em `server/apps/game/tests/test_card_draw.py`: o estado do oponente é idêntico depois da compra, e um `user_id` de fora da partida é recusado com `NotAParticipantError` (FR-004)
- [X] T016 [US2] Testes da guarda de mão em `server/apps/game/tests/test_card_draw.py`: mão em 10 devolve `None`, as quatro zonas ficam idênticas em conteúdo e ordem, não levanta erro, e mão em 9 compra e fecha em 10 (FR-005, FR-006, FR-007)
- [X] T017 [US2] Teste da ordem das guardas em `server/apps/game/tests/test_card_draw.py`: mão em 10 **e** deck vazio não reseta — o cemitério continua com as mesmas cartas e `match.next_roll_ordinal` não avança (FR-003, FR-024)
- [X] T018 [US3] Testes do reset através da compra em `server/apps/game/tests/test_card_draw.py`: deck vazio com cemitério cheio reseta e entrega a carta na mesma chamada, e só o cemitério do próprio jogador é usado — o do oponente com cartas não salva um jogador de cemitério vazio (FR-013, FR-015)
- [X] T019 [US2] Teste do caso defensivo em `server/apps/game/tests/test_card_draw.py`: deck e cemitério os dois vazios com mão abaixo de 10 devolve `None`, não altera zona nenhuma, não consome sorteio e não levanta (FR-033, FR-034, SC-011)
- [X] T020 [US4] Testes da compra múltipla em `server/apps/game/tests/test_card_draw.py`: 8 na mão pedindo 3 entrega 2 e fecha em 10; `count == 0` devolve lista vazia sem mudar nada; `count` negativo levanta `NegativeDrawCountError` citando o valor; 10 na mão pedindo 3 devolve lista vazia (FR-025 a FR-028)
- [X] T021 [US4] Teste da compra múltipla atravessando um reset em `server/apps/game/tests/test_card_draw.py`: 2 na mão, 1 no deck e 3 no cemitério, pedindo 3, entrega as 3 e a mão fecha em 5
- [X] T022 [US3] Teste do reset ilimitado em `server/apps/game/tests/test_card_draw.py`: encadear 100 resets devolvendo a carta ao cemitério a cada volta e conferir que a compra continua entregando — nenhum contador, nenhum teto (FR-014, SC-006)

**Checkpoint**: `pytest apps/game/tests/test_card_draw.py` verde com os testes
novos **e** os antigos; suíte inteira verde; `mypy` verde.

---

## Phase 4: US6 (primeira metade) — migrar os três chamadores (Priority: P2)

**Goal**: o setup e o mulligan passam a comprar pela regra da §9, e o
comportamento observável deles não muda.

**Independent Test**: a suíte do setup da feature 003 passa **sem uma linha
alterada**.

**Aditiva**: a porta velha continua aberta; o que muda é quem a usa.

- [X] T023 [US6] Trocar o laço de `_deal_opening_hand` por `draw_cards(match, player.user_id, OPENING_HAND_SIZE, randomness=randomness)` em `server/apps/game/engine/match_setup.py`
- [X] T024 [US6] Trocar a compra de compensação de `finish_setup` por `draw_card(...)` sobre o `user_id` do oponente do dono do token em `server/apps/game/engine/match_setup.py`
- [X] T025 [US6] Trocar o laço de reposição de `_swap_returned_cards` por `draw_cards(match, player.user_id, len(returned), randomness=randomness)` em `server/apps/game/engine/mulligan.py`
- [X] T026 [US6] Rodar `pytest apps/game/tests/test_match_setup.py apps/game/tests/test_mulligan.py apps/game/tests/test_setup_randomness.py` e confirmar com `git diff --stat` que os três arquivos não foram tocados (FR-029, FR-030, SC-008)

**Checkpoint**: suíte verde, três arquivos de teste da 003 com diff vazio.
Se algum deles precisou de edição, **pare**: o comportamento do setup mudou e
FR-030 falhou.

---

## Phase 5: US6 (segunda metade) — fechar a porta (Priority: P2)

**Goal**: existir um único lugar no código onde uma carta sai do deck e entra
na mão.

**Independent Test**: `grep -rn "draw_from_deck_top\|EmptyDeckError" apps/`
devolve vazio.

**⚠️ Ordem obrigatória**: a Fase 4 já migrou os três chamadores, então os
únicos usos restantes da porta velha estão em `test_card_draw.py` e no
`__init__.py`. T027 tira os primeiros; T028 tira o segundo **junto** com o
rename, na mesma edição. Separar T028 em duas deixa
`engine/__init__.py` importando um nome que não existe, e isso derruba a suíte
inteira, não um arquivo.

- [X] T027 [US6] Remover de `server/apps/game/tests/test_card_draw.py` os testes que afirmam a superfície que vai sumir — os que chamam `draw_from_deck_top` diretamente e o `test_an_empty_deck_is_refused_naming_the_owner`, cuja pergunta a Fase 3 já respondeu em T019 (research D2)
- [X] T028 [US6] Numa edição só: renomear `draw_from_deck_top` para `_take_from_deck_top` e apagar `EmptyDeckError` em `server/apps/game/engine/card_draw.py`, e tirar os dois nomes do import e do `__all__` de `server/apps/game/engine/__init__.py` (FR-001, FR-031)
- [X] T029 [US6] Reescrever o docstring do módulo `server/apps/game/engine/card_draw.py`: a previsão de que "as duas condições ficam em volta desta função" se cumpriu, e o texto passa a dizer o que o módulo é agora e por que o movimento ficou privado — reescrito, não apagado (plan.md, seção "O que precisa ser reescrito")
- [X] T030 [P] [US6] Reescrever o docstring do pacote `server/apps/game/engine/__init__.py`: a §9 entrou, e a lista do que ainda falta encolhe para o Upkeep da §4 e o combate da §7
- [X] T031 [US6] Provar a porta única: `cd server && grep -rn "draw_from_deck_top\|EmptyDeckError" apps/` devolve vazio (SC-010)

**Checkpoint**: suíte verde, `mypy` verde, `grep` vazio.

---

## Phase 6: US6 (round-trip) e portas

**Purpose**: a garantia da feature 002 continua valendo depois de um reset, e
as três portas da constituição fecham.

- [X] T032 [US6] Teste de round-trip em `server/apps/game/tests/test_deck_reset.py`: uma partida logo depois de um reset — cemitério vazio, deck reordenado, `next_roll_ordinal` acima de 1 — passa por `to_match_document` e `match_from_document` e volta igual campo a campo, sem Redis (FR-032, SC-009, research D10)
- [X] T033 Rodar `cd server && pytest` e confirmar verde
- [X] T034 Rodar `cd server && mypy` e confirmar verde, sem relaxação nova em `server/mypy.ini`
- [X] T035 Rodar `black server/` e confirmar `black --check server/` limpo
- [X] T036 Rodar os dois trechos executáveis de [quickstart.md](./quickstart.md) e conferir os sete `True` e o determinismo do reset
- [X] T037 Conferir que `grep -rn "draw_card\|draw_cards" apps/ --include=*.py | grep -v tests` só encontra as definições em `engine/card_draw.py`, a lista de `engine/__init__.py` e os três call sites do setup e do mulligan — nada fora do `engine/`

---

## Dependencies

```
Fase 1 (Setup)
   ↓
Fase 2 (US3 + US5) ─── deck_reset.py existe e é testado
   ↓
Fase 3 (US1 + US2 + US4) ─── draw_card chama o reset da Fase 2
   ↓
Fase 4 (US6 metade 1) ─── os chamadores usam draw_card/draw_cards
   ↓
Fase 5 (US6 metade 2) ─── a porta velha é apagada
   ↓
Fase 6 (round-trip e portas)
```

Dependências reais, e só elas:

- **T011 depende de T004.** O braço de reset de `draw_card` chama a função da
  Fase 2. Escrever a regra antes obrigaria a deixar o braço vazio.
- **T012 depende de T011.** `draw_cards` é um laço sobre `draw_card`.
- **T023 a T025 dependem de T013.** Não dá para migrar para um nome que o
  pacote ainda não exporta.
- **T027 e T028 dependem de T026.** Fechar a porta antes de provar que a
  migração não mudou o setup joga fora o checkpoint que separa "migrei" de
  "mudei o jogo".
- **T032 depende de T004.** Precisa de um estado pós-reset para serializar.

Não há dependência entre US1/US2/US4 e US3/US5 em sentido contrário: o reset é
testável sozinho, e é por isso que ele vem primeiro.

---

## Parallel Execution

Pouca coisa aqui é paralela de verdade — a feature toca dois arquivos de código
e dois de teste, e as tarefas de teste dentro de um mesmo arquivo colidem.

O que dá para rodar junto:

```
Fase 1:
Task: "deck_reset.py vazio em server/apps/game/engine/"
Task: "test_deck_reset.py vazio em server/apps/game/tests/"

Fase 5:
Task: "T030 docstring de engine/__init__.py"     (enquanto T029 mexe em card_draw.py)
```

Com mais de uma pessoa, o corte útil é por arquivo:

- Enquanto alguém faz a Fase 2 inteira (`deck_reset.py` + `test_deck_reset.py`),
  outra pessoa pode escrever os testes da Fase 3 (T014 a T022) contra o
  contrato, que já está escrito — eles só não passam até T011 e T012 existirem.
- A Fase 4 é de uma pessoa só: são três edições pequenas em dois arquivos, e o
  valor dela está no checkpoint, não na velocidade.

---

## Implementation Strategy

### MVP (US1 + US2 + US3)

1. Fase 1 — Setup
2. Fase 2 — o reset
3. Fase 3 — a regra da §9
4. **PARE E VALIDE**: `draw_card` responde as quatro linhas da tabela da §9
   (ver [data-model.md](./data-model.md) §2), e o quickstart passa.

Neste ponto a feature está funcionalmente pronta. O que falta é migrar quem já
compra e apagar a porta velha — sem isso, existem duas portas, e é exatamente
isso que FR-001 proíbe.

### Entrega incremental

1. Fase 2 (US3, US5) → o cemitério vira deck, de forma repetível
2. Fase 3 (US1, US2, US4) → a §9 inteira, com as guardas na ordem
3. Fase 4 (US6) → o setup compra pela regra nova, sem mudar de comportamento
4. Fase 5 (US6) → sobra uma porta só
5. Fase 6 → round-trip e as três portas

### Onde não parar

**Não pare entre a Fase 3 e a Fase 5.** Parar ali deixa duas portas de compra
no repositório, e a mais curta de digitar é a que pula as duas guardas. É a
mesma dívida que esta feature existe para pagar, com um nome novo ao lado.

---

## Notes

- `[P]` = arquivos diferentes, sem dependência pendente. Duas tarefas no mesmo
  arquivo de teste nunca levam `[P]`
- Todo teste roda com `cd server && pytest`; nada de runner próprio
- Nenhum teste desta feature toca I/O. Se algum precisar de fixture de Redis, o
  desenho saiu do plano — inclusive T032, que passa pela serialização direto
- Aleatoriedade só pelas duas fontes nomeadas: `ScriptedRandomSource` para
  ordem concreta, `SeededRandomSource` para determinismo. Nenhum stub inline,
  nenhum `lambda`
- Dois docstrings existentes **mudam de verdade** e são reescritos, não
  apagados: o de `card_draw.py` (T029) e o de `engine/__init__.py` (T030). A
  constituição trata comentário perdido em refactor como perda de intenção
- Um terceiro docstring **não** muda e é bom que não mude: o de
  `Match.mint_card_instance_id`, que já afirma que "o reset de deck da §9
  devolve as mesmas cartas com os mesmos números". T007 é o teste que torna a
  frase verificável
- Commit por tarefa ou por grupo lógico. T027 e T028 podem ir no mesmo commit;
  T028 nunca vai partido ao meio
- Fora de escopo, e nenhuma tarefa acima os pressupõe: o Upkeep da §4, o
  descarte e as mortes que alimentam o cemitério, feitiços que compram, e o
  timeout da §13
