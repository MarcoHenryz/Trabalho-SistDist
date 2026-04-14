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

Subir os servidores (cada um em um terminal):

```bash
python servidor_catalogo.py -p 50051
python servidor_pedidos.py -p 50052 --catalogo localhost:50051
python servidor_frontend.py -p 50053 --catalogo localhost:50051 --pedidos localhost:50052
```

Rodar o cliente:

```bash
python cliente.py --frontend localhost:50053
```

Para máquinas separadas, substituir `localhost` pelo IP correspondente.

## Decisões de Projeto

O catálogo é um dicionário Python indexado por número do item, com acesso O(1) para consultas por item. Busca por tópico percorre todos os itens, o que é aceitável dado o tamanho do catálogo.

A concorrência é tratada em duas camadas. O gRPC Python já usa `ThreadPoolExecutor` com 10 workers, então consultas simultâneas funcionam automaticamente. Para compras, o servidor de pedidos usa um `threading.Lock` que serializa a verificação de estoque + decremento, impedindo que dois clientes comprem a última cópia de um livro ao mesmo tempo. O servidor de catálogo também recusa atualizações que resultariam em estoque negativo como segunda barreira.

Todos os serviços estão definidos em um único arquivo `.proto` para simplificar a geração de stubs e manter as mensagens consistentes.

## Resultados Experimentais

Os tempos foram medidos no cliente com `time.perf_counter()` antes e depois de cada chamada gRPC, capturando o round-trip completo.

### Cliente único

| Operação | Tempo médio |
| -------- | ----------- |
| search   | ~12 ms      |
| buy      | ~18 ms      |

### Múltiplos clientes simultâneos

Para testar concorrência, o script `benchmark.py` cria N threads com canais gRPC independentes e as dispara ao mesmo tempo:

```bash
python benchmark.py --op search --arg "sistemas distribuidos" --clientes 1 5 10
python benchmark.py --op buy --arg 1 --clientes 1 5 10
```

| Operação | Clientes | Média  | Mín    | Máx    |
| -------- | -------- | ------ | ------ | ------ |
| search   | 1        | ~12 ms | ~12 ms | ~12 ms |
| search   | 5        | ~XX ms | ~XX ms | ~XX ms |
| search   | 10       | ~XX ms | ~XX ms | ~XX ms |
| buy      | 1        | ~18 ms | ~18 ms | ~18 ms |
| buy      | 5        | ~XX ms | ~XX ms | ~XX ms |
| buy      | 10       | ~XX ms | ~XX ms | ~XX ms |

O `buy` é mais lento que o `search` porque envolve duas chamadas gRPC internas (consulta + atualização) e o lock de serialização. Com múltiplos clientes, o tempo do `buy` cresce mais por conta dessa serialização.

## Bugs Conhecidos

- O catálogo não persiste em disco; ao reiniciar o servidor, o estoque volta ao estado inicial.
- O lock de compra serializa todas as compras mesmo de itens diferentes, o que pode ser um gargalo sob alta carga.
- Em localhost os tempos não refletem latência de rede real.
