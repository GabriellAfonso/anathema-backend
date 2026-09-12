# Research: Decks do jogador, e o catálogo servido ao cliente

**Feature**: `011-deck-catalog-api` | **Date**: 2026-09-12

Nenhuma dúvida técnica ficou aberta. As duas decisões de produto — teto de
decks e deck incompleto — foram respondidas na spec (20 decks; sem rascunho).
Abaixo, as decisões de desenho e o que foi descartado.

---

## D1. Onde mora o deck: `apps.players`

**Decision**: o modelo `PlayerDeck` vive em `apps/players/models/deck.py`, com
FK para `PlayerProfile` e `related_name="decks"`. Os serviços de leitura,
escrita e validação ficam em `apps/players/services/`, e a API HTTP em
`apps/players/deck_views.py`.

**Rationale**: deck é dado de jogador, e a direção de importação já existente é
`apps.game` → `apps.players` (`consumers/matchmaking.py` importa
`player_queries`). Pondo o deck em `players`, o grafo real de módulos fica:

```text
apps.players.services.deck_*   ──▶ apps.game.cards      (as três regras, o catálogo)
apps.game.consumers.matchmaking ──▶ apps.players.services.deck_queries
apps.game.cards                 ──▶ (nada de apps.players)
```

`apps.game.cards` é folha e continua folha. Não há ciclo de importação.

**Alternatives considered**:

- **App novo `apps.decks`.** Daria `apps.game` → `apps.decks` → `apps.game.cards`,
  um ciclo aparente entre dois apps, e um quarto app em `INSTALLED_APPS` para
  um modelo só. Rejeitado.
- **Deck em `apps.game`.** O deck não é regra de partida, é posse de jogador, e
  ficaria longe do `PlayerProfile` que o possui e da transação que o cria.
  Rejeitado.

## D2. A forma do deck no banco: uma lista JSON

**Decision**:

