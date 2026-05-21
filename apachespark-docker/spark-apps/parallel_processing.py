from pyspark.sql import SparkSession
from pyspark.sql.functions import col, rand
import time

spark = (
    SparkSession.builder.appName("ParallelProcessing")
    .master("spark://spark-master:7077")
    .config("spark.executor.instances", "3")
    .config("spark.executor.cores", "2")
    .config("spark.executor.memory", "2g")
    .getOrCreate()
)

# Criando um dataset grande para processamento
# 10 milhões de linhas kkkkkk

df = spark.range(0, 1000000).withColumn("random_value", rand())

# Repartindo para garantir a distribuição de processamento

df = df.repartition(12)  # 3 workers * 2 cores * 2 tasks por core

print("Iniciando computação distribuída")
start_time = time.time()

result = (
    df.groupBy((col("id") % 100).alias("partition"))
    .agg({"random_value": "avg", "id": "count"})
    .orderBy("partition")
)

count = result.count()
end_time = time.time()

print(f"\n Foram processados {count} partições em {end_time - start_time:.2f} segundos")
print("Resultados: \n")
result.show(10)


print("Numero de partições distribuídas:", df.rdd.getNumPartitions())

spark.stop()
