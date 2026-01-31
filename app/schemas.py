from pydantic import BaseModel, Field
from typing import Optional

class ReviewCreate(BaseModel):
    book_title: str = Field(..., min_length=1, max_length=100)
    author: str = Field(..., min_length=1, max_length=100)
    reviewer: str = Field(..., min_length=1, max_length=50)
    rating: int = Field(..., ge=1, le=10)
    text: str = Field(..., min_length=10)
    description: Optional[str] = None
    cover_url: str
    status: str