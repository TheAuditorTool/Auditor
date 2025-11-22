/**
 * Shopping Cart Store with Computed Values
 * Tests: Complex state updates, computed values, array manipulation
 */

import { create } from 'zustand';
import { devtools, subscribeWithSelector } from 'zustand/middleware';
import { persist } from 'zustand/middleware';

/**
 * Shopping Cart Store
 * Tests: Store with computed totals, item management
 */
const useCartStore = create(
  devtools(
    persist(
      subscribeWithSelector((set, get) => ({
        // State
        items: [],
        couponCode: null,
        couponDiscount: 0,
        shippingMethod: 'standard',
        shippingCost: 0,

        /**
         * Add item to cart
         * Tests: Array state update with duplicate check
         * TAINT FLOW: product (user input) -> cart items
         */
        addItem: (product, quantity = 1) => {
          set((state) => {
            const existingItem = state.items.find(
              (item) => item.id === product.id
            );

            if (existingItem) {
              // Update quantity if item exists
              return {
                items: state.items.map((item) =>
                  item.id === product.id
                    ? { ...item, quantity: item.quantity + quantity }
                    : item
                )
              };
            }

            // Add new item
            return {
              items: [
                ...state.items,
                {
                  id: product.id,
                  name: product.name,
                  price: product.price,
                  quantity,
                  imageUrl: product.imageUrl,
                  sku: product.sku
                }
              ]
            };
          });
        },

        /**
         * Remove item from cart
         * Tests: Array filtering
         */
        removeItem: (productId) => {
          set((state) => ({
            items: state.items.filter((item) => item.id !== productId)
          }));
        },

        /**
         * Update item quantity
         * Tests: Array item update
         */
        updateQuantity: (productId, quantity) => {
          if (quantity <= 0) {
            get().removeItem(productId);
            return;
          }

          set((state) => ({
            items: state.items.map((item) =>
              item.id === productId ? { ...item, quantity } : item
            )
          }));
        },

        /**
         * Clear entire cart
         * Tests: State reset
         */
        clearCart: () => {
          set({
            items: [],
            couponCode: null,
            couponDiscount: 0
          });
        },

        /**
         * Apply coupon code
         * Tests: Async validation, discount calculation
         * TAINT FLOW: code (user input) -> couponCode state
         */
        applyCoupon: async (code) => {
          try {
            // Validate coupon with API
            const response = await fetch(`/api/coupons/validate`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ code, cartTotal: get().getSubtotal() })
            });

            const data = await response.json();

            if (data.valid) {
              set({
                couponCode: code,
                couponDiscount: data.discountAmount
              });

              return { success: true, discount: data.discountAmount };
            }

            return { success: false, error: 'Invalid coupon' };
          } catch (error) {
            return { success: false, error: error.message };
          }
        },

        /**
         * Remove coupon
         * Tests: Coupon state reset
         */
        removeCoupon: () => {
          set({
            couponCode: null,
            couponDiscount: 0
          });
        },

        /**
         * Set shipping method
         * Tests: Shipping calculation
         */
        setShippingMethod: (method) => {
          const shippingCosts = {
            standard: 5.99,
            express: 14.99,
            overnight: 29.99,
            pickup: 0
          };

          set({
            shippingMethod: method,
            shippingCost: shippingCosts[method] || 0
          });
        },

        /**
         * Get subtotal (before discounts and shipping)
         * Tests: Computed value from array reduce
         */
        getSubtotal: () => {
          const { items } = get();

          return items.reduce((total, item) => {
            return total + item.price * item.quantity;
          }, 0);
        },

        /**
         * Get total items count
         * Tests: Computed count
         */
        getItemCount: () => {
          const { items } = get();

          return items.reduce((count, item) => count + item.quantity, 0);
        },

        /**
         * Get discount amount
         * Tests: Computed discount
         */
        getDiscountAmount: () => {
          const { couponDiscount } = get();
          return couponDiscount;
        },

        /**
         * Get tax amount (8% of subtotal after discount)
         * Tests: Tax calculation
         */
        getTaxAmount: () => {
          const subtotal = get().getSubtotal();
          const discount = get().getDiscountAmount();
          const taxableAmount = subtotal - discount;

          return taxableAmount * 0.08; // 8% tax
        },

        /**
         * Get grand total
         * Tests: Complex computed value
         */
        getTotal: () => {
          const subtotal = get().getSubtotal();
          const discount = get().getDiscountAmount();
          const tax = get().getTaxAmount();
          const { shippingCost } = get();

          return subtotal - discount + tax + shippingCost;
        },

        /**
         * Check if cart is empty
         * Tests: Boolean computed value
         */
        isEmpty: () => {
          const { items } = get();
          return items.length === 0;
        },

        /**
         * Get cart summary
         * Tests: Complex object return with all computed values
         */
        getCartSummary: () => {
          return {
            itemCount: get().getItemCount(),
            subtotal: get().getSubtotal(),
            discount: get().getDiscountAmount(),
            tax: get().getTaxAmount(),
            shipping: get().shippingCost,
            total: get().getTotal(),
            isEmpty: get().isEmpty(),
            couponApplied: !!get().couponCode
          };
        },

        /**
         * Validate cart before checkout
         * Tests: Validation logic
         */
        validateCart: async () => {
          const { items } = get();

          if (items.length === 0) {
            return { valid: false, error: 'Cart is empty' };
          }

          // Validate stock availability
          try {
            const response = await fetch('/api/cart/validate', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ items })
            });

            const data = await response.json();

            if (!data.valid) {
              return {
                valid: false,
                error: 'Some items are out of stock',
                outOfStockItems: data.outOfStockItems
              };
            }

            return { valid: true };
          } catch (error) {
            return { valid: false, error: error.message };
          }
        },

        /**
         * Sync cart with backend (for logged-in users)
         * Tests: Async sync operation
         */
        syncCart: async (userId) => {
          const { items, couponCode, shippingMethod } = get();

          try {
            await fetch(`/api/users/${userId}/cart`, {
              method: 'PUT',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ items, couponCode, shippingMethod })
            });

            return { success: true };
          } catch (error) {
            return { success: false, error: error.message };
          }
        }
      })),
      {
        name: 'cart-storage',
        partialize: (state) => ({
          items: state.items,
          couponCode: state.couponCode,
          couponDiscount: state.couponDiscount,
          shippingMethod: state.shippingMethod,
          shippingCost: state.shippingCost
        })
      }
    ),
    {
      name: 'CartStore',
      enabled: process.env.NODE_ENV === 'development'
    }
  )
);

/**
 * Selectors
 * Tests: Selector patterns for cart state
 */

export const selectItems = (state) => state.items;
export const selectItemCount = (state) => state.getItemCount();
export const selectSubtotal = (state) => state.getSubtotal();
export const selectTotal = (state) => state.getTotal();
export const selectCartSummary = (state) => state.getCartSummary();
export const selectIsEmpty = (state) => state.isEmpty();
export const selectCouponCode = (state) => state.couponCode;
export const selectShippingMethod = (state) => state.shippingMethod;

// Find specific item
export const selectItemById = (itemId) => (state) =>
  state.items.find((item) => item.id === itemId);

// Check if item exists in cart
export const selectHasItem = (itemId) => (state) =>
  state.items.some((item) => item.id === itemId);

export default useCartStore;
