---
title: "HY562 / CS-562 — Lab Environment Setup Guide"
subtitle: "Big Data Processing & Analytics · University of Crete · Fall 2026"
---

# 1. What you get

One Docker environment, identical for everybody, used in **all labs and assignments**:

| Component | Version | Where |
|---|---|---|
| Python | 3.12 | container `spark-lab` |
| Java (OpenJDK) | 17 | container `spark-lab` |
| Apache Spark / PySpark | **4.2.0** (Scala 2.13) | `pip install pyspark==4.2.0` inside the image |
| JupyterLab | 4.x | <http://localhost:8888> |
| Spark UI | — | <http://localhost:4040> (4041 for a 2nd session) |
| Kafka connector | `org.apache.spark:spark-sql-kafka-0-10_2.13:4.2.0` | preset in `spark.jars.packages` |
| Apache Kafka (KRaft, single node) | `apache/kafka:4.3.1` | container `kafka`, reachable as **`kafka:9092`** from the notebooks, `localhost:29092` from your laptop |
| Extras | pandas, pyarrow, matplotlib, networkx, kafka-python, qiskit, qiskit-aer | container `spark-lab` |

Folder layout (keep it as is — notebooks use relative paths such as `../../05_Data/retail.parquet`):

```
HY562_2026/
├── 02_Labs/          Lab1_…  Lab5_…  (notebooks, slides)
├── 03_Assignments/
├── 04_Environment/   Dockerfile, docker-compose.yml, conf/, 00_check_environment.ipynb, this guide
└── 05_Data/          toy.csv, retail.csv, retail.parquet
```

The **whole `HY562_2026` folder** is mounted into the container as `/home/jovyan/work`. Everything you save
in JupyterLab is stored in that folder on your own disk; deleting the container never deletes your work.

# 2. Install Docker

**Windows 10/11** — install *Docker Desktop* (<https://docs.docker.com/desktop/>). Accept the **WSL 2** backend
when asked (run `wsl --install` in an administrator PowerShell first if WSL is missing, then reboot).
Put the course folder on a normal local drive (e.g. `C:\Users\<you>\HY562_2026`) or, for best speed,
inside the WSL file system (`\\wsl$\Ubuntu\home\<you>\HY562_2026`).

**macOS (Intel or Apple Silicon)** — install *Docker Desktop for Mac* (choose the right chip).
In *Settings → Resources* give Docker at least **4 CPUs and 6 GB RAM**.

**Linux** — install *Docker Engine* and the *compose plugin* from <https://docs.docker.com/engine/install/>
(e.g. Ubuntu: `sudo apt install docker-ce docker-ce-cli containerd.io docker-compose-plugin`), then
`sudo usermod -aG docker $USER` and log out/in so you can run `docker` without `sudo`.

Check: `docker --version` and `docker compose version` (Compose v2 — the command is `docker compose`, with a space).

# 3. Start the environment

```bash
cd HY562_2026/04_Environment
docker compose up -d --build      # first time: builds the image (5-10 min, ~2.5 GB download)
docker compose ps                 # spark-lab and kafka "running"; kafka-init "exited (0)"
```

Afterwards simply `docker compose up -d` (start) and `docker compose down` (stop).
After `git pull`/an updated Dockerfile, rebuild with `docker compose build --pull`.

# 4. Open JupyterLab

Open **<http://localhost:8888/lab?token=hy562>** (the token is set in `docker-compose.yml` → `JUPYTER_TOKEN`;
change it if you like). `docker compose logs spark-lab` also prints the URL.

In JupyterLab open `04_Environment/00_check_environment.ipynb` and choose **Run ▸ Run All Cells**. You should see:

* ✅ Java 17, ✅ Spark 4.2.0 / Scala 2.13, ✅ a small DataFrame job,
* ✅ data folder with `retail.parquet` (20 000 transactions),
* ✅ Kafka broker reachable at `kafka:9092` and topic `retail-events`,
* ✅ pandas / pyarrow / matplotlib / networkx / kafka / qiskit.

While a notebook holds an active `SparkSession`, the Spark UI is at <http://localhost:4040>.

# 5. Troubleshooting

