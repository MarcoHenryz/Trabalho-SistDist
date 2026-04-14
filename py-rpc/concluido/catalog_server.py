import grpc
from concurrent import futures
import threading
import sys
import catalog_pb2
import catalog_pb2_grpc

# Estoque inicial em memória
CATALOG = {
    1: {"name": "How Distributed Systems Work", "topic": "distributed", "stock": 10},
    2: {"name": "Socket Programming for Dummies", "topic": "distributed", "stock": 5},
    3: {"name": "Cooking for Engineers",          "topic": "cooking",     "stock": 3},
    4: {"name": "The Art of Debugging",           "topic": "distributed", "stock": 0},
}

# Lock para sincronização (evita que duas compras peguem o último exemplar)
catalog_lock = threading.Lock()

class CatalogServicer(catalog_pb2_grpc.CatalogServicer):

    def Query(self, request, context):
        results = []
        with catalog_lock:
            for item_num, info in CATALOG.items():
                # Busca por tópico OU por número de item
                if request.arg == info["topic"] or request.arg == str(item_num):
                    results.append(catalog_pb2.BookInfo(
                        item_number=item_num,
                        name=info["name"],
                        topic=info["topic"],
                        stock=info["stock"]
                    ))
        return catalog_pb2.QueryResponse(books=results, success=True)

    def Update(self, request, context):
        with catalog_lock:
            if request.item_number not in CATALOG:
                return catalog_pb2.UpdateResponse(success=False, message="Item não encontrado")
            CATALOG[request.item_number]["stock"] += request.qty
        return catalog_pb2.UpdateResponse(success=True, message="Estoque atualizado")

def serve(port):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    catalog_pb2_grpc.add_CatalogServicer_to_server(CatalogServicer(), server)
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    print(f"[Catálogo] Rodando na porta {port}")
    server.wait_for_termination()

if __name__ == "__main__":
    port = sys.argv[1] if len(sys.argv) > 1 else "50051"
    serve(port)