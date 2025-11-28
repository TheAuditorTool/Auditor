import { searchProducts } from "../../lib/database";

export default async function handler(req, res) {
  if (req.method !== "GET") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const {
    search,
    category,
    minPrice,
    maxPrice,
    sort = "name",
    limit = 50,
  } = req.query;

  try {
    const products = await searchProducts(
      search,
      category,
      minPrice ? parseFloat(minPrice) : null,
      maxPrice ? parseFloat(maxPrice) : null,
    );

    const sortedProducts = applySorting(products, sort);

    const limitedProducts = sortedProducts.slice(0, parseInt(limit));

    return res.status(200).json({
      products: limitedProducts,
      total: products.length,
      filters: {
        search: search || null,
        category: category || null,
        minPrice: minPrice || null,
        maxPrice: maxPrice || null,
      },
    });
  } catch (err) {
    console.error("Error searching products:", err);
    return res.status(500).json({ error: "Internal server error" });
  }
}

function applySorting(products, sortField) {
  const sortMap = {
    name: (a, b) => a.name.localeCompare(b.name),
    "price-asc": (a, b) => a.price - b.price,
    "price-desc": (a, b) => b.price - a.price,
    rating: (a, b) => (b.avg_rating || 0) - (a.avg_rating || 0),
    reviews: (a, b) => (b.review_count || 0) - (a.review_count || 0),
  };

  const sortFn = sortMap[sortField] || sortMap["name"];
  return [...products].sort(sortFn);
}
