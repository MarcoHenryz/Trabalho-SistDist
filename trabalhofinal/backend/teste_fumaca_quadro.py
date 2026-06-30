"""Teste de fumaca do fluxo de quadro (sem GUI).

Sobe Servico de Nomes + Coordenador, faz dois clientes ingressarem via Join
(stream), envia uma operacao e verifica: registro/descoberta, onboarding com
estado inicial, ordenacao por sequencia e broadcast para todos.

Rodar: python teste_fumaca_quadro.py
"""

import queue
import threading
import time

import grpc

import sdwb_pb2
import sdwb_pb2_grpc
import servico_nomes as sn
import coordenador as coord


def coletor_join(stub, membro, fila, parar):
    try:
        for ev in stub.Join(sdwb_pb2.PedidoJoin(membro=membro)):
            fila.put(ev)
            if parar.is_set():
                break
    except grpc.RpcError:
        pass


def pegar(fila, timeout=3):
    return fila.get(timeout=timeout)


def principal():
    porta_nomes = 50100
    porta_coord = 50101
    addr_nomes = f"127.0.0.1:{porta_nomes}"
    addr_coord = f"127.0.0.1:{porta_coord}"

    srv_nomes = sn.servir(porta=porta_nomes, bloquear=False)
    srv_coord, _estado = coord.servir("quadro-teste", porta_coord, bloquear=False)
    assert coord.registrar_no_nomes(addr_nomes, "quadro-teste", "127.0.0.1", porta_coord)

    try:
        # descoberta
        with grpc.insecure_channel(addr_nomes) as canal:
            lst = sdwb_pb2_grpc.ServicoNomesStub(canal).ListarQuadros(sdwb_pb2.Vazio()).quadros
            assert len(lst) == 1 and lst[0].porta == porta_coord, lst

        canal_a = grpc.insecure_channel(addr_coord)
        stub_a = sdwb_pb2_grpc.CoordenadorStub(canal_a)
        fila_a = queue.Queue()
        parar = threading.Event()
        threading.Thread(target=coletor_join, args=(
            stub_a, sdwb_pb2.InfoMembro(id_cliente="A", ip="127.0.0.1", porta=1), fila_a, parar),
            daemon=True).start()

        # A recebe ESTADO_INICIAL vazio
        ev = pegar(fila_a)
        assert ev.tipo == sdwb_pb2.ESTADO_INICIAL, ev.tipo
        assert len(ev.estado.objetos) == 0

        # A desenha uma linha
        op = sdwb_pb2.Operacao(
            tipo=sdwb_pb2.CRIAR, id_cliente="A",
            objeto=sdwb_pb2.Objeto(
                tipo=sdwb_pb2.LINHA,
                pontos=[sdwb_pb2.Ponto(x=0, y=0), sdwb_pb2.Ponto(x=10, y=10)],
                cor="black"))
        r = stub_a.EnviarOperacao(op)
        assert r.ok, r.mensagem

        # A recebe o broadcast da propria operacao (com id e seq atribuidos)
        # (pode vir um evento MEMBROS antes; filtra)
        ap = None
        prazo = time.time() + 3
        while time.time() < prazo and ap is None:
            ev = pegar(fila_a)
            if ev.tipo == sdwb_pb2.OPERACAO:
                ap = ev.operacao
        assert ap is not None, "operacao nao difundida para o autor"
        assert ap.sequencia == 1 and ap.objeto.id == "obj-1" and ap.objeto.dono == "A"

        # B ingressa depois e ja ve a linha no estado inicial
        canal_b = grpc.insecure_channel(addr_coord)
        stub_b = sdwb_pb2_grpc.CoordenadorStub(canal_b)
        fila_b = queue.Queue()
        threading.Thread(target=coletor_join, args=(
            stub_b, sdwb_pb2.InfoMembro(id_cliente="B", ip="127.0.0.1", porta=2), fila_b, parar),
            daemon=True).start()
        ev = pegar(fila_b)
        assert ev.tipo == sdwb_pb2.ESTADO_INICIAL
        assert len(ev.estado.objetos) == 1 and ev.estado.objetos[0].id == "obj-1"
        assert len(ev.estado.membros) == 2

        # exclusao mutua basica (ja implementada): A seleciona, B falha
        assert stub_a.Selecionar(sdwb_pb2.PedidoLock(objeto_id="obj-1", id_cliente="A")).ok
        rb = stub_b.Selecionar(sdwb_pb2.PedidoLock(objeto_id="obj-1", id_cliente="B"))
        assert not rb.ok, "B nao deveria conseguir selecionar objeto travado por A"

        parar.set()
        canal_a.close()
        canal_b.close()
        print("OK: teste de fumaca do quadro passou (descoberta, onboarding, ordenacao, broadcast).")
    finally:
        srv_coord.stop(0).wait()
        srv_nomes.stop(0).wait()


if __name__ == "__main__":
    principal()
