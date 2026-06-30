"""Teste de fumaca da exclusao mutua (Fase 3A).

Verifica: A trava um objeto; B nao consegue travar nem operar; A opera (libera
o lock); so entao B consegue travar e operar. Sem 2PC (fora de escopo).

Rodar: python teste_fumaca_exclusao.py
"""

import queue
import threading

import grpc

import sdwb_pb2
import sdwb_pb2_grpc
import servico_nomes as sn
import coordenador as coord


def coletor(stub, membro, fila, parar):
    try:
        for ev in stub.Join(sdwb_pb2.PedidoJoin(membro=membro)):
            fila.put(ev)
            if parar.is_set():
                break
    except grpc.RpcError:
        pass


def lock(oid, cliente):
    return sdwb_pb2.PedidoLock(objeto_id=oid, id_cliente=cliente)


def principal():
    porta_nomes, porta_coord = 50120, 50121
    srv_nomes = sn.servir(porta=porta_nomes, bloquear=False)
    srv_coord, _ = coord.servir("excl", porta_coord, bloquear=False)
    assert coord.registrar_no_nomes(f"127.0.0.1:{porta_nomes}", "excl", "127.0.0.1", porta_coord)

    parar = threading.Event()
    addr = f"127.0.0.1:{porta_coord}"
    cA = grpc.insecure_channel(addr); cB = grpc.insecure_channel(addr)
    try:
        A = sdwb_pb2_grpc.CoordenadorStub(cA)
        B = sdwb_pb2_grpc.CoordenadorStub(cB)
        fA, fB = queue.Queue(), queue.Queue()
        threading.Thread(target=coletor, args=(A, sdwb_pb2.InfoMembro(id_cliente="A", ip="127.0.0.1", porta=1), fA, parar), daemon=True).start()
        threading.Thread(target=coletor, args=(B, sdwb_pb2.InfoMembro(id_cliente="B", ip="127.0.0.1", porta=2), fB, parar), daemon=True).start()
        assert fA.get(timeout=3).tipo == sdwb_pb2.ESTADO_INICIAL
        assert fB.get(timeout=3).tipo == sdwb_pb2.ESTADO_INICIAL

        # A cria objeto
        assert A.EnviarOperacao(sdwb_pb2.Operacao(
            tipo=sdwb_pb2.CRIAR, id_cliente="A",
            objeto=sdwb_pb2.Objeto(tipo=sdwb_pb2.QUADRADO,
                                   pontos=[sdwb_pb2.Ponto(x=0, y=0), sdwb_pb2.Ponto(x=9, y=9)]))).ok
        oid = "obj-1"

        # A trava; B nao consegue travar o mesmo
        assert A.Selecionar(lock(oid, "A")).ok
        rb = B.Selecionar(lock(oid, "B"))
        assert not rb.ok, "B nao deveria travar objeto ja travado por A"

        # B tenta colorir/remover sem deter o lock -> recusado
        assert not B.EnviarOperacao(sdwb_pb2.Operacao(
            tipo=sdwb_pb2.COLORIR, id_cliente="B", objeto_id=oid, cor="red")).ok
        assert not B.EnviarOperacao(sdwb_pb2.Operacao(
            tipo=sdwb_pb2.REMOVER, id_cliente="B", objeto_id=oid)).ok

        # A colore (detem o lock) -> ok, e o lock e liberado apos a operacao
        assert A.EnviarOperacao(sdwb_pb2.Operacao(
            tipo=sdwb_pb2.COLORIR, id_cliente="A", objeto_id=oid, cor="red")).ok

        # agora B consegue travar (foi liberado) e remover
        assert B.Selecionar(lock(oid, "B")).ok, "lock deveria estar livre apos A operar"
        assert B.EnviarOperacao(sdwb_pb2.Operacao(
            tipo=sdwb_pb2.REMOVER, id_cliente="B", objeto_id=oid)).ok

        print("OK: teste de fumaca de exclusao mutua passou.")
    finally:
        parar.set()
        cA.close(); cB.close()
        srv_coord.stop(0).wait()
        srv_nomes.stop(0).wait()


if __name__ == "__main__":
    principal()
