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


# Classe implementada do serviço de nomes
class ServicoNomesServicer(sdwb_pb2_grpc.ServicoNomesServicer):
    def __init__(self):
        # nome_do_quadro -> InfoQuadro -> contém as informações do quadro
        self._quadros: dict[str, sdwb_pb2.InfoQuadro] = {}
        self._trava = threading.Lock()  # para controle de acesso.

    # Entrada: Struct InfoQuadro (nome do quadro, ip coordenador atual, porta atual)
    # Retorna: ACK -> OK Registrado novo quadro, ou quadro com esse nome já existe.
    def RegistrarQuadro(self, novoquadro, contexto):
        with self._trava:
            if novoquadro.nome in self._quadros:
                return sdwb_pb2.Resposta(
                    ok=False, mensagem=f"Quadro '{novoquadro.nome}' ja existe."
                )
            self._quadros[novoquadro.nome] = novoquadro
        print(
            f"Quadro '{novoquadro.nome}' registrado {novoquadro.ip}:{novoquadro.porta}"
        )
        return sdwb_pb2.Resposta(ok=True, mensagem="registrado")

    # Retorna: lista dos quadros disponíveis (todos as struct InfoQuadro)
    def ListarQuadros(self, pedido, contexto):
        with self._trava:
            return sdwb_pb2.ListaQuadros(quadros=list(self._quadros.values()))

    # Entrada: Struct InfoQuadro(nome do quadro, ip coordenador atual, porta atual)
    # Retorna: ACK -> OK quadro atualizado
    # Info: Usada pelo novo coordenador ao ganhar a eleição

    def AtualizarQuadro(self, novoquadrocoord, contexto):
        with self._trava:
            self._quadros[novoquadrocoord.nome] = novoquadrocoord
        print(
            f"Quadro '{novoquadrocoord.nome}' atualizado  {novoquadrocoord.ip}:{novoquadrocoord.porta}"
        )
        return sdwb_pb2.Resposta(ok=True, mensagem="Atualizado com sucesso")

    # Entrada: Struct InfoQuadro(nome do quadro, ip coordenador atual, porta atual).
    # Retorna: ok = existia, se quadro existente. Inexistente caso contrário.
    def RemoverQuadro(self, pedido, contexto):
        with self._trava:
            existia = self._quadros.pop(pedido.nome, None) is not None
        if existia:
            print(f"Quadro '{pedido.nome}' removido")
        return sdwb_pb2.Resposta(
            ok=existia, mensagem="removido" if existia else "inexistente"
        )


# Entrada: Porta da aplicação
# Saída: servidor Grpc -> Serviço de nomes
def servir(porta: int = PORTA_PADRAO, bloquear: bool = True) -> grpc.Server:
    servidor = grpc.server(
        futures.ThreadPoolExecutor(max_workers=8)
    )  # iniciando servidor grpc, com max_workers = 8 threads
    sdwb_pb2_grpc.add_ServicoNomesServicer_to_server(ServicoNomesServicer(), servidor)
    servidor.add_insecure_port(f"[::]:{porta}")
    servidor.start()
    print(
        f"Servico de Nomes ouvindo na porta {porta}"
    )  # inicia efetivamente o serviço de nomes na porta
    if bloquear:
        servidor.wait_for_termination()
    return servidor


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Servico de Nomes do SDWB")
    ap.add_argument("--porta", type=int, default=PORTA_PADRAO)
    args = ap.parse_args()  # pega os argumentos da linha de comaando
    servir(args.porta)  # inicia pasasndo a porta
