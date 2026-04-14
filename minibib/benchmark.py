"""Benchmark — mede tempos de resposta com clientes simultâneos."""

import argparse
import statistics
import threading
import time

import grpc
import minibib_pb2
import minibib_pb2_grpc


def medir_busca(stub, topico, resultados: list):
    inicio = time.perf_counter()
    stub.Buscar(minibib_pb2.BuscaRequest(topico=topico))
    tempo = (time.perf_counter() - inicio) * 1000
    resultados.append(tempo)


def medir_compra(stub, numero_item, resultados: list):
    inicio = time.perf_counter()
    stub.Comprar(minibib_pb2.CompraRequest(numero_item=numero_item))
    tempo = (time.perf_counter() - inicio) * 1000
    resultados.append(tempo)


def executar_concorrente(endereco_frontend: str, operacao: str, n_clientes: int, arg):
    canais = [grpc.insecure_channel(endereco_frontend) for _ in range(n_clientes)]
    stubs = [minibib_pb2_grpc.ServicoFrontEndStub(ch) for ch in canais]

    resultados = []
    threads = []

    for i in range(n_clientes):
        if operacao == "search":
            t = threading.Thread(target=medir_busca, args=(stubs[i], arg, resultados))
        else:
            t = threading.Thread(target=medir_compra, args=(stubs[i], int(arg), resultados))
        threads.append(t)

    inicio_total = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    total = (time.perf_counter() - inicio_total) * 1000

    return resultados, total


def main():
    parser = argparse.ArgumentParser(description="Benchmark Minibib")
    parser.add_argument("--frontend", type=str, default="localhost:50053")
    parser.add_argument("--op", choices=["search", "buy"], required=True, help="Operação a testar")
    parser.add_argument("--arg", type=str, required=True, help="Argumento (tópico ou numero_item)")
    parser.add_argument("--clientes", type=int, nargs="+", default=[1, 5, 10],
                        help="Números de clientes simultâneos")
    parser.add_argument("--rodadas", type=int, default=5, help="Rodadas por configuração")
    args = parser.parse_args()

    print(f"Benchmark: {args.op}({args.arg})")
    print(f"Rodadas por configuração: {args.rodadas}")
    print("-" * 60)

    for n in args.clientes:
        todos_tempos = []
        for r in range(args.rodadas):
            resultados, _ = executar_concorrente(args.frontend, args.op, n, args.arg)
            todos_tempos.extend(resultados)

        media = statistics.mean(todos_tempos)
        minimo = min(todos_tempos)
        maximo = max(todos_tempos)
        desvio = statistics.stdev(todos_tempos) if len(todos_tempos) > 1 else 0.0

        print(f"  {n:>3} clientes | média: {media:7.2f} ms | mín: {minimo:7.2f} ms | máx: {maximo:7.2f} ms | desvio: {desvio:6.2f} ms")

    print("-" * 60)


if __name__ == "__main__":
    main()
