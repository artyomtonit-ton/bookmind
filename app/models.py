from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    
    reviews = relationship("Review", back_populates="owner")
    comments = relationship("Comment", back_populates="user")
    likes = relationship("Like", back_populates="user", cascade="all, delete-orphan")

class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    book_title = Column(String, nullable=False)
    author = Column(String, nullable=False)
    rating = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    cover_url = Column(String)
    status = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="reviews")
    comments = relationship("Comment", back_populates="review", cascade="all, delete-orphan")
    likes = relationship("Like", back_populates="review", cascade="all, delete-orphan")

class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user_id = Column(Integer, ForeignKey("users.id"))
    review_id = Column(Integer, ForeignKey("reviews.id"))

    user = relationship("User", back_populates="comments")
    review = relationship("Review", back_populates="comments")

class Like(Base):
    __tablename__ = "likes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    review_id = Column(Integer, ForeignKey("reviews.id"))

    user = relationship("User", back_populates="likes")
    review = relationship("Review", back_populates="likes")