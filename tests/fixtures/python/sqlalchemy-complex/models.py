"""Complex SQLAlchemy models with advanced patterns."""

import hashlib
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    and_,
    event,
    func,
    or_,
    select,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.ext.hybrid import hybrid_method, hybrid_property
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.ext.orderinglist import ordering_list
from sqlalchemy.orm import (
    Query,
    backref,
    column_property,
    joinedload,
    object_session,
    relationship,
    validates,
)
from sqlalchemy.orm.collections import attribute_mapped_collection
from sqlalchemy.sql import case

Base = declarative_base()


class TimestampMixin:
    """Mixin for automatic timestamp management."""

    @declared_attr
    def created_at(self):
        return Column(DateTime, default=func.now(), nullable=False)

    @declared_attr
    def updated_at(self):
        return Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


class SoftDeleteMixin:
    """Mixin for soft delete functionality."""

    @declared_attr
    def deleted_at(self):
        return Column(DateTime, nullable=True)

    @declared_attr
    def is_deleted(self):
        return column_property(self.deleted_at != None)  # noqa: E711 - SQLAlchemy IS NOT NULL

    def soft_delete(self):
        self.deleted_at = datetime.utcnow()

    def restore(self):
        self.deleted_at = None


user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True),
    Column("role_id", UUID(as_uuid=True), ForeignKey("roles.id"), primary_key=True),
    Column("assigned_at", DateTime, default=func.now()),
    Column("assigned_by", UUID(as_uuid=True), ForeignKey("users.id")),
    Column("expires_at", DateTime),
    UniqueConstraint("user_id", "role_id", name="uq_user_role"),
)


class ProductWarehouse(Base):
    __tablename__ = "product_warehouses"

    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), primary_key=True)
    warehouse_id = Column(UUID(as_uuid=True), ForeignKey("warehouses.id"), primary_key=True)
    quantity = Column(Integer, default=0, nullable=False)
    location = Column(String(50))
    last_restocked = Column(DateTime)
    min_stock_level = Column(Integer, default=10)
    max_stock_level = Column(Integer, default=1000)

    product = relationship("Product", back_populates="warehouse_associations")
    warehouse = relationship("Warehouse", back_populates="product_associations")

    restock_orders = relationship("RestockOrder", back_populates="product_warehouse")

    __table_args__ = (
        CheckConstraint("quantity >= 0", name="check_positive_quantity"),
        CheckConstraint("min_stock_level < max_stock_level", name="check_stock_levels"),
        Index("idx_low_stock", "product_id", "warehouse_id", "quantity"),
    )