```python
class PlayerDeck(models.Model):
    profile = models.ForeignKey(PlayerProfile, on_delete=models.CASCADE,
                                related_name="decks")
    name = models.CharField(max_length=50)
    card_ids = models.JSONField()   # list[int]: ordem e repetição preservadas
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

A chave primária implícita é exposta como `deck_id`, nunca como `id`.

**Rationale**: o deck é uma **lista**, com repetição e ordem (FR-014). Uma
tabela de junção `deck × card` obrigaria ou a uma coluna de quantidade — que
destrói a ordem e transforma a lista em multiconjunto — ou a 40 linhas por
deck, 800 linhas por jogador no teto, para um valor que só é lido inteiro e só é
escrito inteiro. `JSONField` guarda exatamente o que foi enviado, numa leitura
só.

Não há FK para carta porque **carta não é linha de banco**: o catálogo é código
congelado (`FrozenCardCatalog`), e a integridade referencial de `card_ids` é
justamente o que a regra `UnknownDeckCard` da feature 001 verifica.

**Alternatives considered**: tabela de junção com `position` (correta e cara,
sem ganho: ninguém consulta deck por carta nesta feature); `ArrayField` (só
PostgreSQL, e o projeto roda SQLite).

## D3. Validar no salvamento: as três regras, o nome, e o teto

**Decision**: `apps/players/services/deck_validation.py` é a única porta de
validação de deck salvo, e ela envolve o que já existe:

1. **Nome** — `name.strip()` não vazio, até 50 caracteres. Recusa nomeia o
   campo e o valor recebido (FR-018). Nome repetido é aceito (FR-019).
2. **As três regras** — `deck_problems(card_ids, catalog)` da feature 001,
   chamada como está. Nada é reimplementado (FR-022).
3. **Teto** — 20 decks por jogador, conferido só na criação (FR-020). A
   contagem é um `COUNT` sobre os decks do dono.

Deck que não passa não é salvo, nem parcialmente: a criação não cria, e a
edição deixa o deck guardado como estava (FR-021).

**Rationale**: a spec escolheu "sem rascunho". Com isso o salvamento e a
entrada na fila chamam a **mesma** função de regra, e a diferença entre as duas
validações passa a ser só o instante — que é exatamente a razão de as duas
existirem (FR-022: o catálogo pode mudar entre um salvamento e uma partida).

**Alternatives considered**: validar no `clean()` do modelo (acopla a regra ao
ORM e roda em `full_clean`, que nem todo caminho chama); `UniqueConstraint` em
`(profile, name)` — contraria FR-019.

## D4. A API HTTP dos decks, e o 404 indistinguível

**Decision**: `APIView` em DRF, montada sob `players/decks/`, com
`IsAuthenticated`:

| Método | Rota | O que faz |
|---|---|---|
| `GET` | `players/decks/` | lista os decks do autenticado |
| `POST` | `players/decks/` | cria |
| `GET` | `players/decks/<deck_id>/` | lê um |
| `PATCH` | `players/decks/<deck_id>/` | renomeia e/ou troca a lista |
| `DELETE` | `players/decks/<deck_id>/` | apaga |

O isolamento (FR-017) sai **da consulta**, não de um `if`: toda operação por
identificador parte de `PlayerDeck.objects.filter(profile=request.user.profile,
pk=deck_id)`. Deck de outro jogador e deck inexistente percorrem o mesmo caminho
e produzem a mesma `NotFound`, com o mesmo texto padrão do DRF. Não existe ramo
que saiba a diferença, então não existe ramo que possa vazá-la.

**Rationale**: uma checagem de posse escrita como `if deck.profile_id !=
user.pk: raise PermissionDenied` já respondeu "esse deck existe" no 403. Filtrar
antes de buscar é a forma que não tem como errar.

**Alternatives considered**: `ModelViewSet` + router (traz rotas e
comportamentos que a feature não pede e esconde o filtro de posse numa
sobrescrita de `get_queryset`); `PermissionDenied` explícito (vaza existência).

## D5. O catálogo pelo HTTP: onde, e servido de um cache de processo

**Decision**: `GET game/cards/`, em `apps/game/card_catalog_view.py`, com
`IsAuthenticated` (FR-011). A resposta é
`{"cards": [ ... ]}`, ordenada por `card_id`, montada por
`apps/game/card_payload.py` a partir do `mvp_catalog()` que o motor já usa
(FR-009) — não há segunda lista.

O payload é montado **uma vez por processo** e guardado com `functools.cache`:
o catálogo é congelado na carga e a resposta não depende de quem pergunta
(FR-008).

**Rationale**: 29 cartas, resposta idêntica para todos, catálogo imutável em
tempo de execução. Remontar dicionários a cada requisição é trabalho que não
muda de resultado. O mesmo padrão de `@cache` já está em
`matchmaking/client.py`.

**Alternatives considered**: `ModelSerializer` (não há modelo — a carta é
`dataclass` congelada); rota em `apps.players` (o catálogo é do jogo, não do
jogador); cache HTTP com `ETag` (útil depois, e nada impede; não é requisito).

## D6. A forma do efeito servida: quatro campos, e nenhum `match`

**Decision**: o payload de efeito de feitiço é exatamente o que
`SpellEffectShape` já declara:

```json
"effect": {
  "requires_target": true,
  "target_kind": "enemy_unit",
  "duration": "permanent",
  "declaration_only": false
}
```

`target_kind` e `duration` são `StrEnum`, e o valor servido é o `.value` delas —
**o mesmo texto que o motor usa** (FR-006). `requires_target` é a propriedade
derivada que já existe. `declaration_only` é a restrição de momento (FR-005).

Nenhum `match` sobre a união `SpellEffect` é necessário: os quatro campos estão
na base comum, então um efeito novo é servido corretamente sem tocar neste
módulo.

**`amount` fica de fora.** Nem todo efeito tem (`PreventUnitDamage` não tem;
`SacrificeNexusForAttack` tem dois números), a spec não o pede, e expô-lo
exigiria o `match` por efeito que a decisão acima evita. O número está na
`description`, que é o que o jogador lê.

**Alternatives considered**: servir a classe do efeito (`"kind":
"damage_unit"`) — passaria ao cliente uma regra que é do motor, e a spec é
explícita: o cliente decide a **mira**, não o efeito. Rejeitado.

## D7. Nenhum `id` nu, em nenhum dos dois lados

**Decision**: `card_id`, `deck_id`, `user_id`. O serializador de deck mapeia
`deck_id = serializers.IntegerField(source="pk", read_only=True)`. O payload de
carta nomeia `card_id` e `card_type`.

**Rationale**: princípio II da constituição. Vale para HTTP como vale para o
websocket — é a mesma identidade atravessando camadas.

## D8. Entrar na fila vira uma mensagem, não mais o `connect`

**Decision**: `MatchmakingConsumer.on_connect` deixa de chamar `join_queue`. O
cliente manda:

```json
{"type": "join_queue", "payload": {"deck_id": 3}}
```

e o consumer trata em `handle_join_queue`, pelo roteamento por `type` que
`BaseConsumer.receive_json` já faz.

**Rationale**: o deck precisa viajar na entrada (FR-024), e a recusa não pode
fechar o socket (FR-030) — o cliente tem de poder tentar de novo com outro
deck, sem reconectar. Uma mensagem dá as duas coisas. Entrar no `connect`
obrigaria o deck a vir na query string, onde ele aparece em log de acesso e não
dá segunda tentativa.

`on_disconnect` continua chamando `queue.leave(user_id)`.

**Alternatives considered**: `deck_id` na query string do websocket (sem
retentativa, e o identificador vaza para log); um socket por deck (absurdo).

## D9. As recusas do socket de matchmaking

**Decision**: três códigos novos, em
`apps/game/protocol/matchmaking_refusals.py`, exportados por
`protocol/__init__.py`:

| Código | Quando |
|---|---|
| `deck_not_specified` | `join_queue` sem `deck_id`, ou com `deck_id` que não é inteiro |
| `deck_not_found` | deck inexistente **ou** de outro jogador — o mesmo código e o mesmo texto (FR-027) |
| `invalid_deck` | o deck é do jogador e não passa nas três regras |

Saem por `send_refusal`, que já existe e não fecha o socket. `send_refusal`
ganha `**details`, opcional, para o `invalid_deck` levar a lista estruturada de
problemas ao lado do texto. O socket de partida não passa `details` e os frames
dele não mudam — a feature 009 fica intacta (FR-039).

O `matchmaking_failed` de hoje continua existindo para o que ele já cobre:
perfil ausente de um dos pareados e deck recusado pelo `start_match`.

**Rationale**: o cliente Unity casa recusa por texto estável; a mensagem das
exceções carrega os valores ofensores e não serve de chave. É a mesma razão
escrita em `refusal_codes.py`.

## D10. A fila guarda o deck: uma lista, um hash, um script

**Decision**: `MatchmakingQueue` passa a trabalhar com entradas:

```python
@dataclass(frozen=True, slots=True)
class QueueEntry:
    user_id: int
    deck: Deck
