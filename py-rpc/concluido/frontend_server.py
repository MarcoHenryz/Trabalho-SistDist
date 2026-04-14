import grpc
from concurrent import futures
import sys
import bookstore_pb2
import bookstore_pb2_grpc
import catalog_pb2
import catalog_pb2_grpc
import order_pb2
import order_pb2_grpc

class BookstoreServicer(bookstore_pb2_grpc.BookstoreServicer):

    def __init__(self, catalog_host, order_host):
        self.catalog_stub = catalog_pb2_grpc.CatalogStub(
            grpc.insecure_channel(catalog_host)
        )
        self.order_stub = order_pb2_grpc.OrderStub(
            grpc.insecure_channel(order_host)
        )

    def Search(self, request, context):
        resp = self.catalog_stub.Query(
            catalog_pb2.QueryRequest(arg=request.topic)
        )
        books = [
            bookstore_pb2.BookInfo(
                item_number=b.item_number, name=b.name,
                topic=b.topic, stock=b.stock
            )
            for b in resp.books
        ]
        return bookstore_pb2.SearchResponse(books=books)

    def Lookup(self, request, context):
        resp = self.catalog_stub.Query(
            catalog_pb2.QueryRequest(arg=str(request.item_number))
        )
        if not resp.books:
            return bookstore_pb2.LookupResponse(success=False)
        b = resp.books[0]
        return bookstore_pb2.LookupResponse(
            book=bookstore_pb2.BookInfo(
                item_number=b.item_number, name=b.name,
                topic=b.topic, stock=b.stock
            ),
            success=True
        )

    def Buy(self, request, context):
        resp = self.order_stub.Buy(
            order_pb2.BuyRequest(item_number=request.item_number)
        )
        return bookstore_pb2.BuyResponse(
            success=resp.success, message=resp.message
        )

def serve(port, catalog_host, order_host):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    bookstore_pb2_grpc.add_BookstoreServicer_to_server(
        BookstoreServicer(catalog_host, order_host), server
    )
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    print(f"[Front-end] Rodando na porta {port}")
    server.wait_for_termination()

if __name__ == "__main__":
    # Uso: python frontend_server.py 50050 localhost:50051 localhost:50052
    port         = sys.argv[1] if len(sys.argv) > 1 else "50050"
    catalog_host = sys.argv[2] if len(sys.argv) > 2 else "localhost:50051"
    order_host   = sys.argv[3] if len(sys.argv) > 3 else "localhost:50052"
    serve(port, catalog_host, order_host)