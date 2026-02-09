from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .database import get_db, engine, Base
from .models import Review
from .utils import fetch_book_info

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
    return templates.TemplateResponse("index.html", {"request": request, "title": "Лента", "reviews": reviews})

@app.get("/search")
async def search_book(title: str):
    if not title:
        return {"error": "Введите название"}
    book_data = await fetch_book_info(title)
    return book_data if book_data else {"error": "Книга не найдена"}

@app.get("/review/{review_id}", response_class=HTMLResponse)
async def read_review(review_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    query = select(Review).where(Review.id == review_id)
    result = await db.execute(query)
    review = result.scalar_one_or_none()
    
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    
    return templates.TemplateResponse(
        "review_detail.html", 
        {"request": request, "review": review, "title": review.book_title}
    )

@app.post("/review/{review_id}/delete")
async def delete_review(review_id: int, db: AsyncSession = Depends(get_db)):
    query = select(Review).where(Review.id == review_id)
    result = await db.execute(query)
    review = result.scalar_one_or_none()
    
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    
    await db.delete(review)
    await db.commit()
    
    return RedirectResponse(url="/", status_code=303)

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
    description: str = Form(None),
    cover_url: str = Form(...),
    status: str = Form(...)
):
    new_review = Review(
        book_title=book_title,
        author=author,
        reviewer=reviewer,
        rating=rating,
        text=text,
        description=description,
        cover_url=cover_url,
        status=status
    )
    db.add(new_review)
    await db.commit()
    return RedirectResponse(url="/", status_code=303)