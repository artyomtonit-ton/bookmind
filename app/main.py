from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

app = FastAPI(title="BookMind")

# Указываем FastAPI, где лежат наши шаблоны
templates = Jinja2Templates(directory="app/templates")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    # Теперь мы не просто возвращаем текст, а отрисовываем шаблон
    return templates.TemplateResponse(
        "index.html", 
        {"request": request, "title": "Главная страница"}
    )