```

`join(entry) -> tuple[QueueEntry, QueueEntry] | None`. No Redis, a lista FIFO
continua guardando só `user_id` — é o que faz `LREM` funcionar na reentrada — e
os decks vão para um hash paralelo, escrito e lido **no mesmo script Lua**:

```lua
-- KEYS[1] = fila, KEYS[2] = hash de decks
-- ARGV[1] = user_id, ARGV[2] = deck em JSON
redis.call('LREM', KEYS[1], 0, ARGV[1])
redis.call('RPUSH', KEYS[1], ARGV[1])
redis.call('HSET', KEYS[2], ARGV[1], ARGV[2])
if redis.call('LLEN', KEYS[1]) < 2 then
    return nil
end
local pair = redis.call('LPOP', KEYS[1], 2)
local decks = redis.call('HMGET', KEYS[2], pair[1], pair[2])
redis.call('HDEL', KEYS[2], pair[1], pair[2])
return {pair[1], pair[2], decks[1], decks[2]}
```

`leave` vira script também, para que `LREM` e `HDEL` não deixem deck órfão:

```lua
redis.call('LREM', KEYS[1], 0, ARGV[1])
redis.call('HDEL', KEYS[2], ARGV[1])
```

A serialização é `json.dumps(list(deck))` / `json.loads`, e mora dentro de
`queue.py`: o formato no Redis é assunto do envoltório, não de quem chama.

**Rationale**: guardar `{"user_id": 7, "deck": [...]}` como membro da lista
quebraria o `LREM` da reentrada, que remove **por valor exato** — um jogador
que reentra com outro deck ficaria duas vezes na fila e poderia ser pareado
consigo mesmo. O comentário que explica esse `LREM` está no código desde a
feature do matchmaking e continua valendo.

O par continua saindo de uma operação indivisível, que é a razão de o script
existir. `HSET` antes do teste de tamanho garante que, quando o par se fecha,
os dois decks já estão no hash — inclusive o de quem acabou de entrar.

`HMGET` que devolva `false` para um dos dois é estado impossível; o envoltório
levanta com os dois `user_id` na mensagem, e o consumer responde
`matchmaking_failed`.

**Alternatives considered**: ler o deck do banco no pareamento (é exatamente o
que FR-031 e FR-032 proíbem: o par fecha em outro worker, e uma edição entre o
join e o par produziria partida diferente da validada); dois comandos
separados (abre janela entre `RPUSH` e `HSET`).

## D11. O deck chega ao consumer por porta injetada

**Decision**: um `Protocol` estreito, consumido pelo consumer e implementado em
`apps/players/services/deck_queries.py`:

```python
class PlayerDeckSource(Protocol):
    async def deck_for(self, *, user_id: int, deck_id: int) -> Deck | None: ...
