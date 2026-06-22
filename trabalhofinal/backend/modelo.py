"""
O estado do quadro vive replicado em todos os nos. O Coordenador apenas
ordena as operacoes (atribui sequencia/id) e envia para os nós. Estas funcoes ajudam a construir esse estado.
"""

import sdwb_pb2


def id_no(ip: str, porta: int) -> int:
    """ID de um no, derivado de ip:porta.

    Usado como prioridade na eleicao (maior ID vence).
    """
    octetos = ip.split(".")
    if len(octetos) == 4 and all(o.isdigit() for o in octetos):
        base = sum(int(o) << (8 * (3 - i)) for i, o in enumerate(octetos))
    else:
        # ip nao-IPv4 (ex.: nome de host): cai num hash estavel
        base = abs(hash(ip)) % (1 << 32)
    return (base << 16) | (porta & 0xFFFF)


def endereco(ip: str, porta: int) -> str:
    return f"{ip}:{porta}"
