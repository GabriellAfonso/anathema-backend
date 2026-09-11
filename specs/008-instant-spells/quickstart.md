# Quickstart: Feitiço imediato

**Feature**: 008-instant-spells | **Data**: 2026-09-11 | **Fase**: 1

Como rodar e como provar que a pilha saiu e que o feitiço resolve na hora sem
passar a vez. Nada aqui precisa de websocket nem de banco; só
`test_match_store.py` usa o fake de Redis que já existe.

---

## Portas de qualidade

```bash
cd server && pytest
cd server && mypy
cd server && black --check .
```

As três precisam estar verdes. No container:

```bash
docker compose run --rm backend sh -c "cd server && pytest && mypy"
```

---

## Nenhum resto de pilha

A prova de SC-003 e FR-021 é uma busca que devolve **só** os dois testes que
afirmam a ausência da chave `stack` — `test_the_document_has_no_stack_key` e
`test_the_view_has_no_stack_key`, que não têm como afirmá-la sem escrevê-la:

```bash
rg -i "pilha|stack|fizzl|empilh|CastCombatSpell|cast_combat_spell|STACK_RESOLUTION" server/apps/game   | rg -v "has_no_stack_key|\"stack\" not in"
# esperado: nenhuma linha
```

Se sobrar uma linha, ou é resto a apagar, ou é um comentário a reescrever
([research.md, D10](./research.md#d10-os-comentários-que-afirmam-a-pilha)). A
busca inclui `server/apps/game/tests`: teste que ainda afirma pilha é teste da
regra errada.

Os arquivos que não podem mais existir:

```bash
ls server/apps/game/engine/stack_resolution.py \
   server/apps/game/engine/cast_combat_spell.py \
   server/apps/game/match/spell_stack.py \
   server/apps/game/tests/test_stack_resolution.py \
   server/apps/game/tests/test_spell_stack.py \
   server/apps/game/tests/test_cast_combat_spell.py
# esperado: seis "No such file or directory"
```

---

## Os arquivos de teste desta feature

| Arquivo | O que prova | História |
|---|---|---|
| `test_cast_spell.py` | o feitiço aceito resolve na hora, fica com a vez, zera passes, e dá o mesmo estado nas duas fases | US1, US2 |
| `test_cast_spell_refusals.py` | as recusas, iguais nas duas fases, com a partida intocada | US1, US2 |
| `test_spell_in_combat.py` | o que o feitiço do defensor muda no dano e na partida que acaba dentro da janela | US2 |
| `test_round_cycle.py` | dois passes seguidos fecham a rodada, inclusive depois de um feitiço | US3 |
| `test_declare_attack.py` | declarar ataque sem guarda de pilha, inclusive depois de feitiços na mesma vez | US3 |
| `test_blocker_pairing.py` | quem fica com a vez e quem devolve | US1, US2 |
| `test_match_serialization.py`, `test_player_view.py`, `test_match_state.py` | documento, visão e fases sem pilha | US4 |
| `test_full_match.py` | do setup à vitória com feitiço aceito nas duas fases | US5 |

Rodando só o que esta feature toca:

```bash
cd server && pytest apps/game/tests -k "spell or round_cycle or declare_attack or blocker or serialization or player_view or match_state or full_match"
```

---

## Cenários para conferir à mão

Os mesmos que os testes cobrem, escritos para quem quiser seguir num REPL
(`cd server && python manage.py shell`) com `fake_spell_board` e
`submit_action`. Cartas e números em
[contracts/cast_spell.md](./contracts/cast_spell.md#exemplos).

1. **Resolve na hora.** Fase de Ação, A com a vez e SUMMONED AX na mão; B com
   MORTEM no banco. Jogar AX em MORTEM. Esperado, sem nenhum passe: MORTEM no
   cemitério de B, AX no cemitério de A, energia de A menos 5.

2. **Fica com a vez.** Logo depois do 1: `match.priority_user_id` ainda é A, e
   `match.consecutive_passes` é 0. Jogar um segundo feitiço é aceito.

3. **Unidade devolve a vez.** Logo depois do 2: A joga uma unidade.
   `match.priority_user_id` passa a B.

4. **Passe depois de feitiço não fecha a rodada.** B passa; A joga um feitiço e
   passa. A rodada **não** fechou: `consecutive_passes` é 1 e a vez é de B. B
   passa: rodada seguinte, Upkeep executado.

5. **Ataque depois de feitiço.** A, dono do token, joga dois feitiços e declara
   ataque. As três jogadas são aceitas; a vez passa a B só na terceira.

6. **Mesmo feitiço no combate.** Com o combate aberto, o defensor usa a mesma
   `CastSpellAction` do cenário 1. Aceita; a vez continua com o defensor; o
   atacante que tentar recebe `NotYourPriorityError`.

7. **Modificador na hora.** A joga SOMEONE'S SHIELD numa unidade própria. O
   `HealthModifier` já está na unidade, sem nenhum passe.

8. **Nada pendente.** Em qualquer ponto acima,
   `"stack" not in to_match_document(match)` e
   `"stack" not in build_player_view(match, A)`.

---

## Depois do merge

A spec da feature 009 (`009-match-protocol`) está pausada esperando esta. O
que ela precisa rever está em
[contracts/removed_surface.md](./contracts/removed_surface.md#para-a-feature-009).
