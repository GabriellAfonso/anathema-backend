# Implementation Plan: Compra de Carta e Reset de Deck

**Branch**: `004-card-draw-deck-reset` | **Date**: 2026-09-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/004-card-draw-deck-reset/spec.md`

## Summary

A §9 do Fluxo de Partida vira código, e o `engine/` que a feature 003 criou
ganha a segunda regra do motor. `engine/card_draw.py` deixa de expor o
movimento cru e passa a expor a regra inteira: `draw_card` avalia a guarda de
mão, depois o reset de deck, depois move a carta; `draw_cards` repete isso N
vezes, cada uma com as guardas na sua vez. Um módulo novo, `engine/deck_reset.py`,
executa o reset — todo o cemitério vira o deck embaralhado — sem decidir se ele
deve acontecer. Os três chamadores de compra que já existem (as 4 iniciais do
setup, a compensação de quem não recebeu o token, e a reposição do mulligan)
migram para a regra nova, e a suíte de testes do setup não é tocada.

Quatro decisões sustentam o plano. **A porta fica sozinha**: `draw_from_deck_top`
vira `_take_from_deck_top`, privada do módulo, e `EmptyDeckError` é apagada
porque o único caminho até ela passa a ser a própria regra, que nunca a alcança
(D1, D2). **A assinatura recebe `Match` e `user_id`, não `PlayerState`**: o
sorteio do reset sai de `match.mint_roll()`, e receber os dois abriria a porta
para o par errado — a mesma razão de `MatchEntry` na 003 (D3). **`None` é a
compra que não aconteceu**, e não erro: `Match.bank_unit()` já usa esse formato
para a resposta normal que não é uma coisa, e o mypy `strict` cobra o
tratamento de quem lê (D4). **O reset não decide nada**: recebe o `Roll` já
cunhado, para que o contador de sorteios não avance quando a regra descobre que
não há cemitério para resetar (D5).

Uma consequência que o plano assume de frente: o cenário "deck vazio e
cemitério vazio" é inalcançável em partida legal — a conta está na seção
Clarifications da spec — e mesmo assim ganha código e teste. É defesa contra
estado corrompido, e a alternativa (levantar) mataria a partida exatamente pelo
motivo que a §9 proíbe.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: nenhuma nova, e nenhum import novo de terceiros. Só o
que já existe no projeto: `apps.game.match` (feature 002) para as zonas e a
identidade de carta, `apps.game.randomness` (feature 003) para `RandomSource` e
`Roll`, e o próprio `apps.game.engine`.

**Storage**: nenhuma mudança. A feature não grava — quem grava é o chamador,
pelo `MatchStore.mutate` que a feature 003 entregou. Nenhum campo novo no
estado, então `documents.py` e `serialization.py` não são tocados, e não há
migration.

**Testing**: pytest 9.1, com `cd server && pytest`. Todos os testes desta
feature são síncronos e sem I/O — inclusive o de round-trip, que passa por
`to_match_document`/`match_from_document` direto, sem Redis (D10).

**Target Platform**: servidor Linux (container `python:3.14-alpine3.22`),
uvicorn com múltiplos workers. Importa aqui por um motivo só: o sorteio do reset
precisa vir do contador que mora na partida, para que um reset provocado depois
de uma recarga do Redis continue a sequência de onde parou.

**Project Type**: pacote de domínio interno dentro do app Django `apps.game`.
Não expõe HTTP nem websocket. Ninguém do lado do transporte muda nesta feature.

**Performance Goals**: o caminho quente é uma compra por jogador por rodada
(§4). Sem reset, a operação é uma comparação de tamanho e um `pop(0)` numa lista
de no máximo 40. Com reset, um embaralhamento de no máximo 40 cartas. O reset é
raro por construção — acontece quando o deck zera, o que leva dezenas de
rodadas.

**Constraints**: `cd server && mypy` verde sob `strict = True` e
`warn_unreachable = True`, sem relaxação nova em `mypy.ini`; funções de 4 a 20
linhas; arquivos abaixo de 500 linhas; nenhum campo `id` nu; nenhum import de
`random` fora de `apps/game/randomness.py`; nenhuma alteração nos arquivos de
teste da feature 003.

**Scale/Scope**: 1 módulo novo, 4 editados, 1 arquivo de teste novo e 1
reescrito. Nenhum fake novo — `ScriptedRandomSource` e `fake_match_state.py` já
dão tudo que os testes precisam.

## Constitution Check

*GATE: verificado antes da Fase 0 e de novo depois da Fase 1.*

| Princípio | Veredito | Como o desenho atende |
|---|---|---|
| I. Notas de decisão são a fonte da verdade | ✅ PASS | Os três passos e a ordem entre eles vêm da §9 de `Game/Fluxo de Partida.md`, literalmente. O teto de 10 e o "reset ilimitado" vêm da §12. A garantia de que nenhuma partida acaba por deck (§9, §10) é o que decide o caso deck-e-cemitério-vazios. Nada contradiz uma nota, e nenhuma nota nova é escrita. |
| II. Identidade nomeada, nunca `id` nu | ✅ PASS | As assinaturas recebem `user_id`; as recusas citam `user_id` e o valor ofensor. Nenhum campo novo no estado, então nenhuma chance de `id`. O identificador de carta continua sendo `card_instance_id`, e o reset o preserva por construção — as cartas são os mesmos objetos. |
| III. Tipos explícitos sob mypy strict | ✅ PASS | `MatchCard \| None` e `list[MatchCard]` como retornos, `int` para `count`, `RandomSource` e `Roll` já tipados pela 003. Nenhum `Any`, nenhuma relaxação nova. O `\| None` é o mypy cobrando de todo leitor o tratamento que FR-007 exige. |
| IV. Unidades pequenas, uma responsabilidade | ✅ PASS | `draw_card` fica em ~8 linhas com dois `return` cedo e 1 nível de indentação. `card_draw.py` vai de ~55 para ~110 linhas; `deck_reset.py` nasce com ~35. A decisão de separar o reto do reset (D5) é o que mantém os dois pequenos. |
| V. Comportamento testado com fakes nomeados | ✅ PASS | `ScriptedRandomSource` para a ordem concreta, `SeededRandomSource` para o determinismo (D11) — a divisão que o próprio `fake_random_source.py` documenta. Nenhum stub inline, nenhum `lambda` de aleatoriedade. Zero I/O, então zero fake de I/O novo. |
| Stack fixada | ✅ PASS | Nenhuma dependência nova, nenhum bump, nenhum import de terceiros. |
| Estrutura Django previsível | ✅ PASS | Um módulo dentro de um pacote que já existe. Sem app novo, sem `INSTALLED_APPS`, sem migration, sem URL, sem consumer. |
| Injeção de dependência | ✅ PASS | A fonte de aleatoriedade chega por parâmetro nomeado a `draw_card`, `draw_cards` e `reset_deck_from_graveyard`, como já chega a `start_match` e `record_mulligan`. Nenhum módulo desta feature importa `random`. |
| Portas de qualidade | ✅ PASS | `pytest`, `mypy` e `black` rodam sem configuração nova. |
| Comentários preservados no refactor | ⚠️ ATENÇÃO | Dois docstrings existentes deixam de ser verdade e precisam ser **reescritos**, não apagados. Detalhe abaixo. |

### O que precisa ser reescrito, e por quê

Os dois textos foram escritos prevendo esta feature. Eles não estão errados —
estão cumpridos, e o texto precisa passar do futuro para o presente.

1. **`engine/card_draw.py`, docstring do módulo.** Hoje diz: *"As duas condições
   da §9 (...) ficam **em volta** desta função, não dentro (...) a regra geral
   que a §9 pede vai ser uma função que checa as duas e delega aqui, em vez de
   uma segunda cópia do movimento."* A previsão se realizou, e o "em volta"
   passou a ser o mesmo módulo. O texto novo diz o que o módulo é agora e por
   que o movimento ficou privado.

2. **`engine/__init__.py`, docstring do pacote.** Hoje diz: *"Por enquanto só o
   setup da §3 mora aqui. O Upkeep da §4, a regra geral de compra da §9 e o
   combate da §7 caem no mesmo lugar quando entrarem."* A §9 entrou; a lista
   encolhe para o que ainda falta.

Um terceiro texto **não** muda, e é bom que não mude: o docstring de
`Match.mint_card_instance_id` já afirma que *"o reset de deck da §9 devolve as
mesmas cartas com os mesmos números"*. Esta feature é o que torna a frase
verificável, e FR-019 tem teste para ela.

O docstring de `PlayerState` — *"Os tetos de mão (10) e de banco (6) da §12
**não** são validados aqui. Aplicá-los é regra — o de mão acontece na compra
(§9)"* — também fica intacto, e é a justificativa de D6.

### Reverificação depois da Fase 1

O desenho fechado não mudou nenhum veredito. Quatro pontos que a Fase 1 tornou
concretos:

- **Princípio II**: o nome `draw_cards` ao lado de `draw_card` foi pesado
  contra a regra de nomes específicos. O par difere por uma letra, o que é um
  risco de leitura real; ficou porque `count` é posicional e obrigatório, então
  todo call site do plural carrega um terceiro argumento que o singular não
  tem — `draw_cards(match, user_id, 4, randomness=...)` não se confunde com
  `draw_card(match, user_id, randomness=...)` nem de relance.
- **Princípio III**: `draw_cards` devolve `list[MatchCard]` e não `int` porque
  a lista já dá a contagem e mais; nenhum chamador atual usa as cartas, e o
  Upkeep vai usar.
- **Princípio IV**: o módulo maior depois da feature é `card_draw.py`, na casa
  de 110 linhas — quatro funções públicas ou privadas, uma exceção e uma
  constante. Longe do teto de 500.
- **Princípio V**: `test_card_draw.py` é reescrito, não estendido: metade dos
  testes atuais afirmam a superfície de `draw_from_deck_top`, que deixa de
  existir. As perguntas que eles faziam — a carta vem do topo, a identidade não
  muda, o contador não avança — continuam, agora contra `draw_card`.

## Project Structure

### Documentation (this feature)

```text
specs/004-card-draw-deck-reset/
├── plan.md                    # Este arquivo
├── spec.md                    # A especificação
├── research.md                # Fase 0 — 11 decisões de desenho e alternativas
├── data-model.md              # Fase 1 — zonas tocadas, invariantes, a tabela da §9
├── quickstart.md              # Fase 1 — como rodar e provar que funciona
├── contracts/
│   └── card_draw.md           # Fase 1 — a superfície pública da compra
├── checklists/
│   └── requirements.md        # Checklist de qualidade da spec (16/16)
└── tasks.md                   # Fase 2 — criado por /speckit-tasks, não por este comando
```

### Source Code (repository root)

```text
server/
└── apps/
    └── game/
        ├── engine/
        │   ├── card_draw.py             # EDITADO — MAX_HAND_SIZE, draw_card,
        │   │                            #   draw_cards, NegativeDrawCountError,
        │   │                            #   _take_from_deck_top (era público),
        │   │                            #   sem EmptyDeckError
        │   ├── deck_reset.py            # NOVO — reset_deck_from_graveyard
        │   ├── __init__.py              # EDITADO — __all__ e docstring do pacote
        │   ├── match_setup.py           # EDITADO — 2 call sites migram
        │   └── mulligan.py              # EDITADO — 1 call site migra
        ├── match/                       # não alterado — nenhum campo novo
        ├── randomness.py                # não alterado — reaproveitado
        └── tests/
            ├── test_card_draw.py        # REESCRITO — US1, US2, US4, FR-033
            ├── test_deck_reset.py       # NOVO — US3, US5, round-trip (FR-032)
            ├── test_match_setup.py      # NÃO TOCADO — é a prova de SC-008
            ├── test_mulligan.py         # NÃO TOCADO — idem
            ├── test_setup_randomness.py # NÃO TOCADO — idem
            ├── fake_random_source.py    # reaproveitado, não alterado
            └── fake_match_state.py      # reaproveitado, não alterado
