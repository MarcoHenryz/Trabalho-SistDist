"""Servidor de Catálogo — mantém o inventário em memória."""

import argparse
import threading
from concurrent import futures

import grpc
import minibib_pb2
import minibib_pb2_grpc


CATALOGO_INICIAL = [
    {
        "numero_item": 1,
        "nome": "livro 1 super mario",
        "topico": "sistemas distribuidos",
        "estoque": 10,
    },
    {
        "numero_item": 2,
        "nome": "livro 2 batman",
        "topico": "sistemas distribuidos",
        "estoque": 10,
    },
    {
        "numero_item": 3,
        "nome": "Livro 3 de teste",
        "topico": "pos-graduacao",
        "estoque": 5,
    },
    {
        "numero_item": 4,
        "nome": "livro 4 superman",
        "topico": "pos-graduacao",
        "estoque": 8,
    },
    {"numero_item": 5, "nome": "livro 5 luigi", "topico": "autoajuda", "estoque": 15},
    {
        "numero_item": 6,
        "nome": "livro 6 muahahaha",
        "topico": "ciencia da computacao",
        "estoque": 3,
    },
    {
        "numero_item": 7,
        "nome": "livro 7 seja feliz",
        "topico": "ciencia da computacao",
        "estoque": 7,
    },
]


class ServidorCatalogo(minibib_pb2_grpc.ServicoCatalogoServicer):
    def __init__(self):
        self.lock = threading.Lock()
        self.catalogo = {
            livro["numero_item"]: dict(livro) for livro in CATALOGO_INICIAL
        }

    def ConsultaPorTopico(self, request, context):
        with self.lock:
            itens = [
                livro["numero_item"]
                for livro in self.catalogo.values()
                if livro["topico"].lower() == request.topico.lower()
            ]
        return minibib_pb2.ConsultaPorTopicoReply(numeros_itens=itens)

    def ConsultaPorItem(self, request, context):
        with self.lock:
            livro = self.catalogo.get(request.numero_item)
        if livro is None:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"Item {request.numero_item} não encontrado.")
            return minibib_pb2.InfoLivro()
        return minibib_pb2.InfoLivro(
            numero_item=livro["numero_item"],
            nome=livro["nome"],
            topico=livro["topico"],
            estoque=livro["estoque"],
        )

    def Atualizar(self, request, context):
        with self.lock:
            livro = self.catalogo.get(request.numero_item)
            if livro is None:
                return minibib_pb2.AtualizacaoReply(
                    sucesso=False,
                    mensagem=f"Item {request.numero_item} não encontrado.",
                )
            novo_estoque = livro["estoque"] + request.quantidade
            if novo_estoque < 0:
                return minibib_pb2.AtualizacaoReply(
                    sucesso=False,
                    mensagem=f"Estoque insuficiente (atual: {livro['estoque']}).",
                )
            livro["estoque"] = novo_estoque
        return minibib_pb2.AtualizacaoReply(
            sucesso=True,
            mensagem=f"Estoque atualizado para {novo_estoque}.",
        )


def iniciar(porta: int):
    servidor = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    minibib_pb2_grpc.add_ServicoCatalogoServicer_to_server(ServidorCatalogo(), servidor)
    servidor.add_insecure_port(f"[::]:{porta}")
    servidor.start()
    print(f"[ServidorCatalogo] Rodando na porta {porta}")
    servidor.wait_for_termination()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Servidor de Catálogo")
    parser.add_argument(
        "-p",
        "--porta",
        type=int,
        default=50051,
        help="Porta do servidor (padrão: 50051)",
    )
    args = parser.parse_args()
    iniciar(args.porta)
