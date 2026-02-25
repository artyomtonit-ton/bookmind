from fastapi import FastAPI, Request, Depends, Form, HTTPException, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy import func, desc
from sqlalchemy.orm import selectinload
from jose import JWTError, jwt
from starlette.middleware.sessions import SessionMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from .database import get_db, engine, Base
from .models import Review, User, Comment, Like
from .utils import fetch_book_info
from .auth_utils import hash_password, verify_password, create_access_token
from .secrets import JWT_SECRET, ALGORITHM
from pydantic import ValidationError
from .schemas import UserCreate, ReviewCreate

app = FastAPI(title="BookMind")
app.add_middleware(SessionMiddleware, secret_key=JWT_SECRET)
templates = Jinja2Templates(directory="app/templates")

@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return templates.TemplateResponse(
            "404.html", 
            {"request": request, "title": "Страница не найдена", "user": None}, 
            status_code=404
        )
    return HTMLResponse(content=f"<div style='background:black;color:white;padding:20px;font-family:sans-serif;'><h1>Ошибка {exc.status_code}</h1><p>{exc.detail}</p><a href='/' style='color:gray;'>На главную</a></div>", status_code=exc.status_code)

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
    query = select(Review).order_by(Review.created_at.desc()).options(
        selectinload(Review.owner),
        selectinload(Review.likes)
    )
    result = await db.execute(query)
    reviews = result.scalars().all()
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "title": "Лента", 
        "reviews": reviews,
        "user": user
    })
       
