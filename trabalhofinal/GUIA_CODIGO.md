# Guia de código do SDWB (para estudar a apresentação)

Este guia explica **cada arquivo** do trabalho, na ordem que vale a pena entender,
detalhando as funções usadas e o **porquê** de cada decisão. Leia de cima para baixo:
cada seção assume a anterior.

Ideia central a repetir na cabeça o tempo todo:

> O sistema é uma **máquina de estado replicada**. Todo nó tem uma cópia completa do
> quadro. O **Coordenador não é dono do estado** — ele só **ordena** (dá número de
> sequência) e **repassa** (broadcast). Por isso a eleição funciona: quem ganha já tem
> o estado todo na mão.

Componentes: **Serviço de Nomes** (descoberta), **Coordenador** (ordena/difunde) e
**Cliente/Nó** (interface + réplica). O Coordenador é um *serviço* que roda **dentro** de
um nó e **migra** para outro quando o nó cai.

---

## 1. `backend/sdwb.proto` — o contrato (comece por aqui)

É o **arquivo mais importante**. Define todas as mensagens e serviços gRPC. Tudo no
código deriva dele. Os arquivos `sdwb_pb2.py` (mensagens) e `sdwb_pb2_grpc.py` (stubs de
cliente/servidor) são **gerados** a partir dele com:

```bash
cd backend
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. sdwb.proto
```

Nunca edite os `*_pb2.py`; só o `.proto` e regere.

### Antes de tudo: o que é gRPC e o que é uma RPC

**RPC = Remote Procedure Call** (Chamada de Procedimento Remoto). Ideia: chamar uma função
que **roda em outro processo / outra máquina** como se fosse uma função local. Você escreve
`stub.EnviarOperacao(op)` no cliente; por baixo, o gRPC **serializa** os argumentos, manda
pela rede (TCP/HTTP2), o servidor executa o método de verdade e devolve a resposta
serializada. O programador não vê sockets — vê uma chamada de função.

**gRPC** é a biblioteca que faz isso. Peças:

- **`.proto`** — o **contrato**. Descreve as *mensagens* (structs de dados) e os *serviços*
  (conjuntos de métodos remotos). Linguagem-neutra.
- **`protoc`** (compilador) — lê o `.proto` e **gera código**: classes de mensagem
  (`sdwb_pb2.py`) e os *stubs*.
- **Stub** (lado cliente) — objeto com os métodos do serviço. Chamar um método do stub
  dispara a RPC. No nosso código: `CoordenadorStub`, `NoStub`, `ServicoNomesStub`.
- **Servicer** (lado servidor) — classe onde você **implementa de verdade** os métodos. O
  gRPC chama seu servicer quando uma RPC chega. No nosso código: `_CoordenadorServicer`,
  `_NoServicer`, `ServicoNomesServicer`.
- **Channel** — o "cano" TCP até um endereço (`grpc.insecure_channel("ip:porta")`). O stub
  fala através do channel.

Fluxo: `cliente → stub.Metodo(msg) → [rede] → servicer.Metodo(msg) → resposta → [rede] → cliente`.

### Os 4 tipos de RPC (e onde stream entra)

Cada método num serviço tem uma **forma**, definida pela palavra `stream` no `.proto`:

| Forma | Assinatura no `.proto` | Significado |
|-------|------------------------|-------------|
| **Unária** | `rpc M(Req) returns (Res)` | manda 1, recebe 1. Função normal. |
| **Server-streaming** | `rpc M(Req) returns (stream Res)` | manda 1, recebe **vários** ao longo do tempo. |
| **Client-streaming** | `rpc M(stream Req) returns (Res)` | manda vários, recebe 1. |
| **Bidirecional** | `rpc M(stream Req) returns (stream Res)` | os dois lados mandam vários. |

A palavra **`stream` = "fluxo contínuo"**. Uma RPC unária é uma carta: pergunta → resposta,
acabou, conexão fecha. Uma RPC **com `stream` na resposta** é uma assinatura de jornal: você
pede **uma vez** e o servidor vai **te entregando edições** (mensagens) enquanto a conexão
fica aberta — pode ser 1, pode ser 1000, sem novo pedido a cada uma.

No nosso `.proto`, **só o `Join` usa stream**:

```proto
rpc Join(PedidoJoin) returns (stream Evento);   // server-streaming
rpc EnviarOperacao(Operacao) returns (Resposta); // unária
rpc Heartbeat(InfoMembro) returns (Resposta);    // unária
```

### Como stream aparece no código Python

No **servidor**, um método streaming **não usa `return`** — usa **`yield`**. Cada `yield`
empurra **uma** mensagem pela conexão aberta. Enquanto o método não termina, a conexão fica
viva:

```python
def Join(self, pedido, contexto):
    fila = registrar_membro(...)
    while contexto.is_active():     # enquanto cliente conectado
        evento = fila.get()
        yield evento                # << empurra UM Evento; conexao segue aberta
```

No **cliente**, uma RPC streaming **devolve um iterador** — você faz `for` nela, e o laço
**bloqueia esperando** o próximo item chegar pela rede:

