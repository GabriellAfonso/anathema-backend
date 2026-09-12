# Contract: mensagens do cliente — delta da feature 010

**Feature**: `010-match-timers`

Base: [009 client_messages.md](../../009-match-protocol/contracts/client_messages.md).
Nenhum tipo de mensagem novo, nenhum campo novo.

## SACRIFICIAL FIRE (`card_id` 1003)

Lançado pelo mesmo `cast_spell`, **sem** `target_card_instance_id` (ausente ou
`null`):

```json
{"type": "cast_spell", "payload": {"card_instance_id": 23}}
```

| Situação | Resultado |
|---|---|
| Declaração, atacante, sem alvo | aceito; +3 de ataque em toda unidade que está na zona de ataque agora |
| Declaração, com qualquer alvo | `spell_takes_no_target` |
| Fora da Declaração, com ou sem alvo | `spell_only_in_declaration` |

O evento `spell_cast` sai com `target_card_instance_id: null`. O bônus aparece
nos `modifiers` de cada unidade na `view`.

## Relógio

O cliente não manda nada por causa do relógio. Não existe mensagem de "pedir
mais tempo", nem de confirmar o aviso.