@app.get("/top", response_class=HTMLResponse)
async def read_top_books(
    request: Request, 
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    query = (
        select(
            Review.book_title,
            Review.author,
            Review.cover_url,
            func.count(Review.id).label("review_count")
        )
        .group_by(Review.book_title, Review.author, Review.cover_url)
        .order_by(desc("review_count"))
        .limit(20)
    )
    
    result = await db.execute(query)
    top_books = result.all() 
    
    return templates.TemplateResponse("top.html", {
        "request": request, 
        "title": "Топ книг", 
        "top_books": top_books,
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
    return templates.TemplateResponse("register.html", {"request": request, "title": "Регистрация", "user": user})

@app.post("/register")
async def register_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...)
):
    try:
        user_data = UserCreate(username=username, email=email, password=password)
    except ValidationError as e:
        error_msg = e.errors()[0]['msg']
        if "value is not a valid email" in str(e):
            error_msg = "Некорректный формат Email"
        elif "String should have at least 6 characters" in str(e):
            error_msg = "Пароль должен быть минимум 6 символов"
        elif "String should match pattern" in str(e):
            error_msg = "Никнейм должен содержать только англ. буквы и цифры"
        flash(request, f"ОШИБКА: {error_msg}", "error")
        return RedirectResponse(url="/register", status_code=303)

    hashed_pw = hash_password(user_data.password)
    new_user = User(username=user_data.username, email=user_data.email, hashed_password=hashed_pw)
    
    try:
        db.add(new_user)
        await db.commit()
    except Exception:
        await db.rollback()
        flash(request, "ОШИБКА: ИМЯ ИЛИ EMAIL УЖЕ ЗАНЯТЫ", "error")
        return RedirectResponse(url="/register", status_code=303)
        
    flash(request, "РЕГИСТРАЦИЯ УСПЕШНА. ВОЙДИТЕ В АККАУНТ.", "success")
    return RedirectResponse(url="/login", status_code=303)

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("login.html", {"request": request, "title": "Вход", "user": user})

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
        return RedirectResponse(url="/login", status_code=303)
    
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
    return templates.TemplateResponse("add_review.html", {"request": request, "title": "Новая мысль", "user": user})

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
        flash(request, "СНАЧАЛА ВОЙДИТЕ В АККАУНТ", "error")
        return RedirectResponse(url="/login", status_code=303)
        
    if not cover_url:
        cover_url = "https://placehold.co/400x600/18181b/ffffff?text=NO+COVER"

    try:
        review_data = ReviewCreate(
            book_title=book_title,
            author=author,
            rating=rating,
            text=text,
            description=description,
            cover_url=cover_url,
            status=status
        )
    except ValidationError as e:
        error_msg = e.errors()[0]['msg']
        if "Input should be greater than or equal to 1" in str(e) or "Input should be less than or equal to 10" in str(e):
             error_msg = "Оценка должна быть от 1 до 10"
        elif "String should have at least 10 characters" in str(e):
             error_msg = "Текст рецензии слишком короткий"
        flash(request, f"ОШИБКА: {error_msg}", "error")
        return RedirectResponse(url="/add", status_code=303)

    new_review = Review(
        book_title=review_data.book_title,
        author=review_data.author,
        rating=review_data.rating,
        text=review_data.text,
        description=review_data.description,
        cover_url=review_data.cover_url,
        status=review_data.status,
        user_id=user.id
    )
    db.add(new_review)
    await db.commit()
    flash(request, "НОВАЯ ЗАПИСЬ ОПУБЛИКОВАНА", "success")
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
        selectinload(Review.comments).selectinload(Comment.user),
        selectinload(Review.likes)
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

    try:
        review_data = ReviewCreate(
            book_title=book_title,
            author=author,
            rating=rating,
            text=text,
            description=description,
            cover_url=cover_url,
            status=status
        )
    except ValidationError as e:
        error_msg = e.errors()[0]['msg']
        if "Input should be greater than or equal to 1" in str(e) or "Input should be less than or equal to 10" in str(e):
             error_msg = "Оценка должна быть от 1 до 10"
        elif "String should have at least 10 characters" in str(e):
             error_msg = "Текст рецензии слишком короткий"
        flash(request, f"ОШИБКА: {error_msg}", "error")
        return RedirectResponse(url=f"/review/{review_id}/edit", status_code=303)

    review.book_title = review_data.book_title
    review.author = review_data.author
    review.rating = review_data.rating
    review.text = review_data.text
    review.description = review_data.description
    review.cover_url = review_data.cover_url
    review.status = review_data.status
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
    new_comment = Comment(text=text, user_id=user.id, review_id=review_id)
    db.add(new_comment)
    await db.commit()
    flash(request, "КОММЕНТАРИЙ ОПУБЛИКОВАН", "success")
    return RedirectResponse(url=f"/review/{review_id}", status_code=303)

@app.post("/review/{review_id}/like")
async def toggle_like(
    review_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if not user:
        flash(request, "ВОЙДИТЕ, ЧТОБЫ ОЦЕНИТЬ ЗАПИСЬ", "error")
        return RedirectResponse(url="/login", status_code=303)
    query_review = select(Review).where(Review.id == review_id)
    result_review = await db.execute(query_review)
    if not result_review.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Review not found")
    query_like = select(Like).where(Like.user_id == user.id, Like.review_id == review_id)
    result_like = await db.execute(query_like)
    existing_like = result_like.scalar_one_or_none()
    if existing_like:
        await db.delete(existing_like)
    else:
        new_like = Like(user_id=user.id, review_id=review_id)
        db.add(new_like)
    await db.commit()
    referer = request.headers.get("referer")
    redirect_url = referer if referer else f"/review/{review_id}"
    return RedirectResponse(url=redirect_url, status_code=303)

@app.get("/profile", response_class=HTMLResponse)
async def read_my_profile(
    request: Request, 
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    query = select(Review).where(Review.user_id == user.id).order_by(Review.created_at.desc()).options(
        selectinload(Review.owner),
        selectinload(Review.likes)
    )
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
    query = select(User).where(User.username == username).options(
        selectinload(User.reviews).selectinload(Review.likes),
        selectinload(User.reviews).selectinload(Review.owner)
    )
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