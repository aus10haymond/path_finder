import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
BACKEND = ROOT / "backend"
VENV_PYTHON = BACKEND / "venv" / "Scripts" / "python.exe"


def main():
    parser = argparse.ArgumentParser(description="Start the Path Finder server")
    parser.add_argument(
        "--test",
        action="store_true",
        help="Use test spreadsheet and send email to TEST_RECIPIENT_EMAIL instead of the real one",
    )
    parser.add_argument("--port", type=int, default=8080, help="Port (default: 8080)")
    parser.add_argument("--reload", action="store_true", help="Auto-reload on code changes")
    args = parser.parse_args()

    python = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable

    env = os.environ.copy()
    if args.test:
        env["TEST_MODE"] = "1"
        print("TEST MODE — using test spreadsheet and test recipient email")

    cmd = [python, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", str(args.port)]
    if args.reload:
        cmd.append("--reload")

    print(f"Server starting at http://localhost:{args.port} — http://127.0.0.1:{args.port}")
    subprocess.run(cmd, cwd=str(BACKEND), env=env)


if __name__ == "__main__":
    main()
