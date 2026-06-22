"""Coordenador do Quadro.

O Coordenador apenas ORDENA operacoes (atribui sequencia a elas e
ids) e envia elas via broadcast para todos os membros via streams do Join. Como
todo nó mantem uma replica completa, a eleicao pode mover este servico para
outro nó sem perder estado.
"""

import argparse
import queue
import threading
import time
from concurrent import futures

import grpc

import sdwb_pb2
import sdwb_pb2_grpc
import servico_nomes as sn

# Heartbeat: cliente envia para o coordenador a cada 2 segundos; quem passar
# de 4 sem dar sinal é removido da lista de membros.
T_HEARTBEAT = 2.0
FATOR_TIMEOUT = 2


class EstadoCoordenador:
    def __init__(self, nome_quadro: str):
        self.nome_quadro = nome_quadro
        self._trava = threading.RLock()
        self._objetos: dict[str, sdwb_pb2.Objeto] = {}
        self._membros: dict[str, sdwb_pb2.InfoMembro] = {}
        self._locks: dict[str, str] = {}  # objeto_id -> id_cliente
        self._sequencia = 0
        self._proximo_obj = 0
        # id_cliente -> Queue de Evento (uma fila por stream do Join)
        self._filas: dict[str, queue.Queue] = {}
        # heartbeat: id_cliente -> instante do ultimo sinal
        self._ultimo_visto: dict[str, float] = {}
        self._monitor = None
        self._parar_monitor = threading.Event()

    @classmethod
    def de_snapshot(
        cls, nome_quadro: str, snap: sdwb_pb2.EstadoQuadro
    ) -> "EstadoCoordenador":
        """Reconstroi o estado (usado na migracao apos
        eleicao). O novo coordenador ja tinha tudo replicado como cliente."""
        est = cls(nome_quadro)
        for o in snap.objetos:
            novo = sdwb_pb2.Objeto()
            novo.CopyFrom(o)
            est._objetos[novo.id] = novo
        for m in snap.membros:
            est._membros[m.id_cliente] = m
            est._ultimo_visto[m.id_cliente] = time.monotonic()
        est._locks = dict(snap.locks)
        est._sequencia = snap.ultima_sequencia
        # continua a numeracao de ids sem colidir
        maior = 0
        for oid in est._objetos:
            if oid.startswith("obj-") and oid[4:].isdigit():
                maior = max(maior, int(oid[4:]))
        est._proximo_obj = maior
        return est

    # snapshot do quadro no momento da entrada, estado inicial entregue a quem entrar

    def snapshot(self) -> sdwb_pb2.EstadoQuadro:
        with self._trava:
            return sdwb_pb2.EstadoQuadro(
                objetos=list(self._objetos.values()),
                membros=list(self._membros.values()),
                locks=dict(self._locks),
                ultima_sequencia=self._sequencia,
            )

    # registra um membro e cria sua fila com o estado inicial e difunde para os demais membros

    def registrar_membro(self, membro: sdwb_pb2.InfoMembro) -> queue.Queue:

        with self._trava:
            self._membros[membro.id_cliente] = membro
            self._ultimo_visto[membro.id_cliente] = time.monotonic()
            fila: queue.Queue = queue.Queue()
            self._filas[membro.id_cliente] = fila
            fila.put(
                sdwb_pb2.Evento(
                    tipo=sdwb_pb2.ESTADO_INICIAL,
                    estado=self.snapshot(),
                    membros=list(self._membros.values()),
                )
            )
        self._difundir_membros()
        print(
            f"[coordenador:{self.nome_quadro}] entrou {membro.id_cliente} "
            f"({membro.ip}:{membro.porta}); membros={self._n_membros()}"
        )
        return fila

    def remover_membro(self, id_cliente: str):
        with self._trava:
            self._membros.pop(id_cliente, None)
            self._filas.pop(id_cliente, None)
            self._ultimo_visto.pop(id_cliente, None)
            # libera quaisquer locks presos por quem saiu
            for oid in [o for o, c in self._locks.items() if c == id_cliente]:
                del self._locks[oid]
        self._difundir_membros()
        print(
            f"[coordenador:{self.nome_quadro}] saiu {id_cliente}; membros={self._n_membros()}"
        )

    def _n_membros(self) -> int:
        with self._trava:
            return len(self._membros)

    # heartbeat

    def registrar_heartbeat(self, id_cliente: str):
        with self._trava:
            if id_cliente in self._membros:
                self._ultimo_visto[id_cliente] = time.monotonic()

    def iniciar_monitor_heartbeat(self):
        """Thread responsável por remover membros silenciosos por mais de 4 segundos."""

        if self._monitor is not None:
            return
        self._parar_monitor.clear()
        self._monitor = threading.Thread(target=self._loop_monitor, daemon=True)
        self._monitor.start()

    def parar_monitor_heartbeat(self):
        self._parar_monitor.set()

    def _loop_monitor(self):
        limite = FATOR_TIMEOUT * T_HEARTBEAT
        while not self._parar_monitor.wait(T_HEARTBEAT):
            agora = time.monotonic()
            with self._trava:
                mortos = [
                    c for c, t in self._ultimo_visto.items() if agora - t > limite
                ]
            for c in mortos:
                print(
                    f"[coordenador: {self.nome_quadro} heartbeat estourou para {c} (>{limite}s); removendo membro"
                )
                self.remover_membro(c)

    # broadcast

    def _difundir(self, evento: sdwb_pb2.Evento):
        with self._trava:
            filas = list(self._filas.values())
        for f in filas:
            f.put(evento)

    def _difundir_membros(self):
        with self._trava:
            membros = list(self._membros.values())
        self._difundir(sdwb_pb2.Evento(tipo=sdwb_pb2.MEMBROS, membros=membros))

    def _difundir_locks(self):
        with self._trava:
            locks = dict(self._locks)
        self._difundir(sdwb_pb2.Evento(tipo=sdwb_pb2.LOCK, locks=locks))

    # operacoes

    def aplicar_operacao(self, op: sdwb_pb2.Operacao) -> sdwb_pb2.Resposta:
        """Ordena (sequencia/id), aplica na replica local e difunde a todos."""
        with self._trava:
            objeto_resultante = None
            lock_mudou = False

            if op.tipo == sdwb_pb2.CRIAR:
                self._proximo_obj += 1
                novo = sdwb_pb2.Objeto()
                novo.CopyFrom(op.objeto)
                novo.id = f"obj-{self._proximo_obj}"
                novo.dono = op.id_cliente
                self._objetos[novo.id] = novo
                objeto_resultante = novo

            elif op.tipo == sdwb_pb2.COLORIR:
                alvo = self._objetos.get(op.objeto_id)
                if alvo is None:
                    return sdwb_pb2.Resposta(ok=False, mensagem="objeto inexistente")
                # exclusao mutua: so opera quem detem o lock do objeto
                if self._locks.get(op.objeto_id) != op.id_cliente:
                    return sdwb_pb2.Resposta(
                        ok=False, mensagem="selecione o objeto antes de colorir"
                    )
                alvo.cor = op.cor
                objeto_resultante = alvo
                self._locks.pop(op.objeto_id, None)  # libera apos operar
                lock_mudou = True

            elif op.tipo == sdwb_pb2.REMOVER:
                if op.objeto_id not in self._objetos:
                    return sdwb_pb2.Resposta(ok=False, mensagem="objeto inexistente")
                if self._locks.get(op.objeto_id) != op.id_cliente:
                    return sdwb_pb2.Resposta(
                        ok=False, mensagem="selecione o objeto antes de remover"
                    )
                del self._objetos[op.objeto_id]
                self._locks.pop(op.objeto_id, None)
                lock_mudou = True

            else:
                return sdwb_pb2.Resposta(ok=False, mensagem="operacao desconhecida")

            self._sequencia += 1
            aplicada = sdwb_pb2.OperacaoAplicada(
                sequencia=self._sequencia,
                operacao=op,
                objeto=objeto_resultante
                if objeto_resultante is not None
                else sdwb_pb2.Objeto(),
            )

        self._difundir(sdwb_pb2.Evento(tipo=sdwb_pb2.OPERACAO, operacao=aplicada))
        if lock_mudou:
            self._difundir_locks()  # objeto foi liberado/removido apos a operacao
        return sdwb_pb2.Resposta(ok=True, mensagem=f"seq={aplicada.sequencia}")

    # ---------- exclusao mutua (Fase 3) ----------

    def selecionar(self, oid: str, id_cliente: str) -> sdwb_pb2.Resposta:
        with self._trava:
            if oid not in self._objetos:
                return sdwb_pb2.Resposta(ok=False, mensagem="objeto inexistente")
            dono = self._locks.get(oid)
            if dono is not None and dono != id_cliente:
                return sdwb_pb2.Resposta(
                    ok=False, mensagem=f"objeto ja selecionado por {dono}"
                )
            self._locks[oid] = id_cliente
        self._difundir_locks()
        return sdwb_pb2.Resposta(ok=True, mensagem="selecionado")

    def liberar(self, oid: str, id_cliente: str) -> sdwb_pb2.Resposta:
        with self._trava:
            if self._locks.get(oid) == id_cliente:
                del self._locks[oid]
        self._difundir_locks()
        return sdwb_pb2.Resposta(ok=True, mensagem="liberado")


