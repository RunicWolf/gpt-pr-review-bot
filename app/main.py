from fastapi import FastAPI

app = FastAPI(title="GPT PR Review Bot", version="0.1.0")


@app.get("/healthz")
def healthz():
    return {"ok": True}

# BAD: just to trigger the review bot
import subprocess

def _demo_bad():
    return subprocess.run("echo hi", shell=True)  # shell=True on purpose

# demo change to trigger GPT review
def _bot_demo_warning():
    import subprocess
    return subprocess.run('echo hi', shell=True)  # shell=True on purpose
