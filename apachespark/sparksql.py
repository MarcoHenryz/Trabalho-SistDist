from pyspark.sql import SparkSession, Row
import pandas as pd
from datetime import datetime, date
from pyspark.sql import Column
from pyspark.sql.functions import pandas_udf, upper


# spark = (
#     SparkSession.builder.appName("Python Spark SQL Example")
#     .config("spark.some.config.option", "some value")
#     .getOrCreate()
# )

spark = SparkSession.builder.getOrCreate()

# criando um dataframe

df = spark.createDataFrame(
    [
        Row(a=1, b=2.0, c="string1", d=date(2000, 1, 1), e=datetime(2000, 1, 1, 12, 0)),
        Row(a=2, b=3.0, c="string2", d=date(2000, 2, 1), e=datetime(2000, 1, 2, 12, 0)),
        Row(a=4, b=5.0, c="string3", d=date(2000, 3, 1), e=datetime(2000, 1, 3, 12, 0)),
    ]
)

# criando um dataframe com esquema específico

df2 = spark.createDataFrame(
    [
        (1, 2.0, "string1", date(2000, 1, 1), datetime(2000, 1, 1, 12, 0)),
        (2, 3.0, "string2", date(2000, 2, 1), datetime(2000, 1, 2, 12, 0)),
        (3, 4.0, "string3", date(2000, 3, 1), datetime(2000, 1, 3, 12, 0)),
    ],
    schema="a long, b double, c string, d date, e timestamp",
)

# da para criar um spark dataframe a partir de um pandas dataframe

pandas_df = pd.DataFrame(
    {
        "a": [1, 2, 3],
        "b": [2.0, 3.0, 4.0],
        "c": ["string1", "string2", "string3"],
        "d": [date(2000, 1, 1), date(2000, 2, 1), date(2000, 3, 1)],
        "e": [
            datetime(2000, 1, 1, 12, 0),
            datetime(2000, 1, 2, 12, 0),
            datetime(2000, 1, 3, 12, 0),
        ],
    }
)

# df3 = spark.createDataFrame(pandas_df)
#
# print(df3)
#
# df3.show()
#
# print(df2)
#
# df2.show()
#
print(df)

df.show()
df.printSchema()  # printa o esquema do dataframe, quais os tipos de dados envolvidos
df.show(1)  # mostrando a primeiras x linhas só trocar o valor no parâmetro

spark.conf.set(
    "spark.sql.repl.eagerEval.enabled", True
)  # comando para setar uma config no spark

df.show(1, vertical=True)
print(df.columns)


# Para mostrar o sumário do dataframe
#
print(df.select("a", "b", "c").describe().show())

# dataFrame.collect() coleta os dados distribuídos e coloca no lado do driver como dados locais

df.collect()  # retorna uma lista de linhas, cada uma representando uma linha do dataFrame

df_pandas = df.toPandas()  # retorna um df pandas, também é adicionado os dados no lado do driver, logo se for muito grande, pode dar erro de falta de memória

# A simples de seleção de uma coluan de um DataFrame não inicia a computação, mas sim retorna uma instância de Coluna(Column)
#
# Seleção de uma coluna do dataframe, retorna um novo dataFrame

column_c = df.select("c")
column_c.show()

# adicionar uma nova coluna no dataframe, se usar o nome de uma que já existe substitui

new_df = df.withColumn("c_upper", upper(df.c))
new_df.show()

# para selecionar uma certa quantidade de linhas se faz

df.filter(df.a == 1).show()

# o pyspark tem suporte a funções feitas pelo usuário ou por outras APIs, como a pandas UDF (UDF = User Defined Funcition)


@pandas_udf("long")
def pandas_plus_one(series: pd.Series) -> pd.Series:
    return series + 1


df.select(pandas_plus_one(df.a)).show()

# mais um formato de usar funções em pandas utilizando o mapInPandas


def pandas_filter_func(iterator):
    for pandas_df in iterator:
        yield pandas_df[pandas_df.a == 1]


df.mapInPandas(pandas_filter_func, schema=df.schema).show()

df_novo = spark.createDataFrame(
    [
        ["red", "banana", 1, 10],
        ["blue", "banana", 2, 20],
        ["red", "carrot", 3, 30],
        ["blue", "grape", 4, 40],
        ["red", "carrot", 5, 50],
        ["black", "carrot", 6, 60],
        ["red", "banana", 7, 70],
        ["red", "grape", 8, 80],
    ],
    schema=["color", "fruit", "v1", "v2"],
)

df_novo.show()

# método de agrupar dados usando um argumento em comum, divide aplica filtro, combina deopis.

print(df_novo.groupby("color"))  # retona um tipo de dado GroupedData

df_novo.groupby(
    "color"
).avg().show()  # o primeiro call retorna o tipo GroupedData que não tem a função show(), mas a função avg() retorna um DataFrame o que permite a gente utilizar o show()

# Ao invés de usar um método pronto , podem usar uma função nativa do python criada para cada grupo usando a API do pandas


def plus_mean(pandas_df):
    return pandas_df.assign(v1=pandas_df.v1 - pandas_df.v1.mean())


result_schema = "color string, fruit string, v1 double, v2 long"  # necessário criar outro porque resultado da conta de plus mean pode não ser um valor inteiro


df_novo.groupby("color").applyInPandas(plus_mean, schema=result_schema).show()
