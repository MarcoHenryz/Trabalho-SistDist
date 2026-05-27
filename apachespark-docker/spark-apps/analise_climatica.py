from pyspark.sql import SparkSession, Window
from pyspark.sql.functions import (
    col, year, month, to_date, avg, stddev, max as _max, min as _min, 
    regexp_replace, expr, count, when, lag, round as _round
)
from pyspark.ml.regression import LinearRegression
from pyspark.ml.feature import VectorAssembler

# 1. Inicialização da Sessão Spark
spark = SparkSession.builder \
    .appName("AnaliseClimaticaGlobal") \
    .master("spark://spark-master:7077") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")

print("="*50)
print("INICIANDO PIPELINE DE DADOS E ANÁLISE")
print("="*50)

# ==========================================
# FASE 1: INGESTÃO E LIMPEZA DE DADOS (ETL)
# ==========================================

# Lendo a base de Temperaturas (Atualizado para ByMajorCity)
df_temp = spark.read.csv("/opt/spark-data/input/GlobalLandTemperaturesByMajorCity.csv", header=True, inferSchema=True)

# Limpeza e Ajustes: Datas, Remoção de Nulos e Filtro de Incerteza (Pergunta 5)
df_temp_clean = df_temp.withColumn("dt", to_date(col("dt"))) \
    .withColumn("Year", year(col("dt"))) \
    .withColumn("Month", month(col("dt"))) \
    .dropna(subset=["AverageTemperature"]) \
    .withColumn("Latitude", regexp_replace(col("Latitude"), "[NSEW]", "").cast("double")) \
    .withColumn("Longitude", regexp_replace(col("Longitude"), "[NSEW]", "").cast("double"))

# Otimização: Cache no DataFrame principal limpo
df_temp_clean.cache()

# P5: Qualidade de Dados - Filtrar incerteza > 10% da média histórica da cidade
window_city = Window.partitionBy("City", "Country")
df_temp_filtered = df_temp_clean.withColumn("HistAvg", avg("AverageTemperature").over(window_city)) \
    .filter(col("AverageTemperatureUncertainty") <= (0.10 * col("HistAvg")))

# Lendo e limpando a base de CO2 (Atualizado para co2_emission.csv)
df_co2 = spark.read.csv("/opt/spark-data/input/co2_emission.csv", header=True, inferSchema=True)

# Limpeza específica da base de CO2 nova
df_co2_clean = df_co2.filter(col("Year") >= 1900) \
    .filter(~col("Entity").isin(["World", "Asia", "Europe", "Africa", "North America", "South America"])) \
    .select(
        col("Entity").alias("Country_CO2"), 
        col("Year").alias("Year_CO2"), 
        col("Annual CO₂ emissions (tonnes )").alias("co2")
    )

# ==========================================
# FASE 2: ANÁLISE E RESPOSTAS ÀS PERGUNTAS
# ==========================================

# P1: Média Móvel de Temperatura (Evolução por década)
print("\n--- Q1: Evolução da temperatura média global por década ---")
df_decada = df_temp_filtered.withColumn("Decade", (col("Year") / 10).cast("int") * 10) \
    .groupBy("Decade").agg(_round(avg("AverageTemperature"), 2).alias("AvgGlobalTemp")) \
    .orderBy("Decade")
df_decada.show(truncate=False)

# P2: Anomalias Locais (10 anos mais quentes por 'Continente/Região' - Adaptado para Países Representativos)
print("\n--- Q2: 10 Anos mais quentes (Filtro América do Sul) nos últimos 50 anos ---")
df_recent = df_temp_filtered.filter(col("Year") >= 1974)
df_sa = df_recent.filter(col("Country").isin(["Brazil", "Argentina", "Chile", "Colombia"])) \
    .groupBy("Year").agg(_round(avg("AverageTemperature"), 2).alias("AvgTemp")) \
    .orderBy(col("AvgTemp").desc()).limit(10)
df_sa.show()

