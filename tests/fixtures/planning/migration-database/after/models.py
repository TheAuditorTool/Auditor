"""
Database models AFTER migration (User → Account rename).

Tests ORM relationship extraction after rename:
- Account has one Profile (1-to-1)
- Account has many Posts (1-to-many with cascade delete)
- All FK references updated from User to Account
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Account(Base):
    """Account model (renamed from User)."""

    __tablename__ = 'accounts'

    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(200), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime)

    # Bidirectional relationships (updated to Account)
    profile = relationship('Profile', back_populates='account', uselist=False, cascade='all, delete-orphan')
    posts = relationship('Post', back_populates='author', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Account(username='{self.username}')>"


class Profile(Base):
    """Account profile (1-to-1 with Account)."""

    __tablename__ = 'profiles'

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey('accounts.id', ondelete='CASCADE'), unique=True, nullable=False)
    bio = Column(Text)
    avatar_url = Column(String(500))
    updated_at = Column(DateTime)

    # Bidirectional relationship (renamed to account)
    account = relationship('Account', back_populates='profile')

    def __repr__(self):
        return f"<Profile(account_id={self.account_id})>"


class Post(Base):
    """Account post (many-to-one with Account)."""

    __tablename__ = 'posts'

    id = Column(Integer, primary_key=True)
    author_id = Column(Integer, ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text)
    created_at = Column(DateTime)

    # Bidirectional relationship
    author = relationship('Account', back_populates='posts')

    def __repr__(self):
        return f"<Post(title='{self.title}')>"
