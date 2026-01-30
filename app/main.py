from fastapi import FastAPI

app = FastAPI(title="BookMind")

@app.get("/")
async def root():
    return {"message": "Система BookMind запущена и готова к работе!"}