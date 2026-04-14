"""Script de teste — sobe servidores, testa operações, derruba tudo."""

import subprocess
import sys
import time

import grpc
import minibib_pb2
import minibib_pb2_grpc

PORTA_CATALOGO = 50051
PORTA_PEDIDOS = 50052
PORTA_FRONTEND = 50053


def aguardar_porta(porta, timeout=5):
    """Tenta conectar até o servidor estar pronto."""
    import socket
    limite = time.time() + timeout
    while time.time() < limite:
        try:
            s = socket.create_connection(("localhost", porta), timeout=0.5)
            s.close()
            return True
        except OSError:
            time.sleep(0.2)
    return False


def main():
    processos = []
    try:
        # 1. Sobe catálogo
        p1 = subprocess.Popen([sys.executable, "servidor_catalogo.py", "-p", str(PORTA_CATALOGO)])
        processos.append(p1)
        assert aguardar_porta(PORTA_CATALOGO), "Catálogo não subiu"
        print("[OK] Servidor de catálogo rodando")

        # 2. Sobe pedidos
        p2 = subprocess.Popen([sys.executable, "servidor_pedidos.py", "-p", str(PORTA_PEDIDOS),
                                "--catalogo", f"localhost:{PORTA_CATALOGO}"])
        processos.append(p2)
        assert aguardar_porta(PORTA_PEDIDOS), "Pedidos não subiu"
        print("[OK] Servidor de pedidos rodando")

        # 3. Sobe frontend
        p3 = subprocess.Popen([sys.executable, "servidor_frontend.py", "-p", str(PORTA_FRONTEND),
                                "--catalogo", f"localhost:{PORTA_CATALOGO}",
                                "--pedidos", f"localhost:{PORTA_PEDIDOS}"])
        processos.append(p3)
        assert aguardar_porta(PORTA_FRONTEND), "Frontend não subiu"
        print("[OK] Servidor front-end rodando")

        # 4. Conecta como cliente
        canal = grpc.insecure_channel(f"localhost:{PORTA_FRONTEND}")
        stub = minibib_pb2_grpc.ServicoFrontEndStub(canal)

        print("\n--- Testes ---")

        # buscar
        t0 = time.perf_counter()
        resp = stub.Buscar(minibib_pb2.BuscaRequest(topico="sistemas distribuidos"))
        dt = (time.perf_counter() - t0) * 1000
        print(f"buscar('sistemas distribuidos') = {list(resp.numeros_itens)}  ({dt:.2f} ms)")

        # consultar
        t0 = time.perf_counter()
        livro = stub.Consultar(minibib_pb2.ConsultaRequest(numero_item=1))
        dt = (time.perf_counter() - t0) * 1000
        print(f"consultar(1) = {livro.nome} | topico={livro.topico} | estoque={livro.estoque}  ({dt:.2f} ms)")

        # comprar
        t0 = time.perf_counter()
        resp_compra = stub.Comprar(minibib_pb2.CompraRequest(numero_item=1))
        dt = (time.perf_counter() - t0) * 1000
        print(f"comprar(1) = sucesso={resp_compra.sucesso} | {resp_compra.mensagem}  ({dt:.2f} ms)")

        # consultar de novo (estoque decrementado)
        livro2 = stub.Consultar(minibib_pb2.ConsultaRequest(numero_item=1))
        print(f"consultar(1) após compra: estoque={livro2.estoque} (era {livro.estoque})")

        # comprar item inexistente
        resp_compra2 = stub.Comprar(minibib_pb2.CompraRequest(numero_item=999))
        print(f"comprar(999) = sucesso={resp_compra2.sucesso} | {resp_compra2.mensagem}")

        # buscar tópico inexistente
        resp2 = stub.Buscar(minibib_pb2.BuscaRequest(topico="nada"))
        print(f"buscar('nada') = {list(resp2.numeros_itens)}")

        print("\n[TODOS OS TESTES PASSARAM]")

    finally:
        for p in processos:
            p.terminate()
        for p in processos:
            p.wait(timeout=3)
        print("[OK] Servidores encerrados")


if __name__ == "__main__":
    main()
