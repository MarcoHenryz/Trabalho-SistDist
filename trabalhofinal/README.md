# SDWB — Shared Distributed Write Board

Quadro branco distribuído: vários nós colaboram em tempo real, sem servidor fixo.
Descoberta via **Serviço de Nomes**; ordenação/consistência via **Coordenador migrante**
(um dos próprios nós). Python 3 + gRPC + Tkinter.

> Escopo: 2PC (transações distribuídas) foi removido — seção riscada no enunciado oficial.

## Dependências

```bash
pip install grpcio grpcio-tools
```

`tkinter` vem na stdlib (no Arch: `sudo pacman -S tk` se faltar).

## Gerar stubs (após editar `backend/sdwb.proto`)

```bash
cd backend
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. sdwb.proto
```

Nunca edite os `*_pb2.py` gerados; só o `.proto`.

## Subir o sistema (uma máquina, várias portas)

1. Serviço de Nomes (endereço fixo, nunca falha):

   ```bash
   cd backend && python servico_nomes.py            # porta 50000
   ```

2. Cliente (interface). Cada cliente é um nó com servidor gRPC próprio:

   ```bash
   cd frontend && python cliente.py                 # porta do nó: livre/automática
   cd frontend && python cliente.py --porta 60001   # porta fixa, p/ demos
   ```

   - **Criar novo quadro**: o próprio nó passa a hospedar o Coordenador (in-process) e ingressa nele.
   - **Ingressar**: lista os quadros do Serviço de Nomes e conecta ao Coordenador escolhido.

Para vários participantes, abra vários `python cliente.py` (portas distintas).
O Coordenador é **migrante**: se o nó que o hospeda cai, os sobreviventes
elegem um novo (algoritmo do Valentão) e o estado replicado é preservado.

## Demonstrar tolerância a falhas

1. Suba o Serviço de Nomes e ≥3 clientes; um deles cria o quadro.
2. **Matar o coordenador** (queda): `kill -9 <pid do cliente que criou>` ou feche
   bruscamente. Os demais detectam (heartbeat/stream), elegem o de maior ID, que
   atualiza o Serviço de Nomes — o quadro continua operando.

## Testes de fumaça

```bash
cd backend
python teste_fumaca_nomes.py     # Serviço de Nomes: registrar/listar/atualizar/remover
python teste_fumaca_quadro.py    # descoberta, onboarding, ordenação, broadcast, lock
python teste_fumaca_ops.py       # colorir/remover individual + convergência de réplicas
python teste_fumaca_exclusao.py  # exclusão mútua (locks por objeto)
python teste_fumaca_eleicao.py   # morte do coordenador -> eleição do Valentão + migração
```
