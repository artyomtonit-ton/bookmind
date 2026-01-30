from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

app = FastAPI(title="BookMind")

templates = Jinja2Templates(directory="app/templates")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    fake_reviews = [
        {
            "id": 1,
            "book_title": "Меня не сломать",
            "author": "Дэвид Гоггинс",
            "reviewer": "Максим",
            "rating": 10,
            "text": "Книга по-настоящему цепляет сознание и переворачивает представление о боли. Читая первые главы, я буквально проживал его жизнь...",
            "cover_url": "https://m.media-amazon.com/images/I/61bFMJQvmrL._AC_UL480_FMwebp_QL65_.jpg",
            "status": "Прочитано"
        },
        {
            "id": 2,
            "book_title": "Атомные привычки",
            "author": "Джеймс Клир",
            "reviewer": "Алексей",
            "rating": 9,
            "text": "Отличное практическое руководство. Понял, почему мои старые привычки не работали. Система маленьких шагов реально меняет жизнь.",
            "cover_url": "https://m.media-amazon.com/images/I/817HaeblezL._AC_UL480_FMwebp_QL65_.jpg",
            "status": "Прочитано"
        },
        {
            "id": 3,
            "book_title": "Дюна",
            "author": "Фрэнк Герберт",
            "reviewer": "Елена",
            "rating": 8,
            "text": "Масштаб поражает. Это не просто фантастика, это целая философия и политика. Немного затянуто в начале, но финал того стоит.",
            "cover_url": "https://m.media-amazon.com/images/I/71oO1E-XPuL._AC_UL480_FMwebp_QL65_.jpg",
            "status": "Читаю сейчас"
        }
    ]
    return templates.TemplateResponse(
        "index.html", 
        {"request": request, "title": "Лента отзывов", "reviews": fake_reviews}
    )