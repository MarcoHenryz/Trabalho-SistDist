from pyspark.sql import SparkSession, Window
from pyspark.sql.functions import (
    col,
    year,
    month,
    to_date,
    avg,
    stddev,
    max as _max,
    min as _min,
    regexp_replace,
    expr,
    count,
    when,
    lag,
    round as _round,
)
from pyspark.ml.regression import LinearRegression
from pyspark.ml.feature import VectorAssembler

# 1. Inicialização da Sessão Spark
spark = (
    SparkSession.builder.appName(
        "AnaliseClimaticaGlobal",
    )
    .master("spark://spark-master:7077")
    .getOrCreate()
)

spark.sparkContext.setLogLevel("WARN")

print("Iniciando computação dos dados")

# FASE 1: INGESTÃO E LIMPEZA DE DADOS (ETL)

# Lendo a base de Temperaturas (Atualizado para ByMajorCity)
df = spark.read.csv(
    "/opt/spark-data/input/GlobalLandTemperaturesByCity.csv",
    header=True,
    inferSchema=True,
)

# Limpeza e Ajustes: Datas, Remoção de Nulos e Filtro de Incerteza (Pergunta 5)
df_limpo = (
    df.withColumn("dt", to_date(col("dt")))
    .withColumn("Year", year(col("dt")))
    .withColumn("Month", month(col("dt")))
    .dropna(subset=["AverageTemperature"])
    .withColumn(
        "Latitude", regexp_replace(col("Latitude"), "[NSEW]", "").cast("double")
    )
    .withColumn(
        "Longitude", regexp_replace(col("Longitude"), "[NSEW]", "").cast("double")
    )
)

df_limpo.show(5)
# Otimização: Cache no DataFrame principal limpo, para evitar ficar reprocessar todas as vezes em novas ações
df_limpo.cache()

# P5: Qualidade de Dados - Filtrar incerteza > 10% da média histórica da cidade
print("P5: Registros com incerteza > 10% da média histórica\n")
window_city = Window.partitionBy(
    "City", "Country"
)  # window permite a gente fazer calculos baseados por um certo número de linhas, retornando o resultado para cada linha individualmente. Em um primeiro momento voce cria-se apenas a especificação da janela.

df_limpo_com_histavg = df_limpo.withColumn(
    "HistAvg", avg("AverageTemperature").over(window_city)
)  # depois se aplica uma função sobre aquela janela e adiciona uma coluna ao dataframe original com o resultado.

# Mostrando registros que serão filtrados

df_alta_incerteza = df_limpo_com_histavg.filter(
    col("AverageTemperatureUncertainty") > (0.10 * col("HistAvg"))
)
print("Registros com alta incerteza que serão removidos: \n")
df_alta_incerteza.groupBy("Country").count().orderBy(col("count").desc()).show(10)

# montado df filtrado que será usado depois
df_filtrado = df_limpo_com_histavg.filter(
    col("AverageTemperatureUncertainty") <= (0.10 * col("HistAvg"))
)

print(f"Registros restantes após filtro de incerteza: {df_filtrado.count()}")


# Lendo e limpando a base de CO2 (Atualizado para co2_emission.csv)
df_co2 = spark.read.csv(
    "/opt/spark-data/input/owid-co2-data.csv", header=True, inferSchema=True
)

# Limpeza específica da base de CO2 nova
df_co2_clean = (
    df_co2.filter(col("year") >= 1900)
    .filter(
        ~col("country").isin(
            [
                "World",
                "Asia",
                "Asia (GCP)",
                "Asia (excl. China and India)",
                "Europe",
                "Europe (GCP)",
                "Europe (excl. EU-27)",
                "Europe (excl. EU-28)",
                "European Union (27)",
                "European Union (28)",
                "Africa",
                "Africa (GCP)",
                "North America",
                "North America (GCP)",
                "North America (excl. USA)",
                "South America",
                "South America (GCP)",
                "Central America (GCP)",
                "Oceania",
                "Oceania (GCP)",
                "High-income countries",
                "Low-income countries",
                "Lower-middle-income countries",
                "Upper-middle-income countries",
                "OECD (GCP)",
                "OECD (Jones et al.)",
                "Non-OECD (GCP)",
            ]
        )
    )
    .select(
        col("country").alias("Country_CO2"),
        col("year").alias("Year_CO2"),
        col("co2"),
        col("co2_per_capita"),
        col("total_ghg"),
    )
    .dropna(subset=["co2"])
)

# FASE 2: ANÁLISE E RESPOSTAS ÀS PERGUNTAS

# P1: Média Móvel de Temperatura (Evolução por década)

print("\nP1: Evolução da temperatura média global por década: \n")
df_decada = (
    df_filtrado.withColumn("Decada", (col("Year") / 10).cast("int") * 10)
    .groupBy("Decada")
    .agg(_round(avg("AverageTemperature"), 2).alias("AvgGlobalTemp"))
    .orderBy("Decada")
)
df_decada.show(truncate=False)

print("\nP2: 10 Anos mais quentes por continente nos últimos 50 anos")
df_recente = df_filtrado.filter(col("Year") >= 1974)

