"""Teste de fumaca das operacoes COLORIR e REMOVER com broadcast (Fase 2).

Dois clientes; A cria, colore e remove um objeto. Verifica que ambos recebem
os eventos ordenados e que as replicas convergem (mesma cor, mesma remocao).

Rodar: python teste_fumaca_ops.py
"""

import queue
import threading
import time

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


def esperar_operacao(fila, tipo_op, timeout=3):
    """Le eventos da fila ate achar uma OPERACAO do tipo pedido; retorna-a."""
    prazo = time.time() + timeout
    while time.time() < prazo:
        ev = fila.get(timeout=timeout)
        if ev.tipo == sdwb_pb2.OPERACAO and ev.operacao.operacao.tipo == tipo_op:
            return ev.operacao
    raise AssertionError(f"operacao {tipo_op} nao difundida")


def principal():
    porta_nomes, porta_coord = 50110, 50111
    addr_nomes = f"127.0.0.1:{porta_nomes}"
    addr_coord = f"127.0.0.1:{porta_coord}"

    srv_nomes = sn.servir(porta=porta_nomes, bloquear=False)
    srv_coord, _ = coord.servir("ops", porta_coord, bloquear=False)
    assert coord.registrar_no_nomes(addr_nomes, "ops", "127.0.0.1", porta_coord)

    parar = threading.Event()
    canais = []
    try:
        stubs = {}
        filas = {}
        for nome, p in [("A", 1), ("B", 2)]:
            canal = grpc.insecure_channel(addr_coord)
            canais.append(canal)
            stub = sdwb_pb2_grpc.CoordenadorStub(canal)
            fila = queue.Queue()
            threading.Thread(target=coletor, args=(
                stub, sdwb_pb2.InfoMembro(id_cliente=nome, ip="127.0.0.1", porta=p), fila, parar),
                daemon=True).start()
            assert fila.get(timeout=3).tipo == sdwb_pb2.ESTADO_INICIAL
            stubs[nome] = stub
            filas[nome] = fila

        # A cria uma linha
        assert stubs["A"].EnviarOperacao(sdwb_pb2.Operacao(
            tipo=sdwb_pb2.CRIAR, id_cliente="A",
            objeto=sdwb_pb2.Objeto(
                tipo=sdwb_pb2.LINHA,
                pontos=[sdwb_pb2.Ponto(x=0, y=0), sdwb_pb2.Ponto(x=5, y=5)],
                cor="black"))).ok
        ap_a = esperar_operacao(filas["A"], sdwb_pb2.CRIAR)
        ap_b = esperar_operacao(filas["B"], sdwb_pb2.CRIAR)
        oid = ap_a.objeto.id
        assert ap_b.objeto.id == oid  # mesmo id nas duas replicas

        # A colore de vermelho (precisa travar antes) -> ambos veem cor=red
        assert stubs["A"].Selecionar(sdwb_pb2.PedidoLock(objeto_id=oid, id_cliente="A")).ok
        assert stubs["A"].EnviarOperacao(sdwb_pb2.Operacao(
            tipo=sdwb_pb2.COLORIR, id_cliente="A", objeto_id=oid, cor="red")).ok
        assert esperar_operacao(filas["A"], sdwb_pb2.COLORIR).objeto.cor == "red"
        assert esperar_operacao(filas["B"], sdwb_pb2.COLORIR).objeto.cor == "red"

        # A remove (trava de novo; lock foi liberado apos colorir) -> ambos veem
        assert stubs["A"].Selecionar(sdwb_pb2.PedidoLock(objeto_id=oid, id_cliente="A")).ok
        assert stubs["A"].EnviarOperacao(sdwb_pb2.Operacao(
            tipo=sdwb_pb2.REMOVER, id_cliente="A", objeto_id=oid)).ok
        assert esperar_operacao(filas["A"], sdwb_pb2.REMOVER).operacao.objeto_id == oid
        assert esperar_operacao(filas["B"], sdwb_pb2.REMOVER).operacao.objeto_id == oid

        # C entra agora e nao ve objeto algum (estado convergiu)
        canal_c = grpc.insecure_channel(addr_coord)
        canais.append(canal_c)
        fila_c = queue.Queue()
        threading.Thread(target=coletor, args=(
            sdwb_pb2_grpc.CoordenadorStub(canal_c),
            sdwb_pb2.InfoMembro(id_cliente="C", ip="127.0.0.1", porta=3), fila_c, parar),
            daemon=True).start()
        ev = fila_c.get(timeout=3)
        assert ev.tipo == sdwb_pb2.ESTADO_INICIAL and len(ev.estado.objetos) == 0

        print("OK: teste de fumaca de operacoes (colorir/remover/convergencia) passou.")
    finally:
        parar.set()
        for c in canais:
            c.close()
        srv_coord.stop(0).wait()
        srv_nomes.stop(0).wait()


if __name__ == "__main__":
    principal()