```python
for evento in stub.Join(PedidoJoin(membro=self.info)):
    aplicar(evento)   # roda toda vez que o coordenador faz um yield
# o for so termina quando a stream fecha (coordenador morreu/saiu)
```

Compare com uma unária, que retorna **um valor só** e segue em frente:

```python
resposta = stub.EnviarOperacao(op)   # 1 ida, 1 volta, acabou
```

### Mensagens-chave

- **`Objeto`** — um sdesenho: `id`, `tipo` (`LINHA`/`QUADRADO`), `pontos` (lista de
  `Ponto{x,y}` — 2 pontos), `cor`, `dono`. O `id` é dado pelo Coordenador.
- **`InfoMembro`** — `(id_cliente, ip, porta)`. Identifica um nó. O `ip:porta` aponta para
  o servidor gRPC daquele nó (é assim que a eleição alcança os outros).
- **`InfoQuadro`** — `(nome, ip, porta)`. O que o Serviço de Nomes guarda: nome do quadro
  e endereço do Coordenador atual.
- **`Operacao`** — o que o cliente manda ao Coordenador: `tipo` (`CRIAR`/`COLORIR`/
  `REMOVER`), `id_cliente` (autor), e os campos conforme o tipo (`objeto`, `objeto_id`,
  `cor`).
- **`EstadoQuadro`** — *snapshot* completo: `objetos`, `membros`, `locks`
  (`map objeto_id→id_cliente`), `ultima_sequencia`. É o que um nó recebe ao entrar e o que
  semeia o novo Coordenador na migração.
- **`Evento`** — o que o Coordenador **empurra** pela stream do `Join`. Tem um `tipo`
  (`TipoEvento`) e a carga correspondente:
  - `ESTADO_INICIAL` → `estado` (snapshot) — primeiro evento ao entrar;
  - `OPERACAO` → `operacao` (`OperacaoAplicada` = `sequencia` + `operacao` + `objeto`);
  - `MEMBROS` → `membros` (lista mudou);
  - `LOCK` → `locks` (tabela de travas mudou);
  - `NOVO_COORDENADOR` → `novo_coordenador` (reservado).
- **`PedidoEleicao`** / **`AnuncioCoordenador`** — mensagens do Valentão.

### Serviços (cada um vira uma classe `*Servicer` no Python)

- **`ServicoNomes`**: `RegistrarQuadro`, `ListarQuadros`, `AtualizarQuadro`,
  `RemoverQuadro`.
- **`Coordenador`**: `Join` (**server-streaming** — retorna `stream Evento`),
  `EnviarOperacao`, `Selecionar`, `Liberar`, `Heartbeat`, `Sair`.
- **`No`**: `Eleicao`, `AnunciarCoordenador`. Hospedado por **todos** os nós.

### Por que `Join` é streaming (decore o porquê)

O problema: quando o cliente A desenha, **todos** os outros clientes precisam ver — mas o
Coordenador não sabe *quando* A vai desenhar. Os outros precisam de um jeito de **receber
novidades a qualquer momento**, sem ficar perguntando.

Duas formas de resolver:

- **Polling (ruim):** cada cliente chamaria `Listar()` unária de 100 em 100 ms perguntando
  "tem novidade?". Desperdiça rede, atrasa o desenho, escala mal.
- **Stream (o que usamos):** o cliente chama `Join` **uma vez**. O Coordenador devolve
  primeiro o `ESTADO_INICIAL` (snapshot do quadro pra quem chegou agora) e **mantém a
  conexão aberta**. Toda operação nova que qualquer um faz, o Coordenador faz `yield` na
  fila de cada cliente → chega na hora, **empurrada** (push), sem perguntar.

Então `Join` streaming faz **duas coisas numa chamada só**: (1) onboarding — o estado atual
de uma vez; (2) broadcast — o fluxo de tudo que acontece depois. E de quebra vira o
**detector de falha**: se essa stream **quebra** (o `for` termina sozinho), foi porque o
Coordenador morreu → dispara a eleição. Por isso o `Join` é o eixo do sistema todo.

---

## 2. `backend/modelo.py` — utilitário pequeno

Só duas funções. A importante:

```python
def id_no(ip: str, porta: int) -> int:
    octetos = ip.split(".")
    if len(octetos) == 4 and all(o.isdigit() for o in octetos):
        base = sum(int(o) << (8 * (3 - i)) for i, o in enumerate(octetos))
    else:
        base = abs(hash(ip)) % (1 << 32)
    return (base << 16) | (porta & 0xFFFF)
```

- Transforma `ip:porta` num **inteiro único e estável** — a prioridade do nó na eleição do
  Valentão (**maior id vence**). Precisa ser **determinístico**: todo nó calcula o mesmo id
  para o mesmo `ip:porta`, senão a eleição não fecha.

**O que cada operador faz (revisão de bits):**

- `<<` é *deslocamento à esquerda*: `x << n` = `x * 2ⁿ`. Empurra os bits para "casas mais
  altas", abrindo zeros à direita.
