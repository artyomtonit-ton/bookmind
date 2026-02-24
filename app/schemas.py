from pydantic import BaseModel, Field, EmailStr, field_validator

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=20, pattern=r"^[a-zA-Z0-9_]+$")
    email: EmailStr
    password: str = Field(..., min_length=6)

    @field_validator('username')
    @classmethod
    def check_admin(cls, v: str) -> str:
        if "admin" in v.lower() and v.lower() != "admin":
            raise ValueError("Нельзя притворяться админом")
        return v

class ReviewCreate(BaseModel):
    book_title: str = Field(..., min_length=1, max_length=200)
    author: str = Field(..., min_length=1, max_length=100)
    rating: int = Field(..., ge=1, le=10)
    text: str = Field(..., min_length=10)
    description: str | None = None
    cover_url: str | None = None
    status: str