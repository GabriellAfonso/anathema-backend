# Data Model — Pilha de Feitiços e Efeitos

**Feature**: `006-spell-stack-effects` | **Data**: 2026-09-10

Fase 1. O que esta feature acrescenta ao estado, o que ela altera do que já
existe, e as invariantes que os testes seguram.

Ao contrário das features 004 e 005, **esta acrescenta estado**. É a primeira
desde a 002 a fazê-lo, e o motivo é só um: a partida agora pode acabar, e o fim
é estado (research [D1](./research.md)). Tudo o mais que a feature produz —
pilha cheia, modificadores, dano, cemitério — já era modelado pela feature 002 e
só estava vazio.

---

## 1. Estado novo

### 1.1 `MatchOutcome` — `apps/game/match/match_outcome.py` (NOVO)

```python
@dataclass(frozen=True, slots=True)
class MatchOutcome:
    defeated_user_ids: tuple[int, ...]

    @property
    def is_draw(self) -> bool: ...
```

| Campo | Tipo | Significado |
|---|---|---|
| `defeated_user_ids` | `tuple[int, ...]` | Quem chegou a Nexus ≤ 0. Um elemento é derrota; dois é empate. |
| `is_draw` | derivado | `len(defeated_user_ids) == 2`. Nunca gravado. |

**Validação na construção** (`InvalidMatchOutcomeError`, citando o valor
recebido e a forma esperada):

- vazia → recusa. Partida sem derrotado não terminou.
- três ou mais → recusa. A partida tem dois jogadores.
- repetida → recusa. O mesmo jogador não perde duas vezes.

Não existe campo de vencedor: ele é `match.players` menos os derrotados
(research [D2](./research.md)).

### 1.2 `MatchPhase.FINISHED` — `match/match_state.py` (EDITADO)

Sétimo valor do conjunto fechado. Terminal: nenhuma transição sai dele.

Não entra em `allowed_phases` de ação nenhuma, e não entra em
`_AUTOMATIC_PHASES`. As duas ausências são o que faz a partida terminada recusar
toda ação e parar a cascata **sem código novo em nenhum dos dois lugares**.

### 1.3 `Match.outcome` — `match/match_state.py` (EDITADO)

| Campo | Tipo | Default | Significado |
|---|---|---|---|
| `outcome` | `MatchOutcome \| None` | `None` | `None` é partida em andamento. |
| `is_over` | derivado | — | `outcome is not None`. Propriedade, nunca campo. |

---

## 2. Estado existente que esta feature passa a preencher

Nada aqui muda de forma. A feature 002 modelou tudo isto e a feature 005 o
deixou intocado; esta é a primeira que escreve nesses campos.

| Campo | Quem escreve | O que passa a acontecer |
|---|---|---|
| `Match.stack` | `cast_spell` empilha, `resolve_stack` esvazia | Deixa de estar sempre vazia. Fim da lista é o topo. |
| `PlayerState.nexus` | `change_nexus` | Primeira alteração de Nexus do jogo. Sobe (LIFE POTION), desce (SACRIFICIAL FIRE), e pode ficar negativo. |
| `BankUnit.damage_taken` | `deal_damage_to_unit` | Primeiro dano do jogo. Acumula; nunca é zerado por esta feature. |
| `BankUnit.modifiers` | `apply_spell_effect` | Primeiros modificadores criados por regra. Os três tipos passam a ocorrer. |
| `PlayerState.graveyard` | `resolve_stack`, `bury_dead_units` | Primeira carta a entrar. Duas origens: feitiço resolvido e unidade morta. |
| `PlayerState.bank` | `bury_dead_units` | Primeira remoção. Antes, o banco só crescia. |
| `PlayerState.energy_current` | `cast_spell` | Segunda regra a descontar energia, junto de `play_unit`. |
| `Match.consecutive_passes` | `cast_spell` zera, `resolve_stack` zera | Uma terceira ação passa a quebrar a sequência de passes. |
| `Match.priority_user_id` | `resolve_stack` | Primeira vez que a prioridade vai para alguém que **não** é o oponente de quem agiu. |
| `Match.phase` | `resolve_stack`, `_finish_match` | `STACK_RESOLUTION` deixa de ser inalcançável; `FINISHED` nasce. |

**Não escrito por esta feature**: `round_number`, `token_holder_user_id`,
`token_consumed`, `energy_max`, `deck`, `mulligan_taken`,
`next_card_instance_id`, `random_seed`, `next_roll_ordinal`.

O último par merece registro: **esta feature não consome aleatoriedade
nenhuma.** Nem lançar, nem resolver, nem matar unidade sorteia. `next_roll_ordinal`
sai de qualquer sequência de ações desta feature exatamente como entrou, e é
isso que FR-058 verifica nas recusas.