continentes = {
    "America do Sul": ["Brazil", "Argentina", "Chile", "Colombia", "Peru"],
    "America do Norte": ["United States", "Canada", "Mexico"],
    "Europa": ["Germany", "France", "United Kingdom", "Spain", "Italy"],
    "Asia": ["China", "India", "Japan", "Russia", "Indonesia"],
    "Africa": ["Nigeria", "South Africa", "Ethiopia", "Egypt", "Kenya"],
}

for continente, paises in continentes.items():
    print(f"\n>> {continente}:")
    df_cont = (
        df_recente.filter(col("Country").isin(paises))
        .groupBy("Year")
        .agg(_round(avg("AverageTemperature"), 2).alias("AvgTemp"))
        .orderBy(col("AvgTemp").desc())
        .limit(10)
    )
    df_cont.show()


# P3: Cidades em Risco (Maior desvio padrão no último século)

print("\nP3: Cidades com maior instabilidade climática no último século")
df_risk = (
    df_filtrado.filter(col("Year") >= 1920)
    .groupBy("City", "Country")
    .agg(_round(stddev("AverageTemperature"), 2).alias("Temperature_StdDev"))
    .orderBy(col("Temperature_StdDev").desc())
    .limit(10)
)
df_risk.show()

# P4: Correlação de Estações (Zonas Tropicais: Lat entre -23.5 e 23.5)
print("\nP4: Correlação T_Max e T_Min em Zonas Tropicais")
df_tropicos = (
    df_filtrado.filter((col("Latitude") >= -23.5) & (col("Latitude") <= 23.5))
    .groupBy("City", "Year")
    .agg(
        _max("AverageTemperature").alias("T_Max"),
        _min("AverageTemperature").alias("T_Min"),
    )
)
corr_t = df_tropicos.stat.corr("T_Max", "T_Min")
print(
    f"Coeficiente de Correlação (Pearson) T_Max vs T_Min nas zonas tropicais: {corr_t:.4f}"
)
# t max e t min representam o maior e menor valor mensal de AverageTemperature, agrupados por cidades/ano, pois o dataset não tem min/max diarios

# P6: Correlação entre Emissões e Aquecimento (Join)
print("\n--- Q6: Correlação entre CO2 e Aquecimento (Últimos 50 anos) ---")
df_temp_country = (
    df_filtrado.filter(col("Year") >= 1974)
    .groupBy("Country", "Year")
    .agg(avg("AverageTemperature").alias("AvgTemp"))
)

# Padronização de nomes de países antes do join para reduzir perda de registros

df_temp_country = df_temp_country.withColumn(
    "Country", regexp_replace(col("Country"), "United States", "United States")
).withColumn("Country", regexp_replace(col("Country"), "Brasil", "Brazil"))

df_co2_clean = df_co2_clean.withColumn(
    "Country_CO2", regexp_replace(col("Country_CO2"), "United States", "United States")
)

df_join = df_temp_country.join(
    df_co2_clean,
    (df_temp_country["Country"] == df_co2_clean["Country_CO2"])
    & (df_temp_country["Year"] == df_co2_clean["Year_CO2"]),
    "inner",
).dropna(subset=["co2", "AvgTemp"])

corr_co2 = df_join.stat.corr("co2", "AvgTemp")
print(f"Coeficiente de Correlação (Pearson) CO2 vs Temperatura Média: {corr_co2:.4f}")

# P7: Ranking de Aceleração Térmica (Window Functions)
print("\nQ7: Aceleração Térmica por País (Diferença de temp. década atual vs anterior)")
df_decada_pais = (
    df_filtrado.withColumn("Decada", (col("Year") / 10).cast("int") * 10)
    .groupBy("Country", "Decada")
    .agg(avg("AverageTemperature").alias("TempDecada"))
)

window_accel = Window.partitionBy("Country").orderBy("Decada")
df_accel = (
    df_decada_pais.withColumn("TempAnterior", lag("TempDecada", 1).over(window_accel))
    .withColumn("Aceleracao", col("TempDecada") - col("TempAnterior"))
    .filter(col("Decada") == 2010)
    .orderBy(col("Aceleracao").desc())
    .limit(10)
)
df_accel.select("Country", _round("Aceleracao", 3).alias("Graus_Aceleracao")).show()

# P8: Previsão de Tendência (Spark MLlib) - Regressão Linear para São Paulo
print("\nQ8: Previsão de Temperatura para os próximos 5 anos (São Paulo)")
df_sp = (
    df_filtrado.filter((col("City") == "São Paulo") & (col("Year") >= 1993))
    .groupBy("Year")
    .agg(avg("AverageTemperature").alias("label"))
    .orderBy("Year")
)

assembler = VectorAssembler(inputCols=["Year"], outputCol="features")
df_ml = assembler.transform(df_sp).select("features", "label")

lr = LinearRegression(featuresCol="features", labelCol="label")
lr_model = lr.fit(df_ml)

anos_futuros = spark.createDataFrame([(y,) for y in range(2014, 2019)], ["Year"])
anos_futuros_ml = assembler.transform(anos_futuros)
previsoes = lr_model.transform(anos_futuros_ml)
previsoes.select("Year", _round("prediction", 2).alias("Temperatura_Prevista")).show()

# FASE 3: ARTEFATOS DE SAÍDA (DATA LAKE)

print("\nSalvando amostra em CSV")
df_join.limit(1000).write.mode("overwrite").csv(
    "/opt/spark-data/output/dataset_final.csv", header=True
)
print("Processamento concluído com sucesso!")

spark.stop()
