from pyspark.sql import SparkSession

logFile = "README.md"  # arquivo no diretorio atual

spark = SparkSession.builder.appName("SimpleApp").getOrCreate()
logData = spark.read.text(logFile).cache()

numAs = logData.filter(logData.value.contains("a")).count()
numBs = logData.filter(logData.value.contains("b")).count()

print(f"Lines with a: {numAs}, lines with b: {numBs}")

spark.stop()
