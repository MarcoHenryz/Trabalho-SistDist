from pyspark.sql import SparkSession
from pyspark.sql.window import Window

spark = SparkSession.builder.appName("pyspark_window").getOrCreate()

sampleData = (
    ("Olivia", 28, "Sales", 3000),
    ("Harry", 33, "Sales", 4600),
    ("Smith", 40, "Sales", 4100),
    ("Marry", 25, "Finance", 3000),
    ("Henry", 28, "Sales", 3000),
    ("Lars", 46, "Management", 3300),
    ("Jeny", 26, "Finance", 3900),
    ("Aya", 30, "Marketing", 3000),
    ("Omar", 29, "Marketing", 2000),
    ("Johnny", 39, "Sales", 4100),
)

columns = ["Employee_Name", "Age", "Department", "Salary"]

df = spark.createDataFrame(data=sampleData, schema=columns)

windowPartition = Window.partitionBy("Department").orderBy("Age")
df.printSchema()

df.show()
