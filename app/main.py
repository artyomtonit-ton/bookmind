from fastapi import FastAPI, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from .database import get_db, engine, Base
from .models import Review
from fastapi.responses import HTMLResponse
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