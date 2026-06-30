# Testando o SDWB em dois computadores (todos os cenários)

Guia para rodar o quadro distribuído em **duas máquinas reais** na mesma rede e exercitar
todos os cenários: entrada cruzada, exclusão mútua entre máquinas, morte do coordenador com
sobreviventes na outra máquina, encerramento e saída graciosa.

Ao longo do guia, suponha:

| Máquina | IP de exemplo | Papel |
|---------|---------------|-------|
| **PC1** | `192.168.0.10` | hospeda o Serviço de Nomes |
| **PC2** | `192.168.0.11` | só clientes |

Troque pelos IPs reais. Descubra o seu com:

```bash
hostname -I        # primeiro IP costuma ser o da LAN
# ou
ip -4 addr show | grep inet
```

---

## 0. Pré-requisitos (nas DUAS máquinas)

1. **Mesmo código** nas duas (copie a pasta `trabalhofinal/` ou use `git`/`scp`).
2. Dependências: `pip install grpcio grpcio-tools` e `tkinter` (no Arch: `sudo pacman -S tk`).
3. **Mesma rede** e portas liberadas. Para um teste rápido em LAN confiável, libere o
   firewall das portas usadas (Serviço de Nomes `50000` e as portas dos nós, ex.: `60001`,
   `60002`):

   ```bash
   # Arch/ufw
   sudo ufw allow 50000/tcp
   sudo ufw allow 60001:60010/tcp
   # ou, só para o teste, parar o firewall:
   sudo systemctl stop ufw     # (ou firewalld / iptables, conforme a distro)
   ```

4. **Relógios não precisam estar sincronizados** — o heartbeat usa tempo *monotônico* local
   do coordenador, não horário de parede.

### Regras de ouro da rede (decore)

- **Sempre passe `--ip` com o IP de LAN da própria máquina** (NUNCA `127.0.0.1`). Esse é o
  endereço que o nó anuncia aos outros; com `127.0.0.1` a outra máquina não te alcança.
- **Use `--porta` fixa** em cada nó (facilita firewall e deixa previsível qual é o endereço
  do coordenador).
- O `--nomes` é **o mesmo para todos**: `IP_DO_PC1:50000`.

---

## 1. Subir a base

### No PC1 — Serviço de Nomes (uma vez só, fica no ar o tempo todo)

```bash
cd trabalhofinal/backend
python servico_nomes.py            # ouve em [::]:50000 (todas as interfaces)
```

> O Serviço de Nomes "nunca falha" (enunciado). Deixe-o rodando em PC1 durante todos os
> testes.

### Clientes (em qualquer máquina)

Modelo do comando (note o `--ip` da própria máquina e o `--nomes` apontando para PC1):

```bash
cd trabalhofinal/frontend
# no PC1:
python cliente.py --ip 192.168.0.10 --porta 60001 --nomes 192.168.0.10:50000
# no PC2:
python cliente.py --ip 192.168.0.11 --porta 60001 --nomes 192.168.0.10:50000
```

(Portas podem repetir entre máquinas diferentes — os IPs já as distinguem. Numa **mesma**
máquina, use portas diferentes: `60001`, `60002`, ...)

---

## 2. Prever quem vence a eleição (importante)

A prioridade do Valentão é o `id_no(ip, porta)`. Ele é **dominado pelo IP**: entre máquinas
diferentes, **o IP maior tem o id maior** (a porta só desempata dentro do mesmo IP).

Calcule o id de qualquer nó para prever o vencedor:

```bash
cd trabalhofinal/backend
python -c "from modelo import id_no; print(id_no('192.168.0.10',60001))"
python -c "from modelo import id_no; print(id_no('192.168.0.11',60001))"
```

No exemplo, `192.168.0.11` > `192.168.0.10`, então **qualquer cliente do PC2 tem id maior**
que qualquer cliente do PC1. Logo, quando o coordenador cair, **um nó do PC2 tende a vencer**
(se houver sobrevivente lá). Para forçar a migração **para o PC1**, faça o oposto: o
sobrevivente de maior IP precisa estar no PC1 — ou seja, escolha qual máquina é "maior"
conforme o que quer demonstrar.