- `|` é *OU bit-a-bit*: junta dois números que **não se sobrepõem** em bits (encaixa um nos
  zeros do outro).
- `& 0xFFFF` *mascara* os 16 bits baixos: garante que a porta cabe em 16 bits
  (0–65535), descartando qualquer coisa acima.

**Como o IP vira 32 bits:** um IPv4 são 4 octetos (0–255 = 8 bits cada). `192.168.0.10`:

```
base = 192<<24 | 168<<16 | 0<<8 | 10
     = 192·2²⁴ + 168·2¹⁶ + 0·2⁸ + 10
```

O `sum(int(o) << (8*(3-i)) ...)` faz exatamente isso: o 1º octeto (`i=0`) desloca 24 bits, o
2º (`i=1`) 16, o 3º 8, o 4º 0. Empacota o IP num único inteiro de 32 bits.

**Depois junta a porta:** `(base << 16) | (porta & 0xFFFF)` empurra o IP mais 16 bits para
cima e encaixa a porta embaixo. Layout do id (48 bits):

```
[ 32 bits do IP ][ 16 bits da porta ]
```

- **Consequência prática (importante para o teste em 2 PCs):** como o IP fica nos bits
  **altos**, o id é **dominado pelo IP**. Entre máquinas diferentes, **quem tem o IP maior
  tem o id maior**, não importa a porta. A porta só desempata **dentro do mesmo IP** (mesma
  máquina). Por isso, no teste de 2 PCs, dá pra **prever o vencedor** da eleição olhando só
  os IPs.
- O `else` (`hash(ip)`) cobre o caso de o "ip" ser um nome de host (não-IPv4): cai num hash
  estável de 32 bits, só pra não quebrar.

---

## 3. `backend/servico_nomes.py` — as "Páginas Amarelas"

O serviço mais simples. Processo separado, endereço fixo, **nunca falha** (por enunciado),
então é uma tabela em memória protegida por um lock.

**Por que tão simples?** O enunciado garante que o Serviço de Nomes não cai. Logo **não
precisa** de replicação, persistência em disco nem eleição — luxos que o resto do sistema
tem justamente porque os Coordenadores *podem* cair. É um `dict` na RAM. Só isso.

**Modelo de concorrência (vale para os 3 servidores gRPC):** `grpc.server(
ThreadPoolExecutor(max_workers=8))` cria um **pool de 8 threads**. Cada RPC que chega é
atendida por **uma thread do pool** — então **duas chamadas rodam ao mesmo tempo**, em
threads diferentes. Se duas mexerem no `dict` `_quadros` simultaneamente (ex.: dois
`RegistrarQuadro`), há **corrida** (dado corrompido). Por isso todo acesso ao dicionário
fica dentro de `with self._trava:` — o `threading.Lock` deixa **uma thread por vez** entrar
na região crítica. `with` garante que o lock é solto mesmo se der exceção.

- `class ServicoNomesServicer`:
  - `self._quadros: dict[str, InfoQuadro]` — `nome_do_quadro → (nome, ip, porta)`.
  - `self._trava = threading.Lock()` — gRPC atende em várias threads; o lock evita corrida
    ao mexer no dicionário.
  - **`RegistrarQuadro`**: se o nome já existe, devolve `Resposta(ok=False)`; senão grava e
    devolve `ok=True`. (Impede dois quadros com o mesmo nome.)
  - **`ListarQuadros`**: devolve `ListaQuadros(quadros=list(...))`. É o que o cliente chama
    para descobrir os quadros.
  - **`AtualizarQuadro`**: sobrescreve o endereço de um quadro. Usado **após a eleição**: o
    novo Coordenador grava aqui o seu `ip:porta`.
  - **`RemoverQuadro`**: apaga o quadro (quando ele encerra).
- `def servir(porta, bloquear=True)`: cria `grpc.server(ThreadPoolExecutor(...))`, registra
  o servicer com `add_ServicoNomesServicer_to_server`, faz `add_insecure_port`, `start()`.
  `bloquear=True` chama `wait_for_termination()` (uso normal); `bloquear=False` é usado nos
  testes para subir e derrubar o servidor no mesmo processo.

> Resumo para a prova: o Serviço de Nomes só guarda **(nome, ip, porta)** dos
> Coordenadores. É um *service discovery*. Sem ele, ninguém se encontra.

---

## 4. `backend/coordenador.py` — o estado do quadro e a ordenação

Dividido em duas partes: a **classe de estado** (`EstadoCoordenador`, sem gRPC, testável) e
o **servicer** (`CoordenadorServicer`, casca gRPC que delega ao estado). Essa separação é
de propósito: o estado é **reaproveitado na migração** (o novo Coordenador cria um
`EstadoCoordenador` a partir da própria réplica).

### Conceitos novos que aparecem aqui (entenda antes)

- **`threading.RLock`** (lock *reentrante*) em vez de `Lock` comum. Diferença: um método já
  segurando o lock pode chamar **outro** método que também pega o mesmo lock, **na mesma
  thread**, sem travar a si mesmo (*deadlock*). Acontece aqui: `registrar_membro` segura a
  trava e chama `snapshot()`, que pega a trava de novo. Com `Lock` comum, congelaria; com
  `RLock`, a mesma thread reentra.
