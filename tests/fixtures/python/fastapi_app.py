"""FastAPI fixture covering route metadata and dependency injection."""

from typing import List, Optional, Dict

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/v1", tags=["users"])


def get_db():
    return object()


def get_current_user():
    return {"id": 1, "email": "current@example.com"}


class UserResponse(BaseModel):
    id: int
    email: str


class UserCreate(BaseModel):
    email: str
    password: str


@router.get("/users", response_model=list[UserResponse])
def list_users(db=Depends(get_db)):
    del db
    return []


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    del db, current_user
    return UserResponse(id=user_id, email="user@example.com")


@router.post("/users", response_model=UserResponse, status_code=201)
def create_user(payload: UserCreate, db=Depends(get_db)):
    del db
    return UserResponse(id=42, email=payload.email)


@router.patch("/users/{user_id}")
def patch_user(
    user_id: int,
    updates: dict[str, str] = Body(default_factory=dict),
    db=Depends(get_db),
):
    del db
    return {"id": user_id, "updates": updates}


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int, db=Depends(get_db)):
    del db
    return None
