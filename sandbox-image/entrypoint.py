import os
import subprocess
import sys
import time
from pathlib import Path

ready = Path("/work/.sovereign-ready")
deadline = time.monotonic() + 30
while not ready.is_file() and time.monotonic() < deadline:
    time.sleep(0.05)
if not ready.is_file():
    print("SANDBOX_INPUT_TIMEOUT", file=sys.stderr)
    raise SystemExit(124)
working_directory = os.environ.get("SANDBOX_CWD", "/work")
if working_directory not in {"/work", "/tmp"}:
    print("SANDBOX_CWD_DENIED", file=sys.stderr)
    raise SystemExit(125)
completed = subprocess.run(sys.argv[1:], cwd=working_directory, check=False)
raise SystemExit(completed.returncode)
