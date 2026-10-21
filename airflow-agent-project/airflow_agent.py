import os
import subprocess
import time
import shutil

# ================= CONFIG =================
AIRFLOW_VERSION = "2.10.2"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(BASE_DIR, "venv")
AIRFLOW_HOME = os.path.join(BASE_DIR, "airflow_home")

POSTGRES_USER = "airflow"
POSTGRES_PASSWORD = "airflow"
POSTGRES_DB = "airflow"

DB_URI = f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@localhost/{POSTGRES_DB}"

# =============== RUN =================
def run(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.returncode, result.stdout.strip(), result.stderr.strip()

# =============== CLEAN =================
def clean_all():
    print("🧹 Cleaning old setup...")

    run("pkill -f 'airflow webserver' || true")
    run("pkill -f 'airflow scheduler' || true")

    time.sleep(2)

    if os.path.exists(VENV_DIR):
        shutil.rmtree(VENV_DIR)

    if os.path.exists(AIRFLOW_HOME):
        shutil.rmtree(AIRFLOW_HOME)

    # ✅ Delete log files
    for log_file in ["scheduler.log", "web.log"]:
        log_path = os.path.join(BASE_DIR, log_file)
        if os.path.exists(log_path):
            os.remove(log_path)
            print(f"🗑 Deleted {log_file}")

# =============== POSTGRES SETUP =================
def setup_postgres():
    print("🗄 Setting up PostgreSQL...")

    run("sudo apt update")
    run("sudo apt install postgresql postgresql-contrib -y")

    # Start service
    run("sudo systemctl start postgresql")

    # Create DB + user safely
    run(f"sudo -u postgres psql -c \"DROP DATABASE IF EXISTS {POSTGRES_DB};\"")
    run(f"sudo -u postgres psql -c \"DROP USER IF EXISTS {POSTGRES_USER};\"")

    run(f"sudo -u postgres psql -c \"CREATE USER {POSTGRES_USER} WITH PASSWORD '{POSTGRES_PASSWORD}';\"")
    run(f"sudo -u postgres psql -c \"CREATE DATABASE {POSTGRES_DB} OWNER {POSTGRES_USER};\"")

    run(f"sudo -u postgres psql -c \"GRANT ALL PRIVILEGES ON DATABASE {POSTGRES_DB} TO {POSTGRES_USER};\"")

# =============== INSTALL =================
def install_airflow(port, username, password):

    clean_all()
    setup_postgres()

    print("📦 Installing system packages...")
    run("sudo apt install python3-venv python3-dev libpq-dev -y")

    print("📦 Creating virtual environment...")
    code, _, err = run(f"python3 -m venv {VENV_DIR}")
    if code != 0:
        print("❌ Venv failed:", err)
        return

    pip = f"{VENV_DIR}/bin/pip"
    airflow = f"{VENV_DIR}/bin/airflow"

    print("📦 Installing Airflow + PostgreSQL driver...")
    code, _, err = run(
        f"{pip} install apache-airflow=={AIRFLOW_VERSION} psycopg2-binary "
        f"--constraint https://raw.githubusercontent.com/apache/airflow/constraints-{AIRFLOW_VERSION}/constraints-3.12.txt"
    )
    if code != 0:
        print("❌ Install failed:", err)
        return

    # ENV
    os.makedirs(AIRFLOW_HOME, exist_ok=True)
    os.environ["AIRFLOW_HOME"] = AIRFLOW_HOME
    os.environ["AIRFLOW__DATABASE__SQL_ALCHEMY_CONN"] = DB_URI
    os.environ["AIRFLOW__CORE__EXECUTOR"] = "LocalExecutor"

    print("🗄 Initializing DB...")
    code, _, err = run(f"{airflow} db migrate")
    if code != 0:
        print("⚠ migrate failed → trying init")
        code, _, err = run(f"{airflow} db init")
        if code != 0:
            print("❌ DB init failed:", err)
            return

    # USER CREATION (SAFE)
    print("👤 Creating user...")
    code, out, _ = run(f"{airflow} users list")

    if username not in out:
        code, _, err = run(
            f"{airflow} users create "
            f"--username {username} "
            f"--password {password} "
            f"--firstname admin "
            f"--lastname user "
            f"--role Admin "
            f"--email admin@example.com"
        )
        if code != 0:
            print("❌ User creation failed:", err)
            return
    else:
        print("✔ User already exists")

    print("🚀 Starting Airflow...")

    run(f"nohup {airflow} webserver --port {port} > web.log 2>&1 &")
    run(f"nohup {airflow} scheduler > scheduler.log 2>&1 &")

    time.sleep(5)

    print(f"\n✅ Airflow running → http://localhost:{port}")

# =============== VERIFY =================
def verify_airflow(port):
    print("🔍 Verifying Airflow...")

    code, _, _ = run(f"ss -ltn | grep :{port}")

    if code == 0:
        print(f"✅ Running → http://localhost:{port}")
    else:
        print("❌ Airflow not running")

# =============== DELETE =================
def delete_airflow():
    print("🧹 Deleting everything...")

    clean_all()

    run(f"sudo -u postgres psql -c \"DROP DATABASE IF EXISTS {POSTGRES_DB};\"")
    run(f"sudo -u postgres psql -c \"DROP USER IF EXISTS {POSTGRES_USER};\"")

    print("✅ Fully deleted")

# =============== MENU =================
def main():

    print("=== AUTO AIRFLOW AGENT (NO WARNINGS FINAL) ===")

    port = input("Enter port: ")
    username = input("Enter username: ")
    password = input("Enter password: ")

    while True:

        print("\n=== MENU ===")
        print("1. Install Airflow")
        print("2. Verify Airflow")
        print("3. Delete Airflow")
        print("4. Exit")

        choice = input("Enter choice: ")

        if choice == "1":
            install_airflow(port, username, password)

        elif choice == "2":
            verify_airflow(port)

        elif choice == "3":
            delete_airflow()

        elif choice == "4":
            print("👋 Exit")
            break

        else:
            print("❌ Invalid choice")

# =============== ENTRY =================
if __name__ == "__main__":
    main()
