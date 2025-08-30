from fastapi import FastAPI

app = FastAPI(title="GPT PR Review Bot", version="0.1.0")


@app.get("/healthz")
def healthz():
    return {"ok": True}
