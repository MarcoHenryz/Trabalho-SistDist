"""Servidor Front-End — interface entre clientes e os serviços internos."""

import argparse
from concurrent import futures

import grpc
import minibib_pb2
import minibib_pb2_grpc


class ServidorFrontEnd(minibib_pb2_grpc.ServicoFrontEndServicer):
    def __init__(self, endereco_catalogo: str, endereco_pedidos: str):
        self.canal_catalogo = grpc.insecure_channel(endereco_catalogo)
        self.stub_catalogo = minibib_pb2_grpc.ServicoCatalogoStub(self.canal_catalogo)

        self.canal_pedidos = grpc.insecure_channel(endereco_pedidos)
        self.stub_pedidos = minibib_pb2_grpc.ServicoPedidosStub(self.canal_pedidos)

    def Buscar(self, request, context):
        try:
            resp = self.stub_catalogo.ConsultaPorTopico(
                minibib_pb2.ConsultaPorTopicoRequest(topico=request.topico)
            )
            return minibib_pb2.BuscaReply(numeros_itens=resp.numeros_itens)
        except grpc.RpcError as e:
            context.set_code(e.code())
            context.set_details(e.details())
            return minibib_pb2.BuscaReply()

    def Consultar(self, request, context):
        try:
            return self.stub_catalogo.ConsultaPorItem(
                minibib_pb2.ConsultaPorItemRequest(numero_item=request.numero_item)
            )
        except grpc.RpcError as e:
            context.set_code(e.code())
            context.set_details(e.details())
            return minibib_pb2.InfoLivro()

    def Comprar(self, request, context):
        try:
            return self.stub_pedidos.Comprar(
                minibib_pb2.CompraRequest(numero_item=request.numero_item)
            )
        except grpc.RpcError as e:
            context.set_code(e.code())
            context.set_details(e.details())
            return minibib_pb2.CompraReply(sucesso=False, mensagem="Erro interno.")


def iniciar(porta: int, endereco_catalogo: str, endereco_pedidos: str):
    servidor = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    minibib_pb2_grpc.add_ServicoFrontEndServicer_to_server(
        ServidorFrontEnd(endereco_catalogo, endereco_pedidos), servidor
    )
    servidor.add_insecure_port(f"[::]:{porta}")
    servidor.start()
    print(
        f"[ServidorFrontEnd] Rodando na porta {porta} | "
        f"Catálogo em {endereco_catalogo} | Pedidos em {endereco_pedidos}"
    )
    servidor.wait_for_termination()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Servidor Front-End")
    parser.add_argument("-p", "--porta", type=int, default=50053, help="Porta do servidor (padrão: 50053)")
    parser.add_argument("--catalogo", type=str, required=True, help="Endereço do catálogo (host:porta)")
    parser.add_argument("--pedidos", type=str, required=True, help="Endereço do servidor de pedidos (host:porta)")
    args = parser.parse_args()
    iniciar(args.porta, args.catalogo, args.pedidos)
