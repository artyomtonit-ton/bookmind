from fastapi import FastAPI, Request, Depends, Form, HTTPException, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from jose import JWTError, jwt

from starlette.middleware.sessions import SessionMiddleware

from .database import get_db, engine, Base
from .models import Review, User, Comment
from .utils import fetch_book_info
from .auth_utils import hash_password, verify_password, create_access_token
from .secrets import JWT_SECRET, ALGORITHM

app = FastAPI(title="BookMind")
app.add_middleware(SessionMiddleware, secret_key=JWT_SECRET)
templates = Jinja2Templates(directory="app/templates")


def flash(request: Request, message: str, category: str = "success"):
    if "flash_messages" not in request.session:
        request.session["flash_messages"] = []
    request.session["flash_messages"].append({"message": message, "category": category})

def get_flashed_messages(request: Request):
    return request.session.pop("flash_messages", [])

templates.env.globals.update(get_flashed_messages=get_flashed_messages)

async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
    except JWTError:
        return None
    
    result = await db.execute(select(User).where(User.id == int(user_id)))
    return result.scalar_one_or_none()

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.get("/", response_class=HTMLResponse)
async def read_root(
    request: Request, 
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    query = select(Review).order_by(Review.created_at.desc()).options(selectinload(Review.owner))
    result = await db.execute(query)
    reviews = result.scalars().all()
    
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "title": "Лента", 
        "reviews": reviews,
        "user": user
    })

@app.get("/search")
async def search_book(title: str):
    if not title:
        return {"error": "Введите название"}
    book_data = await fetch_book_info(title)
    return book_data if book_data else {"error": "Книга не найдена"}

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("register.html", {
        "request": request, 
        "title": "Регистрация",
        "user": user
    })

@app.post("/register")
async def register_user(
    db: AsyncSession = Depends(get_db),
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...)
):
    hashed_pw = hash_password(password)
    new_user = User(username=username, email=email, hashed_password=hashed_pw)
    try:
        db.add(new_user)
        await db.commit()
    except Exception:
        await db.rollback()
        return {"error": "Имя или email заняты"}
    return RedirectResponse(url="/login", status_code=303)

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("login.html", {
        "request": request, 
        "title": "Вход",
        "user": user
    })

@app.post("/login")
async def login(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    username: str = Form(...),
    password: str = Form(...)
):
    query = select(User).where(User.username == username)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(password, user.hashed_password):
        flash(request, "Неверный никнейм или пароль", "error")
        return {"error": "Неверные данные"}
    
    access_token = create_access_token(data={"sub": str(user.id)})
    resp = RedirectResponse(url="/", status_code=303)
    resp.set_cookie(key="access_token", value=access_token, httponly=True)
    
    flash(request, f"С возвращением, {user.username}!", "success")
    return resp

@app.get("/logout")
async def logout(request: Request):
    resp = RedirectResponse(url="/", status_code=303)
    resp.delete_cookie("access_token")
    flash(request, "Вы успешно вышли из системы", "success")
    return resp

