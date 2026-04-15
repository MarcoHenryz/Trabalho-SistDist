# Minibib.com

Sistema distribuído de livraria online com gRPC em Python.

## Como Executar

Instalar dependências:

```bash
pip install grpcio grpcio-tools
```

Regenerar stubs (opcional, já estão inclusos):

```bash
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. minibib.proto
```

Subir os servidores (cada um em um terminal separado):

```bash
# Terminal 1
python servidor_catalogo.py -p 50051

# Terminal 2
python servidor_pedidos.py -p 50052 --catalogo localhost:50051

# Terminal 3
python servidor_frontend.py -p 50053 --catalogo localhost:50051 --pedidos localhost:50052
```

Rodar o cliente:

```bash
python cliente.py --frontend localhost:50053
```

Para máquinas separadas, substituir `localhost` pelo IP correspondente.

---

## 1. Decisões de Projeto

### Estrutura de dados do catálogo

O catálogo é um dicionário Python (`dict`) indexado pelo número do item (`int`). Essa estrutura foi escolhida por oferecer acesso em tempo O(1) para `ConsultaPorItem` e `Atualizar`, que são as operações mais frequentes (chamadas por toda compra). A busca por tópico (`ConsultaPorTopico`) percorre todos os itens em O(n), o que é aceitável dado o tamanho reduzido do catálogo. Uma estrutura secundária (e.g., índice por tópico) poderia acelerar buscas, mas adicionaria complexidade desnecessária para o escopo do projeto.

### Design de concorrência

A concorrência é tratada em duas camadas independentes:

**Camada 1 — Leituras paralelas:** O servidor gRPC Python usa `ThreadPoolExecutor(max_workers=10)`, o que permite que múltiplas requisições `search` e `lookup` sejam processadas simultaneamente sem bloqueio. O `threading.Lock` no `ServidorCatalogo` protege apenas as escritas no dicionário, e é adquirido por tempo mínimo, garantindo baixa contenção em leituras.

**Camada 2 — Serialização de compras:** O `ServidorPedidos` usa um único `threading.Lock` (`lock_compra`) que engloba o par _verificar estoque → decrementar_, tornando essa operação atômica. Isso impede que dois clientes simultâneos comprem a última cópia de um livro (race condition clássico). Como segunda barreira de segurança, o `ServidorCatalogo` também recusa qualquer atualização que resultaria em estoque negativo.

### Proto único

Todos os serviços (`ServicoCatalogo`, `ServicoPedidos`, `ServicoFrontEnd`) foram definidos em um único arquivo `minibib.proto`. Isso simplifica a geração de stubs (um único comando `protoc`) e garante que todas as mensagens compartilhadas (como `InfoLivro` e `CompraReply`) sejam consistentes entre os serviços.

### Canais gRPC no ServidorPedidos

O `ServidorPedidos` cria um novo canal para o catálogo a cada requisição (`_obter_stub_catalogo`). Isso evita problemas de estado compartilhado entre threads concorrentes e é funcional para o volume de carga esperado. Em um sistema de produção, seria preferível usar um canal persistente com pool de conexões.

---

## 2. Resultados Experimentais

Os tempos foram medidos no cliente com `time.perf_counter()` imediatamente antes e após cada chamada gRPC, capturando o round-trip completo (serialização + rede + processamento + desserialização). Todos os testes foram executados com todos os componentes na mesma máquina (localhost), o que elimina latência de rede real — tempos reais em máquinas separadas seriam maiores dependendo da infraestrutura.

Para os testes com múltiplos clientes simultâneos, o script `benchmark.py` cria N threads com canais gRPC independentes e as dispara ao mesmo tempo com `thread.start()`, medindo o tempo de cada thread individualmente.

### Cliente único (20 rodadas para search, 10 para buy)

| Operação | Média    | Mínimo  | Máximo   | Desvio padrão |
| -------- | -------- | ------- | -------- | ------------- |
| `search` | 1,59 ms  | 1,30 ms | 1,96 ms  | 0,15 ms       |
| `buy`    | 11,67 ms | 4,25 ms | 17,20 ms | 4,20 ms       |

O `buy` é consistentemente mais lento que o `search` porque envolve duas chamadas gRPC internas (uma `ConsultaPorItem` + uma `Atualizar`) e a aquisição do lock de serialização.

### Múltiplos clientes simultâneos

Os benchmarks abaixo foram coletados com o script `benchmark.py`:

