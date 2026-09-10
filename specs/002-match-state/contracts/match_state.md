# Contrato — `apps.game.match`

**Feature**: Estado de Partida (`002-match-state`)
**Data**: 2026-09-09

Esta feature não expõe HTTP nem websocket. A interface pública é a de um pacote
Python consumido por outro código do backend — o store do Redis, os consumers,
o matchmaking e, depois, o motor de regras. O que está aqui é o que esses
consumidores podem depender; o resto é interno e pode mudar sem aviso.

Detalhe de campo em [data-model.md](../data-model.md); as razões de desenho em
[research.md](../research.md).

---

## Superfície pública

```python
from apps.game.match import (
    # Identidade e cartas
    CardInstanceId, MatchCard, BankUnit,
    # Modificadores
    ModifierKind, AttackModifier, HealthModifier, DamageImmunity, UnitModifier,
    # Pilha
    StackEntry,
    # Estado
    MatchPhase, PlayerState, Match, NotAParticipantError,
    # Forma gravada
    MatchDocument, PlayerDocument, CardDocument,
    BankUnitDocument, StackEntryDocument, ModifierDocument,
    to_match_document, match_from_document,
    # Visão
    PlayerView, PlayerSideView, OpponentSideView, build_player_view,
)
```

`__init__.py` declara `__all__` explícito. `mypy.ini` roda com `strict`, que
liga `no_implicit_reexport`: sem a lista, nenhum consumidor importa do pacote.

---

## Criar uma partida

```python
match = Match.start(player1, player2)
```

`player1` e `player2` são `PlayerData` — o que
`get_player_public_data(user_id)` devolve, e o que o matchmaking já tem em mãos
quando fecha um par.

**Pós-condições**: rodada 1, fase `UPKEEP`, Nexus 20 dos dois lados, energias
em 0, `token_consumed=False`, `consecutive_passes=0`, pilha vazia, quatro zonas
de carta vazias, `next_card_instance_id=1`. `token_holder_user_id` e
`priority_user_id` são o `user_id` de `player1`.

**O que isto não faz**: embaralhar, comprar, mulligan, sortear o token. É o
setup da §3 e é da próxima feature. A partida devolvida é **válida** — todo
campo tem valor do tipo certo e o gate de participante funciona — e **não é
jogável**.

Na prática, quem chama é `MatchStore.create()`, nunca um consumer direto: o
estado precisa chegar ao Redis para os outros workers do uvicorn enxergarem a
partida.

---

## Perguntar quem joga

```python
match.has_player(user_id)          # bool
```

O gate de `MatchConsumer`. Aceita `int | None` e devolve `False` para `None` —
um socket sem usuário autenticado nunca passa, e nunca levanta.

```python
player   = match.player(user_id)        # PlayerState
opponent = match.opponent_of(user_id)   # PlayerState
```

**Levantam** `NotAParticipantError` quando o `user_id` não joga a partida. A
mensagem cita o `user_id` pedido e o `match_id`.

A assimetria com `has_player` é deliberada: `has_player` é a pergunta do
portão, feita justamente sobre quem talvez não seja participante. `player()` é
feita depois do portão, por código que já sabe que é — e ali um `user_id` de
fora é erro de programação.

---

## Cunhar identidade de carta

```python
instance_id = match.mint_card_instance_id()   # CardInstanceId
```

Devolve o valor atual de `next_card_instance_id` e incrementa. É o **único**
lugar que produz um `CardInstanceId`; nenhum outro código deve construir um do
nada.

**Garantia**: o número devolvido nunca foi usado nesta partida, nem antes nem
depois de uma ida e volta pelo Redis — o contador é campo do estado, não do
processo.

**Nunca chame ao mover carta entre zonas.** O identificador nasce com a carta e
acompanha ela: mover é `hand.pop()` e `bank.append(...)`, sem passar por aqui.
O reset de deck da §9 também não passa — devolve as mesmas cartas, com os
mesmos números.

---

## Mover carta entre zonas

Não há operação para isso: mover é manipular as listas, e quem move é o motor.
O contrato é o formato, e ele existe para tornar o movimento correto barato:

```python
# mão -> banco
player.bank.append(
    BankUnit(card=player.hand.pop(index), damage_taken=0, modifiers=[])
)

# banco -> cemitério
player.graveyard.append(dead_unit.card)

# reset de deck (§9): cemitério inteiro volta, mesmos identificadores
player.deck = player.graveyard
player.graveyard = []
```

O `MatchCard` atravessa como o mesmo objeto. Dano e modificadores ficam para
trás porque moram no `BankUnit`, que deixa de existir.

---

## Revalidar um alvo

```python
target = match.bank_unit(card_instance_id)   # BankUnit | None
```

A pergunta da §6, feita no momento de resolver a pilha. Varre os dois bancos e
devolve a unidade, ou `None` se aquele identificador não está em campo — porque
morreu, porque nunca esteve, ou porque está em outra zona.

**`None` não é erro.** É a resposta que autoriza o fizzle. Quem chama não
precisa envolver em `try`, e não precisa saber de qual jogador o alvo é.

```python
target = match.bank_unit(entry.target_card_instance_id)

if target is None:
    ...  # fizzle: o feitiço vai para o cemitério sem fazer nada
```

Decidir se o alvo é **legal** — aliado contra inimigo, o que `TargetKind` do
feitiço exige — é regra, e é de outra feature. Este método só responde se está
em campo.

---

## A pilha

