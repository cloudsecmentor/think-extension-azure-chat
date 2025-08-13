import os
import subprocess
import sys
from pathlib import Path


def start_web_docs(port: int) -> subprocess.Popen:
    env = os.environ.copy()
    env["PORT"] = str(port)
    web_docs_dir = Path(__file__).parent / "web_docs"
    # Run the script directly with cwd inside web_docs to avoid import-name collision with the pip 'mcp' package
    return subprocess.Popen([sys.executable, "main.py"], env=env, cwd=str(web_docs_dir))


def main() -> None:
    # Assign fixed ports per server; extend as you add more servers
    processes: list[subprocess.Popen] = []
    try:
        processes.append(start_web_docs(port=8801))

        # Wait indefinitely while children run; forward signals on Docker stop
        for proc in processes:
            proc.wait()
    except KeyboardInterrupt:
        pass
    finally:
        for proc in processes:
            try:
                proc.terminate()
            except Exception:
                pass


if __name__ == "__main__":
    main()


