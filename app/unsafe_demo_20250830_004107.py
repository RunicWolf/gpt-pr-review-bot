# file created 20250830_004107 to trigger GPT review
import subprocess

API_KEY = "abc123"  # hardcoded secret (bad)

def run_cmd(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)  # bad: shell=True
