<template>
  <div class="product-list">
    <div class="filters">
      <input
        v-model="searchTerm"
        type="text"
        placeholder="Search products..."
        @input="debouncedSearch"
      />
      <select v-model="selectedCategory">
        <option value="">All Categories</option>
        <option value="electronics">Electronics</option>
        <option value="clothing">Clothing</option>
        <option value="books">Books</option>
      </select>
    </div>

    <div v-if="loading" class="loading">Loading...</div>

    <div v-else class="product-grid">
      <div
        v-for="product in filteredProducts"
        :key="product.id"
        class="product-card"
        @click="handleProductClick(product.id)"
      >
        <h3>{{ product.name }}</h3>
        <p class="description">{{ product.description }}</p>
        <p class="price">${{ formatPrice(product.price) }}</p>
        <p class="category">{{ product.category }}</p>
        <button @click.stop="addToCart(product.id)">Add to Cart</button>
      </div>
    </div>

    <p class="result-count">Showing {{ filteredProducts.length }} of {{ totalProducts }} products</p>
  </div>
</template>

<script>
/**
 * ProductList component with Vue 3 Composition API
 *
 * Tests:
 * - v-model two-way binding with tainted data
 * - computed properties with filter logic
 * - watch with debounce pattern
 * - Event handlers with tainted parameters
 * - Taint flows: user input -> ref -> computed -> axios API calls
 */

import { ref, computed, watch, onMounted } from 'vue';
import axios from 'axios';

export default {
  name: 'ProductList',

  props: {
    category: {
      type: String,
      default: ''
      // TAINT SOURCE: category from parent component (potentially from URL)
    }
  },

  setup(props) {
    // Reactive refs
    const products = ref([]);
    const loading = ref(false);
    const searchTerm = ref('');  // TAINT SOURCE: User input via v-model
    const selectedCategory = ref(props.category);  // TAINT SOURCE: Prop

    let debounceTimer = null;

    /**
     * Computed: filteredProducts
     * Tests: Computed property with filter logic on tainted data
     */
    const filteredProducts = computed(() => {
      let filtered = products.value;

      // TAINT FLOW: searchTerm (user input) -> filter logic
      if (searchTerm.value) {
        const term = searchTerm.value.toLowerCase();
        filtered = filtered.filter(p =>
          p.name.toLowerCase().includes(term) ||
          p.description.toLowerCase().includes(term)
        );
      }

      // TAINT FLOW: selectedCategory (user input) -> filter logic
      if (selectedCategory.value) {
        filtered = filtered.filter(p => p.category === selectedCategory.value);
      }

      return filtered;
    });

    /**
     * Computed: totalProducts
     * Tests: Simple computed property
     */
    const totalProducts = computed(() => products.value.length);

    /**
     * Fetch products from API
     * Tests: Async function with tainted query parameters
     */
    async function fetchProducts() {
      loading.value = true;

      try {
        const params = new URLSearchParams();

        // MULTI-SOURCE TAINT: searchTerm + selectedCategory -> API call
        if (searchTerm.value) {
          params.append('search', searchTerm.value);
        }

        if (selectedCategory.value) {
          params.append('category', selectedCategory.value);
        }

        // TAINT FLOW: tainted params -> axios API call
        const response = await axios.get(`/api/products?${params.toString()}`);
        products.value = response.data;
      } catch (err) {
        console.error('Failed to fetch products:', err);
      } finally {
        loading.value = false;
      }
    }

    /**
     * Debounced search
     * Tests: Debounce pattern with tainted user input
     */
    function debouncedSearch() {
      clearTimeout(debounceTimer);

      debounceTimer = setTimeout(() => {
        // TAINT FLOW: searchTerm (user input) -> fetchProducts
        fetchProducts();
      }, 300);
    }

    /**
     * Format price
     * Tests: Pure function for computed values
     */
    function formatPrice(price) {
      return price.toFixed(2);
    }

    /**
     * Handle product click
     * Tests: Event handler with tainted product ID
     */
    function handleProductClick(productId) {
      // TAINT FLOW: productId (from user click) -> axios API call
      axios.get(`/api/products/${productId}`);
    }

    /**
     * Add to cart
     * Tests: Event handler with tainted product ID
     */
    async function addToCart(productId) {
      try {
        // TAINT FLOW: productId (from user click) -> axios POST
        await axios.post('/api/cart', { productId, quantity: 1 });
      } catch (err) {
        console.error('Failed to add to cart:', err);
      }
    }

    /**
     * Watch: selectedCategory
     * Tests: Watcher on tainted v-model ref
     */
    watch(selectedCategory, (newCategory) => {
      // TAINT FLOW: selectedCategory change -> fetchProducts
      fetchProducts();
    });

    /**
     * Watch: props.category
     * Tests: Watcher on tainted prop
     */
    watch(() => props.category, (newCategory) => {
      selectedCategory.value = newCategory;
      // This will trigger the selectedCategory watcher above
    });

    /**
     * Lifecycle: onMounted
     */
    onMounted(() => {
      fetchProducts();
    });

    // Expose to template
    return {
      products,
      loading,
      searchTerm,
      selectedCategory,
      filteredProducts,
      totalProducts,
      debouncedSearch,
      formatPrice,
      handleProductClick,
      addToCart
    };
  }
};
</script>

<style scoped>
.product-list {
  padding: 20px;
}

.filters {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.filters input,
.filters select {
  padding: 8px;
  border: 1px solid #ccc;
  border-radius: 4px;
  flex: 1;
}

.product-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 20px;
}

.product-card {
  padding: 15px;
  border: 1px solid #ddd;
  border-radius: 8px;
  cursor: pointer;
  transition: transform 0.2s;
}

.product-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 4px 8px rgba(0,0,0,0.1);
}

.result-count {
  margin-top: 20px;
  text-align: center;
  color: #666;
}
</style>
