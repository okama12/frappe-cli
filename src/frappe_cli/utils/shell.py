import subprocess
from typing import List, Optional

def run(cmd: List[str], check: bool = True, capture_output: bool = True, text: bool = True, sudo: bool = False, **kwargs):
    if sudo and cmd[0] != "sudo":
        cmd = ["sudo"] + cmd
    try:
        result = subprocess.run(cmd, check=check, capture_output=capture_output, text=text, **kwargs)
        return result.stdout.strip() if capture_output else None
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{e.stderr}") 