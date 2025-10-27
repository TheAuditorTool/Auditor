"""Synthetic Python fixtures to exercise extraction parity features."""

from flask import Blueprint
from fastapi import APIRouter, Depends
from pydantic import BaseModel, validator, root_validator
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import declarative_base, relationship, backref


# SQLAlchemy setup
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, nullable=False)
    posts = relationship(
        "Post",
        back_populates="owner",
        cascade="all, delete-orphan",
    )
    profile = relationship(
        "Profile",
        back_populates="user",
        uselist=False,
    )


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="posts")
    comments = relationship(
        "Comment",
        backref=backref("post", cascade="all, delete"),
    )


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True)
    body = Column(String)
    post_id = Column(Integer, ForeignKey("posts.id"))


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    bio = Column(String)
    user = relationship("User", back_populates="profile", uselist=False)

# Pydantic validators
class Account(BaseModel):
    email: str
    password: str
    password_confirm: str

    @validator("email")
    def email_must_have_at(cls, value: str) -> str:
        if "@" not in value:
            raise ValueError("invalid email")
        return value

    @root_validator
    def passwords_match(cls, values):
        if values.get("password") != values.get("password_confirm"):
            raise ValueError("password mismatch")
        return values


# FastAPI router with dependencies
router = APIRouter()


def get_db():
    return object()


def get_current_user():
    return {"id": 1}


@router.get("/users/{user_id}")
def get_user(user_id: int, db=Depends(get_db), current_user=Depends(get_current_user)):
    return {"user_id": user_id, "current": current_user}


# Flask blueprint sample
api = Blueprint("sample_api", __name__, url_prefix="/sample")


@api.route("/ping")
def ping():
    return "pong"
