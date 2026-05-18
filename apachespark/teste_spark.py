from pyspark.sql import SparkSession

spark = (
    SparkSession.builder.appName("TesteAmbiente")
    .master("local[*]")
    .config("spark.driver.memory", "4g")
    .getOrCreate()
)

print("Spark rodando! Versão:", spark.version)

# Teste básico
dados = [("Brasil", 27.5), ("Canada", -5.2), ("India", 30.1)]
df = spark.createDataFrame(dados, ["Pais", "Temp"])
df.show()

spark.stop()
