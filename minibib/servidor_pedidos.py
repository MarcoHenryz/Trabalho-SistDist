"""Servidor de Pedidos — processa compras consultando o catálogo."""

import argparse
import threading
from concurrent import futures

import grpc
import minibib_pb2
import minibib_pb2_grpc


class ServidorPedidos(minibib_pb2_grpc.ServicoPedidosServicer):
    def __init__(self, endereco_catalogo: str):
        self.endereco_catalogo = endereco_catalogo
        self.lock_compra = threading.Lock()

    def _obter_stub_catalogo(self):
        canal = grpc.insecure_channel(self.endereco_catalogo)
        return minibib_pb2_grpc.ServicoCatalogoStub(canal)

    def Comprar(self, request, context):
        # Lock garante que duas compras simultâneas não comprem a última cópia
        with self.lock_compra:
            stub = self._obter_stub_catalogo()

            # 1. Verifica estoque
            try:
                livro = stub.ConsultaPorItem(
                    minibib_pb2.ConsultaPorItemRequest(numero_item=request.numero_item)
                )
            except grpc.RpcError as e:
                return minibib_pb2.CompraReply(
                    sucesso=False,
                    mensagem=f"Erro ao consultar catálogo: {e.details()}",
                )

            if livro.estoque <= 0:
                return minibib_pb2.CompraReply(
                    sucesso=False,
                    mensagem=f"Item {request.numero_item} fora de estoque.",
                )

            # 2. Decrementa estoque em 1
            resp = stub.Atualizar(
                minibib_pb2.AtualizacaoRequest(
                    numero_item=request.numero_item, quantidade=-1
                )
            )
            if not resp.sucesso:
                return minibib_pb2.CompraReply(sucesso=False, mensagem=resp.mensagem)

        return minibib_pb2.CompraReply(
            sucesso=True,
            mensagem=f"Compra de '{livro.nome}' realizada com sucesso.",
        )


def iniciar(porta: int, endereco_catalogo: str):
    servidor = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    minibib_pb2_grpc.add_ServicoPedidosServicer_to_server(
        ServidorPedidos(endereco_catalogo), servidor
    )
    servidor.add_insecure_port(f"[::]:{porta}")
    servidor.start()
    print(
        f"[ServidorPedidos] Rodando na porta {porta} | Catálogo em {endereco_catalogo}"
    )
    servidor.wait_for_termination()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Servidor de Pedidos")
    parser.add_argument(
        "-p",
        "--porta",
        type=int,
        default=50052,
        help="Porta do servidor (padrão: 50052)",
    )
    parser.add_argument(
        "--catalogo", type=str, required=True, help="Endereço do catálogo (host:porta)"
    )
    args = parser.parse_args()
    iniciar(args.porta, args.catalogo)
