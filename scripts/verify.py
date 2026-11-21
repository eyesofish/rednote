"""Run the public acceptance suite in its own Compose project from any checkout."""
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def main():
    frontend = ROOT / "frontend"
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if npm is None or not (frontend / "node_modules/@playwright/test/package.json").is_file():
        raise SystemExit("Install Node.js and run npm ci in frontend/ before starting acceptance.")

    env = os.environ.copy()
    web_port = env.get("TEST_WEB_PORT", "18085")
    mysql_port = env.get("TEST_MYSQL_PORT", "13316")
    base_url = f"http://127.0.0.1:{web_port}"
    env.update(
        COMPOSE_PROJECT_NAME="rednote-test",
        COMPOSE_FILE=os.pathsep.join(str(ROOT / file) for file in ("compose.yaml", "compose.test.yaml")),
        WEB_PORT=web_port,
        TEST_BASE_URL=base_url,
        E2E_BASE_URL=base_url,
        REDNOTE_LIVE="1",
        SQL_REQUEST_TRACE="1",
        TEST_DATABASE_URL=f"mysql+pymysql://rednote:rednote@127.0.0.1:{mysql_port}/rednote_test?charset=utf8mb4",
        PYTHONIOENCODING="utf-8",
    )

    def run(*args, cwd=ROOT):
        print(f"\n> {' '.join(args)}", flush=True)
        subprocess.run(args, cwd=cwd, env=env, check=True)

    run("docker", "compose", "up", "--build", "-d", "--wait", "--wait-timeout", "240")
    # Keep business tests and their independent Alembic run away from the demo tables.
    run("docker", "compose", "exec", "-T", "mysql", "mysql", "-uroot", "-plocal-root", "-e",
        "CREATE DATABASE IF NOT EXISTS rednote_test CHARACTER SET utf8mb4; "
        "GRANT ALL PRIVILEGES ON rednote_test.* TO 'rednote'@'%';")
    run(sys.executable, "-m", "pytest", "-q", "-s", "tests", cwd=ROOT / "backend")
    run(npm, "run", "build", cwd=frontend)
    run(npm, "run", "test:e2e", cwd=frontend)
    print(f"\nAcceptance passed. Test community: {base_url}", flush=True)


if __name__ == "__main__":
    main()
