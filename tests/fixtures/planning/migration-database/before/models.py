"""
Database models BEFORE migration (User → Account rename).

Tests ORM relationship extraction:
- User has one Profile (1-to-1)
- User has many Posts (1-to-many with cascade delete)
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class User(Base):
    """User model (to be renamed to Account)."""

    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(200), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime)

    # Bidirectional relationships
    profile = relationship('Profile', back_populates='user', uselist=False, cascade='all, delete-orphan')
    posts = relationship('Post', back_populates='author', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<User(username='{self.username}')>"


class Profile(Base):
    """User profile (1-to-1 with User)."""

    __tablename__ = 'profiles'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False)
    bio = Column(Text)
    avatar_url = Column(String(500))
    updated_at = Column(DateTime)

    # Bidirectional relationship
    user = relationship('User', back_populates='profile')

    def __repr__(self):
        return f"<Profile(user_id={self.user_id})>"


class Post(Base):
    """User post (many-to-one with User)."""

    __tablename__ = 'posts'

    id = Column(Integer, primary_key=True)
    author_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text)
    created_at = Column(DateTime)

    # Bidirectional relationship
    author = relationship('User', back_populates='posts')

    def __repr__(self):
        return f"<Post(title='{self.title}')>"