---

## 3. Cenário A — Entrada cruzada (PC2 entra em quadro do PC1)

1. **PC1**: suba um cliente (`--ip 192.168.0.10 --porta 60001`). Clique **Criar novo
   quadro**, nome `demo`. A status bar mostra `COORDENADOR`. Desenhe uma linha.
2. **PC2**: suba um cliente (`--ip 192.168.0.11 --porta 60001`). Clique **Atualizar lista**
   → aparece `demo (192.168.0.10:60001)` → selecione → **Ingressar**.
3. **Verifique**: o PC2 vê a linha que o PC1 desenhou (onboarding). Desenhe no PC2 → aparece
   no PC1 (broadcast). Contador `membros=2` nos dois.

✅ Critério: novo nó vê o estado e as atualizações em tempo real, entre máquinas.

---

## 4. Cenário B — Vice-versa (PC1 entra em quadro do PC2)

Igual ao A, trocando os papéis: o **PC2 cria** o quadro (`--ip 192.168.0.11`), o **PC1
ingressa**. O coordenador agora roda no PC2; o Serviço de Nomes continua no PC1. Confirma
que o sentido da conexão é independente de onde está o Serviço de Nomes.

---

## 5. Cenário C — Exclusão mútua entre máquinas

1. Com o quadro `demo` ativo e um objeto desenhado, **PC1**: clique **Selecionar** → clique
   no objeto. Ele fica com traço grosso no PC1; no **PC2** aparece **tracejado** (travado
   por outro).
2. **PC2**: clique **Selecionar** → clique no **mesmo** objeto. A status bar mostra
   `nao foi possivel selecionar ... ja selecionado por <cliente do PC1>`.
3. **PC1**: clique **Vermelho** (colore e libera). O tracejado some no PC2. Agora o PC2
   consegue selecionar.

✅ Critério: dois clientes em máquinas diferentes não operam o mesmo objeto ao mesmo tempo.

---

## 6. Cenário D — Morte do coordenador com sobreviventes na outra máquina

Este é o cenário 3 obrigatório, na versão distribuída.

**Arranjo sugerido (migração cruzada PC1 → PC2):**

1. **PC1**: cliente `--ip 192.168.0.10 --porta 60001` cria o quadro `demo` (é o
   coordenador). Desenhe algo.
2. **PC1**: suba um segundo cliente `--porta 60002` e **Ingressar**.
3. **PC2**: cliente `--ip 192.168.0.11 --porta 60001` **Ingressar**. Agora há 3 membros (2
   no PC1, 1 no PC2). O do PC2 tem o **maior id** (IP maior).
4. **Matar o coordenador (queda)** no PC1:

   ```bash
   pgrep -af "python cliente.py"      # ache o PID do cliente que criou o quadro
   kill -9 <PID>                       # "cai" (SIGKILL nao pode ser capturado)
   ```

   (Fechar a janela no **X** também derruba o host e dispara eleição, pois há outros.)
5. **Observe**: os sobreviventes mostram `coordenador caiu ... eleicao em andamento`. O nó
   de maior id (o do **PC2**) vira `COORDENADOR`. No PC1, rode para confirmar que o Serviço
   de Nomes foi atualizado:

   ```bash
   cd trabalhofinal/backend
   python -c "import grpc,sdwb_pb2,sdwb_pb2_grpc; \
c=grpc.insecure_channel('192.168.0.10:50000'); \
print([(q.nome,q.ip,q.porta) for q in sdwb_pb2_grpc.ServicoNomesStub(c).ListarQuadros(sdwb_pb2.Vazio()).quadros])"
   ```

   Deve apontar para `192.168.0.11:60001` (o novo coordenador no PC2).
6. **Verifique a continuidade**: desenhe nas janelas restantes — funciona, e o objeto
   desenhado antes da queda continua lá (estado preservado pela réplica).

✅ Critério: o sistema continua operando após a queda do coordenador; o estado migra para
outra máquina sem ser reconstruído.

