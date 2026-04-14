"""Cliente CLI — interface interativa para a Minibib.com."""

import argparse
import time

import grpc
import minibib_pb2
import minibib_pb2_grpc


def executar(endereco_frontend: str):
    canal = grpc.insecure_channel(endereco_frontend)
    stub = minibib_pb2_grpc.ServicoFrontEndStub(canal)

    print("=" * 50)
    print("  Minibib.com — A menor livraria online do mundo")
    print("=" * 50)
    print()
    print("Comandos disponíveis:")
    print("  search <tópico>           — busca livros por tópico")
    print("  lookup <numero_item>      — detalhes de um livro")
    print("  buy <numero_item>         — compra um livro")
    print("  quit                      — encerrar")
    print()

    while True:
        try:
            entrada = input("minibib> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAté mais!")
            break

        if not entrada:
            continue

        partes = entrada.split(maxsplit=1)
        comando = partes[0].lower()
        argumento = partes[1] if len(partes) > 1 else ""

        if comando in ("quit", "exit", "sair"):
            print("Até mais!")
            break

        elif comando == "search":
            if not argumento:
                print("Uso: search <tópico>")
                continue
            inicio = time.perf_counter()
            try:
                resp = stub.Buscar(minibib_pb2.BuscaRequest(topico=argumento))
                tempo = (time.perf_counter() - inicio) * 1000
                if resp.numeros_itens:
                    print(f"Itens encontrados para '{argumento}': {list(resp.numeros_itens)}")
                else:
                    print(f"Nenhum item encontrado para o tópico '{argumento}'.")
                print(f"  (tempo: {tempo:.2f} ms)")
            except grpc.RpcError as e:
                print(f"Erro: {e.details()}")

        elif comando == "lookup":
            if not argumento:
                print("Uso: lookup <numero_item>")
                continue
            try:
                numero = int(argumento)
            except ValueError:
                print("numero_item deve ser um inteiro.")
                continue
            inicio = time.perf_counter()
            try:
                livro = stub.Consultar(minibib_pb2.ConsultaRequest(numero_item=numero))
                tempo = (time.perf_counter() - inicio) * 1000
                print(f"  Item:    {livro.numero_item}")
                print(f"  Nome:    {livro.nome}")
                print(f"  Tópico:  {livro.topico}")
                print(f"  Estoque: {livro.estoque}")
                print(f"  (tempo: {tempo:.2f} ms)")
            except grpc.RpcError as e:
                print(f"Erro: {e.details()}")

        elif comando == "buy":
            if not argumento:
                print("Uso: buy <numero_item>")
                continue
            try:
                numero = int(argumento)
            except ValueError:
                print("numero_item deve ser um inteiro.")
                continue
            inicio = time.perf_counter()
            try:
                resp = stub.Comprar(minibib_pb2.CompraRequest(numero_item=numero))
                tempo = (time.perf_counter() - inicio) * 1000
                status = "✓" if resp.sucesso else "✗"
                print(f"  [{status}] {resp.mensagem}")
                print(f"  (tempo: {tempo:.2f} ms)")
            except grpc.RpcError as e:
                print(f"Erro: {e.details()}")

        else:
            print(f"Comando desconhecido: '{comando}'. Use: search, lookup, buy, quit.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cliente Minibib")
    parser.add_argument("--frontend", type=str, default="localhost:50053",
                        help="Endereço do front-end (padrão: localhost:50053)")
    args = parser.parse_args()
    executar(args.frontend)