- **`queue.Queue`** — fila **thread-safe** pronta. A thread do Coordenador faz `fila.put(ev)`;
  a thread do `Join` faz `fila.get()`. Sem precisar de lock manual — a `Queue` já sincroniza.
  É a ponte entre "quem produz evento" e "quem empurra pela stream". **Uma fila por cliente.**
- **`time.monotonic()`** em vez de `time.time()` no heartbeat. `monotonic` é um relógio que
  **só anda pra frente**, imune a ajuste de horário/NTP/fuso. Para medir *"passou tempo
  demais?"* é o certo — `time.time()` poderia até **voltar** se o relógio fosse acertado, e
  derrubar membros vivos. **Por isso os relógios das 2 máquinas não precisam estar
  sincronizados.**
- **`novo.CopyFrom(o)`** — mensagens protobuf são objetos mutáveis; guardar a referência
  direta deixaria o estado mudar "pelas costas" se o remetente alterasse o objeto. `CopyFrom`
  faz **cópia profunda**, isolando o estado.
- **campo `map` (locks)** — no `.proto`, `locks` é um `map<string,string>`
  (`objeto_id → id_cliente`). No Python vira um `dict`. `dict(self._locks)` copia antes de
  difundir.

### `EstadoCoordenador` — o coração

Campos (todos sob `self._trava = threading.RLock()`):

- `_objetos: dict[id → Objeto]` — o desenho.
- `_membros: dict[id_cliente → InfoMembro]` — quem está no quadro.
- `_locks: dict[objeto_id → id_cliente]` — exclusão mútua.
- `_sequencia` — contador de ordenação (sobe a cada operação).
- `_proximo_obj` — contador de ids de objeto (`obj-1`, `obj-2`, ...).
- `_filas: dict[id_cliente → queue.Queue]` — **uma fila por cliente conectado**. É assim
  que o broadcast funciona: empurrar um `Evento` em todas as filas.
- `_ultimo_visto: dict[id_cliente → timestamp]` — para o heartbeat.

Métodos:

- **`snapshot()`** → monta um `EstadoQuadro` com cópia de objetos/membros/locks/sequência.
  É o `ESTADO_INICIAL` entregue a quem entra.
- **`de_snapshot(nome, snap)`** (classmethod) → reconstrói um `EstadoCoordenador` a partir
  de um `EstadoQuadro`. **Usado na migração.** Recalcula `_proximo_obj` pegando o maior
  `obj-N` existente, para não colidir ids depois.
- **`registrar_membro(membro)`** → adiciona o membro, cria sua fila, **coloca já o
  `ESTADO_INICIAL` na fila** e difunde a lista de membros. Retorna a fila (o `Join` vai
  consumir dela). É o *onboarding*.
- **`remover_membro(id)`** → tira o membro, sua fila, seu `ultimo_visto` e **libera as
  travas que ele segurava**; difunde a lista nova.
- **`_difundir(evento)`** → coloca o evento em **todas** as filas. Base do broadcast.
  `_difundir_membros()` e `_difundir_locks()` são atalhos para os eventos `MEMBROS`/`LOCK`.
- **`aplicar_operacao(op)`** → o método central de ordenação:
  - `CRIAR`: incrementa `_proximo_obj`, copia o objeto, dá `id = obj-N` e `dono`, guarda.
  - `COLORIR`: confere se o objeto existe **e se o autor detém a trava** (exclusão mútua);
    troca a cor; **libera a trava** depois (`lock_mudou=True`).
  - `REMOVER`: idem (precisa da trava); apaga o objeto e a trava.
  - incrementa `_sequencia`, monta `OperacaoAplicada(sequencia, operacao, objeto)` e
    **difunde** como evento `OPERACAO`. Se mexeu em trava, difunde `LOCK` também.
  - Repare: a renderização nos clientes só acontece quando esse evento volta — garante
    ordem igual em todos.
- **`selecionar(oid, id_cliente)`** → se o objeto está livre (ou já é seu), grava
  `_locks[oid]=id_cliente` e difunde `LOCK`; se está com outro, devolve `ok=False`
  (mensagem de erro). É a **exclusão mútua centralizada**.
- **`liberar(oid, id_cliente)`** → remove a trava se for sua; difunde `LOCK`.
- **Heartbeat:** `registrar_heartbeat(id)` atualiza `_ultimo_visto[id]` (cada cliente bate o
  ponto a cada `T`). `iniciar_monitor_heartbeat()` sobe uma thread *daemon* (`_loop_monitor`)
  que, a cada `T`, varre `_ultimo_visto` e remove quem passou de `FATOR_TIMEOUT * T`
  (= 2T = 4s) sem dar sinal. É a **detecção de falha centralizada** (o Coordenador detecta
  *clientes* mortos; quem detecta o *Coordenador* morto é a quebra da stream, lá no nó).
  - Detalhe do laço: `while not self._parar_monitor.wait(T_HEARTBEAT):`. O
    `Event.wait(T)` **dorme T segundos OU acorda na hora se alguém setar o Event**. Retorna
    `True` se foi setado (→ `parar` → sai do laço), `False` se só esgotou o tempo (→ faz mais
    uma rodada). Isso dá um "sleep cancelável": ao parar o monitor (migração/encerramento),
    a thread acorda **na hora**, sem esperar o T inteiro.
  - `daemon=True`: a thread não segura o processo vivo; morre junto com o programa.

