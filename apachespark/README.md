# Análise Global de Mudanças Climáticas — Apache Spark

Projeto da disciplina **Sistemas Distribuídos**. Processa dados históricos de
temperatura global (Berkeley Earth) e emissões de CO2 (Our World in Data) com
**PySpark 4.1.1** em modo local (`local[*]`) para identificar tendências de
aquecimento, anomalias térmicas e correlação CO2 × temperatura.

Especificação completa do trabalho: `refs/Trabalho_SD_2026_Spark.pdf`.

## Pré-requisitos

- **Java 17** (JDK)
- **Python 3.11**
- ~2 GB de RAM livre (Spark driver usa até 6 GB se disponível)
- ~520 MB de disco para os datasets

## Setup do ambiente

Todos os comandos abaixo são executados **dentro da pasta `apachespark/`**.

### Opção A — mise (recomendado)

[mise](https://mise.jdx.dev) gerencia as versões de Java e Python e exporta a
variável de ambiente necessária automaticamente (já configurado em `mise.toml`).

**1. Instalar o mise:**

- **Arch Linux:**
  ```bash
  sudo pacman -S mise
  ```
- **Ubuntu / Debian:**
  ```bash
  curl https://mise.run | sh
  ```
- **Windows (PowerShell):**
  ```powershell
  winget install jdx.mise
  ```

Ative o mise no shell (uma vez):

- zsh: `echo 'eval "$(mise activate zsh)"' >> ~/.zshrc && exec zsh`
- bash: `echo 'eval "$(mise activate bash)"' >> ~/.bashrc && exec bash`
- Windows: siga https://mise.jdx.dev/installing-mise.html#windows

**2. Instalar Java 17 + Python 3.11 (lê `mise.toml`):**

```bash
cd apachespark
mise install
```

Isso instala as versões fixadas em `mise.toml` e passa a exportar
`JAVA_TOOL_OPTIONS="-XX:-UseContainerSupport"` ao entrar na pasta.

### Opção B — Instalação manual (fallback, sem mise)

Instale Java 17 e Python 3.11 pelo gerenciador da sua plataforma:

- **Arch Linux:**
  ```bash
  sudo pacman -S python jdk17-openjdk
  ```
- **Ubuntu / Debian:**
  ```bash
  sudo apt update
  sudo apt install -y python3.11 python3.11-venv python3-pip openjdk-17-jdk
  ```
- **Windows (PowerShell):**
  ```powershell
  winget install Python.Python.3.11
  winget install Microsoft.OpenJDK.17
  ```

> **Arch Linux — passo obrigatório:** com Java 17 + cgroup v2, o Spark lê a
> memória do sistema errado e falha. Exporte a variável (o mise faz isso
> automaticamente; manualmente é necessário):
> ```bash
> export JAVA_TOOL_OPTIONS="-XX:-UseContainerSupport"
> ```
> Adicione a linha ao seu `~/.zshrc` / `~/.bashrc` para torná-la permanente.

### Criar o virtualenv e instalar dependências

```bash
cd apachespark
python -m venv .venv
```

Ative o virtualenv:

- **Linux / macOS:** `source .venv/bin/activate`
- **Windows (PowerShell):** `.venv\Scripts\Activate.ps1`
- **Windows (cmd):** `.venv\Scripts\activate.bat`

Instale as dependências:

```bash
pip install -r requirements.txt
```

## Obter os datasets

Os CSVs **não** estão no repositório (`.gitignore`). Baixe e coloque ambos em
`apachespark/data/`:

- **Temperaturas (Berkeley Earth):** Kaggle —
  https://www.kaggle.com/datasets/berkeleyearth/climate-change-earth-surface-temperature-data
  → arquivo `GlobalLandTemperaturesByCity.csv`
- **Emissões de CO2 (Our World in Data):**
  https://github.com/owid/co2-data → arquivo `owid-co2-data.csv`

Estrutura final esperada:

```
apachespark/data/GlobalLandTemperaturesByCity.csv
apachespark/data/owid-co2-data.csv
```

## Verificar a instalação

```bash
python teste_spark.py
```

Saída esperada (aproximada):

```
Spark rodando! Versão: 4.1.1
+------+-----+
|  Pais| Temp|
+------+-----+
|Brasil| 27.5|
|Canada| -5.2|
| India| 30.1|
+------+-----+
```

## Rodar o notebook

```bash
jupyter notebook analise_clima.ipynb
```

A Spark UI fica disponível em http://localhost:4040 enquanto a `SparkSession`
estiver ativa.
