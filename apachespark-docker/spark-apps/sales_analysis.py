from pyspark.sql import SparkSession
from pyspark.sql.functions import col, sum as _sum, avg, count, round as _round
from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    IntegerType,
    DoubleType,
    DateType,
)

spark = (
    SparkSession.builder.appName("Sale Analysis")
    .master("spark://spark-master:7077")
    .getOrCreate()
)

# define o esquema para melhor performance
schema = StructType(
    [
        StructField("date", DateType(), True),
        StructField("product", StringType(), True),
        StructField("category", StringType(), True),
        StructField("quantity", IntegerType(), True),
        StructField("price", DoubleType(), True),
    ]
)

# Lendo o CSV

sales_df = (
    spark.read.option("header", "true")
    .option("dateFormat", "yyyy-MM-dd")
    .schema(schema)
    .csv("/opt/spark-data/input/sales_data.csv")
)

sales_df = sales_df.withColumn("revenue", col("quantity") * col("price"))

print("Total de vendas por produto")

product_sales = (
    sales_df.groupBy("product")
    .agg(
        _sum("quantity").alias("total_quantity"),
        _round(_sum("revenue"), 2).alias("total_revenue"),
    )
    .orderBy(col("total_revenue").desc())
)

product_sales.show()

print("Vendas por categoria")

# Vendas por categoria

category_sales = (
    sales_df.groupBy("category")
    .agg(
        count("*").alias("transactions"),
        _sum("quantity").alias("total_items"),
        _round(_sum("revenue"), 2).alias("total_revenue"),
        _round(avg("revenue"), 2).alias("avg_transaction_value"),
    )
    .orderBy(col("total_revenue").desc())
)

category_sales.show()

# Salvando Resultados no CSV

print("Salvando resultados")

product_sales.coalesce(1).write.mode("overwrite").option("header", "true").csv(
    "/opt/spark-data/output/category_sales"
)

print("Análise completa! Resultados salvos no diretorio output")

spark.stop()