### `CoordenadorServicer` — a casca gRPC

Recebe um `EstadoCoordenador` e delega:

- **`Join(pedido, contexto)`** — registra o membro (pega a fila), e:
  ```python
  contexto.add_callback(ao_encerrar)   # quando o cliente desconecta, remove o membro
  while contexto.is_active():
      try: evento = fila.get(timeout=1.0)
      except queue.Empty: continue
      yield evento                     # empurra cada evento pela stream
  ```
  O `yield` é o que transforma o método numa **stream** (ver Seção 1): cada `yield` manda um
  `Evento` ao cliente; a função **não retorna** enquanto a conexão vive.
  - `contexto` = objeto do gRPC que representa **esta** chamada/conexão.
  - `contexto.add_callback(ao_encerrar)` registra uma função que o gRPC chama **quando o
    cliente desconecta** (fechou, caiu, deu kill). É assim que o Coordenador descobre que um
    membro saiu **mesmo sem `Sair` explícito** → `remover_membro` libera locks e atualiza a
    lista.
  - `contexto.is_active()` é `True` enquanto a conexão está viva. O laço só continua
    empurrando eventos enquanto isso for verdade.
  - `fila.get(timeout=1.0)`: sem timeout, o `get` bloquearia pra sempre numa fila vazia e o
    laço **nunca reavaliaria** `is_active()` — não perceberia a desconexão. Com timeout de
    1s, a cada segundo no máximo ele acorda, vê `queue.Empty`, e **rechecа** se a conexão
    ainda vive. Mantém a stream responsiva à queda do cliente.
- `EnviarOperacao`/`Selecionar`/`Liberar`/`Heartbeat`/`Sair` → chamam o método
  correspondente do estado.

### Funções de módulo

- `servir(nome, porta)` — sobe um Coordenador standalone (usado pelos testes).
- `registrar_no_nomes(...)` / `remover_do_nomes(...)` — falam com o Serviço de Nomes.
- O bloco `__main__` permite rodar um Coordenador sozinho pela linha de comando (usado em
  testes); trata `SIGTERM`/`SIGINT` removendo o quadro do nomes na saída.

> Para a prova: o Coordenador **ordena e difunde**; o estado vive aqui mas é só uma
> réplica como qualquer outra. A separação `EstadoCoordenador` (lógica) × `Servicer`
> (rede) é o que permite a migração.

---

## 5. `backend/no.py` — o Nó (a peça que junta tudo)

Cada **processo cliente é um Nó**. Um Nó sobe **um** servidor gRPC com **dois** serviços:

- `No` (eleição) — sempre ativo;
- `Coordenador` — só responde de verdade quando este nó é o coordenador
  (`self.estado_coord is not None`); senão **rejeita** com `UNAVAILABLE`.

### Conceitos novos que aparecem aqui (entenda antes)

- **`threading.Event` como bandeira de parada (`parar`).** Um `Event` é um booleano
  thread-safe com `.set()`/`.is_set()`/`.wait(t)`. Cada conexão com um coordenador cria um
  `parar = threading.Event()`; as threads daquela conexão checam `parar.is_set()` para saber
  se devem morrer. Ao trocar de coordenador (migração), o nó faz `self._parar_conexao.set()`
  → as threads antigas se encerram **sozinhas**, sem matar thread à força (não dá pra matar
  thread em Python; o padrão é a thread se auto-encerrar olhando uma flag).
- **Por que duas threads por conexão** (`_loop_join` + `_loop_heartbeat`): a do Join fica
  **bloqueada** no `for ev in stub.Join(...)` esperando eventos chegarem (é a stream); ela
  não poderia, ao mesmo tempo, ficar mandando heartbeat de tempos em tempos. Então o
  heartbeat roda numa thread **separada**. Detecções independentes da queda → mais robusto.
- **`daemon=True`** em todas as threads: não seguram o processo vivo; somem quando o programa
  fecha.
- **`add_insecure_port("[::]:porta")`** — `[::]` é o "qualquer endereço" do **IPv6** e, como
  o socket é *dual-stack*, aceita também IPv4. Ouvir em `[::]` = aceitar conexões de
  **qualquer interface de rede** (loopback E a placa de LAN) — essencial para outra máquina
  alcançar este nó. (Se a distro for IPv4-only e isso falhar, troca-se por `"0.0.0.0:porta"`.)
- **Channel × Stub.** `grpc.insecure_channel(addr)` abre o cano TCP; `XStub(canal)` é o
  objeto com os métodos remotos. Trocar de coordenador = `canal.close()` no antigo + abrir um
  novo. "insecure" = sem TLS (rede confiável de laboratório).
