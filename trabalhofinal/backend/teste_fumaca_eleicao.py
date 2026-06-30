"""Teste de fumaca da tolerancia a falhas (Fase 4): morte do coordenador.

Cenario:
  - A cria o quadro (vira coordenador), B e C ingressam;
  - A desenha um objeto (replicado em B e C);
  - A "cai" (servidor parado abruptamente);
  - B e C detectam a queda (heartbeat/stream) e fazem eleicao do Valentao;
  - o maior ID entre os sobreviventes (C, maior porta) assume, atualiza o
    Servico de Nomes e mantem o estado replicado;
  - B reconecta ao novo coordenador e continua operando.

Rodar: python teste_fumaca_eleicao.py
"""

import time

import grpc

import sdwb_pb2
import sdwb_pb2_grpc
import servico_nomes as sn
import no as no_mod


def espere(cond, prazo=12.0, intervalo=0.2, msg="condicao"):
    fim = time.time() + prazo
    while time.time() < fim:
        if cond():
            return
        time.sleep(intervalo)
    raise AssertionError(f"timeout esperando: {msg}")


def quadro_no_nomes(addr_nomes, nome):
    with grpc.insecure_channel(addr_nomes) as c:
        for q in sdwb_pb2_grpc.ServicoNomesStub(c).ListarQuadros(sdwb_pb2.Vazio()).quadros:
            if q.nome == nome:
                return q
    return None


def principal():
    porta_nomes = 50130
    addr_nomes = f"127.0.0.1:{porta_nomes}"
    srv_nomes = sn.servir(porta=porta_nomes, bloquear=False)

    # IDs crescem com a porta (mesmo ip) -> C tem o maior ID
    pA, pB, pC = 51201, 51202, 51203
    A = no_mod.No(addr_nomes, "127.0.0.1", pA, id_cliente="A")
    B = no_mod.No(addr_nomes, "127.0.0.1", pB, id_cliente="B")
    C = no_mod.No(addr_nomes, "127.0.0.1", pC, id_cliente="C")

    try:
        assert A.criar_quadro("q").ok
        B.ingressar("q", f"127.0.0.1:{pA}")
        C.ingressar("q", f"127.0.0.1:{pA}")

        # todos enxergam 3 membros
        espere(lambda: len(A.membros) == 3 and len(B.membros) == 3 and len(C.membros) == 3,
               msg="3 membros")

        # A desenha um objeto -> replicado em B e C
        assert A.enviar_operacao(sdwb_pb2.Operacao(
            tipo=sdwb_pb2.CRIAR, id_cliente="A",
            objeto=sdwb_pb2.Objeto(tipo=sdwb_pb2.LINHA,
                                   pontos=[sdwb_pb2.Ponto(x=0, y=0), sdwb_pb2.Ponto(x=4, y=4)]))).ok
        espere(lambda: len(B.objetos) == 1 and len(C.objetos) == 1, msg="objeto replicado")

        # A "cai"
        print(">>> matando coordenador A")
        A.encerrar()

        # C (maior ID) deve assumir; nomes aponta para C
        espere(lambda: C.sou_coordenador(), prazo=15, msg="C vira coordenador")
        espere(lambda: (q := quadro_no_nomes(addr_nomes, "q")) is not None and q.porta == pC,
               prazo=15, msg="nomes aponta para C")
        assert not B.sou_coordenador(), "B nao deveria ser coordenador (id menor que C)"

        # estado preservado no novo coordenador
        assert len(C.estado_coord.snapshot().objetos) == 1, "objeto perdido na migracao"

        # B reconectou e continua operando atraves de C
        espere(lambda: B.coord_addr == f"127.0.0.1:{pC}", prazo=15, msg="B reconectou em C")
        assert B.enviar_operacao(sdwb_pb2.Operacao(
            tipo=sdwb_pb2.CRIAR, id_cliente="B",
            objeto=sdwb_pb2.Objeto(tipo=sdwb_pb2.QUADRADO,
                                   pontos=[sdwb_pb2.Ponto(x=1, y=1), sdwb_pb2.Ponto(x=2, y=2)]))).ok
        espere(lambda: len(C.objetos) == 2 and len(B.objetos) == 2, msg="nova operacao apos migracao")

        print("OK: teste de fumaca de eleicao/migracao passou.")
    finally:
        for n in (A, B, C):
            try:
                n.encerrar()
            except Exception:
                pass
        srv_nomes.stop(0).wait()


if __name__ == "__main__":
    principal()