---

## 3. A forma gravada

### 3.1 `MatchOutcomeDocument` — `match/documents.py` (NOVO)

```python
class MatchOutcomeDocument(TypedDict):
    defeated_user_ids: list[int]
```

Lista e não tupla: JSON não tem tupla, e a volta reembrulha — o mesmo que
`CardId`, `CardInstanceId` e `RandomSeed` já fazem.

### 3.2 `MatchDocument` ganha uma chave

```python
class MatchDocument(TypedDict):
    ...
    outcome: MatchOutcomeDocument | None
```

`None` enquanto a partida corre, como `token_holder_user_id` é `None` enquanto o
sorteio da §3 não aconteceu.

**Nenhum teste existente quebra**: o único caminho que constrói um
`MatchDocument` é `to_match_document`, ele é simétrico com
`match_from_document`, e nenhum teste da feature 002 enumera as chaves do
documento (research [D15](./research.md)).

### 3.3 `PlayerView` ganha a mesma chave

```python
class PlayerView(TypedDict):
    ...
    outcome: MatchOutcomeDocument | None
```

O resultado é informação pública dos dois lados: quem perdeu não é segredo de
ninguém. Sem essa chave o cliente teria o estado terminal e não teria o
desfecho.

---

## 4. Transições de fase

O diagrama da feature 005, com as duas arestas que faltavam:

```
                      ┌───────────────────────────────┐
                      │                               │
                      ▼                               │
   UPKEEP ────────> ACTION ──────> STACK_RESOLUTION ──┘
      ▲                │                   │
      │                │                   │  (Nexus <= 0)
      │                ▼                   ▼
      └────────── ROUND_END            FINISHED
```

| De | Para | Quando | Quem escreve |
|---|---|---|---|
| `ACTION` | `STACK_RESOLUTION` | 2 passes com a pilha não vazia | `_exit_action_phase` (já existia) |
| `STACK_RESOLUTION` | `ACTION` | pilha esvaziada, partida viva | `_reopen_action_phase` |
| `STACK_RESOLUTION` | `FINISHED` | um Nexus chegou a ≤ 0 | `_finish_match` |
| `FINISHED` | — | nunca | — |

`STACK_RESOLUTION` **nunca** leva a `ROUND_END`: ela zera a contagem de passes
antes de devolver a Fase de Ação, e é assim que os dois passes que a
dispararam são consumidos (FR-026).

---

## 5. As três operações que alteram o tabuleiro

### 5.1 Empilhar (§5B) — `cast_spell`

Quatro guardas específicas, **nesta ordem**, todas antes da primeira
atribuição:

1. a carta citada está na mão do autor
2. a carta é um feitiço
3. `energia_atual >= custo`
4. o alvo casa com o que o efeito declara

Só então: `energy_current -= custo`, `hand.remove(card)`,
`stack.append(StackEntry(...))`, `consecutive_passes = 0`.

A ordem é a regra, não um detalhe: sem a carta resolvida não há custo a citar na
recusa de energia, e sem o efeito não há `TargetKind` a citar na recusa de alvo.

### 5.2 Resolver (§6) — `resolve_stack`

```
iniciador := stack[0].caster_user_id        # antes de esvaziar
enquanto stack não vazia:
    entrada := stack.pop()                  # topo
    se a partida não acabou:
        se a entrada mira e o alvo sumiu:  fizzle
        senão:                             aplica o efeito
    cemitério[entrada.lançador] += entrada.carta
se a partida não acabou:
    passes := 0; prioridade := iniciador; fase := ACTION
```

Invariante do laço: **a carta vai ao cemitério em todos os caminhos**, e o `pop`
acontece antes de qualquer decisão. Por isso a pilha esvazia mesmo quando a
partida termina no meio.

### 5.3 Aplicar (§5B, catálogo) — `apply_spell_effect`

Despacho exaustivo sobre a união fechada `SpellEffect`. Cada braço em uma linha
de intenção:

| Efeito | O que faz | Duração do modificador |
|---|---|---|
| `BuffUnitHealth(amount=2)` | `HealthModifier` no alvo | `effect.duration` (permanente) |
| `PreventUnitDamage()` | `DamageImmunity` no alvo | `effect.duration` (até o fim da rodada) |
| `DamageUnit(amount=3)` | `deal_damage_to_unit(alvo, 3)` | — |
| `RestoreNexus(amount=5)` | `change_nexus(lançador, +5)` | — |
| `SacrificeNexusForAttack(8, 3)` | `AttackModifier` em **todo** o banco do lançador, **depois** `change_nexus(lançador, -8)` | `effect.duration` (permanente) |

