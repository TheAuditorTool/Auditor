import React, { useState, useEffect, useCallback } from "react";

function UserDashboard({ userId, sessionToken }) {
  const [userData, setUserData] = useState(null);
  const [orders, setOrders] = useState([]);

  useEffect(() => {
    fetch(`/api/users/${userId}`, {
      headers: { Authorization: `Bearer ${sessionToken}` },
    })
      .then((res) => res.json())
      .then((data) => setUserData(data));
  }, [userId, sessionToken]);

  useEffect(() => {
    if (userData) {
      fetch(`/api/orders?user=${userId}`, {
        headers: { Authorization: `Bearer ${sessionToken}` },
      })
        .then((res) => res.json())
        .then((data) => setOrders(data));
    }
  }, [userId, sessionToken, userData]);

  return <div>{userData?.name}</div>;
}

function ProductList({ category, priceMin, priceMax, sortBy }) {
  const [products, setProducts] = useState([]);

  useEffect(() => {
    fetch(
      `/api/products?category=${category}&min=${priceMin}&max=${priceMax}&sort=${sortBy}`,
    )
      .then((res) => res.json())
      .then((data) => setProducts(data));
  }, [category, priceMin, priceMax, sortBy]);

  return <div>{products.length} products</div>;
}

function PaymentForm({ amount, userId, cardToken }) {
  useEffect(() => {
    console.log(
      `Processing payment: ${amount} for user ${userId} with token ${cardToken}`,
    );
  }, [amount, userId, cardToken]);

  return <form>Payment form</form>;
}

export { UserDashboard, ProductList, PaymentForm };
