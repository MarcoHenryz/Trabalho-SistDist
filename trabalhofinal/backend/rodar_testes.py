"""Runner dos testes de fumaca / cenarios obrigatorios do SDWB.

Mapeia cada teste aos cenarios exigidos no enunciado e roda todos em sequencia,
em processos isolados (portas proprias). Rodar: python rodar_testes.py
"""

import subprocess
import sys
import time

# (arquivo, descricao -> cenario do enunciado)
TESTES = [
    ("teste_fumaca_nomes.py", "Servico de Nomes (registrar/listar/atualizar/remover)"),
    ("teste_fumaca_quadro.py", "Cenario 1 - Entrada dinamica: descoberta + onboarding + ordenacao + broadcast"),
    ("teste_fumaca_ops.py", "Sincronizacao: colorir/remover individual + convergencia de replicas"),
    ("teste_fumaca_exclusao.py", "Cenario 2 - Concorrencia: exclusao mutua por objeto (locks)"),
    ("teste_fumaca_eleicao.py", "Cenario 3 - Morte do coordenador: eleicao do Valentao + migracao"),
]


def main():
    falhas = 0
    for arquivo, desc in TESTES:
        print(f"\n=== {arquivo} ===\n{desc}")
        ini = time.time()
        r = subprocess.run([sys.executable, arquivo], capture_output=True, text=True, timeout=60)
        dur = time.time() - ini
        ok = r.returncode == 0
        print(f"  -> {'OK' if ok else 'FALHOU'} ({dur:.1f}s)")
        if not ok:
            falhas += 1
            print(r.stdout[-2000:])
            print(r.stderr[-2000:])
    print(f"\n{'='*50}\nResultado: {len(TESTES) - falhas}/{len(TESTES)} passaram.")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