Depois de qualquer braço: `bury_dead_units(match, catalog=catalog)`.

Duas ordens que são regra:

- **SACRIFICIAL FIRE aplica o buff antes do custo.** A troca é indivisível
  (FR-039), e nessa ordem ela é indivisível qualquer que seja o comportamento da
  verificação de vitória. Na ordem contrária, um lançador que se derrota poderia
  perder o buff dependendo de onde a §10 é checada.
- **A duração vem de `effect.duration`, nunca de um literal.** É o que faz o Fim
  de Rodada varrer a imunidade e não varrer o buff de vida sem que o aplicador
  saiba o que é varrido (FR-047, FR-062).

---

## 6. Vida, dano e morte

Duas quantidades, com dois nomes, porque a spec usa "vida efetiva" com dois
sentidos (research [D9](./research.md)):

| Nome | Conta | Onde a spec o chama de "vida efetiva" |
|---|---|---|
| `unit_max_health(unidade)` | `molde.health + Σ HealthModifier.amount` | FR-044, US5-15, US5-17 |
| `unit_remaining_health(unidade)` | `unit_max_health − damage_taken` | FR-034 |

As duas leituras concordam em todo cenário, porque a morte é a mesma
desigualdade escrita de dois jeitos:

```
damage_taken >= unit_max_health   ⟺   unit_remaining_health <= 0
```

`unit_is_dead` é escrita como `unit_remaining_health(...) <= 0`.

**Dano não é modificador.** Não expira, não é varrido pela §8, e mora em
`BankUnit.damage_taken` — o docstring da feature 002 já diz isso, e esta feature
é a primeira a exercitá-lo.

**Somar vida não é curar.** `BuffUnitHealth` mexe em `unit_max_health` e não
toca `damage_taken`; a restante sobe como consequência (FR-035).

**Imunidade barra a entrada, não o efeito.** `deal_damage_to_unit` devolve sem
escrever quando a unidade tem `DamageImmunity` ativa. O feitiço **não fizzla** —
o alvo estava em campo e o efeito foi aplicado; aplicar 0 é o resultado certo.

**Morte é varredura dos dois bancos**, e a unidade vai para o cemitério do
**dono**, deixando dano e modificadores para trás — a carta que entra no
cemitério é o `MatchCard`, que não tem onde guardá-los (FR-046).

---

## 7. Invariantes

Cada uma é afirmada por pelo menos um teste.

**Do estado terminal**

- `outcome is not None` ⟺ `phase is MatchPhase.FINISHED`. Um ponto só escreve o
  par.
- `outcome` tem 1 ou 2 `user_id`, todos participantes da partida.
- Uma partida terminada nunca volta a `ACTION`, e a §10 é idempotente: uma
  segunda verificação não troca o resultado.
- Nenhuma ação é aceita depois. `MatchIsOverError` cita o resultado.

**Da pilha**

- Depois de `resolve_stack`, `match.stack == []` — sempre, inclusive quando a
  partida terminou no meio.
- Toda carta que sai da pilha entra no cemitério do **lançador**, e em nenhum
  outro lugar.
- A prioridade devolvida é `stack[0].caster_user_id` lido **antes** do primeiro
  `pop`.
- `round_number` é o mesmo antes e depois.

**Do lançamento**

- Uma recusa deixa `to_match_document(match)` idêntico, campo a campo,
  contadores inclusive.
- `next_card_instance_id` e `next_roll_ordinal` não avançam em ação nenhuma
  desta feature — nem aceita, nem recusada.

**Da compatibilidade**

- `match_from_document(json.loads(json.dumps(to_match_document(m)))) == m` para
  qualquer estado que esta feature produza, incluindo pilha cheia, os três tipos
  de modificador, dano, cemitérios povoados e partida terminada.
- A varredura do Fim de Rodada não muda: os `DamageImmunity` que esta feature
  cria são removidos pela mesma função, e os `HealthModifier` e `AttackModifier`
  permanentes sobrevivem por ela.

---

## 8. O que continua fora do estado

- **O iniciador da pilha** não é campo. É variável local de `resolve_stack`, e a
  razão está em research [D12](./research.md).
- **A vida efetiva** não é campo. É conta, e o docstring de `BankUnit` já
  registra por quê: guardar vida absoluta obrigaria a desfazer na mão a
  expiração de um buff temporário.
- **O vencedor** não é campo. É `match.players` menos `outcome.defeated_user_ids`.
- **A origem da aplicação do efeito** — pilha ou combate — não é campo, não é
  parâmetro, e não existe. É FR-029, e é a fronteira que mantém a feature de
  combate pequena.