```

**Structure Decision**: nenhum pacote novo. A feature 003 criou `engine/` já
dizendo que *"o Upkeep da §4, a regra geral de compra da §9 e o combate da §7
caem no mesmo lugar quando entrarem"* — esta é a §9 caindo lá, e o pacote plano
com um módulo por responsabilidade continua sendo a forma.

A única escolha estrutural real foi separar `deck_reset.py` de `card_draw.py`.
São duas responsabilidades — decidir pela §9 e mover o cemitério para o deck —
e juntá-las daria um módulo com duas razões para mudar e um reset sem teste
próprio. A razão longa está em [research.md](./research.md) D5.

`match/` não é tocado, e isso é resultado, não sorte: o reset move cartas entre
listas que já existem e não cria estado. É o que faz FR-032 valer por
construção.

## Complexity Tracking

Nenhuma violação de princípio a justificar. Quatro pontos que esta feature toca
e resolve ou registra:

| Ponto | O que é | Encaminhamento |
|---|---|---|
| A dívida de porta única do `card_draw.py` | O docstring do módulo, escrito na 003, registra que a §9 precisa envolver o movimento *"em vez de uma segunda cópia"*. Enquanto só o setup comprava, a porta pública crua era inofensiva. | **Resolvida aqui.** O movimento vira privado e a regra vira a única porta (D1). O docstring é reescrito, não apagado: ele registra por que a função existe separada. |
| `EmptyDeckError` deixa de ter caminho | Com o reset no lugar, o braço "comprar de deck vazio" é inalcançável a partir da única porta pública. | **Apagada** (D2). A intenção migra para o docstring de `draw_card`, que passa a explicar o que a §9 responde nesse caso. O teste correspondente é substituído pelo de deck e cemitério vazios. |
| Cenário inalcançável com código e teste | Deck e cemitério vazios ao mesmo tempo não acontece em partida legal — a conta está na spec. | **Implementado mesmo assim**, como defesa. É a única resposta que não contradiz a §9, e sem teste ninguém saberia que a defesa existe. Registrado em FR-033/FR-034 e na seção Clarifications. |
| `play_card` roteado para o vazio | `consumers/base.py:155` roteia `{"type": "play_card"}` para um handler que `MatchConsumer` não implementa. | Continua fora de escopo, como os planos das features 002 e 003 já registraram. Jogar carta é a §5A. |

**Registro no vault**: nada novo para `Backend/TODO.md`. O Upkeep da §4 — o
primeiro chamador de verdade desta regra — é a próxima feature, e está fora de
escopo por decisão da spec, não por dívida.
