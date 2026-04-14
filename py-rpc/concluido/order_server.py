import grpc
from concurrent import futures
import threading
import sys
import order_pb2
import order_pb2_grpc
import catalog_pb2
import catalog_pb2_grpc

order_lock = threading.Lock()  # Garante que só uma compra acontece por vez

class OrderServicer(order_pb2_grpc.OrderServicer):

    def __init__(self, catalog_host):
        # Conecta ao servidor de catálogo
        channel = grpc.insecure_channel(catalog_host)
        self.catalog_stub = catalog_pb2_grpc.CatalogStub(channel)

    def Buy(self, request, context):
        with order_lock:  # Seção crítica: apenas um buy por vez
            # 1. Consulta o catálogo para ver se tem estoque
            resp = self.catalog_stub.Query(
                catalog_pb2.QueryRequest(arg=str(request.item_number))
            )
            if not resp.books:
                return order_pb2.BuyResponse(success=False, message="Item não encontrado")
            
            book = resp.books[0]
            if book.stock <= 0:
                return order_pb2.BuyResponse(success=False, message="Sem estoque")

            # 2. Decrementa o estoque
            self.catalog_stub.Update(
                catalog_pb2.UpdateRequest(item_number=request.item_number, qty=-1)
            )
            return order_pb2.BuyResponse(
                success=True, message=f"Compra de '{book.name}' realizada!"
            )

def serve(port, catalog_host):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    order_pb2_grpc.add_OrderServicer_to_server(OrderServicer(catalog_host), server)
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    print(f"[Pedidos] Rodando na porta {port}, catálogo em {catalog_host}")
    server.wait_for_termination()

if __name__ == "__main__":
    # Uso: python order_server.py 50052 localhost:50051
    port         = sys.argv[1] if len(sys.argv) > 1 else "50052"
    catalog_host = sys.argv[2] if len(sys.argv) > 2 else "localhost:50051"
    serve(port, catalog_host)