import subprocess


def greet(name):
    return f"Hello {name}"


# BAD: hardcoded secret (the bot should flag this)
API_KEY = "abc123"


# BAD: shell=True (the bot should flag this)
def run_cmd(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)
