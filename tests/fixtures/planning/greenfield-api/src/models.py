"""
Database models for greenfield API.

This fixture demonstrates:
- ORM models with bidirectional relationships
- Foreign key constraints with cascade behaviors
- Hybrid properties and computed fields
- Methods as potential taint sinks
"""


from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.ext.hybrid import hybrid_property

db = SQLAlchemy()


class Role(db.Model):
    """User role model for RBAC."""

    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)
    description = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=db.func.now())

    # Bidirectional relationship
    users = db.relationship('User', back_populates='role', lazy='dynamic')

    def to_dict(self):
        """Serialize to dict."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description
        }


class User(db.Model):
    """User model with full ORM features."""

    __tablename__ = 'users'

    # Standard fields
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False, index=True)
    email = db.Column(db.String(200), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, onupdate=db.func.now())
    last_login = db.Column(db.DateTime)

    # Foreign keys
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id', ondelete='SET NULL'), index=True)

    # Bidirectional relationships
    role = db.relationship('Role', back_populates='users')
    orders = db.relationship('Order', back_populates='user', cascade='all, delete-orphan', lazy='dynamic')

    # Hybrid property (computed field)
    @hybrid_property
    def is_admin(self):
        """Check if user has admin role."""
        return self.role and self.role.name == 'admin'

    def verify_password(self, password):
        """Verify password hash (potential taint sink)."""
        import bcrypt
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))

    def to_dict(self, include_email=False):
        """
        Serialize to dict (potential data leak sink).

        Args:
            include_email: Whether to include email (PII exposure risk)
        """
        data = {
            'id': self.id,
            'username': self.username,
            'role': self.role.name if self.role else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

        if include_email:
            # PII exposure risk
            data['email'] = self.email

        return data


class Product(db.Model):
    """Product model."""

    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, index=True)
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    stock = db.Column(db.Integer, default=0)
    category = db.Column(db.String(100), index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, onupdate=db.func.now())

    # Relationship to order items
    order_items = db.relationship('OrderItem', back_populates='product', lazy='dynamic')

    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'price': float(self.price),
            'stock': self.stock,
            'category': self.category,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Order(db.Model):
    """Order model with relationships."""

    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    status = db.Column(db.String(50), default='pending', index=True)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, onupdate=db.func.now())

    # Foreign key to user
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)

    # Bidirectional relationships
    user = db.relationship('User', back_populates='orders')
    items = db.relationship('OrderItem', back_populates='order', cascade='all, delete-orphan', lazy='dynamic')

    def calculate_total(self):
        """Calculate total from items (tests aggregate query)."""
        total = sum(item.quantity * item.price for item in self.items)
        return total

    def to_dict(self):
        """Serialize to dict."""
        return {
            'id': self.id,
            'order_number': self.order_number,
            'status': self.status,
            'total_amount': float(self.total_amount),
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'items_count': self.items.count()
        }


class OrderItem(db.Model):
    """Order item model (junction table with data)."""

    __tablename__ = 'order_items'

    id = db.Column(db.Integer, primary_key=True)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)

    # Foreign keys
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='RESTRICT'), nullable=False, index=True)

    # Bidirectional relationships
    order = db.relationship('Order', back_populates='items')
    product = db.relationship('Product', back_populates='order_items')

    def to_dict(self):
        """Serialize to dict."""
        return {
            'id': self.id,
            'order_id': self.order_id,
            'product_id': self.product_id,
            'product_name': self.product.name if self.product else None,
            'quantity': self.quantity,
            'price': float(self.price),
            'subtotal': float(self.quantity * self.price)
        }