- **Coordenador dinâmico (in-process).** O `_CoordenadorServicer` lê `self.no.estado_coord`
  **a cada chamada**. Enquanto for `None`, o nó está *dormente* e responde `abort(UNAVAILABLE)`.
  Quando vence uma eleição, `estado_coord` vira um `EstadoCoordenador` e o **mesmo servidor
  gRPC** passa a coordenar — **sem subir processo novo**. É isso que faz o coordenador
  "migrar" para dentro de um nó já existente.

### Os dois servicers internos

- **`_CoordenadorServicer`** — igual ao do `coordenador.py`, mas lê
  `self.no.estado_coord` dinamicamente. `_estado(contexto)`: se `estado_coord is None`,
  chama `contexto.abort(grpc.StatusCode.UNAVAILABLE, ...)` — é assim que um nó **dormente**
  recusa virar coordenador sem querer. `Join` faz o mesmo onboarding/stream do estado ativo.
- **`_NoServicer`** — `Eleicao` e `AnunciarCoordenador` chamam de volta o Nó
  (`_ao_receber_eleicao`, `_ao_receber_anuncio`).

### A classe `No`

`__init__(nomes_addr, ip, porta=0, id_cliente=None)`:
- `self.porta = porta or porta_livre()` — porta 0 escolhe uma livre (`porta_livre()` faz
  `bind(("",0))` e lê a porta do SO).
- `self.id_cliente` — string única (`no-XXXXXXXX` via `uuid`).
- `self.id = id_no(ip, porta)` — prioridade na eleição.
- réplica: `objetos`, `membros`, `locks`, `sequencia`.
- `self.estado_coord = None` — dormente; vira `EstadoCoordenador` quando coordena.
- `self.eventos = queue.Queue()` — **canal Nó → UI**. A interface lê daqui.
- `self._em_eleicao = threading.Event()` — evita disparar duas eleições juntas.
- `_iniciar_servidor()` — cria o `grpc.server`, registra os dois servicers, `add_insecure_port("[::]:porta")` (o `[::]` ouve em **todas as interfaces** — essencial para rede), `start()`.

Propriedade `info` → `InfoMembro(id_cliente, ip, porta)` (mandado no `Join` e na eleição).

#### Criar / ingressar

- **`criar_quadro(nome)`**: registra no nomes; cria `self.estado_coord =
  EstadoCoordenador(nome)`; sobe o monitor de heartbeat; chama
  `_conectar_coordenador(self.ip:self.porta)` — ou seja, **o nó vira coordenador e entra no
  próprio quadro** (conecta-se a si mesmo). Não há subprocess.
- **`ingressar(nome, endereco)`**: só conecta ao Coordenador remoto.

#### Conexão com o Coordenador (`_conectar_coordenador`)

Encerra a conexão anterior (`self._parar_conexao.set()` + fecha o canal — **sem** disparar
eleição, porque a troca é intencional), cria `grpc.insecure_channel(endereco)` e
`CoordenadorStub`, e sobe **duas threads**:

- **`_loop_join(stub, parar)`**:
  ```python
  for ev in stub.Join(PedidoJoin(membro=self.info)):
      if parar.is_set(): return
      self._aplicar_evento_replica(ev)   # atualiza a réplica do Nó
      self.eventos.put(ev)               # manda para a UI desenhar
  # se a stream caiu sem ser troca intencional -> o coordenador caiu:
  if not parar.is_set() and not self._encerrado:
      self._gatilho_queda_coordenador()
  ```
  É a stream do broadcast **e** o detector de queda (se ela quebra, o Coordenador morreu).
- **`_loop_heartbeat(stub, parar)`**: a cada `T_HEARTBEAT`, chama `stub.Heartbeat(self.info)`.
  Se falhar (`RpcError`), também chama `_gatilho_queda_coordenador()`. Dupla detecção.

`_aplicar_evento_replica(ev)` mantém a réplica do Nó sincronizada (objetos/membros/locks/
sequência) — separada da renderização da UI. **Essa réplica é o que semeia o novo
Coordenador na migração.**

`_snapshot_replica()` monta um `EstadoQuadro` da réplica, **excluindo o coordenador morto**
(o membro cujo `ip:porta` == `coord_addr`).

#### Operações (UI → Coordenador)

`enviar_operacao(op)`, `selecionar(oid)`, `liberar(oid)` — só chamam o `_coord_stub`
correspondente. Simples repasses.

#### Eleição do Valentão (a parte que vale nota)

- **`_gatilho_queda_coordenador()`** — avisa a UI (`COORD_CAIU`) e dispara
  `_iniciar_eleicao()` numa thread.
- **`_iniciar_eleicao()`**:
  1. trava com `self._em_eleicao` (não duplica).
  2. monta `maiores` = membros com `id_no(ip,porta) > self.id` (exceto eu e o coord morto).
  3. para cada um, chama `NoStub(...).Eleicao(PedidoEleicao(id=self.id, membro=info))` com
     `timeout=TIMEOUT_ELEICAO`. Se **algum** responde `ok` → existe um nó maior vivo →
     **recuo** e agendo `_retentar_se_preciso` (Timer) caso o anúncio não chegue.
  4. se **ninguém** responde → **eu venço** → `_virar_coordenador()`.