| Symptom | Fix |
|---|---|
| `port is already allocated` (8888, 4040 or 29092) | Another Jupyter/Spark/Kafka is running. Stop it, or change the *left* side of the mapping in `docker-compose.yml`, e.g. `"8889:8888"`, and open `localhost:8889`. |
| Windows: container killed, `Java heap space`, very slow | WSL 2 memory limit. Create `%UserProfile%\.wslconfig` with `[wsl2]` / `memory=6GB` / `processors=4`, run `wsl --shutdown`, restart Docker Desktop. |
| Windows: the course folder looks empty inside Jupyter | Docker Desktop → *Settings → Resources → File sharing* must include the drive; avoid OneDrive "online-only" folders (make them "Always keep on this device"). |
| macOS Apple Silicon (M1–M4) | The image builds natively for `arm64` (all components have arm64 builds). If you see `exec format error` you pulled an amd64 image: run `docker compose build --no-cache`. |
| Linux: `Permission denied` when saving notebooks | The container user has UID 1000. Either `sudo chown -R 1000:1000 HY562_2026` or build with your UID: `docker compose build --build-arg NB_UID=$(id -u)`. |
| First `SparkSession` hangs at `:: resolving dependencies ::` | Spark downloads the Kafka connector from Maven Central the first time (if the build could not pre-fetch it). Wait ~1 min with Internet access; it is cached afterwards. |
| `Spark UI` is on 4041 | A second notebook created its own `SparkSession`. Stop idle kernels (*Kernel ▸ Shut Down*). |
| Kafka unhealthy / `kafka-init` failed | `docker compose logs kafka`; then `docker compose down -v && docker compose up -d`. |
| Browser asks for a password/token | Use the token `hy562` (or your `JUPYTER_TOKEN`). |

# 6. Alternative without Docker (fallback)

Works on Linux, macOS and Windows (natively or in WSL 2); **Kafka is not included** (the Kafka part of Lab 3
is optional and guarded by a flag).

1. Install a **Java 17 JDK** (e.g. Eclipse Temurin 17 from <https://adoptium.net>) and set `JAVA_HOME`.
   Check with `java -version` (Java 21 also works with Spark 4.x).
2. Python 3.10–3.13 and a virtual environment:

```bash
python3 -m venv ~/hy562-venv
source ~/hy562-venv/bin/activate          # Windows: %USERPROFILE%\hy562-venv\Scripts\activate
pip install pyspark==4.2.0 jupyterlab "pandas<3" pyarrow matplotlib networkx kafka-python qiskit qiskit-aer
cd HY562_2026 && jupyter lab
```

3. Windows native (not WSL): Spark also needs `winutils.exe`/`hadoop.dll` for writing files; WSL 2 is
   strongly recommended instead.

# 7. Scala users

Scala is allowed for assignments (Spark 4.x is **Scala 2.13 only**).

* **Inside the container**: open a JupyterLab *Terminal* (or `docker compose exec spark-lab bash`) and run
  `spark-shell` — the PySpark installation ships the full Spark distribution including the Scala REPL.
  Kafka: `spark-shell --packages org.apache.spark:spark-sql-kafka-0-10_2.13:4.2.0` (already in the defaults).
* **sbt project on your laptop** (`build.sbt`):

```scala
ThisBuild / scalaVersion := "2.13.16"
libraryDependencies ++= Seq(
  "org.apache.spark" %% "spark-sql"            % "4.2.0" % "provided",
  "org.apache.spark" %% "spark-sql-kafka-0-10" % "4.2.0"
)
```

  Build a jar with `sbt package`, copy it into the course folder and run it in the container with
  `spark-submit --class Main target/scala-2.13/<name>.jar`.

# 8. Useful commands

```bash
docker compose ps                         # status
docker compose logs -f spark-lab          # Jupyter log / URL
docker compose exec spark-lab bash        # shell inside the lab container
docker compose exec kafka /opt/kafka/bin/kafka-console-consumer.sh \
        --bootstrap-server kafka:9092 --topic retail-events --from-beginning --max-messages 5
docker compose down                       # stop (your files stay in HY562_2026/)
docker system prune                       # free disk space from old images
```

Questions: course forum / TAs **Manos Limnaios, Sofia Sideri, Michalis Grigorakis**.
