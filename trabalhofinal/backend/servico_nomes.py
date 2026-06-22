"""Servico de Nomes

Guarda a tabela (nome_do_quadro, ip, porta) dos Coordenadores.
"""

import argparse
import threading
from concurrent import futures

import grpc

import sdwb_pb2
import sdwb_pb2_grpc

PORTA_PADRAO = 50000


class ServicoNomesServicer(sdwb_pb2_grpc.ServicoNomesServicer):
    def __init__(self):
        # nome_do_quadro -> InfoQuadro
        self._quadros: dict[str, sdwb_pb2.InfoQuadro] = {}
        self._trava = threading.Lock()

    def RegistrarQuadro(self, pedido, contexto):
        with self._trava:
            if pedido.nome in self._quadros:
                return sdwb_pb2.Resposta(
                    ok=False, mensagem=f"Quadro '{pedido.nome}' ja existe."
                )
            self._quadros[pedido.nome] = pedido
        print(f"Quadro '{pedido.nome}' registrado {pedido.ip}:{pedido.porta}")
        return sdwb_pb2.Resposta(ok=True, mensagem="registrado")

    def ListarQuadros(self, pedido, contexto):
        with self._trava:
            return sdwb_pb2.ListaQuadros(quadros=list(self._quadros.values()))

    def AtualizarQuadro(self, pedido, contexto):
        # Usado pelo novo coordenador apos uma eleicao.
        with self._trava:
            self._quadros[pedido.nome] = pedido
        print(f"Quadro '{pedido.nome}' atualizado  {pedido.ip}:{pedido.porta}")
        return sdwb_pb2.Resposta(ok=True, mensagem="atualizado")

    def RemoverQuadro(self, pedido, contexto):
        with self._trava:
            existia = self._quadros.pop(pedido.nome, None) is not None
        if existia:
            print(f"Quadro '{pedido.nome}' removido")
        return sdwb_pb2.Resposta(
            ok=existia, mensagem="removido" if existia else "inexistente"
        )


def servir(porta: int = PORTA_PADRAO, bloquear: bool = True) -> grpc.Server:
    servidor = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
    sdwb_pb2_grpc.add_ServicoNomesServicer_to_server(ServicoNomesServicer(), servidor)
    servidor.add_insecure_port(f"[::]:{porta}")
    servidor.start()
    print(f"Servico de Nomes ouvindo na porta {porta}")
    if bloquear:
        servidor.wait_for_termination()
    return servidor


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Servico de Nomes do SDWB")
    ap.add_argument("--porta", type=int, default=PORTA_PADRAO)
    args = ap.parse_args()
    servir(args.porta)
