/**
 * ProductList component (ANTI-PATTERN)
 *
 * Tests:
 * - React hook anti-pattern detection
 * - Missing useCallback causing unnecessary re-renders
 * - useState + useEffect without memoization
 */

import { useState, useEffect } from 'react';
import axios from 'axios';

/**
 * ProductList component with ANTI-PATTERN
 *
 * ISSUE: Uses useState + useEffect but MISSING useCallback
 * This causes fetchProducts to be recreated on every render,
 * potentially triggering infinite loops or unnecessary API calls.
 *
 * Tests:
 * - react_component_hooks detection (should find useState, useEffect)
 * - Anti-pattern query: "Find components with useState + useEffect but NOT useCallback"
 *
 * @param {Object} props
 * @param {string} props.category - Product category (TAINT SOURCE)
 * @param {string} props.searchTerm - Search term (TAINT SOURCE)
 */
function ProductList({ category, searchTerm }) {
  // STATE HOOKS
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // ANTI-PATTERN: Missing useCallback for fetchProducts
  // This function is recreated on every render
  const fetchProducts = async () => {
    setLoading(true);
    setError(null);

    try {
      // TAINT SINK: API call with tainted category and searchTerm
      const params = new URLSearchParams();
      if (category) params.append('category', category);
      if (searchTerm) params.append('search', searchTerm);

      const response = await axios.get(`/api/products?${params.toString()}`);
      setProducts(response.data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  /**
   * TAINTED DEPENDENCIES: category and searchTerm from props
   *
   * ANTI-PATTERN: fetchProducts is recreated every render,
   * so this useEffect potentially runs more than necessary.
   *
   * CORRECT would be:
   *   const fetchProducts = useCallback(async () => { ... }, [category, searchTerm]);
   */
  useEffect(() => {
    fetchProducts();
  }, [category, searchTerm]); // ← fetchProducts should be in deps but would cause issues

  if (loading) {
    return <div>Loading products...</div>;
  }

  if (error) {
    return <div>Error: {error}</div>;
  }

  return (
    <div className="product-list">
      <h2>Products {category && `in ${category}`}</h2>
      <div className="products">
        {products.map(product => (
          <div key={product.id} className="product-card">
            <h3>{product.name}</h3>
            <p>{product.description}</p>
            <p className="price">${product.price}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

export default ProductList;
