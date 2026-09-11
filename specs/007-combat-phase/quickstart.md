# Quickstart: Combate

**Feature**: 007-combat-phase | **Data**: 2026-09-11 | **Fase**: 1

Como rodar e como provar que o combate faz o que a §7 manda. Nada aqui precisa
de Redis, de websocket nem de banco: o motor recebe a partida e devolve a
partida.

---

## Portas de qualidade

```bash
cd server && pytest
cd server && mypy
cd server && black --check .
```

As três precisam estar verdes. A suíte inteira é síncrona e sem I/O — inclusive
o round-trip, que passa por `to_match_document` / `match_from_document` direto.

No container:

```bash
docker compose run --rm backend sh -c "cd server && pytest && mypy"
```

---

## Os arquivos de teste desta feature

| Arquivo | O que prova | História |
|---|---|---|
| `test_combat_state.py` | o estado de combate e as perguntas que ele responde | (fundação) |
| `test_declare_attack.py` | a quarta ação da §5 e as sete recusas dela | US1 |
| `test_blocker_pairing.py` | a janela livre, o 1:1 estrito e as cinco recusas | US2 |
| `test_cast_combat_spell.py` | o feitiço que resolve na hora, e a igualdade com o caminho da pilha | US3 |
| `test_combat_damage.py` | o dano simultâneo, o órfão, a imunidade e a apuração única | US4 |
| `test_combat_cleanup.py` | limpeza, volta à Fase de Ação e a rodada que continua | US5, US6 |
| `test_combat_state_round_trip.py` | o pareamento sobrevivendo à forma gravada | US7 |
| `test_full_match.py` | do setup à vitória, sem tocar em transporte | US8 |
| `fake_combat_board.py` | o tabuleiro de combate, com as cartas reais do MVP | (auxiliar) |

Rodando só o combate:

```bash
cd server && pytest apps/game/tests -k "combat or declare_attack or blocker"
```

---

## O tabuleiro dos testes

`fake_combat_board.py` segue o formato de `fake_spell_board.py`, e pela mesma
razão: os números sob teste são os das cartas reais do MVP, não `card_id`
soltos.

Unidades escolhidas pelo par (ataque, vida) que cada cenário precisa:

| Carta | `card_id` | Ataque | Vida | Para quê |
|---|---|---|---|---|
| DARK AGE | 5 | 3 | 2 | morre para quase tudo |
| KHRAS | 6 | 2 | 4 | sobrevive a um golpe de 3 |
| SKILLET | 7 | 4 | 5 | bloqueador que aguenta |
| POLAROID | 13 | 2 | 6 | bate fraco e não morre |
| MORTEM | 3 | 7 | 2 | mata qualquer um e morre para qualquer um |

A troca canônica de mútua destruição é **DARK AGE contra MORTEM**: 3 de dano
numa vida 2 e 7 de dano numa vida 2, os dois morrem.

---

## Roteiro 1 — declarar, bloquear, resolver

O caminho central da feature, do começo ao fim.

1. Monte uma partida na Fase de Ação com o token no jogador 1, a pilha vazia,
   DARK AGE e MORTEM no banco dele e KHRAS no banco do jogador 2.
2. Jogador 1 declara ataque com DARK AGE e MORTEM.
   - `match.token_consumed is True`
   - `match.phase is MatchPhase.COMBAT`
   - `match.priority_user_id` é o jogador 2
   - `match.combat.attacker_card_instance_ids` tem os dois, na ordem citada
3. Jogador 2 atribui KHRAS na frente de DARK AGE.
   - `match.priority_user_id` **continua** sendo o jogador 2
   - `match.phase` continua `COMBAT`
4. Jogador 2 encerra a janela.
   - DARK AGE acumula 2 de dano (vida 2) e vai para o cemitério do jogador 1
   - KHRAS acumula 3 de dano (vida 4) e continua no banco do jogador 2
   - MORTEM passou direto: o Nexus do jogador 2 cai 7, de 20 para 13
   - o Nexus do jogador 1 não mudou
   - `match.combat is None`
   - `match.phase is MatchPhase.ACTION`, `match.priority_user_id` é o jogador 1,
     `match.consecutive_passes == 0`
   - `match.round_number` é o mesmo do passo 1

---

## Roteiro 2 — o atacante é espectador

