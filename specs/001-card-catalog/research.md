# Fase 0 — Pesquisa e decisões de desenho

**Feature**: Catálogo de Cartas do MVP (`001-card-catalog`)
**Data**: 2026-09-09

A Technical Context do plano não deixou nenhum `NEEDS CLARIFICATION`: a spec
chegou fechada e a stack está fixada pela constituição. O que este documento
resolve são as escolhas de desenho que a spec deliberadamente não fez, por ser
independente de implementação.

---

## D1 — Onde o catálogo mora

**Decisão**: subpacote `server/apps/game/cards/`.

**Rationale**: `apps.game` já é organizado por subpacote de responsabilidade —
`match/`, `matchmaking/`, `consumers/`. O catálogo é domínio de jogo e será
consumido pelo motor de partida, que mora ali do lado. Zero modelo e zero
migration significam que um app Django não compra nada.

**Alternativas consideradas**:

- **App Django novo `apps/cards`**: dá ownership próprio e um lugar óbvio para
  a tabela, se um dia houver. Custa entrada em `INSTALLED_APPS` e um `AppConfig`
  para um pacote sem modelo. Rejeitado por cerimônia sem contrapartida; a
  promoção depois é contida.
- **Dentro de `apps/game/match/`**: erra a responsabilidade. Catálogo não é
  estado de partida, e a spec separa os dois de propósito.

---

## D2 — Como a carta é representada

**Decisão**: `@dataclass(frozen=True, slots=True)`, com `Card = Unit | Spell`
como união de tipos.

**Rationale**: `frozen=True` é a forma mais barata de fazer FR-026 e FR-027
valerem em tempo de execução — tentar escrever em uma carta levanta
`FrozenInstanceError`, não corrompe silenciosamente o catálogo de todas as
partidas. `slots=True` fecha a porta de atributo novo por atribuição. A união
dá exaustividade verificável pelo mypy: um `match` sobre `Card` que esqueça um
braço é erro de tipo, não bug em produção.

**Alternativas consideradas**:

- **`TypedDict`**, como `MatchState` e `PlayerData` fazem no projeto: certo
  para dado que atravessa JSON, que é o caso deles. O catálogo nunca atravessa
  JSON nesta feature, e `TypedDict` é mutável — não sustenta FR-026.
- **Modelo Django**: persistência está fora de escopo, e traria banco para
  dentro de todo teste de motor de regras.
- **`NamedTuple`**: imutável e leve, mas indexável por posição, o que convida
  exatamente o acesso posicional que a constituição desencoraja em nomes.

---

## D3 — O tipo de `CardId`

**Decisão**: `CardId = NewType("CardId", int)`, definido em
`apps/game/cards/card.py`.

**Rationale**: `user_id` e `card_id` são os dois inteiros e circulam nos mesmos
dicionários de websocket. Alias simples (`CardId = int`) não impede trocar um
pelo outro; `NewType` transforma isso em erro de mypy, com custo zero em tempo
de execução. O ruído de embrulhar literal fica contido em um arquivo, porque
`mvp_catalog.py` constrói as cartas por funções auxiliares que recebem `int`.

**Alternativas consideradas**:

- **`CardId = int`**, seguindo o alias que já existe em `match/models.py`:
  consistente com o código atual, mas o código atual é um placeholder explícito
  ("o baralho ainda não existe") e é justamente o que esta feature substitui.
- **`str`**, como no jogo anterior: o maintainer decidiu numérico, com faixas
  1–1000 para unidade e 1001+ para feitiço.

**Consequência registrada**: fica um `CardId` duplicado no app até o motor
migrar. Está na tabela de Complexity Tracking do plano.

---

## D4 — Como o efeito de feitiço é estruturado

**Decisão**: união fechada de dataclasses congeladas, uma por mecânica, cada
uma declarando `target_kind` e `duration` como campos.

```text
SpellEffect = BuffUnitHealth | PreventUnitDamage | DamageUnit
            | RestoreNexus  | SacrificeNexusForAttack
```

O motor lê `effect.target_kind` e `effect.duration` para validar a jogada
(FR-014, FR-016) e faz `match` sobre a classe para aplicar — mas aplicar é a
feature da pilha, não esta.

**Rationale**: satisfaz FR-013 sem inventar uma linguagem de efeitos. Cada
classe carrega só os números que aquela mecânica usa, então não existe campo
opcional que só vale para um feitiço. A união fechada dá exaustividade no
mypy: quando a pilha de feitiços for implementada, esquecer um braço do `match`
é erro de tipo.

**Alternativas consideradas**:

- **Enum de tipo de efeito + saco de parâmetros** (`EffectKind.DAMAGE` mais
  `params: dict[str, int]`): reintroduz `dict` genérico e tira do mypy qualquer
  chance de verificar que `DamageUnit` tem `amount`. Contra o princípio III.
