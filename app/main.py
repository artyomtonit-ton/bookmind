from fastapi import FastAPI, Request, Depends, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from .database import get_db, engine, Base
from .models import Review
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

app = FastAPI(title="BookMind")

templates = Jinja2Templates(directory="app/templates")

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Review).order_by(Review.created_at.desc()))
    reviews = result.scalars().all()
    
    return templates.TemplateResponse(
        "index.html", 
        {"request": request, "title": "Лента", "reviews": reviews}
    )

@app.get("/add", response_class=HTMLResponse)
async def add_review_page(request: Request):
    return templates.TemplateResponse("add_review.html", {"request": request, "title": "Новая мысль"})

@app.post("/add")
async def create_review(
    db: AsyncSession = Depends(get_db),
    book_title: str = Form(...),
    author: str = Form(...),
    reviewer: str = Form(...),
    rating: int = Form(...),
    text: str = Form(...),
    cover_url: str = Form(...),
    status: str = Form(...)
):
    new_review = Review(
        book_title=book_title,
        author=author,
        reviewer=reviewer,
        rating=rating,
        text=text,
        cover_url=cover_url,
        status=status
    )
    
    db.add(new_review)
    await db.commit()
    return RedirectResponse(url="/", status_code=303)