class User(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(80), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=False, index=True)
    _password_hash = Column("password_hash", String(255), nullable=False)
    first_name = Column(String(50))
    last_name = Column(String(50))
    is_active = Column(Boolean, default=True, nullable=False)
    email_verified = Column(Boolean, default=False, nullable=False)
    profile_data = Column(MutableDict.as_mutable(JSONB), default={})
    search_vector = Column(TSVECTOR)

    roles = relationship("Role", secondary=user_roles, back_populates="users", lazy="selectin")

    orders = relationship(
        "Order",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="desc(Order.created_at)",
    )

    addresses = relationship(
        "Address",
        back_populates="user",
        cascade="all, delete-orphan",
        collection_class=attribute_mapped_collection("type"),
    )

    manager_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    subordinates = relationship(
        "User", backref=backref("manager", remote_side=[id]), cascade="all, delete-orphan"
    )

    role_names = association_proxy("roles", "name")

    notifications = relationship(
        "Notification",
        back_populates="user",
        foreign_keys="Notification.user_id",
        order_by="desc(Notification.created_at)",
    )

    @hybrid_property
    def password(self):
        return self._password_hash

    @password.setter
    def password(self, password):
        self._password_hash = hashlib.sha256(password.encode()).hexdigest()

    @hybrid_property
    def full_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username

    @full_name.expression
    def full_name(self):
        return case(
            [
                (
                    and_(self.first_name != None, self.last_name != None),  # noqa: E711 - SQLAlchemy IS NOT NULL
                    func.concat(self.first_name, " ", self.last_name),
                )
            ],
            else_=self.username,
        )

    @hybrid_method
    def has_role(self, role_name):
        return any(role.name == role_name for role in self.roles)

    @has_role.expression
    def has_role(self, role_name):
        return self.roles.any(Role.name == role_name)

    @validates("email")
    def validate_email(self, key, email):
        if "@" not in email:
            raise ValueError("Invalid email address")
        return email.lower()

    @validates("username")
    def validate_username(self, key, username):
        if len(username) < 3:
            raise ValueError("Username must be at least 3 characters")
        if not username.replace("_", "").isalnum():
            raise ValueError("Username must be alphanumeric")
        return username.lower()

    @classmethod
    def find_by_email_or_username(cls, identifier):
        return (
            object_session(cls)
            .query(cls)
            .filter(or_(cls.email == identifier.lower(), cls.username == identifier.lower()))
            .first()
        )

    def get_active_orders(self, limit=10):
        """Get recent active orders with eager loading."""
        return (
            object_session(self)
            .query(Order)
            .filter(Order.user_id == self.id)
            .filter(Order.status != "cancelled")
            .options(joinedload(Order.order_items).joinedload(OrderItem.product))
            .order_by(Order.created_at.desc())
            .limit(limit)
            .all()
        )

    __table_args__ = (
        Index("idx_user_search", "username", "email", "first_name", "last_name"),
        Index("idx_user_active_email", "is_active", "email_verified"),
        UniqueConstraint("email", "deleted_at", name="uq_email_active"),
    )


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sku = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    price = Column(Float, nullable=False)
    cost = Column(Float, nullable=False)
    weight = Column(Float)
    dimensions = Column(JSON)
    metadata = Column(MutableDict.as_mutable(JSONB), default={})
    tags = Column(ARRAY(String), default=[])
    status = Column(String(20), default="active")

    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"))
    brand_id = Column(UUID(as_uuid=True), ForeignKey("brands.id"))

    category = relationship("Category", back_populates="products")
    brand = relationship("Brand", back_populates="products")

    warehouse_associations = relationship(
        "ProductWarehouse", back_populates="product", cascade="all, delete-orphan"
    )

    warehouses = association_proxy("warehouse_associations", "warehouse")

    reviews = relationship(
        "Review",
        primaryjoin="and_(Product.id==Review.reviewable_id, Review.reviewable_type=='Product')",
        foreign_keys="Review.reviewable_id",
        cascade="all, delete-orphan",
    )

    related_products = relationship(
        "Product",
        secondary="related_products",
        primaryjoin="Product.id==related_products.c.product_id",
        secondaryjoin="Product.id==related_products.c.related_id",
        backref="related_to",
    )

    @hybrid_property
    def profit_margin(self):
        if self.cost and self.price:
            return ((self.price - self.cost) / self.price) * 100
        return 0

    @profit_margin.expression
    def profit_margin(self):
        return case(
            [
                (
                    and_(self.cost != None, self.price != None, self.price > 0),  # noqa: E711 - SQLAlchemy IS NOT NULL
                    ((self.price - self.cost) / self.price) * 100,
                )
            ],
            else_=0,
        )

    @hybrid_property
    def total_stock(self):
        return sum(wa.quantity for wa in self.warehouse_associations)

    @total_stock.expression
    def total_stock(self):
        return (
            select([func.sum(ProductWarehouse.quantity)])
            .where(ProductWarehouse.product_id == self.id)
            .label("total_stock")
        )

    @hybrid_property
    def average_rating(self):
        if self.reviews:
            return sum(r.rating for r in self.reviews) / len(self.reviews)
        return None

    @average_rating.expression
    def average_rating(self):
        return (
            select([func.avg(Review.rating)])
            .where(and_(Review.reviewable_id == self.id, Review.reviewable_type == "Product"))
            .label("average_rating")
        )

    @validates("price", "cost")
    def validate_pricing(self, key, value):
        if value < 0:
            raise ValueError(f"{key} cannot be negative")

        if key == "price" and self.cost:
            if value < self.cost * 1.1:
                raise ValueError("Price must be at least 10% above cost")
        elif key == "cost" and self.price and self.price < value * 1.1:
            raise ValueError("Cost would result in less than 10% markup")

        return value

    @validates("sku")
    def validate_sku(self, key, sku):
        import re

        if not re.match(r"^[A-Z]{3}-[A-Z]{3,5}-\d{5}$", sku):
            raise ValueError("SKU must match format: XXX-XXX-00000")
        return sku

    def check_stock_levels(self):
        """Check if any warehouse has low stock."""
        low_stock = []
        for wa in self.warehouse_associations:
            if wa.quantity < wa.min_stock_level:
                low_stock.append(
                    {
                        "warehouse": wa.warehouse.name,
                        "current": wa.quantity,
                        "minimum": wa.min_stock_level,
                    }
                )
        return low_stock

    __table_args__ = (
        CheckConstraint("price > cost", name="check_positive_margin"),
        CheckConstraint(
            "status IN ('active', 'discontinued', 'out_of_stock')", name="check_valid_status"
        ),
        Index("idx_product_category_status", "category_id", "status"),
        Index("idx_product_search", "name", "description", postgresql_using="gin"),
    )