# P3: Cidades em Risco (Maior desvio padrão no último século)
print("\n--- Q3: Cidades com maior instabilidade climática (Desvio Padrão > 1920) ---")
df_risk = df_temp_filtered.filter(col("Year") >= 1920) \
    .groupBy("City", "Country") \
    .agg(_round(stddev("AverageTemperature"), 2).alias("Temperature_StdDev")) \
    .orderBy(col("Temperature_StdDev").desc()).limit(10)
df_risk.show()

# P4: Correlação de Estações (Zonas Tropicais: Lat entre -23.5 e 23.5)
print("\n--- Q4: Correlação T_Max e T_Min em Zonas Tropicais ---")
df_tropicos = df_temp_filtered.filter((col("Latitude") >= -23.5) & (col("Latitude") <= 23.5)) \
    .groupBy("City", "Year") \
    .agg(_max("AverageTemperature").alias("T_Max"), _min("AverageTemperature").alias("T_Min"))
corr_t = df_tropicos.stat.corr("T_Max", "T_Min")
print(f"Coeficiente de Correlação (Pearson) T_Max vs T_Min nas zonas tropicais: {corr_t:.4f}")

# P6: Correlação entre Emissões e Aquecimento (Join)
print("\n--- Q6: Correlação entre CO2 e Aquecimento (Últimos 50 anos) ---")
df_temp_country = df_temp_filtered.filter(col("Year") >= 1974) \
    .groupBy("Country", "Year") \
    .agg(avg("AverageTemperature").alias("AvgTemp"))

# Join das duas bases via País (Country / Entity) e Ano
df_join = df_temp_country.join(
    df_co2_clean, 
    (df_temp_country["Country"] == df_co2_clean["Country_CO2"]) & 
    (df_temp_country["Year"] == df_co2_clean["Year_CO2"]), 
    "inner"
).dropna(subset=["co2", "AvgTemp"])

corr_co2 = df_join.stat.corr("co2", "AvgTemp")
print(f"Coeficiente de Correlação (Pearson) CO2 vs Temperatura Média: {corr_co2:.4f}")

# P7: Ranking de Aceleração Térmica (Window Functions)
print("\n--- Q7: Aceleração Térmica por País (Diferença de temp. década atual vs anterior) ---")
df_decada_pais = df_temp_filtered.withColumn("Decade", (col("Year") / 10).cast("int") * 10) \
    .groupBy("Country", "Decade").agg(avg("AverageTemperature").alias("TempDecada"))

window_accel = Window.partitionBy("Country").orderBy("Decade")
df_accel = df_decada_pais.withColumn("TempAnterior", lag("TempDecada", 1).over(window_accel)) \
    .withColumn("Aceleracao", col("TempDecada") - col("TempAnterior")) \
    .filter(col("Decade") == 2010) \
    .orderBy(col("Aceleracao").desc()).limit(10)
df_accel.select("Country", _round("Aceleracao", 3).alias("Graus_Aceleracao")).show()

# P8: Previsão de Tendência (Spark MLlib) - Regressão Linear para São Paulo
print("\n--- Q8: Previsão de Temperatura para os próximos 5 anos (São Paulo) ---")
df_sp = df_temp_filtered.filter((col("City") == "São Paulo") & (col("Year") >= 2000)) \
    .groupBy("Year").agg(avg("AverageTemperature").alias("label")).orderBy("Year")

assembler = VectorAssembler(inputCols=["Year"], outputCol="features")
df_ml = assembler.transform(df_sp).select("features", "label")

lr = LinearRegression(featuresCol="features", labelCol="label")
lr_model = lr.fit(df_ml)

anos_futuros = spark.createDataFrame([(y,) for y in range(2020, 2025)], ["Year"])
anos_futuros_ml = assembler.transform(anos_futuros)
previsoes = lr_model.transform(anos_futuros_ml)
previsoes.select("Year", _round("prediction", 2).alias("Temperatura_Prevista")).show()

# ==========================================
# FASE 3: ARTEFATOS DE SAÍDA (DATA LAKE)
# ==========================================
print("\nSalvando amostra no formato Parquet...")
df_join.limit(1000).write.mode("overwrite").parquet("/opt/spark-data/output/dataset_final.parquet")
print("Processamento concluído com sucesso!")

spark.stop()