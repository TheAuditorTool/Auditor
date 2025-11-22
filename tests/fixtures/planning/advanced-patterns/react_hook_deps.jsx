/**
 * React hooks with multiple dependencies.
 * Tests: react_hooks JOIN react_hook_dependencies
 */

import React, { useState, useEffect, useCallback } from 'react';


function UserDashboard({ userId, sessionToken }) {
  const [userData, setUserData] = useState(null);
  const [orders, setOrders] = useState([]);

  /**
   * useEffect with 2 dependencies: userId, sessionToken
   * Should create 2 rows in react_hook_dependencies.
   * Taint risk: sessionToken is sensitive.
   */
  useEffect(() => {
    fetch(`/api/users/${userId}`, {
      headers: { 'Authorization': `Bearer ${sessionToken}` }
    })
      .then(res => res.json())
      .then(data => setUserData(data));
  }, [userId, sessionToken]);  // 2 dependencies

  /**
   * useEffect with 3 dependencies: userId, sessionToken, userData
   * Should create 3 rows in react_hook_dependencies.
   */
  useEffect(() => {
    if (userData) {
      fetch(`/api/orders?user=${userId}`, {
        headers: { 'Authorization': `Bearer ${sessionToken}` }
      })
        .then(res => res.json())
        .then(data => setOrders(data));
    }
  }, [userId, sessionToken, userData]);  // 3 dependencies

  return <div>{userData?.name}</div>;
}


function ProductList({ category, priceMin, priceMax, sortBy }) {
  const [products, setProducts] = useState([]);

  /**
   * useEffect with 4 dependencies: category, priceMin, priceMax, sortBy
   * Should create 4 rows in react_hook_dependencies.
   * Anti-pattern: Missing useCallback, re-fetches on every prop change.
   */
  useEffect(() => {
    fetch(`/api/products?category=${category}&min=${priceMin}&max=${priceMax}&sort=${sortBy}`)
      .then(res => res.json())
      .then(data => setProducts(data));
  }, [category, priceMin, priceMax, sortBy]);  // 4 dependencies

  return <div>{products.length} products</div>;
}


function PaymentForm({ amount, userId, cardToken }) {
  /**
   * useEffect with sensitive dependencies: amount, userId, cardToken
   * Should create 3 rows in react_hook_dependencies.
   * Security risk: cardToken in dependency array = re-executes on token change.
   */
  useEffect(() => {
    console.log(`Processing payment: ${amount} for user ${userId} with token ${cardToken}`);
    // BAD: Logging sensitive card token
  }, [amount, userId, cardToken]);  // 3 dependencies (1 is sensitive)

  return <form>Payment form</form>;
}


export { UserDashboard, ProductList, PaymentForm };