class CoordenadorServicer(sdwb_pb2_grpc.CoordenadorServicer):
    def __init__(self, estado: EstadoCoordenador):
        self.estado = estado

    def Join(self, pedido, contexto):
        membro = pedido.membro
        fila = self.estado.registrar_membro(membro)

        def ao_encerrar():
            self.estado.remover_membro(membro.id_cliente)

        contexto.add_callback(ao_encerrar)

        while contexto.is_active():
            try:
                evento = fila.get(timeout=1.0)
            except queue.Empty:
                continue
            yield evento

    def EnviarOperacao(self, pedido, contexto):
        return self.estado.aplicar_operacao(pedido)

    def Selecionar(self, pedido, contexto):
        return self.estado.selecionar(pedido.objeto_id, pedido.id_cliente)

    def Liberar(self, pedido, contexto):
        return self.estado.liberar(pedido.objeto_id, pedido.id_cliente)

    def Heartbeat(self, pedido, contexto):
        self.estado.registrar_heartbeat(pedido.id_cliente)
        return sdwb_pb2.Resposta(ok=True, mensagem="pong")

    def Sair(self, pedido, contexto):
        self.estado.remover_membro(pedido.id_cliente)
        return sdwb_pb2.Resposta(ok=True, mensagem="saiu")


def servir(nome_quadro: str, porta: int, bloquear: bool = True):
    estado = EstadoCoordenador(nome_quadro)
    servidor = grpc.server(futures.ThreadPoolExecutor(max_workers=16))
    sdwb_pb2_grpc.add_CoordenadorServicer_to_server(
        CoordenadorServicer(estado), servidor
    )
    servidor.add_insecure_port(f"[::]:{porta}")
    servidor.start()
    estado.iniciar_monitor_heartbeat()
    print(f"[coord:{nome_quadro}] Coordenador ouvindo na porta {porta}")
    if bloquear:
        servidor.wait_for_termination()
    return servidor, estado