```bash
python benchmark.py --op search --arg "sistemas distribuidos" --clientes 1 5 10 --rodadas 5
python benchmark.py --op buy --arg 1 --clientes 1 5 10 --rodadas 5
```

**Search:**

| Clientes | Média    | Mínimo  | Máximo   | Desvio padrão |
| -------- | -------- | ------- | -------- | ------------- |
| 1        | 1,59 ms  | 1,30 ms | 1,96 ms  | 0,15 ms       |
| 5        | 6,10 ms  | 5,42 ms | 6,77 ms  | 0,61 ms       |
| 10       | 28,63 ms | 7,37 ms | 74,93 ms | 31,31 ms      |

**Buy:**

| Clientes | Média    | Mínimo   | Máximo    | Desvio padrão |
| -------- | -------- | -------- | --------- | ------------- |
| 1        | 11,67 ms | 4,25 ms  | 17,20 ms  | 4,20 ms       |
| 5        | 18,26 ms | 9,91 ms  | 25,20 ms  | 6,23 ms       |
| 10       | 69,95 ms | 27,28 ms | 101,07 ms | 29,35 ms      |

**Análise:** O tempo de `search` escala de forma razoável até 5 clientes, mas apresenta alta variância com 10 clientes simultâneos (desvio de 31 ms), indicando contenção no ThreadPoolExecutor. O `buy` com 10 clientes tem tempo médio ~6× maior que com 1 cliente, refletindo diretamente o efeito do lock de serialização: cada thread espera as anteriores completarem o par consulta→decremento antes de prosseguir. O alto desvio padrão em ambos os casos com 10 clientes é esperado em testes de localhost, onde o escalonador do sistema operacional influencia a ordem de execução das threads.

### Teste em máquinas separadas

Para validar o sistema em um ambiente distribuído real, os servidores de catálogo e pedidos foram executados em uma máquina com Arch Linux (`192.168.0.193`), enquanto o servidor front-end, o cliente e o benchmark foram executados em uma máquina Windows com WSL/Ubuntu (`192.168.0.62`), ambas conectadas na mesma rede local via cabo Ethernet e Wi-Fi.

```bash
# Arch (192.168.0.193)
python servidor_catalogo.py -p 50051
python servidor_pedidos.py -p 50052 --catalogo localhost:50051

# Windows/WSL (192.168.0.62)
python servidor_frontend.py -p 50053 --catalogo 192.168.0.193:50051 --pedidos 192.168.0.193:50052
python benchmark.py --op search --arg "sistemas distribuidos" --clientes 1 5 10
python benchmark.py --op buy --arg 1 --clientes 1 5 10
```

**Search (máquinas separadas):**

| Clientes | Média    | Mínimo  | Máximo   | Desvio padrão |
| -------- | -------- | ------- | -------- | ------------- |
| 1        | 11,07 ms | 5,60 ms | 27,22 ms | 9,16 ms       |
| 5        | 9,04 ms  | 4,84 ms | 12,06 ms | 1,97 ms       |
| 10       | 9,01 ms  | 4,42 ms | 13,81 ms | 2,02 ms       |

**Buy (máquinas separadas):**

| Clientes | Média    | Mínimo   | Máximo   | Desvio padrão |
| -------- | -------- | -------- | -------- | ------------- |
| 1        | 30,07 ms | 19,19 ms | 49,76 ms | 12,87 ms      |
| 5        | 12,38 ms | 6,92 ms  | 20,76 ms | 3,54 ms       |
| 10       | 15,26 ms | 7,20 ms  | 24,86 ms | 4,71 ms       |

**Análise:** Com máquinas separadas, o `search` com 1 cliente apresenta tempo médio de ~11 ms contra ~1,6 ms em localhost, refletindo a latência de rede adicionada pela comunicação entre as máquinas. Os tempos com 5 e 10 clientes se mantêm estáveis (~9 ms), o que sugere que o gRPC reaproveita conexões de forma eficiente e a latência de rede domina sobre a contenção de threads. No `buy`, o tempo com 1 cliente (~30 ms) é maior porque envolve duas chamadas gRPC que atravessam a rede (frontend→catálogo para consulta e frontend→pedidos→catálogo para atualização). Os tempos com múltiplos clientes ficaram menores que com 1 cliente, provavelmente porque conexões subsequentes reutilizam canais já estabelecidos (warm-up do gRPC).
