from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from .database import Base

class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    book_title = Column(String, nullable=False)
    author = Column(String, nullable=False)
    reviewer = Column(String, nullable=False)
    rating = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    cover_url = Column(String)
    status = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())