> **Variante (migração PC2 → PC1):** monte o quadro com o coordenador no **PC2** e
> sobreviventes nos dois lados, mas garanta que o sobrevivente de **maior IP** esteja no
> PC1 (ou seja, faça o PC1 ser o de IP maior). Aí, ao matar o coordenador do PC2, o PC1
> assume. Use o cálculo de `id_no` da Seção 2 para escolher o arranjo.

---

## 7. Cenário E — Coordenador sozinho cai → quadro encerra

1. Deixe **apenas um** cliente no quadro (ele é o coordenador e único membro).
2. Feche a janela (ou `kill -9`).
3. Liste os quadros no Serviço de Nomes (comando da Seção 6, passo 5): o quadro **some**
   (`RemoverQuadro`). Não há para quem migrar, então o quadro encerra.

✅ Critério: coordenador sozinho que sai/cai encerra o quadro (removido do Serviço de Nomes).

---

## 8. Cenário F — Coordenador SAI (graciosa) com outros membros → continua hospedando

1. Com 2+ membros, na máquina do coordenador clique no botão **Sair** (não feche a janela).
2. **Observe**: **não** há eleição. O quadro continua no mesmo endereço (o processo do
   ex-membro continua hospedando o serviço Coordenador em segundo plano). Os outros seguem
   desenhando normalmente; o Serviço de Nomes **não muda**.

✅ Critério: distinção "sai" (mensagem, sem eleição) × "cai" (timeout, com eleição).

> Diferença prática: **Sair** = saída graciosa (sem eleição se há outros). **Fechar a
> janela / kill** = queda (com eleição).

---

## 9. Cenário G (extra) — Eleições encadeadas

Depois do Cenário D, **mate também o novo coordenador**. Uma **nova eleição** acontece entre
os que sobraram, e o próximo maior id assume. Repita até sobrar um só — aí o quadro encerra
(vira o Cenário E). Mostra que a tolerância a falhas é repetível, não um truque de uma vez.

---

## 10. Solução de problemas

| Sintoma | Causa provável | Correção |
|---------|----------------|----------|
| PC2 não lista o quadro do PC1 | `--nomes` errado, ou firewall na 50000 | confira `IP_PC1:50000`; libere a porta |
| Lista mostra `127.0.0.1` como ip do quadro | coordenador subiu com `--ip 127.0.0.1` | recrie o quadro passando o **IP de LAN** em `--ip` |
| Ingressa mas não desenha entre máquinas | porta do nó bloqueada no firewall | libere a `--porta` daquele nó |
| Conexão recusada da outra máquina | servidor só em IPv4/loopback | o código usa `add_insecure_port("[::]:porta")` (dual-stack); se a distro for IPv4-only e falhar, troque para `"0.0.0.0:porta"` em `no.py`/`servico_nomes.py` |
| Eleição escolhe a máquina "errada" | id é dominado pelo IP | use o cálculo de `id_no` (Seção 2) para prever; ajuste qual máquina tem IP maior |
| Coordenador não é detectado como morto | só matou a UI, não o processo | use `kill -9 <pid do python cliente.py>` ou feche a janela no X |

---

## 11. Checklist da demonstração

- [ ] Serviço de Nomes no PC1, no ar.
- [ ] Clientes com `--ip` correto (LAN) e `--nomes` apontando para PC1.
- [ ] **A**: entrada cruzada (PC2 entra em quadro do PC1) + broadcast.
- [ ] **B**: vice-versa (PC1 entra em quadro do PC2).
- [ ] **C**: exclusão mútua entre máquinas (erro ao selecionar objeto travado).
- [ ] **D**: matar coordenador → eleição → migração para a outra máquina + estado
      preservado + Serviço de Nomes atualizado.
- [ ] **E**: coordenador sozinho cai → quadro some do Serviço de Nomes.
- [ ] **F**: coordenador usa **Sair** com outros → continua hospedando, sem eleição.
- [ ] **G** (opcional): eleições encadeadas.
