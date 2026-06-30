"""No do SDWB: camada de rede/replica/eleicao (sem interface grafica).

Cada No e um processo que:
  - sobe UM servidor gRPC sempre ativo, hospedando os servicos `No` (eleicao)
    e `Coordenador` (este ultimo so fica ATIVO quando o no é o coordenador do
    quadro; caso contrario rejeita chamadas);
  - mantem uma REPLICA completa do quadro (objetos, membros, locks, sequencia),
    alimentada pela stream do Join. Essa replica é o que permite ao no assumir
    como coordenador, sem perder estado, quando vence uma eleicao;
  - envia heartbeat ao coordenador; detecta a queda do coordenador (stream do
    Join quebra ou heartbeat falha) e dispara a eleicao do Valentao (Bully).

A interface grafica (frontend/cliente.py) consome `No.eventos` para renderizar
e chama os metodos publicos (criar_quadro, ingressar, enviar_operacao, ...).
"""

import queue
import socket
import threading
import time
import uuid
from concurrent import futures

import grpc

import sdwb_pb2
import sdwb_pb2_grpc
import coordenador as coord
from modelo import id_no


def porta_livre() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    p = s.getsockname()[1]
    s.close()
    return p


# Tempos da eleicao em segundos.
TIMEOUT_ELEICAO = 1.5  # espera resposta de um no de id maior
ESPERA_ANUNCIO = 3.0  # apos achar no maior vivo, espera o anuncio do novo coord


# Serviço de coordenador do nó
# Se nó é coordenador -> executa as ações
# Caso contrário -> recusa


class _CoordenadorServicer(sdwb_pb2_grpc.CoordenadorServicer):
    """Delega ao EstadoCoordenador ATIVO do no. Se o nó não é coordenador
    (estado dormente = None), rejeita as chamadas."""

    # Recebe uma instância de nó -> retorna Instância de coordenador, caso seja
    def __init__(self, no: "No"):
        self.no = no

    def _estado(self, contexto):
        est = self.no.estado_coord  # Verifica se o nó é coordenador, caso ele seja est será uma instância do serviço de coordenador, None caso constrário.
        if est is None:
            contexto.abort(grpc.StatusCode.UNAVAILABLE, "este nó não é o coordenador")
        return est

    # Entrada: Struct Pedido Join -> InfoMembro (id_cliente, ip, porta)
    def Join(self, pedido, contexto):
        est = self.no.estado_coord
        if est is None:
            contexto.abort(grpc.StatusCode.UNAVAILABLE, "este nó não é o coordenador")
        membro = pedido.membro  # pega membro
        fila = est.registrar_membro(membro)  # cadastrar membro

        def ao_encerrar():
            est.remover_membro(membro.id_cliente)

        contexto.add_callback(
            ao_encerrar
        )  # add callback para tirar cliente da lista, quando cliente desconectar
        while contexto.is_active():
            try:
                ev = fila.get(timeout=1.0)
            except queue.Empty:
                continue
            yield ev  # continua enviando evento na vila

    # Entrada: Struct Operacao (Tipo operacao, id_cliente, objeto, objeto_id, cor)
    def EnviarOperacao(self, pedido, contexto):
        return self._estado(contexto).aplicar_operacao(pedido)

    # Entrada: Struct Pedido Lock (id_objeto, id_cliente)
    def Selecionar(self, pedido, contexto):
        return self._estado(contexto).selecionar(pedido.objeto_id, pedido.id_cliente)

    # Entrada: Struct Pedido Lock (id_objeto, id_cliente)
    def Liberar(self, pedido, contexto):
        return self._estado(contexto).liberar(pedido.objeto_id, pedido.id_cliente)

    # Entrada: Struct InfoMembro (id_cliente, ip, porta)
    def Heartbeat(self, pedido, contexto):
        self._estado(contexto).registrar_heartbeat(pedido.id_cliente)
        return sdwb_pb2.Resposta(ok=True, mensagem="pong")

    # Entrada: Struct InfoMembro (id_cliente ip, porta)
    def Sair(self, pedido, contexto):
        self._estado(contexto).remover_membro(pedido.id_cliente)
        return sdwb_pb2.Resposta(ok=True, mensagem="saiu")