@app.get("/add", response_class=HTMLResponse)
async def add_review_page(request: Request, user: User = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("add_review.html", {
        "request": request, 
        "title": "Новая мысль",
        "user": user
    })

@app.post("/add")
async def create_review(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    book_title: str = Form(...),
    author: str = Form(...),
    rating: int = Form(...),
    text: str = Form(...),
    description: str = Form(None),
    cover_url: str = Form(None), 
    status: str = Form(...)
):
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if not cover_url:
        cover_url = "https://placehold.co/400x600/18181b/ffffff?text=NO+COVER"
    new_review = Review(
        book_title=book_title,
        author=author,
        rating=rating,
        text=text,
        description=description,
        cover_url=cover_url,
        status=status,
        user_id=user.id
    )
    db.add(new_review)
    await db.commit()
    
    flash(request, "Новая запись успешно опубликована", "success")
    return RedirectResponse(url="/", status_code=303)

@app.get("/review/{review_id}", response_class=HTMLResponse)
async def read_review(
    review_id: int, 
    request: Request, 
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    query = select(Review).where(Review.id == review_id).options(
        selectinload(Review.owner),
        selectinload(Review.comments).selectinload(Comment.user)
    )
    result = await db.execute(query)
    review = result.scalar_one_or_none()
    
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
        
    return templates.TemplateResponse("review_detail.html", {
        "request": request, 
        "review": review, 
        "title": review.book_title,
        "user": user
    })

@app.post("/review/{review_id}/comment")
async def add_comment(
    review_id: int,
    request: Request,
    text: str = Form(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if not user:
        flash(request, "ВОЙДИТЕ, ЧТОБЫ ОСТАВИТЬ КОММЕНТАРИЙ", "error")
        return RedirectResponse(url="/login", status_code=303)

    query = select(Review).where(Review.id == review_id)
    result = await db.execute(query)
    review = result.scalar_one_or_none()
    
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    new_comment = Comment(
        text=text,
        user_id=user.id,
        review_id=review_id
    )
    
    db.add(new_comment)
    await db.commit()
    
    flash(request, "КОММЕНТАРИЙ ОПУБЛИКОВАН", "success")
    return RedirectResponse(url=f"/review/{review_id}", status_code=303)

@app.get("/review/{review_id}/edit", response_class=HTMLResponse)
async def edit_review_page(
    review_id: int, 
    request: Request, 
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/login")
    query = select(Review).where(Review.id == review_id)
    result = await db.execute(query)
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    if review.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your review")
    return templates.TemplateResponse("edit_review.html", {
        "request": request, 
        "review": review, 
        "title": "Редактирование", 
        "user": user
    })

@app.post("/review/{review_id}/edit")
async def update_review(
    review_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    book_title: str = Form(...),
    author: str = Form(...),
    rating: int = Form(...),
    text: str = Form(...),
    description: str = Form(None),
    cover_url: str = Form(None),
    status: str = Form(...)
):
    if not user:
        raise HTTPException(status_code=401)
    query = select(Review).where(Review.id == review_id)
    result = await db.execute(query)
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    if review.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your review")
    if not cover_url:
        cover_url = "https://placehold.co/400x600/18181b/ffffff?text=NO+COVER"
    review.book_title = book_title
    review.author = author
    review.rating = rating
    review.text = text
    review.description = description
    review.cover_url = cover_url
    review.status = status
    await db.commit()
    return RedirectResponse(url=f"/review/{review_id}", status_code=303)

@app.post("/review/{review_id}/delete")
async def delete_review(
    review_id: int,
    request: Request, 
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if not user:
        raise HTTPException(status_code=401, detail="Log in first")
    query = select(Review).where(Review.id == review_id)
    result = await db.execute(query)
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    if review.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your review")
    await db.delete(review)
    await db.commit()
    
    flash(request, "Запись удалена навсегда", "success")
    return RedirectResponse(url="/", status_code=303)

@app.get("/profile", response_class=HTMLResponse)
async def read_my_profile(
    request: Request, 
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    query = select(Review).where(Review.user_id == user.id).order_by(Review.created_at.desc())
    result = await db.execute(query)
    my_reviews = result.scalars().all()
    return templates.TemplateResponse("profile.html", {
        "request": request, 
        "user": user, 
        "profile_user": user,
        "reviews": my_reviews,
        "title": "Мой профиль",
        "is_own_profile": True
    })

@app.get("/user/{username}", response_class=HTMLResponse)
async def read_public_profile(
    username: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = select(User).where(User.username == username).options(selectinload(User.reviews))
    result = await db.execute(query)
    profile_user = result.scalar_one_or_none()
    if not profile_user:
        raise HTTPException(status_code=404, detail="User not found")
    reviews = sorted(profile_user.reviews, key=lambda r: r.created_at, reverse=True)
    return templates.TemplateResponse("profile.html", {
        "request": request,
        "user": current_user,
        "profile_user": profile_user,
        "reviews": reviews,
        "title": f"Профиль {profile_user.username}",
        "is_own_profile": (current_user and current_user.id == profile_user.id)
    })