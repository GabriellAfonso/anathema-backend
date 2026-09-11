# Research: Protocolo de partida

**Feature**: `009-match-protocol` | **Date**: 2026-09-11

Nenhuma dúvida técnica ficou aberta. Abaixo, as decisões e o que foi descartado.

---

## D1. Mensagem vira comando num parser puro

**Decision**: `protocol/client_messages.py` expõe
`parse_client_message(content: object, *, author_user_id: int) -> ClientCommand`.
Recusa levanta `MalformedMessageError(code, message)`. Os `type` aceitos são os
valores de `ActionKind` mais `mulligan` — um conjunto só, sem nome inventado
para o cliente.

A validação é por espécie, com leitores pequenos: `_require_card_id(payload,
"card_instance_id")` aceita só `int` que não é `bool` e é ≥ 1;
`_require_card_ids` aceita lista desses; `_optional_card_id` aceita ausente ou
`null`. Campos a mais são ignorados. O `actor_user_id` vem sempre de
`author_user_id`.

**Alternatives considered**: um `handle_<type>` por espécie no consumer
(descartado: onze métodos que só validam, e a validação ficaria presa ao
Channels); um validador genérico por esquema (descartado: dependência nova, ou
um mini-framework para onze formas).

---

## D2. Catálogo de códigos por tipo exato de exceção

**Decision**: `protocol/refusal_codes.py` tem um dicionário
`type[Exception] -> str`, consultado por `type(error)` e **não** por
`isinstance`. Assim `MatchIsOverError`, subclasse de `PhaseForbidsActionError`,
tem código próprio (FR-025). Os códigos do protocolo (`malformed_message`,
`unknown_message_type`, `match_not_found`, `concurrent_match_write`,
`internal_error`) moram no mesmo módulo.

Um teste varre recursivamente `IllegalActionError.__subclasses__()` e exige
código para cada uma, e exige códigos únicos.

**Alternatives considered**: atributo `code` em cada exceção do motor
(descartado: o motor passaria a conhecer o contrato do cliente); derivar o
código do nome da classe (descartado: renomear uma classe mudaria o contrato
sem ninguém perceber).

---

## D3. A recusa é um frame `message_refused`

**Decision**: `BaseConsumer.send_refusal(code, message)` manda
`{"type": "message_refused", "payload": {"code": ..., "error": ...}}` só ao
socket. `BaseConsumer.receive` passa a tratar frame binário e JSON inválido, e
`receive_json` recusa mensagem sem `type` (`malformed_message`) e `type` sem
tratamento (`unknown_message_type`). Vale para todo socket que usa o envelope.

**Alternatives considered**: um frame de recusa por consumer (descartado: o
cliente casaria dois nomes para a mesma coisa).

---

## D4. Comandos e a aplicação deles

**Decision**: `protocol/commands.py`:

- `MulliganCommand(user_id, card_instance_ids: tuple[CardInstanceId, ...])`
- `ForfeitCommand(user_id)`
- `ClientCommand = PlayerAction | MulliganCommand | ForfeitCommand`
- `apply_command(match, command, *, catalog, randomness) -> None`

O mulligan chama `record_mulligan` e, se a partida ficou em `UPKEEP`,
`begin_round_cycle` — na mesma chamada, portanto na mesma mutação gravada
(FR-009). A desistência chama `forfeit`. As ações vão a `submit_action`.

**Alternatives considered**: fazer `record_mulligan` executar o Upkeep
(descartado: o motor separa "posicionar" de "executar" de propósito, e mudar
isso é mudar o motor).

---

## D5. Eventos pela diferença de estado

**Decision**: `protocol/match_events.py` expõe
`describe_change(before, after, command, *, recipient_user_id) -> list[MatchEvent]`.
Primeiro a jogada (derivada do comando e, para cartas, do `before`), depois as
consequências, nesta ordem fixa: dano em unidade, unidade morta, Nexus alterado,
rodada nova, compras, fim da partida.