# Lógica de eleição do valentão, chamada gRPC
class _NoServicer(sdwb_pb2_grpc.NoServicer):
    def __init__(self, no: "No"):
        self.no = no

    # Entrada: Struct Pedido Eleicao (id do nó que iniciou eleição, struct InfoMembro)
    def Eleicao(self, pedido, contexto):
        return self.no._ao_receber_eleicao(pedido)  # responde que ta vivo

    # Entrada Struct AnuncioCoordenador (Struct Infomembro -> Novo coordenador, nome do quadro)
    def AnunciarCoordenador(self, anuncio, contexto):
        return self.no._ao_receber_anuncio(anuncio)


# Lógica do Nó


class No:
    def __init__(
        self, nomes_addr: str, ip: str, porta: int = 0, id_cliente: str = None
    ):
        self.nomes_addr = nomes_addr
        self.ip = ip
        self.porta = porta or porta_livre()
        self.id_cliente = id_cliente or f"no-{uuid.uuid4().hex[:8]}"
        self.id = id_no(
            self.ip, self.porta
        )  # prioridade na eleição, fazendo o cálculo do id baseado em ip e porta

        # replica local completa do quadro (espelha o estado do coordenador)
        self.objetos: dict[str, sdwb_pb2.Objeto] = {}
        self.membros: list[sdwb_pb2.InfoMembro] = []
        self.locks: dict[str, str] = {}
        self.sequencia = 0

        # vinculo com o quadro/coordenador atual
        self.nome_quadro = None  # no me do quadro que está conectado
        self.coord_addr = None  # endereço do coordenador do quadro
        self._coord_canal = None  # canal iniciado do coordenador
        self._coord_stub = None  # stub para uso de funções do coordenador
        self._parar_conexao = None  # Event que encerra as threads da conexao atual

        # None quando cliente, vira EstadoCoordenador quando coordena
        self.estado_coord: coord.EstadoCoordenador = None

        # fila de eventos para a UI consumir
        self.eventos: queue.Queue = queue.Queue()  # UI desenha elementos na tela

        self._em_eleicao = threading.Event()  # evita desparar duas eleições juntas
        self._encerrado = False
        self._trava = threading.RLock()

        self._iniciar_servidor()  # inicia servidor gRPC

    # Propriedade que retorna as informações do cliente quando chamada
    @property
    def info(self) -> sdwb_pb2.InfoMembro:
        return sdwb_pb2.InfoMembro(
            id_cliente=self.id_cliente, ip=self.ip, porta=self.porta
        )

    # Iniciar servidor gRPC e conextar aos serviços de Nó e de Coordenador
    def _iniciar_servidor(self):
        self.servidor = grpc.server(
            futures.ThreadPoolExecutor(max_workers=16)
        )  # Inicia servidor grpc
        sdwb_pb2_grpc.add_NoServicer_to_server(
            _NoServicer(self), self.servidor
        )  # inicia o serviço do nó
        sdwb_pb2_grpc.add_CoordenadorServicer_to_server(
            _CoordenadorServicer(self), self.servidor
        )
        self.servidor.add_insecure_port(f"[::]:{self.porta}")
        self.servidor.start()
        print(
            f"[no {self.id_cliente}] gRPC ativo em {self.ip}:{self.porta} (id={self.id})"
        )

    def _emitir(self, tipo: str, **dados):
        self.eventos.put((tipo, dados))  # evento para UI

    # Funcionalidade: usa stub do Serviço de nomes, para listar quadros disponíveis.
    def listar_quadros(self) -> list:
        with grpc.insecure_channel(self.nomes_addr) as canal:
            return list(
                sdwb_pb2_grpc.ServicoNomesStub(canal)
                .ListarQuadros(sdwb_pb2.Vazio(), timeout=3)
                .quadros
            )

    # Funcionalidade: usa stub do Serviço de nomes para atualizar como novo coordenador do quadro. O quadro avisa que ele virou coordenador
    def _atualizar_nomes(self):
        try:
            with grpc.insecure_channel(self.nomes_addr) as canal:
                sdwb_pb2_grpc.ServicoNomesStub(canal).AtualizarQuadro(
                    sdwb_pb2.InfoQuadro(
                        nome=self.nome_quadro, ip=self.ip, porta=self.porta
                    ),
                    timeout=3,
                )
            print(
                f"[no {self.id_cliente}] atualizei o coordenador no nomes -> {self.ip}:{self.porta}"
            )
        except grpc.RpcError as e:
            print(f"[no {self.id_cliente}] falha ao atualizar nomes: {e.details()}")

    # Criar novo quadro
    def criar_quadro(self, nome: str) -> sdwb_pb2.Resposta:

        r = coord.registrar_no_nomes(self.nomes_addr, nome, self.ip, self.porta)
        if not r:
            return sdwb_pb2.Resposta(ok=False, mensagem="quadro ja existe")
        self.nome_quadro = nome
        self.estado_coord = coord.EstadoCoordenador(nome)
        self.estado_coord.iniciar_monitor_heartbeat()
        self._conectar_coordenador(f"{self.ip}:{self.porta}")
        return sdwb_pb2.Resposta(ok=True, mensagem="quadro criado")

    def ingressar(self, nome: str, endereco_coord: str):
        self.nome_quadro = nome
        self._conectar_coordenador(endereco_coord)

    #  conexao com o coordenador (Join + heartbeat)

    def _conectar_coordenador(self, endereco: str):
        # encerra conexao anterior, para iniciar uma nova.
        if self._parar_conexao is not None:
            self._parar_conexao.set()
        if self._coord_canal is not None:
            self._coord_canal.close()

        self.coord_addr = endereco
        self._coord_canal = grpc.insecure_channel(endereco)
        self._coord_stub = sdwb_pb2_grpc.CoordenadorStub(self._coord_canal)
        parar = threading.Event()
        self._parar_conexao = parar

        threading.Thread(
            target=self._loop_join, args=(self._coord_stub, parar), daemon=True
        ).start()  # inicia thread para cuidar da entrada de novos clientes no quadro

        threading.Thread(
            target=self._loop_heartbeat, args=(self._coord_stub, parar), daemon=True
        ).start()  # inicia a thread para cuidar do heatbeat

    # Recebe: stub do coordenador, parar que é um threading.Event
    def _loop_join(self, stub, parar: threading.Event):
        try:
            for ev in stub.Join(sdwb_pb2.PedidoJoin(membro=self.info)):
                if parar.is_set():
                    return
                self._aplicar_evento_replica(ev)
                self.eventos.put(ev)
        except grpc.RpcError:
            pass
        # stream encerrou: se não foi troca intencional, o coordenador caiu
        # detecta a queda do coordenador
        if not parar.is_set() and not self._encerrado:
            self._gatilho_queda_coordenador()

    def _loop_heartbeat(self, stub, parar: threading.Event):
        while not parar.wait(coord.T_HEARTBEAT):
            try:
                stub.Heartbeat(self.info, timeout=2)
            except grpc.RpcError:
                # detecta queda de coordenador
                if not parar.is_set() and not self._encerrado:
                    self._gatilho_queda_coordenador()
                return

    #  Atualiza a cópia local do quadro, baseado no evento que aconteceu.

    def _aplicar_evento_replica(self, ev: sdwb_pb2.Evento):
        if ev.tipo == sdwb_pb2.ESTADO_INICIAL:
            self.objetos = {o.id: o for o in ev.estado.objetos}
            self.membros = list(ev.estado.membros)
            self.locks = dict(ev.estado.locks)
            self.sequencia = ev.estado.ultima_sequencia
        elif ev.tipo == sdwb_pb2.OPERACAO:
            ap = ev.operacao
            op = ap.operacao
            if op.tipo == sdwb_pb2.CRIAR:
                self.objetos[ap.objeto.id] = ap.objeto
            elif op.tipo == sdwb_pb2.COLORIR and ap.objeto.id in self.objetos:
                self.objetos[ap.objeto.id] = ap.objeto
            elif op.tipo == sdwb_pb2.REMOVER:
                self.objetos.pop(op.objeto_id, None)
                self.locks.pop(op.objeto_id, None)
            self.sequencia = ap.sequencia
        elif ev.tipo == sdwb_pb2.MEMBROS:
            self.membros = list(ev.membros)
        elif ev.tipo == sdwb_pb2.LOCK:
            self.locks = dict(ev.locks)

    def _snapshot_replica(self) -> sdwb_pb2.EstadoQuadro:
        # pega todos os membros menos o coordenador morto (endereco == coord_addr)
        membros = [m for m in self.membros if f"{m.ip}:{m.porta}" != self.coord_addr]
        return sdwb_pb2.EstadoQuadro(
            objetos=list(self.objetos.values()),
            membros=membros,
            locks=dict(self.locks),
            ultima_sequencia=self.sequencia,
        )

    # cria um novo estado quadro

    # Operações (UI -> coordenador), repasse via stub do coordenador

    def enviar_operacao(self, op: sdwb_pb2.Operacao) -> sdwb_pb2.Resposta:
        return self._coord_stub.EnviarOperacao(op, timeout=5)

    def selecionar(self, oid: str) -> sdwb_pb2.Resposta:
        return self._coord_stub.Selecionar(
            sdwb_pb2.PedidoLock(objeto_id=oid, id_cliente=self.id_cliente), timeout=5
        )

    def liberar(self, oid: str) -> sdwb_pb2.Resposta:
        return self._coord_stub.Liberar(
            sdwb_pb2.PedidoLock(objeto_id=oid, id_cliente=self.id_cliente), timeout=5
        )

    # Eleição de novo coordenador

    def _gatilho_queda_coordenador(self):
        if self._encerrado:
            return
        print(f"[no {self.id_cliente}] coordenador caiu -> iniciando eleicao")
        self._emitir("COORD_CAIU")
        threading.Thread(target=self._iniciar_eleicao, daemon=True).start()
        # inicia thread de eleição

    def _iniciar_eleicao(self):
        if self._em_eleicao.is_set():
            return
        self._em_eleicao.set()
        self._emitir("ELEICAO_INICIO")
        # inicia eleicao

        # contata todos os membros de ID MAIOR (exceto o coordenador morto)
        maiores = [
            m
            for m in self.membros
            if m.id_cliente != self.id_cliente
            and f"{m.ip}:{m.porta}" != self.coord_addr
            and id_no(m.ip, m.porta) > self.id
        ]
        algum_maior_vivo = False
        for m in maiores:
            try:
                r = sdwb_pb2_grpc.NoStub(
                    grpc.insecure_channel(f"{m.ip}:{m.porta}")
                ).Eleicao(
                    sdwb_pb2.PedidoEleicao(id=self.id, membro=self.info),
                    timeout=TIMEOUT_ELEICAO,
                )
                if r.ok:
                    algum_maior_vivo = True
            except grpc.RpcError:
                pass

        if algum_maior_vivo:
            # um no maior assume; espero o anuncio. Se nao vier, tento de novo.
            threading.Timer(ESPERA_ANUNCIO, self._retentar_se_preciso).start()
        else:
            self._virar_coordenador()

    def _retentar_se_preciso(self):
        if self._em_eleicao.is_set() and not self._encerrado:
            print(f"[no {self.id_cliente}] sem anuncio do novo coordenador; reeleicao")
            self._em_eleicao.clear()
            self._iniciar_eleicao()

    def _ao_receber_eleicao(self, pedido) -> sdwb_pb2.Resposta:
        # alguem de id menor me chamou: respondo 'vivo' e inicio minha eleicao
        # (tenho id maior, sou candidato melhor).
        if not self._em_eleicao.is_set():
            threading.Thread(target=self._iniciar_eleicao, daemon=True).start()
        return sdwb_pb2.Resposta(ok=True, mensagem="vivo")

    def _virar_coordenador(self):
        print(f"[no {self.id_cliente}] VENCI a eleicao -> assumindo como coordenador")
        snap = self._snapshot_replica()
        self.estado_coord = coord.EstadoCoordenador.de_snapshot(self.nome_quadro, snap)
        self.estado_coord.iniciar_monitor_heartbeat()
        self._atualizar_nomes()
        self._em_eleicao.clear()

        # anuncia aos demais membros (servico No de cada um)
        for m in snap.membros:
            if m.id_cliente == self.id_cliente:
                continue
            try:
                sdwb_pb2_grpc.NoStub(
                    grpc.insecure_channel(f"{m.ip}:{m.porta}")
                ).AnunciarCoordenador(
                    sdwb_pb2.AnuncioCoordenador(
                        coordenador=self.info, nome_quadro=self.nome_quadro
                    ),
                    timeout=TIMEOUT_ELEICAO,
                )
            except grpc.RpcError:
                pass

        # reconecta a si mesmo (agora coordenador) como cliente
        self._conectar_coordenador(f"{self.ip}:{self.porta}")
        self._emitir("VIREI_COORDENADOR")

    def _ao_receber_anuncio(self, anuncio) -> sdwb_pb2.Resposta:
        novo = anuncio.coordenador
        print(
            f"[no {self.id_cliente}] novo coordenador anunciado: {novo.ip}:{novo.porta}"
        )
        self._em_eleicao.clear()
        self._conectar_coordenador(f"{novo.ip}:{novo.porta}")
        self._emitir("NOVO_COORDENADOR", coordenador=novo)
        return sdwb_pb2.Resposta(ok=True, mensagem="ok")

    # encerramento

    def sou_coordenador(self) -> bool:
        return self.estado_coord is not None

    def sair(self):

        if self._parar_conexao is not None:
            self._parar_conexao.set()
        # avisa o coordenador atual que estou saindo (libera locks/membro)
        try:
            if self._coord_stub is not None:
                self._coord_stub.Sair(self.info, timeout=2)
        except grpc.RpcError:
            pass

        if self.sou_coordenador():
            outros = [
                m
                for m in self.estado_coord.snapshot().membros
                if m.id_cliente != self.id_cliente
            ]
            if outros:
                print(
                    f"[no {self.id_cliente}] coordenador saiu do quadro mas CONTINUA hospedando"
                )
                # mantem estado_coord servindo; apenas deixei de ser membro/cliente
            else:
                print(
                    f"[no {self.id_cliente}] coordenador sozinho saiu -> encerra quadro"
                )
                coord.remover_do_nomes(self.nomes_addr, self.nome_quadro)
                self.estado_coord.parar_monitor_heartbeat()
                self.estado_coord = None

        if self._coord_canal is not None:
            self._coord_canal.close()
            self._coord_canal = None
            self._coord_stub = None
        self.nome_quadro = None
        self.coord_addr = None
        self.objetos = {}
        self.membros = []
        self.locks = {}

    # se coordenador está sozinha -> encerra o quadro
    # se possuir outros clientes -> detectam e iniciam uma eleição
    def encerrar(self):

        self._encerrado = True
        if self._parar_conexao is not None:
            self._parar_conexao.set()
        if self.sou_coordenador():
            outros = [
                m
                for m in self.estado_coord.snapshot().membros
                if m.id_cliente != self.id_cliente
            ]
            if not outros:
                coord.remover_do_nomes(self.nomes_addr, self.nome_quadro)
        try:
            if self._coord_canal is not None:
                self._coord_canal.close()
        except Exception:
            pass
        try:
            self.servidor.stop(0)
        except Exception:
            pass