`match.stack` é uma `list[StackEntry]` e **resolve do fim para o começo**.
`append` empilha; `pop()` sem argumento tira o topo. LIFO (§6, FR-026).

```python
match.stack.append(StackEntry(
    card=spell_card,
    caster_user_id=user_id,
    target_card_instance_id=CardInstanceId(3),   # ou None
))
```

`target_card_instance_id=None` significa que o feitiço **não mira nada** —
`RestoreNexus`, `SacrificeNexusForAttack`. Não significa que o alvo sumiu: essa
é a resposta de `bank_unit()`, e as duas perguntas não se confundem.

---

## Modificadores

```python
unit.modifiers.append(AttackModifier(amount=2, duration=EffectDuration.PERMANENT))
unit.modifiers.append(DamageImmunity(duration=EffectDuration.UNTIL_END_OF_ROUND))
```

`EffectDuration` vem de `apps.game.cards`, o mesmo enum que os efeitos de
feitiço declaram.

Congelados: um modificador é um valor. Expirar é remover da lista, nunca editar
no lugar:

```python
# o que o Fim de Rodada (§8) fará — de outra feature
unit.modifiers = [
    modifier for modifier in unit.modifiers
    if modifier.duration is EffectDuration.PERMANENT
]
```

`amount` negativo é como se reduz ataque. `DamageImmunity` não tem `amount`.

**Ataque e vida efetivos não estão aqui.** A conta é
`molde + soma dos modificadores`, e fazê-la é do motor — esta feature guarda os
insumos (FR-017). O molde chega do catálogo, por parâmetro:

```python
def effective_attack(unit: BankUnit, catalog: CardCatalog) -> int:
    ...
```

---

## Serializar

```python
document: MatchDocument = to_match_document(match)
match = match_from_document(document)
```

**Garantia de ida e volta**: para qualquer `Match` válido,
`match_from_document(json.loads(json.dumps(to_match_document(match))))` é igual
ao original — identificadores, contador, ordem do deck, ordem da pilha, dano
acumulado, modificadores e suas durações (FR-029).

**Garantia de forma**: nenhum objeto do documento tem `user_id` como chave, em
nenhum nível (FR-030). `players` é lista; o `user_id` mora dentro de `profile`,
como valor. Não existe conversão de chave a lembrar.

Zona vazia serializa como `[]` e volta como `[]`, nunca ausente (FR-031).

Quem chama é `MatchStore`:

```python
await self._redis.set(key, json.dumps(to_match_document(match)), ex=MATCH_TTL_SECONDS)
match = match_from_document(cast(MatchDocument, json.loads(stored)))
```

O `cast` continua sendo o único ponto onde o formato não é verificável — o que
sai do Redis é `Any` até alguém afirmar o contrário. Isso não mudou.

---

## Visão de um jogador

```python
view: PlayerView = build_player_view(match, user_id)
```

**Levanta** `NotAParticipantError` para um `user_id` que não joga (FR-037).

**Garantias de ocultação**, e cada uma é estrutural, não uma checagem:

| Garantia | Como é imposta |
|---|---|
| A mão do oponente nunca vaza | `OpponentSideView` não tem campo `hand`. Só `hand_size`. |
| O conteúdo de nenhum dos dois decks vaza | Nenhum dos dois tipos de lado tem campo de conteúdo de deck. Só `deck_size`. |
| A ordem de nenhum dos dois decks vaza | Consequência da anterior: não há lista de deck a ordenar. |

Contagem sim, identidade não. `deck_size` e `hand_size` não revelam carta
nenhuma, e o cliente precisa deles para desenhar a pilha de compra e a mão
virada.

**O que aparece**: própria mão, os dois bancos, os dois Nexus, as duas
energias, os dois cemitérios, fase, prioridade, dono do token, se foi
consumido, passes consecutivos, rodada e a pilha.

As cartas chegam como `CardDocument` — `card_instance_id` e `card_id`. O
identificador é o que permite ao cliente mirar uma cópia específica (FR-036).
Nome, custo, ataque e vida não vão: o cliente tem o catálogo.

**A visão não é o envelope.** Empacotar, transmitir e reenviar na reconexão é
do websocket, e está fora de escopo.

---

## O que este pacote não faz

Nenhuma operação aqui valida jogada, aplica efeito, calcula dano, troca
prioridade, avança fase ou resolve a pilha. Um método que decida qualquer uma
dessas coisas está no arquivo errado — foi exatamente o defeito de `play_card`,
que esta feature apaga.

Também não faz: o setup da §3, a compra e o reset da §9, o pareamento de
bloqueadores da §7.2, a atomicidade do read-modify-write no Redis.

---

## Compatibilidade

O que muda para quem já usa o pacote:

| Chamador | Antes | Depois |
|---|---|---|
| `consumers/match.py` | `from apps.game.match.models import Match` | `from apps.game.match import Match` |
| `consumers/matchmaking.py` | idem | idem |
| `store.py` | `match.as_dict()`, `Match.from_dict(...)` | `to_match_document(match)`, `match_from_document(...)` |
| `MatchStore.create/get/save` | — | assinaturas inalteradas |

Os chamadores do `MatchStore` não mudam (FR-039): o consumer continua chamando
`await self.matches.get(match_id)` e recebendo um `Match`.

**Some sem substituto**: `Match.play_card` (regra, FR-042),
`Match.get_state_for_player` (vira `build_player_view`, com forma diferente),
`Match.board_state`, `Match.hands`, `Match.turn` (viram zonas em `PlayerState`
e `priority_user_id`), e `CardId = str` (o `CardId` inteiro do catálogo assume).
