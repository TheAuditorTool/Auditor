/**
 * Next.js API route: GET /api/products
 *
 * Tests:
 * - API route with query parameters
 * - Multi-source taint (multiple query params -> SQL)
 * - Dynamic query building
 * - sql_query_tables with multiple JOINs
 */

import { searchProducts } from '../../lib/database';

/**
 * GET /api/products
 * Tests: Multi-source taint from query parameters
 *
 * Query params:
 * - search: Search term (TAINT SOURCE)
 * - category: Category filter (TAINT SOURCE)
 * - minPrice: Minimum price (TAINT SOURCE)
 * - maxPrice: Maximum price (TAINT SOURCE)
 * - sort: Sort order
 * - limit: Result limit
 */
export default async function handler(req, res) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const {
    search,      // TAINT SOURCE 1
    category,    // TAINT SOURCE 2
    minPrice,    // TAINT SOURCE 3
    maxPrice,    // TAINT SOURCE 4
    sort = 'name',
    limit = 50
  } = req.query;

  try {
    // MULTI-SOURCE TAINT: All query params -> searchProducts -> SQL query
    const products = await searchProducts(
      search,
      category,
      minPrice ? parseFloat(minPrice) : null,
      maxPrice ? parseFloat(maxPrice) : null
    );

    // Apply sorting
    const sortedProducts = applySorting(products, sort);

    // Apply limit
    const limitedProducts = sortedProducts.slice(0, parseInt(limit));

    return res.status(200).json({
      products: limitedProducts,
      total: products.length,
      filters: {
        search: search || null,
        category: category || null,
        minPrice: minPrice || null,
        maxPrice: maxPrice || null
      }
    });
  } catch (err) {
    console.error('Error searching products:', err);
    return res.status(500).json({ error: 'Internal server error' });
  }
}

/**
 * Apply sorting to products
 * Tests: Computed values from tainted data
 */
function applySorting(products, sortField) {
  const sortMap = {
    'name': (a, b) => a.name.localeCompare(b.name),
    'price-asc': (a, b) => a.price - b.price,
    'price-desc': (a, b) => b.price - a.price,
    'rating': (a, b) => (b.avg_rating || 0) - (a.avg_rating || 0),
    'reviews': (a, b) => (b.review_count || 0) - (a.review_count || 0)
  };

  const sortFn = sortMap[sortField] || sortMap['name'];
  return [...products].sort(sortFn);
}