- **Lista de efeitos atômicos por feitiço** (`effects: tuple[SpellEffect, ...]`),
  com SACRIFICIAL FIRE virando `(PayNexus(8), BuffOwnUnitsAttack(3))`: mais
  geral e provavelmente o desenho certo quando existirem cartas com efeitos
  mistos. Rejeitado agora porque nenhum dos 5 feitiços do MVP precisa, e a
  generalização obrigaria a decidir hoje como agregar `target_kind` e `duration`
  de uma lista — decisão sem caso de uso para calibrar. SACRIFICIAL FIRE vira
  um efeito composto único, `SacrificeNexusForAttack(nexus_cost=8,
  attack_bonus=3)`.
- **Texto interpretado em tempo de execução**: proibido por FR-013.

---

## D5 — Nome do campo de tipo

**Decisão**: o campo se chama `card_type`, com valores `CardType.UNIT` /
`CardType.SPELL` (`StrEnum`, serializando como `"unit"` e `"spell"`).

**Rationale**: a spec pede um campo de tipo próprio, e o que ela exige de fato
é que o tipo não fique codificado no identificador (FR-005) — isso vale com
qualquer nome. `type` puro é o pior nome possível sob a regra de "nome que
devolve menos de 5 hits no grep" e sombreia o builtin dentro do corpo da
classe. Quando existir serializer para o cliente, o campo sai no wire como
`"type"`; o nome interno não vaza.

**Alternativas consideradas**:

- **`type`**, literal como a spec escreveu: fiel ao texto, hostil ao grep e ao
  linter.
- **Sem campo, inferindo por `isinstance`**: funciona em Python, mas FR-006
  pede um campo consultável sem inspecionar quais outros campos a carta tem —
  e o cliente vai precisar do valor no payload.

---

## D6 — Forma do acesso ao catálogo

**Decisão**: `CardCatalog` como `typing.Protocol` com quatro métodos, e
`FrozenCardCatalog` como a implementação que o MVP usa. Consumidores recebem o
catálogo por parâmetro.

**Rationale**: FR-028 e FR-029 pedem exatamente injeção. `Protocol` dá tipagem
estrutural — o fake do teste não precisa herdar de nada, só ter os métodos, que
é como `FakeMatchStore` já se relaciona com `MatchStore` neste projeto.

**Alternativas consideradas**:

- **Classe base abstrata (`ABC`)**: obriga herança e acopla o fake à árvore de
  classes de produção. `FakeMatchStore` já provou que não é o estilo da casa.
- **Módulo com funções de nível superior lendo um dicionário global**: quebra a
  injeção do princípio de dependências e torna impossível o catálogo pequeno de
  teste sem monkeypatch.

---

## D7 — Como a validação de deck reporta problema

**Decisão**: duas funções. `deck_problems(deck, catalog)` devolve uma tupla de
`DeckProblem` — vazia quando o deck é válido. `ensure_valid_deck(deck, catalog)`
chama a primeira e levanta `InvalidDeckError` com todas as mensagens quando há
problema.

**Rationale**: FR-025 exige relatar tudo em uma passada, o que uma função que
levanta na primeira falha não faz. Separar "descobrir" de "recusar" deixa o
teste asseverar a lista exata de problemas sem capturar exceção, e deixa o
chamador escolher — um construtor de deck quer a lista para pintar a tela, o
início de partida quer estourar.

**Alternativas consideradas**:

- **Só levantar, com a lista dentro da exceção**: perde o caso do construtor de
  deck, que não tem erro nenhum a tratar, só uma lista a mostrar.
- **Devolver `bool` e logar**: viola a exigência de mensagem que nomeia o valor
  ofensor (FR-022 a FR-024).

Cada `DeckProblem` é uma dataclass congelada com uma propriedade `message` que
inclui o valor ofensor — a contagem encontrada, o `card_id` excedente com suas
cópias, ou o `card_id` desconhecido. É a mesma regra da constituição para
mensagem de exceção, aplicada a um valor de retorno.

---

## D8 — Onde as faixas de `card_id` são verificadas

**Decisão**: na construção do `FrozenCardCatalog`. Unidade fora de 1–1000 ou
feitiço abaixo de 1001 faz a carga falhar com `CardIdOutOfRangeError`, junto com
a checagem de `card_id` duplicado (FR-030).

**Rationale**: a carga é o único momento em que o catálogo pode estar errado —
depois dele é imutável. Falhar ali é falhar no import, alto e cedo, em vez de
entregar um catálogo torto para o motor. É o que SC-008 mede.

**Ponto que a revisão precisa vigiar**: a faixa é convenção de leitura, não
fonte de verdade. FR-005 proíbe qualquer consumidor decidir tipo comparando
`card_id` com 1000 — `units()` e `spells()` filtram por `card_type`. Isso é uma
regra de revisão, não algo que um teste consiga provar pela ausência.