class Notification(Base, TimestampMixin):
    """Base class for polymorphic notifications."""

    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type = Column(String(50), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title = Column(String(200), nullable=False)
    message = Column(Text)
    read_at = Column(DateTime)
    data = Column(JSONB, default={})

    user = relationship("User", back_populates="notifications")

    __mapper_args__ = {"polymorphic_on": type, "polymorphic_identity": "notification"}

    @property
    def is_read(self):
        return self.read_at is not None

    def mark_as_read(self):
        self.read_at = datetime.utcnow()


class OrderNotification(Notification):
    """Order-specific notification."""

    __tablename__ = "order_notifications"

    id = Column(UUID(as_uuid=True), ForeignKey("notifications.id"), primary_key=True)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"))
    order = relationship("Order")

    __mapper_args__ = {"polymorphic_identity": "order"}


class SystemNotification(Notification):
    """System-wide notification."""

    __tablename__ = "system_notifications"

    id = Column(UUID(as_uuid=True), ForeignKey("notifications.id"), primary_key=True)
    priority = Column(String(20), default="normal")
    expires_at = Column(DateTime)

    __mapper_args__ = {"polymorphic_identity": "system"}

    @validates("priority")
    def validate_priority(self, key, priority):
        valid_priorities = ["low", "normal", "high", "urgent"]
        if priority not in valid_priorities:
            raise ValueError(f"Priority must be one of {valid_priorities}")
        return priority


@event.listens_for(User, "before_insert")
def receive_before_insert(mapper, connection, target):
    """Auto-generate search vector for new users."""
    target.search_vector = func.to_tsvector(
        "english", f"{target.username} {target.email} {target.first_name} {target.last_name}"
    )


@event.listens_for(Product.warehouse_associations, "append")
def receive_append(target, value, initiator):
    """Trigger restock if quantity below minimum."""
    if value.quantity < value.min_stock_level:
        print(f"Low stock alert: {target.name} in {value.warehouse.name}")


class ProductQuery(Query):
    def in_stock(self):
        return self.filter(Product.total_stock > 0)

    def by_category(self, category_name):
        return self.join(Category).filter(Category.name == category_name)

    def price_between(self, min_price, max_price):
        return self.filter(and_(Product.price >= min_price, Product.price <= max_price))


class Role(Base):
    __tablename__ = "roles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(50), unique=True, nullable=False)
    permissions = Column(ARRAY(String), default=[])

    users = relationship("User", secondary=user_roles, back_populates="roles")


class Category(Base):
    __tablename__ = "categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"))

    products = relationship("Product", back_populates="category")
    children = relationship("Category", backref=backref("parent", remote_side=[id]))


class Brand(Base):
    __tablename__ = "brands"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False)
    logo = Column(String(255))

    products = relationship("Product", back_populates="brand")


class Warehouse(Base):
    __tablename__ = "warehouses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False)
    location = Column(String(200))
    capacity = Column(Integer)

    product_associations = relationship("ProductWarehouse", back_populates="warehouse")


class Review(Base, TimestampMixin):
    __tablename__ = "reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reviewable_type = Column(String(50), nullable=False)
    reviewable_id = Column(UUID(as_uuid=True), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    rating = Column(Integer, nullable=False)
    comment = Column(Text)

    user = relationship("User")

    __table_args__ = (
        Index("idx_reviewable", "reviewable_type", "reviewable_id"),
        CheckConstraint("rating >= 1 AND rating <= 5", name="check_valid_rating"),
    )


class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status = Column(String(20), default="pending")
    total = Column(Float, default=0)

    user = relationship("User", back_populates="orders")
    order_items = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderItem.position",
        collection_class=ordering_list("position"),
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    position = Column(Integer)

    order = relationship("Order", back_populates="order_items")
    product = relationship("Product")


class Address(Base):
    __tablename__ = "addresses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    type = Column(String(20), nullable=False)
    street = Column(String(200))
    city = Column(String(100))
    state = Column(String(50))
    country = Column(String(50))
    postal_code = Column(String(20))

    user = relationship("User", back_populates="addresses")


class RestockOrder(Base, TimestampMixin):
    __tablename__ = "restock_orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), nullable=False)
    warehouse_id = Column(UUID(as_uuid=True), nullable=False)
    quantity = Column(Integer, nullable=False)
    status = Column(String(20), default="pending")

    __table_args__ = (
        ForeignKeyConstraint(
            ["product_id", "warehouse_id"],
            ["product_warehouses.product_id", "product_warehouses.warehouse_id"],
        ),
    )

    product_warehouse = relationship("ProductWarehouse", back_populates="restock_orders")


related_products = Table(
    "related_products",
    Base.metadata,
    Column("product_id", UUID(as_uuid=True), ForeignKey("products.id"), primary_key=True),
    Column("related_id", UUID(as_uuid=True), ForeignKey("products.id"), primary_key=True),
    Column("relation_type", String(50)),
    UniqueConstraint("product_id", "related_id", name="uq_related"),
)
