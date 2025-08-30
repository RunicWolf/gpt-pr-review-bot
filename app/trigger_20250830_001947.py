# trigger for GPT review - 20250830_001947
import subprocess

API_KEY = "abc123"  # bad: hardcoded secret

def run_cmd(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)  # bad: shell=True