1. Do estado do passo 2 do roteiro 1, o **jogador 1** tenta qualquer coisa:
   jogar unidade, lançar feitiço, bloquear, encerrar a janela.
2. Todas levantam `NotYourPriorityError`, e a mensagem cita o jogador 2.
3. `match_snapshot(match)` é idêntico ao de antes da tentativa, em todas.

O jogador 2 tentando uma ação da §5 (`PlayUnitAction`, `CastSpellAction`,
`PassAction`) levanta `PhaseForbidsActionError` citando `'combat'`.

---

## Roteiro 3 — o bloqueador órfão

1. Jogador 1 declara ataque com DARK AGE e MORTEM.
2. Jogador 2 bloqueia MORTEM com SKILLET.
3. Jogador 2 lança SUMMONED AX em MORTEM (3 de dano numa vida 2): MORTEM morre e
   sai do banco na hora.
4. Jogador 2 encerra a janela.
   - SKILLET não acumula dano nenhum e continua no banco — é o órfão
   - DARK AGE passou direto: o Nexus do jogador 2 cai 3
   - o cemitério do jogador 1 tem MORTEM; o do jogador 2 tem a carta do SUMMONED
     AX

---

## Roteiro 4 — o defensor limpa tudo com feitiço

1. Jogador 1 declara ataque com um DARK AGE só.
2. Jogador 2 lança SUMMONED AX nele. DARK AGE morre.
3. Jogador 2 encerra a janela sem bloquear nada.
   - nenhum Nexus mudou
   - nenhuma unidade acumulou dano de combate
   - a partida está de volta na Fase de Ação

---

## Roteiro 5 — o empate

Não é alcançável jogando: nenhuma das cinco cartas do MVP subtrai Nexus do
oponente, e o dano de combate só chega ao Nexus do defensor. O cenário é
exercido a partir de um estado montado, e é por isso que
`resolve_combat_damage` cita os **dois** jogadores na apuração.

1. Monte um combate com um atacante não bloqueado de ataque 7, o Nexus do
   defensor em 7 e o Nexus do atacante em 0 — a partida ainda correndo.
2. Encerre a janela.
   - `match.outcome.defeated_user_ids` tem os **dois** `user_id`
   - `match.phase is MatchPhase.FINISHED`

Trocar `change_nexus_simultaneously` por duas chamadas de `change_nexus` faz
este roteiro devolver um derrotado só. É o teste que pega a escolha errada
entre as duas funções.

---

## Roteiro 6 — a rodada continua

1. Termine o roteiro 1.
2. Jogador 1 joga uma unidade: aceito, e a prioridade vai para o jogador 2.
3. Jogador 2 lança um feitiço: vai para a **pilha**, e a prioridade volta — o
   caminho da §5B está de volta, e a exceção da janela não vazou.
4. Jogador 1 declara ataque de novo: `AttackTokenAlreadyConsumedError`.
5. Os dois passam com a pilha vazia: a rodada fecha, o token troca de dono, e o
   Upkeep da rodada seguinte roda dentro da mesma chamada.
6. Jogador 2, agora dono do token, declara ataque: aceito.

---

## Roteiro 7 — a partida inteira

`test_full_match.py` monta uma partida pelo setup da §3, responde o mulligan dos
dois, e alterna ações e combates até um Nexus chegar a 0.

O que ele afirma além do desfecho:

- nenhuma chamada devolveu a partida em `UPKEEP`, `STACK_RESOLUTION` ou
  `ROUND_END` — só `ACTION`, `COMBAT` e `FINISHED`
- nada no caminho importou `redis`, `channels` nem `django.db`

---

## Como provar que uma recusa não mudou nada

`match_snapshot` continua sendo a ferramenta, e continua sem alteração:

```python
before = match_snapshot(match)

with pytest.raises(BlockerAlreadyBlockingError):
    submit_action(match, action, catalog=CATALOG, randomness=source())

assert match_snapshot(match) == before
```

A foto passa por `to_match_document`, então o `CombatState` entra nela
automaticamente assim que a serialização o conhece — sem que nenhum teste
precise listar os campos novos à mão. É o que o docstring de `match_snapshot` já
prometia: *"Nenhum campo fica de fora, porque a serialização é a que já precisa
conhecer todos."*