def registrar_no_nomes(nomes_addr: str, nome_quadro: str, ip: str, porta: int) -> bool:
    with grpc.insecure_channel(nomes_addr) as canal:
        stub = sdwb_pb2_grpc.ServicoNomesStub(canal)
        r = stub.RegistrarQuadro(
            sdwb_pb2.InfoQuadro(nome=nome_quadro, ip=ip, porta=porta)
        )
        print(f"[coord:{nome_quadro}] registro no servico de nomes: {r.mensagem}")
        return r.ok


def remover_do_nomes(nomes_addr: str, nome_quadro: str):
    try:
        with grpc.insecure_channel(nomes_addr) as canal:
            sdwb_pb2_grpc.ServicoNomesStub(canal).RemoverQuadro(
                sdwb_pb2.NomeQuadro(nome=nome_quadro), timeout=2
            )
        print(f"[coord:{nome_quadro}] removido do servico de nomes")
    except grpc.RpcError as e:
        print(f"[coord:{nome_quadro}] falha ao remover do nomes: {e.details()}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Coordenador de um quadro SDWB")
    ap.add_argument("--nome", required=True, help="nome do quadro")
    ap.add_argument("--porta", type=int, required=True, help="porta do coordenador")
    ap.add_argument(
        "--ip", default="127.0.0.1", help="ip anunciado ao servico de nomes"
    )
    ap.add_argument(
        "--nomes",
        default=f"127.0.0.1:{sn.PORTA_PADRAO}",
        help="endereco do servico de nomes",
    )
    args = ap.parse_args()

    if not registrar_no_nomes(args.nomes, args.nome, args.ip, args.porta):
        raise SystemExit("falha ao registrar quadro (nome ja existe?)")

    servidor, _estado = servir(args.nome, args.porta, bloquear=False)

    # Saida graciosa (SIGTERM do cliente que criou, ou Ctrl-C): encerra o quadro
    # removendo-o do Servico de Nomes. NOTA: isto cobre o caminho "sai/desliga
    # gracioso". O caminho "cai" (SIGKILL, nao capturavel) sera tratado na Fase 4
    # via heartbeat -> eleicao/encerramento pelos sobreviventes.
    import signal

    def encerrar(*_):
        remover_do_nomes(args.nomes, args.nome)
        servidor.stop(0)
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, encerrar)
    signal.signal(signal.SIGINT, encerrar)
    try:
        servidor.wait_for_termination()
    except SystemExit:
        pass