- **Compra**: carta que está na mão depois e não estava antes. Para o próprio
  jogador o evento traz as cartas; para o oponente, só a quantidade.
- **Mulligan**: só a quantidade trocada, para os dois.
- **Dano**: `damage_taken` maior numa unidade que está no banco nos dois
  estados.
- **Morte**: unidade no banco antes e no cemitério do dono depois.
- **Rodada nova**: `round_number` maior.
- **Fim**: `outcome` que não existia.

Energia não vira evento: a visão já traz o valor, e o gasto é implícito na
jogada.

**Alternatives considered**: o motor registrar eventos num gravador injetado
(descartado: muda a assinatura de dezenas de funções do motor para um
consumidor só, e a spec pede o motor intocado); mandar só a jogada e deixar o
cliente deduzir (descartado na clarificação da spec: FR-014).

---

## D6. Distribuição pelo grupo de usuário

**Decision**: depois de gravar, o consumer monta um `MatchUpdatePayload` para
cada jogador da partida e manda
`{"type": "match.update", "match_id": ..., "payload": ...}` a
`MatchConsumer.user_group(user_id)`. O handler `match_update` só encaminha se
`match_id` é o do socket. O grupo da partida continua existindo (FR-039/040), e
não recebe visão.

Todo socket do jogador naquela partida recebe (FR-038), inclusive o que mandou —
a atualização é a confirmação (Assumptions da spec).

**Alternatives considered**: mandar ao grupo da partida o estado inteiro antes e
depois, e cada socket montar a sua (descartado: o estado inteiro com as duas
mãos atravessaria o channel layer sem necessidade, e cada worker repetiria o
diff); mandar a visão pronta ao grupo da partida (é o vazamento da spec).

---

## D7. Versão de escrita como posição

**Decision**: `StoredMatch(match: Match, version: int)` em `match/store.py`.
`SWAP_SCRIPT` devolve a versão nova (o `HINCRBY`) ou 0; `SAVE_SCRIPT` devolve a
versão nova. `get_stored(match_id) -> StoredMatch | None` lê estado e versão
juntos; `mutate` devolve `StoredMatch`. `get` fica, para quem só quer a partida.

**Alternatives considered**: contador dentro do documento (descartado: `store.py`
já diz por que versão de escrita não mora no documento); timestamp (descartado:
relógio entre workers não é ordem).

---

## D8. O antes da tentativa gravada

**Decision**: o `change` passado a `mutate` guarda `deepcopy(match)` antes de
aplicar, sobrescrevendo a cada tentativa. Quando `mutate` devolve, o que ficou
guardado é o antes da tentativa que venceu (FR-037).

---

## D9. Estado nunca vem da conexão

**Decision**: o consumer guarda só `match_id` depois dos gates. Toda jogada lê a
partida pelo `mutate` (FR-007). `self.match` sai.

---

## D10. Falhas do protocolo

**Decision**:

| Exceção | Código | Log |
|---|---|---|
| `MalformedMessageError` | o dela | não |
| do catálogo do motor | o do catálogo | não |
| `MatchNotFoundError` | `match_not_found` | não |
| `ConcurrentMatchWriteError` | `concurrent_match_write` | sim, JSON |
| qualquer outra | `internal_error`, mensagem genérica | sim, JSON com traceback |

Nenhuma fecha o socket (FR-023).

---

## D11. Visão com o estado do mulligan

**Decision**: `PlayerSideView.mulligan_taken` e `OpponentSideView.mulligan_taken`,
os dois `bool`. Do oponente é só "já respondeu" (FR-035).

---

## D12. Frame ao conectar

**Decision**: `match_start` passa a ter a mesma forma de envelope do
`match_update`, menos os eventos: `{"version": int, "view": PlayerView}`. Os
testes de reconexão leem `payload["view"]`.

**Alternatives considered**: manter o payload como a visão e enfiar `version`
nela (descartado: a visão é derivada da partida, e a versão não é da partida).
