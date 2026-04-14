import grpc
import sys
import time
import bookstore_pb2
import bookstore_pb2_grpc

def run(frontend_host):
    with grpc.insecure_channel(frontend_host) as channel:
        stub = bookstore_pb2_grpc.BookstoreStub(channel)

        while True:
            print("\n--- Minibib.com ---")
            print("1. search <tópico>")
            print("2. lookup <número>")
            print("3. buy <número>")
            print("4. sair")
            cmd = input("> ").strip().split()

            if not cmd:
                continue
            elif cmd[0] == "search" and len(cmd) > 1:
                start = time.time()
                resp = stub.Search(bookstore_pb2.SearchRequest(topic=cmd[1]))
                elapsed = time.time() - start
                if resp.books:
                    for b in resp.books:
                        print(f"  [{b.item_number}] {b.name} (estoque: {b.stock})")
                else:
                    print("  Nenhum livro encontrado.")
                print(f"  Tempo: {elapsed*1000:.2f}ms")

            elif cmd[0] == "lookup" and len(cmd) > 1:
                start = time.time()
                resp = stub.Lookup(bookstore_pb2.LookupRequest(item_number=int(cmd[1])))
                elapsed = time.time() - start
                if resp.success:
                    b = resp.book
                    print(f"  {b.name} | Tópico: {b.topic} | Estoque: {b.stock}")
                else:
                    print("  Item não encontrado.")
                print(f"  Tempo: {elapsed*1000:.2f}ms")

            elif cmd[0] == "buy" and len(cmd) > 1:
                start = time.time()
                resp = stub.Buy(bookstore_pb2.BuyRequest(item_number=int(cmd[1])))
                elapsed = time.time() - start
                print(f"  {resp.message}")
                print(f"  Tempo: {elapsed*1000:.2f}ms")

            elif cmd[0] == "sair":
                break

if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else "localhost:50050"
    run(host)