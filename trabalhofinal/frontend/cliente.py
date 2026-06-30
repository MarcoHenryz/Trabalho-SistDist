"""Cliente do SDWB: interface grafica (Tkinter) sobre um No (backend/no.py).

A UI nao fala gRPC diretamente: ela possui um `No` (que cuida de rede, replica,
heartbeat e eleicao) e:
  - consome `no.eventos` para renderizar (Eventos protobuf do broadcast +
    avisos internos de eleicao);
  - chama metodos do No para acoes do usuario (criar/ingressar/operar/sair).

Regra de ouro: o desenho NAO e renderizado localmente na hora. A operacao vai
ao Coordenador, que ordena e difunde; so quando o evento volta e que aplicamos
-> todas as replicas convergem identicas.
"""

import argparse
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog

import grpc

# Stubs/backend ficam em backend/; deixa-os importaveis.
_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND = os.path.join(_RAIZ, "backend")
sys.path.insert(0, _BACKEND)

import sdwb_pb2          # noqa: E402
import sdwb_pb2_grpc     # noqa: E402
from no import No, porta_livre  # noqa: E402

NOMES_PADRAO = "127.0.0.1:50000"


class App:
    def __init__(self, raiz: tk.Tk, nomes_addr: str, ip: str, porta_no: int):
        self.raiz = raiz
        self.no = No(nomes_addr, ip, porta_no)

        # estado de render (mapeia objetos -> itens do Canvas)
        self.objetos: dict[str, sdwb_pb2.Objeto] = {}
        self.itens_canvas: dict[str, int] = {}
        self.membros: list = []
        self.locks: dict[str, str] = {}

        # estado de desenho/selecao
        self.modo = None
        self.ponto_inicial = None
        self.selecionado = None
        self._msg = "pronto"
        self._quadros_cache = []

        self._montar_tela_inicial()
        self.raiz.after(50, self._consumir_eventos)
        self.raiz.protocol("WM_DELETE_WINDOW", self._ao_fechar)

    # ===================== TELA INICIAL =====================

    def _montar_tela_inicial(self):
        self._limpar_raiz()
        self.raiz.title("SDWB - Inicio")
        quadro = tk.Frame(self.raiz, padx=16, pady=16)
        quadro.pack(fill="both", expand=True)

        tk.Label(quadro, text="Shared Distributed Write Board",
                 font=("TkDefaultFont", 14, "bold")).pack(pady=(0, 4))
        tk.Label(quadro, text=f"No: {self.no.id_cliente}  ({self.no.ip}:{self.no.porta})  id={self.no.id}",
                 fg="gray").pack(pady=(0, 12))

        linha = tk.Frame(quadro)
        linha.pack(fill="x")
        tk.Label(linha, text="Servico de Nomes:").pack(side="left")
        self.ent_nomes = tk.Entry(linha, width=24)
        self.ent_nomes.insert(0, self.no.nomes_addr)
        self.ent_nomes.pack(side="left", padx=6)

        tk.Button(quadro, text="Criar novo quadro", width=24,
                  command=self._criar_quadro).pack(pady=(12, 4))

        tk.Label(quadro, text="Quadros existentes:").pack(anchor="w", pady=(12, 2))
        self.lista = tk.Listbox(quadro, height=6, width=44)
        self.lista.pack()
        botoes = tk.Frame(quadro)
        botoes.pack(pady=6)
        tk.Button(botoes, text="Atualizar lista", command=self._atualizar_lista).pack(side="left", padx=4)
        tk.Button(botoes, text="Ingressar", command=self._ingressar_selecionado).pack(side="left", padx=4)

        self._atualizar_lista()

    def _atualizar_lista(self):
        self.no.nomes_addr = self.ent_nomes.get().strip()
        self.lista.delete(0, tk.END)
        try:
            self._quadros_cache = self.no.listar_quadros()
        except grpc.RpcError as e:
            messagebox.showerror("Servico de Nomes", f"Falha ao listar: {e.details()}")
            return
        for q in self._quadros_cache:
            self.lista.insert(tk.END, f"{q.nome}   ({q.ip}:{q.porta})")
        if not self._quadros_cache:
            self.lista.insert(tk.END, "(nenhum quadro)")

    def _criar_quadro(self):
        nome = simpledialog.askstring("Criar quadro", "Nome do quadro:", parent=self.raiz)
        if not nome:
            return
        self.no.nomes_addr = self.ent_nomes.get().strip()
        try:
            r = self.no.criar_quadro(nome)
        except grpc.RpcError as e:
            messagebox.showerror("Criar quadro", f"Falha: {e.details()}")
            return
        if not r.ok:
            messagebox.showerror("Criar quadro", r.mensagem)
            return
        self._montar_tela_quadro()

    def _ingressar_selecionado(self):
        sel = self.lista.curselection()
        if not sel or not self._quadros_cache or sel[0] >= len(self._quadros_cache):
            return
        q = self._quadros_cache[sel[0]]
        self.no.ingressar(q.nome, f"{q.ip}:{q.porta}")
        self._montar_tela_quadro()

    # ===================== CONSUMO DE EVENTOS =====================

    def _consumir_eventos(self):
        try:
            while True:
                ev = self.no.eventos.get_nowait()
                if isinstance(ev, tuple):
                    self._evento_interno(ev[0], ev[1])
                else:
                    self._aplicar_evento(ev)
        except queue.Empty:
            pass
        self.raiz.after(50, self._consumir_eventos)

    def _evento_interno(self, tipo, dados):
        if tipo == "STATUS":
            self._status(dados["msg"])
        elif tipo == "COORD_CAIU":
            self._status("coordenador caiu - detectando/elegendo novo...")
        elif tipo == "ELEICAO_INICIO":
            self._status("eleicao do Valentao em andamento...")
        elif tipo == "VIREI_COORDENADOR":
            self._status("voce agora e o COORDENADOR deste quadro")
        elif tipo == "NOVO_COORDENADOR":
            c = dados["coordenador"]
            self._status(f"novo coordenador: {c.ip}:{c.porta}")

    def _aplicar_evento(self, ev: sdwb_pb2.Evento):
        if ev.tipo == sdwb_pb2.ESTADO_INICIAL:
            self.objetos = {o.id: o for o in ev.estado.objetos}
            self.membros = list(ev.estado.membros)
            self._redesenhar_tudo()
            self._aplicar_locks(ev.estado.locks)
            self._atualizar_status()
        elif ev.tipo == sdwb_pb2.OPERACAO:
            self._aplicar_operacao(ev.operacao)
            self._atualizar_status()
        elif ev.tipo == sdwb_pb2.MEMBROS:
            self.membros = list(ev.membros)
            self._atualizar_status()
        elif ev.tipo == sdwb_pb2.LOCK:
            self._aplicar_locks(ev.locks)

    def _aplicar_operacao(self, ap: sdwb_pb2.OperacaoAplicada):
        op = ap.operacao
        if op.tipo == sdwb_pb2.CRIAR:
            self.objetos[ap.objeto.id] = ap.objeto
            self._desenhar_objeto(ap.objeto)
        elif op.tipo == sdwb_pb2.COLORIR:
            if ap.objeto.id in self.objetos:
                self.objetos[ap.objeto.id] = ap.objeto
                self._recolorir(ap.objeto)
        elif op.tipo == sdwb_pb2.REMOVER:
            if self.selecionado == op.objeto_id:
                self.selecionado = None
            self._apagar_objeto(op.objeto_id)

    # ===================== TELA DO QUADRO =====================

    def _montar_tela_quadro(self):
        self._limpar_raiz()
        self.modo = None
        self.ponto_inicial = None
        self.selecionado = None
        self._msg = "pronto"
        self.objetos.clear()
        self.itens_canvas.clear()
        self.raiz.title(f"SDWB - {self.no.nome_quadro}")

        barra = tk.Frame(self.raiz, padx=4, pady=4)
        barra.pack(fill="x")
        tk.Button(barra, text="Linha", command=lambda: self._set_modo("linha")).pack(side="left", padx=2)
        tk.Button(barra, text="Quadrado", command=lambda: self._set_modo("quadrado")).pack(side="left", padx=2)
        tk.Frame(barra, width=12).pack(side="left")
        tk.Button(barra, text="Selecionar", command=lambda: self._set_modo("selecionar")).pack(side="left", padx=2)
        tk.Button(barra, text="Vermelho", fg="white", bg="#cc0000",
                  command=lambda: self._colorir("red")).pack(side="left", padx=2)
        tk.Button(barra, text="Azul", fg="white", bg="#0044cc",
                  command=lambda: self._colorir("blue")).pack(side="left", padx=2)
        tk.Button(barra, text="Remover", command=self._remover).pack(side="left", padx=2)
        tk.Button(barra, text="Sair", command=self._sair_quadro).pack(side="right", padx=2)

        self.canvas = tk.Canvas(self.raiz, width=800, height=560, bg="white",
                                highlightthickness=1, highlightbackground="gray")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Button-1>", self._clique_canvas)

        self.rotulo_status = tk.Label(self.raiz, anchor="w", relief="sunken")
        self.rotulo_status.pack(fill="x")
        self._atualizar_status()

    def _set_modo(self, modo):
        self._liberar_selecao()  # trocar de ferramenta solta o lock atual
        self.modo = modo
        self.ponto_inicial = None
        if modo == "selecionar":
            self._status("modo: selecionar - clique num objeto")
        else:
            self._status(f"modo: {modo} - marque 2 pontos")

    def _clique_canvas(self, ev):
        if self.modo == "selecionar":
            self._selecionar_no_ponto(ev.x, ev.y)
            return
        if self.modo not in ("linha", "quadrado"):
            return
        if self.ponto_inicial is None:
            self.ponto_inicial = (ev.x, ev.y)
            self._status(f"modo: {self.modo} - ponto 1 marcado, marque o ponto 2")
            return
        p0, p1 = self.ponto_inicial, (ev.x, ev.y)
        self.ponto_inicial = None
        tipo = sdwb_pb2.LINHA if self.modo == "linha" else sdwb_pb2.QUADRADO
        op = sdwb_pb2.Operacao(
            tipo=sdwb_pb2.CRIAR, id_cliente=self.no.id_cliente,
            objeto=sdwb_pb2.Objeto(
                tipo=tipo,
                pontos=[sdwb_pb2.Ponto(x=p0[0], y=p0[1]), sdwb_pb2.Ponto(x=p1[0], y=p1[1])],
                cor="black"))
        self._operar(op)  # NAO desenha local; espera o broadcast
        self._status(f"modo: {self.modo} - marque 2 pontos")

    # ---------- selecao / colorir / remover ----------

    def _selecionar_no_ponto(self, x, y):
        if not self.itens_canvas:
            self._status("nada para selecionar")
            return
        item = self.canvas.find_closest(x, y)
        tags = self.canvas.gettags(item[0]) if item else ()
        oid = tags[0] if tags else None
        if oid is None or oid not in self.objetos:
            self._status("nenhum objeto nesse ponto")
            return
        self._liberar_selecao()

        def tarefa():
            try:
                r = self.no.selecionar(oid)
            except grpc.RpcError as e:
                self._post("STATUS", msg=f"falha ao selecionar: {e.details()}")
                return
            if r.ok:
                self.selecionado = oid
                self._post("STATUS", msg=f"selecionado {oid} - escolha cor ou Remover")
            else:
                self._post("STATUS", msg=f"nao foi possivel selecionar {oid}: {r.mensagem}")
        threading.Thread(target=tarefa, daemon=True).start()

    def _liberar_selecao(self):
        oid = self.selecionado
        self.selecionado = None
        if oid is None:
            return

        def tarefa():
            try:
                self.no.liberar(oid)
            except grpc.RpcError:
                pass
        threading.Thread(target=tarefa, daemon=True).start()

    def _colorir(self, cor):
        if not self.selecionado:
            self._status("selecione um objeto antes de colorir")
            return
        op = sdwb_pb2.Operacao(tipo=sdwb_pb2.COLORIR, id_cliente=self.no.id_cliente,
                               objeto_id=self.selecionado, cor=cor)
        self.selecionado = None
        self._operar(op)
        self._status(f"colorindo de {cor}...")

    def _remover(self):
        if not self.selecionado:
            self._status("selecione um objeto antes de remover")
            return
        op = sdwb_pb2.Operacao(tipo=sdwb_pb2.REMOVER, id_cliente=self.no.id_cliente,
                               objeto_id=self.selecionado)
        self.selecionado = None
        self._operar(op)
        self._status("removendo...")

    def _operar(self, op):
        def tarefa():
            try:
                r = self.no.enviar_operacao(op)
                if not r.ok:
                    self._post("STATUS", msg=f"operacao recusada: {r.mensagem}")
            except grpc.RpcError as e:
                self._post("STATUS", msg=f"falha na operacao: {e.details()}")
        threading.Thread(target=tarefa, daemon=True).start()

    def _post(self, tipo, **dados):
        # thread de rede -> UI: enfileira evento interno (consumido na thread Tk)
        self.no.eventos.put((tipo, dados))

    # ---------- Canvas ----------

    def _redesenhar_tudo(self):
        if not hasattr(self, "canvas"):
            return
        self.canvas.delete("all")
        self.itens_canvas.clear()
        for obj in self.objetos.values():
            self._desenhar_objeto(obj)

    def _desenhar_objeto(self, obj: sdwb_pb2.Objeto):
        if not hasattr(self, "canvas"):
            return
        p = obj.pontos
        cor = obj.cor or "black"
        if obj.tipo == sdwb_pb2.LINHA:
            item = self.canvas.create_line(p[0].x, p[0].y, p[1].x, p[1].y,
                                           fill=cor, width=2, tags=obj.id)
        else:
            item = self.canvas.create_rectangle(p[0].x, p[0].y, p[1].x, p[1].y,
                                                outline=cor, width=2, tags=obj.id)
        self.itens_canvas[obj.id] = item

    def _recolorir(self, obj):
        item = self.itens_canvas.get(obj.id)
        if item is None:
            return
        if obj.tipo == sdwb_pb2.LINHA:
            self.canvas.itemconfig(item, fill=obj.cor)
        else:
            self.canvas.itemconfig(item, outline=obj.cor)

    def _apagar_objeto(self, oid):
        self.objetos.pop(oid, None)
        self.locks.pop(oid, None)
        item = self.itens_canvas.pop(oid, None)
        if item is not None and hasattr(self, "canvas"):
            self.canvas.delete(item)

    def _aplicar_locks(self, locks):
        """meu lock -> traco grosso; lock de outro -> tracejado; livre -> normal."""
        self.locks = dict(locks)
        if not hasattr(self, "canvas"):
            return
        for oid, item in self.itens_canvas.items():
            dono = self.locks.get(oid)
            if dono == self.no.id_cliente:
                self.canvas.itemconfig(item, width=4, dash=())
            elif dono is not None:
                self.canvas.itemconfig(item, width=3, dash=(4, 3))
            else:
                self.canvas.itemconfig(item, width=2, dash=())

    # ---------- status / saida ----------

    def _status(self, msg):
        self._msg = msg
        self._render_status()
        print(f"[ui {self.no.id_cliente}] {msg}")

    def _atualizar_status(self):
        self._render_status()

    def _render_status(self):
        if hasattr(self, "rotulo_status"):
            papel = "COORDENADOR" if self.no.sou_coordenador() else "cliente"
            self.rotulo_status.config(
                text=f"[{self.no.nome_quadro}] {papel} | membros={len(self.membros)} | "
                     f"objetos={len(self.objetos)} | {self._msg}")

    def _sair_quadro(self):
        self.no.sair()
        self._montar_tela_inicial()

    def _ao_fechar(self):
        self.no.encerrar()
        self.raiz.destroy()

    def _limpar_raiz(self):
        for w in self.raiz.winfo_children():
            w.destroy()


def principal():
    ap = argparse.ArgumentParser(description="Cliente SDWB")
    ap.add_argument("--nomes", default=NOMES_PADRAO, help="endereco do servico de nomes")
    ap.add_argument("--ip", default="127.0.0.1", help="ip deste no")
    ap.add_argument("--porta", type=int, default=0, help="porta gRPC deste no (0=livre)")
    args = ap.parse_args()

    porta = args.porta or porta_livre()
    raiz = tk.Tk()
    app = App(raiz, args.nomes, args.ip, porta)

    # SIGTERM/SIGINT (pkill/kill): encerra o no antes de morrer.
    import signal

    def _sair(*_):
        try:
            app.no.encerrar()
        finally:
            os._exit(0)

    signal.signal(signal.SIGTERM, _sair)
    signal.signal(signal.SIGINT, _sair)

    raiz.mainloop()


if __name__ == "__main__":
    principal()
