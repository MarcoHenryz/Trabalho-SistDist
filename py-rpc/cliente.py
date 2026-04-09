import grpc
import calculator_pb2
import calculator_pb2_grpc


def run():
    # Conecta ao servidor
    with grpc.insecure_channel("localhost:50051") as channel:
        stub = calculator_pb2_grpc.CalculatorStub(channel)

        # Chama Add
        response_add = stub.Add(calculator_pb2.CalculatorRequest(a=10, b=5))
        print(f"Resultado da Adição: {response_add.result}")

        # Chama Subtract
        response_sub = stub.Subtract(calculator_pb2.CalculatorRequest(a=10, b=5))
        print(f"Resultado da Subtração: {response_sub.result}")


if __name__ == "__main__":
    run()