```

`None` é a resposta única para "não existe" e "não é seu" — a consulta filtra
por dono, então o caminho é um só (mesma razão de D4). A implementação
concreta usa `database_sync_to_async`, como `get_player_public_data` já faz.
O consumer recebe por `as_asgi(decks=...)`, ao lado de `queue`, `matches`,
`catalog`, `randomness` e `clock`.

**Rationale**: princípio de injeção da constituição, e uma razão concreta de
teste: o `conftest.py` de `apps/game/tests` documenta que **nenhum teste de
websocket toca o banco**, e o `no_connection_churn` existe por causa disso. Com
a porta injetada, os testes de socket usam `FakePlayerDeckSource` e continuam
fora do banco; quem testa a consulta de verdade é `apps/players/tests`, com
`django_db`.

**Alternatives considered**: importar `deck_queries` dentro do consumer (mata os
testes de socket sem banco e amarra o transporte ao ORM).

## D12. A validação da entrada na fila, e a ordem das recusas

**Decision**: `handle_join_queue` faz, nesta ordem:

1. `deck_id` ausente ou não inteiro → `deck_not_specified`;
2. `deck = await self.decks.deck_for(...)`; `None` → `deck_not_found`;
3. `problems = deck_problems(deck, self.catalog)`; não vazio → `invalid_deck`
   com todos os problemas;
4. só então `pair = await self.queue.join(QueueEntry(self.user_id, deck))`.

Nenhuma recusa acontece depois do passo 4 (FR-029): o jogador nunca ocupa lugar
na fila com deck que será recusado, e nenhum par é consumido.

`start_match` continua validando os dois decks, como hoje. Não é duplicação: é
a última guarda do motor, que não confia em quem o chama, e é o que produz
`InvalidPlayerDeckError` com o dono nomeado. Esta feature não a toca.

**Rationale**: a spec é explícita sobre por que a recusa é na entrada e não no
pareamento — o oponente não pode perder o tempo de fila dele por um problema
que não é dele.

## D13. `starter_deck` deixa de ser andaime

**Decision**: `apps/game/cards/starter_deck.py` fica, com a mesma função e o
mesmo algoritmo, e ganha docstring nova: ele deixa de ser o deck que o
matchmaking entrega a todo mundo e passa a ser o **conteúdo do deck inicial**
que o jogador ganha ao nascer (FR-040). O `deck_for` do consumer some (FR-036).

**Rationale**: o andaime que a feature remove é a **entrega** — todo jogador
recebendo o mesmo deck no pareamento —, não a derivação. Derivar do catálogo
continua sendo certo: o deck inicial fica válido se o catálogo mudar, e o teste
prova a validade em vez de repetir 40 números.

## D14. O deck inicial nasce na transação do perfil

**Decision**: `create_player_for_user` ganha uma quarta linha, e o serviço novo
`starter_deck_creation.py` cria o `PlayerDeck` com o nome `"Deck inicial"` e a
lista de `starter_deck(catalog)`. O catálogo entra por parâmetro, com
`mvp_catalog()` como padrão no ponto de composição.

A função já é `@transaction.atomic`, então FR-042 sai de graça: ou nascem
perfil, stats, settings e deck, ou não nasce nada.

Conta sem perfil não passa por aqui e não ganha deck (FR-043) — é a mesma razão
registrada no docstring do `RegisterSerializer.create` para não usar
`post_save`.

**Rationale**: um lugar só cria jogador, e é onde a transação já está.

**Alternatives considered**: sinal `post_save` em `PlayerProfile` (o docstring
existente já explica por que não: espalharia a criação por todo perfil salvo no
projeto e ficaria fora da transação).

## D15. Migração

**Decision**: `0002_playerdeck.py`, só `CreateModel`. Nada a migrar: nenhum
deck de jogador existe hoje, e contas já criadas não ganham deck inicial
retroativamente — elas criam o primeiro deck pela API, ou o teste as cria.

`apps/players/models/__init__.py` hoje está vazio, e os modelos só são
importados por `admin.py`. Ele passa a reexportar os quatro modelos com
`__all__` explícito, para que um modelo novo não dependa de alguém lembrar de
importá-lo no admin.

## D16. Testes, e o que cada um prova

| Arquivo | Prova |
|---|---|
| `apps/game/tests/test_card_payload.py` | os campos de desenho e a forma do efeito, carta a carta, contra o catálogo real |
| `apps/game/tests/test_card_catalog_view.py` | as 29 cartas na resposta, resposta igual para dois usuários, sem autenticação recusa, nenhum campo `id` |
| `apps/game/tests/test_matchmaking_join.py` | as quatro recusas da entrada, a ordem (ninguém entra na fila recusado), o par com decks de verdade |
| `apps/game/tests/test_matchmaking_queue.py` (editado) | `QueueEntry` entra e sai inteiro, reentrada troca o deck, `leave` não deixa deck órfão |
| `apps/players/tests/test_deck_validation.py` | nome, teto, as três regras delegadas, recusa com todos os problemas |
| `apps/players/tests/test_deck_api.py` | listar, criar, renomear, trocar lista, apagar, listagem vazia |
| `apps/players/tests/test_deck_isolation.py` | as cinco operações sobre deck alheio, resposta idêntica à de inexistente |
| `apps/players/tests/test_starter_deck_creation.py` | conta nova nasce com deck válido; falha desfaz tudo; conta sem perfil não ganha nada |
| `apps/players/tests/test_deck_queries.py` | a porta assíncrona devolve `None` para deck alheio e para inexistente |

Fakes nomeados, pela constituição V: `FakePlayerDeckSource` (novo, em
`apps/game/tests/`), e o `FakeCardCatalog` que já existe, reusado pelos testes
de validação para não depender das 29 cartas.

Os testes de socket continuam sem banco: quem toca o ORM é `apps/players`, com
`django_db`; quem toca Redis de verdade é `test_matchmaking_queue.py`, como já
é.

## D17. O que foi descartado, e por quê

- **Paginação na listagem de decks.** Teto de 20; a lista cabe numa resposta.
- **`ETag`/`Cache-Control` no catálogo.** Nada impede depois; não é requisito, e
  o `@cache` de processo já tira o custo de montar.
- **Campo "deck jogável" no payload do deck.** Com "sem rascunho", todo deck
  guardado estava válido quando foi salvo. Um campo assim seria verdade velha:
  quem responde "joga ou não" é a entrada na fila, contra o catálogo do momento.
- **Deck padrão / favorito.** Fora de escopo por decisão da spec: a entrada na
  fila sempre diz qual deck usa.
- **Apagar decks que o catálogo invalidou.** Fora de escopo; a spec registra que
  o deck continua guardado e quem recusa é a fila.
- **Expor `amount` do efeito.** Ver D6.
