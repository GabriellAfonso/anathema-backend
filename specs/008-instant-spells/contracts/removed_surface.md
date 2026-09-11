# Contract: o que sai da superfície pública

**Feature**: `008-instant-spells`

Lista fechada de tudo que deixa de existir. Serve a dois leitores: quem
implementa esta feature, para saber quando parou, e a feature 009 (protocolo),
que estava especificada em cima desta superfície e precisa tirar o que sai daqui.

Depois desta feature, nenhum nome desta lista resolve em `apps.game`.

## `apps.game.engine`

| Nome | Era | Substituto |
|---|---|---|
| `CastCombatSpellAction` | feitiço da janela do defensor | `CastSpellAction` |
| `StackIsNotEmptyError` | recusa de declarar ataque com pilha cheia | nenhum |
| `ActionKind.CAST_COMBAT_SPELL` (`"cast_combat_spell"`) | espécie da ação acima | `ActionKind.CAST_SPELL` (`"cast_spell"`) |

Módulos apagados, que não eram exportados: `engine/stack_resolution.py`,
`engine/cast_combat_spell.py`.

Mudam de comportamento sem mudar de nome:

| Nome | Antes | Depois |
|---|---|---|
| `CastSpellAction.allowed_phases` | `{ACTION}` | `{ACTION, COMBAT}` |
| `CastSpellAction.keeps_priority` | `False` | `True` |
| `submit_action` com `CastSpellAction` | empilhava; o efeito vinha depois de dois passes | aplica o efeito na hora |
| `submit_action` com o segundo passe seguido | ia à Resolução de Pilha se houvesse feitiço pendente | vai sempre ao Fim de Rodada |

## `apps.game.match`

| Nome | Era |
|---|---|
| `StackEntry` | entrada da pilha |
| `StackEntryDocument` | forma gravada da entrada |
| `Match.stack` | a pilha |
| `MatchPhase.STACK_RESOLUTION` (`"stack_resolution"`) | fase automática da §6 |
| `to_stack_entry_document`, `stack_entry_from_document` | serialização da entrada (não exportadas) |

Módulo apagado: `match/spell_stack.py`.

## Forma gravada (`MatchDocument`)

Sai a chave `stack`. Nenhuma chave entra.

Um documento gravado antes desta feature, com `stack: []`, continua sendo lido:
`match_from_document` lê as chaves pelo nome. A escrita seguinte sai sem a chave.

## Visão do jogador (`PlayerView`)

Sai a chave `stack`. Nenhuma chave entra.

## Para a feature 009

A spec pausada em `009-match-protocol` cita, e precisa rever:

- "lançar feitiço imediato" como ação separada de "lançar feitiço": é uma só
- "respostas na pilha", "a pilha resolve", "pilha com feitiço" nos cenários de
  reconexão e na partida completa
- fizzle como algo que a descrição do que aconteceu precisa distinguir
- o código de recusa de pilha cheia, que não existe mais
- "a cascata inteira — os dois passam, a pilha resolve, a rodada vira": a
  cascata agora é só Fim de Rodada e Upkeep
