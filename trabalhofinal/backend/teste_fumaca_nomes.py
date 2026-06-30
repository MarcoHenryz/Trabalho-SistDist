"""Teste de fumaca do Servico de Nomes.

Sobe o servico numa porta efemera e exercita Registrar/Listar/Atualizar/Remover.
Rodar: python teste_fumaca_nomes.py
"""

import grpc

import sdwb_pb2
import sdwb_pb2_grpc
import servico_nomes as sn


def principal():
    porta = 50099
    servidor = sn.servir(porta=porta, bloquear=False)
    try:
        with grpc.insecure_channel(f"127.0.0.1:{porta}") as canal:
            stub = sdwb_pb2_grpc.ServicoNomesStub(canal)

            # lista vazia
            assert len(stub.ListarQuadros(sdwb_pb2.Vazio()).quadros) == 0

            # registrar
            r = stub.RegistrarQuadro(sdwb_pb2.InfoQuadro(nome="q1", ip="1.2.3.4", porta=7001))
            assert r.ok, r.mensagem

            # registrar duplicado -> erro
            r = stub.RegistrarQuadro(sdwb_pb2.InfoQuadro(nome="q1", ip="9.9.9.9", porta=9999))
            assert not r.ok

            # listar
            lst = stub.ListarQuadros(sdwb_pb2.Vazio()).quadros
            assert len(lst) == 1 and lst[0].nome == "q1" and lst[0].porta == 7001

            # atualizar (apos eleicao)
            r = stub.AtualizarQuadro(sdwb_pb2.InfoQuadro(nome="q1", ip="5.6.7.8", porta=7002))
            assert r.ok
            lst = stub.ListarQuadros(sdwb_pb2.Vazio()).quadros
            assert lst[0].ip == "5.6.7.8" and lst[0].porta == 7002

            # remover
            r = stub.RemoverQuadro(sdwb_pb2.NomeQuadro(nome="q1"))
            assert r.ok
            assert len(stub.ListarQuadros(sdwb_pb2.Vazio()).quadros) == 0

            # remover inexistente -> ok=False
            assert not stub.RemoverQuadro(sdwb_pb2.NomeQuadro(nome="qX")).ok

        print("OK: teste de fumaca do Servico de Nomes passou.")
    finally:
        servidor.stop(0).wait()


if __name__ == "__main__":
    principal()