- **`_ao_receber_eleicao(pedido)`** — alguém de id menor me chamou; respondo `ok` ("estou
  vivo") **e começo minha própria eleição** (tenho id maior, sou candidato melhor). É o
  comportamento clássico do Valentão.
- **`_virar_coordenador()`**:
  1. `snap = self._snapshot_replica()` (sem o coord morto).
  2. `self.estado_coord = EstadoCoordenador.de_snapshot(nome, snap)` — assume com o estado
     replicado; sobe monitor de heartbeat.
  3. `_atualizar_nomes()` → `AtualizarQuadro` grava o meu `ip:porta` no Serviço de Nomes.
  4. envia `AnunciarCoordenador` para cada outro membro (serviço `No` de cada um).
  5. `_conectar_coordenador(self.ip:self.porta)` — reconecto a mim mesmo como cliente.
  6. avisa a UI (`VIREI_COORDENADOR`).
- **`_ao_receber_anuncio(anuncio)`** — recebo "o novo coordenador é fulano"; limpo
  `_em_eleicao`; `_conectar_coordenador(novo)` — reconecto ao vencedor; aviso a UI
  (`NOVO_COORDENADOR`). O novo `Join` me devolve um `ESTADO_INICIAL` fresco.

> **Por que o Valentão sempre termina com UM vencedor:** todo nó que entra na eleição
> pergunta só aos de **id maior**. Quem não tem ninguém maior vivo se declara coordenador.
> Como os ids são únicos e finitos, **existe um maior id vivo** — e é ele quem acaba
> assumindo (ninguém acima responde a ele). Os `timeout` (`TIMEOUT_ELEICAO`) tratam os nós
> mortos como "não respondeu". O `ESPERA_ANUNCIO` + `_retentar_se_preciso` é a rede de
> segurança: se o "maior vivo" que eu achei também cair **durante** a eleição e nunca
> anunciar, eu refaço a eleição em vez de travar.

#### Saída × queda (modelo de falha)

- **`sair()`** (botão Sair, saída graciosa): manda `Sair` ao Coordenador. **Se eu sou o
  coordenador:** se ainda há outros membros, **continuo hospedando** (não derrubo
  `estado_coord`, sem eleição — como o enunciado pede); se estou **sozinho**, encerro o
  quadro (`remover_do_nomes`, paro o monitor, `estado_coord=None`).
- **`encerrar()`** (fechar a janela / desligar): `self._encerrado=True`, paro as threads. Se
  sou coordenador e estou **sozinho**, removo o quadro do nomes; se há outros, **apenas
  paro** — os sobreviventes detectam e elegem (isto é o caminho "cai").

> Para a prova, saber distinguir:
> - **stream do Join quebra / heartbeat falha** ⇒ Coordenador caiu ⇒ eleição.
> - **`sair()`** é graciosa (mensagem `Sair`); **`encerrar()`/kill** é queda.
> - na migração, **nada se perde** porque o vencedor já tinha a réplica.

---

## 6. `frontend/cliente.py` — a interface (Tkinter)

Camada **fina** sobre um `No`. Ela **não fala gRPC**; só:

- chama métodos do Nó para ações do usuário;
- consome `self.no.eventos` para desenhar.

### Conceitos novos que aparecem aqui (entenda antes)

- **Tkinter NÃO é thread-safe.** Só a thread que rodou `mainloop()` pode tocar em widgets
  (Canvas, Label...). As threads de rede do Nó (`_loop_join`, tarefas de operação) **nunca**
  desenham direto — colocam na fila `no.eventos`. Quem desenha é sempre a thread da UI. Tocar
  o Canvas de outra thread trava/quebra o Tk.
- **`raiz.after(50, fn)`** — agenda `fn` para rodar **na thread da UI** daqui a 50 ms.
  `_consumir_eventos` se reagenda no fim → vira um *poll* de 20×/s que esvazia a fila e
  desenha. É a ponte segura "thread de rede → tela".
- **`fila.get_nowait()` em laço** — drena **todos** os eventos acumulados desde o último tick
  (não só um), até estourar `queue.Empty`. Sem bloquear a UI.
- **RPC sai sempre numa thread** (`_operar`, `tarefa()` em `_selecionar_no_ponto`). Chamadas
  gRPC **bloqueiam** até a resposta; se rodassem na thread da UI, a janela **congelaria**.
  Então a ação dispara `threading.Thread(...)`, e o **resultado** volta pela fila via
  `_post(...)` (que é só `eventos.put((tipo, dados))`). Mesmo padrão de ponte.
- **Tags do Canvas.** Cada item desenhado recebe `tags=obj.id`. Assim, dado um clique,
  `canvas.find_closest(x,y)` acha o item e `gettags` recupera **qual objeto** é — a ponte
  entre "pixel clicado" e "id lógico do objeto".

Pontos a saber:

- `__init__` cria `self.no = No(...)`, prepara dicionários de render
  (`objetos`, `itens_canvas` = `objeto_id → id do item no Canvas`), e agenda
  `self.raiz.after(50, self._consumir_eventos)` — um *poll* a cada 50 ms (Tkinter **não é
  thread-safe**, então a thread de rede só **enfileira**; quem mexe na tela é sempre a
  thread principal, aqui).
- **Tela inicial** (`_montar_tela_inicial`): campo do Serviço de Nomes, botão **Criar
  quadro** (`_criar_quadro` → `no.criar_quadro`), lista de quadros (`no.listar_quadros`) e
  **Ingressar** (`no.ingressar`).
- **Tela do quadro** (`_montar_tela_quadro`): botões Linha, Quadrado, Selecionar, Vermelho,
  Azul, Remover, Sair; um `Canvas`; e uma barra de status.
- **`_consumir_eventos`**: lê a fila do Nó. Se vier uma tupla (`"STATUS"`, `"COORD_CAIU"`,
  `"VIREI_COORDENADOR"`, `"NOVO_COORDENADOR"`, ...), é um aviso interno → atualiza a status
  bar. Se vier um `Evento` protobuf, chama `_aplicar_evento`.
- **`_aplicar_evento`**: traduz o evento em desenho:
  - `ESTADO_INICIAL` → reconstrói `objetos`, redesenha tudo, aplica travas.
  - `OPERACAO` → `_aplicar_operacao` (CRIAR desenha, COLORIR recolore, REMOVER apaga).
  - `MEMBROS` → atualiza contador.
  - `LOCK` → `_aplicar_locks` (destaque visual das travas).
- **Desenho** usa as funções do Canvas: `create_line`, `create_rectangle`, `itemconfig`
  (recolorir / mudar espessura), `delete` (remover), `tags` (cada item recebe o `objeto_id`
  como tag, para achar de volta).
- **Selecionar** (`_selecionar_no_ponto`): `canvas.find_closest(x,y)` acha o item clicado,
  `gettags` recupera o `objeto_id`, e chama `no.selecionar(oid)` numa thread. Se o
  Coordenador recusar (objeto travado por outro), mostra erro.
- **`_aplicar_locks`**: meu lock → traço grosso (`width=4`); lock de outro → tracejado
  (`dash=(4,3)`); livre → normal. Vem do evento `LOCK`, então **todos** veem quem está
  mexendo no quê.
- **Regra de ouro respeitada:** desenhar **não** pinta na hora — chama
  `no.enviar_operacao` e espera o evento `OPERACAO` voltar. Por isso o desenho aparece
  igual em todas as telas e na ordem certa.
- **`principal()`**: lê argumentos (`--nomes`, `--ip`, `--porta`), cria a janela e o App, e
  instala handlers de `SIGTERM`/`SIGINT` que chamam `no.encerrar()` — para `pkill`/`kill`
  não deixarem coordenador órfão.

---

## 7. Testes (`backend/teste_fumaca_*.py` + `rodar_testes.py`)

Cada teste sobe os serviços em processo, exercita um pedaço e usa `assert`. São a sua
**rede de segurança** e provam os cenários do enunciado:

- `teste_fumaca_nomes.py` — registrar/listar/atualizar/remover do Serviço de Nomes.
- `teste_fumaca_quadro.py` — **Cenário 1**: descoberta, onboarding (B entra e vê o que A
  desenhou), ordenação (`seq=1`), broadcast.
- `teste_fumaca_ops.py` — colorir/remover individual e **convergência** (C entra depois e
  vê o estado já consistente).
- `teste_fumaca_exclusao.py` — **Cenário 2**: A trava, B não consegue travar nem operar; A
  opera e libera; aí B consegue.
- `teste_fumaca_eleicao.py` — **Cenário 3**: A (coordenador) cai; B e C elegem; o maior id
  (C) assume, atualiza o nomes, preserva o objeto; B reconecta e opera.
- `rodar_testes.py` — roda todos em sequência e mostra `5/5 passaram`.

Rodar tudo:

```bash
cd backend && python rodar_testes.py
```

---

## Roteiro de 60 segundos para a banca

1. "É uma **máquina de estado replicada**: todo nó tem o quadro inteiro; o Coordenador só
   **ordena e difunde**."
2. "Descoberta pelo **Serviço de Nomes** (nome→ip:porta). Entrada via **`Join` streaming**:
   recebo o estado e fico ouvindo o broadcast."
3. "**Exclusão mútua centralizada**: travo o objeto no Coordenador antes de colorir/remover;
   se outro já travou, dá erro."
4. "**Falhas**: heartbeat a cada T; se passar de 2T some da lista. Se a stream/heartbeat com
   o Coordenador cai, é que **ele** morreu → **eleição do Valentão** (maior id vence) →
   novo Coordenador **já tem a réplica**, atualiza o nomes, todos reconectam."
5. "**2PC ficou fora** porque a seção está riscada no enunciado."
