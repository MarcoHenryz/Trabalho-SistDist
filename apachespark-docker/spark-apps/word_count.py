from pyspark.sql import SparkSession
from pyspark.sql.functions import col, explode, split

spark = (
    SparkSession.builder.appName("WordCount")
    .master("spark://spark-master:7077")
    .getOrCreate()
)

data = [
    ("Apache Spark is a unified analytics engine",),
    ("Spark provides high-level APIs in Java, Scala, Python and R",),
    ("Spark also supports a rich set of higher-level tools",),
]

df = spark.createDataFrame(data, ["text"])

word_count = (
    df.select(explode(split(col("text"), " ")).alias("word"))
    .groupBy("word")
    .count()
    .orderBy(col("count").desc())
)

print("\nWord count results")
word_count.show(20, truncate=False)

spark.stop()
