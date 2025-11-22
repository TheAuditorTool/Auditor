/**
 * Next.js SSR page: Home page with product listing
 *
 * Tests:
 * - getServerSideProps data fetching
 * - SSR pattern extraction
 * - Taint flow from URL params -> SSR -> database
 * - Next.js page component extraction
 */

import { searchProducts } from '../lib/database';

/**
 * Home page component
 * Tests: Next.js page component extraction
 */
export default function HomePage({ products, filters, error }) {
  if (error) {
    return (
      <div className="error">
        <h1>Error</h1>
        <p>{error}</p>
      </div>
    );
  }

  return (
    <div className="home-page">
      <header>
        <h1>Product Catalog</h1>
        {filters.search && <p>Search results for: {filters.search}</p>}
        {filters.category && <p>Category: {filters.category}</p>}
      </header>

      <div className="filters">
        <form method="get">
          <input
            type="text"
            name="search"
            placeholder="Search products..."
            defaultValue={filters.search || ''}
          />
          <select name="category" defaultValue={filters.category || ''}>
            <option value="">All Categories</option>
            <option value="electronics">Electronics</option>
            <option value="clothing">Clothing</option>
            <option value="books">Books</option>
            <option value="home">Home & Garden</option>
          </select>
          <input
            type="number"
            name="minPrice"
            placeholder="Min price"
            defaultValue={filters.minPrice || ''}
          />
          <input
            type="number"
            name="maxPrice"
            placeholder="Max price"
            defaultValue={filters.maxPrice || ''}
          />
          <button type="submit">Search</button>
        </form>
      </div>

      <div className="product-grid">
        {products.length === 0 ? (
          <p>No products found.</p>
        ) : (
          products.map(product => (
            <div key={product.id} className="product-card">
              <h3>{product.name}</h3>
              <p className="description">{product.description}</p>
              <p className="price">${product.price.toFixed(2)}</p>
              <p className="category">{product.category_name}</p>
              <div className="rating">
                <span>{product.avg_rating ? product.avg_rating.toFixed(1) : 'N/A'}</span>
                <span>({product.review_count} reviews)</span>
              </div>
              <button>Add to Cart</button>
            </div>
          ))
        )}
      </div>

      <footer>
        <p>Showing {products.length} products</p>
      </footer>
    </div>
  );
}

/**
 * Server-side data fetching
 * Tests:
 * - getServerSideProps extraction
 * - Taint flow from URL query params -> database
 * - Multi-source taint (search, category, minPrice, maxPrice)
 */
export async function getServerSideProps(context) {
  const { query } = context;

  // TAINT SOURCES: URL query parameters
  const search = query.search || null;      // TAINT SOURCE 1
  const category = query.category || null;  // TAINT SOURCE 2
  const minPrice = query.minPrice ? parseFloat(query.minPrice) : null;  // TAINT SOURCE 3
  const maxPrice = query.maxPrice ? parseFloat(query.maxPrice) : null;  // TAINT SOURCE 4

  try {
    // MULTI-SOURCE TAINT: All query params -> searchProducts -> SQL query
    const products = await searchProducts(search, category, minPrice, maxPrice);

    return {
      props: {
        products,
        filters: {
          search,
          category,
          minPrice,
          maxPrice
        }
      }
    };
  } catch (err) {
    console.error('Error fetching products:', err);

    return {
      props: {
        products: [],
        filters: {},
        error: 'Failed to load products'
      }
    };
  }
}
