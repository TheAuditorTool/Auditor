import { create } from "zustand";
import { devtools, subscribeWithSelector } from "zustand/middleware";
import { persist } from "zustand/middleware";

const useCartStore = create(
  devtools(
    persist(
      subscribeWithSelector((set, get) => ({
        items: [],
        couponCode: null,
        couponDiscount: 0,
        shippingMethod: "standard",
        shippingCost: 0,

        addItem: (product, quantity = 1) => {
          set((state) => {
            const existingItem = state.items.find(
              (item) => item.id === product.id,
            );

            if (existingItem) {
              return {
                items: state.items.map((item) =>
                  item.id === product.id
                    ? { ...item, quantity: item.quantity + quantity }
                    : item,
                ),
              };
            }

            return {
              items: [
                ...state.items,
                {
                  id: product.id,
                  name: product.name,
                  price: product.price,
                  quantity,
                  imageUrl: product.imageUrl,
                  sku: product.sku,
                },
              ],
            };
          });
        },

        removeItem: (productId) => {
          set((state) => ({
            items: state.items.filter((item) => item.id !== productId),
          }));
        },

        updateQuantity: (productId, quantity) => {
          if (quantity <= 0) {
            get().removeItem(productId);
            return;
          }

          set((state) => ({
            items: state.items.map((item) =>
              item.id === productId ? { ...item, quantity } : item,
            ),
          }));
        },

        clearCart: () => {
          set({
            items: [],
            couponCode: null,
            couponDiscount: 0,
          });
        },

        applyCoupon: async (code) => {
          try {
            const response = await fetch(`/api/coupons/validate`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ code, cartTotal: get().getSubtotal() }),
            });

            const data = await response.json();

            if (data.valid) {
              set({
                couponCode: code,
                couponDiscount: data.discountAmount,
              });

              return { success: true, discount: data.discountAmount };
            }

            return { success: false, error: "Invalid coupon" };
          } catch (error) {
            return { success: false, error: error.message };
          }
        },

        removeCoupon: () => {
          set({
            couponCode: null,
            couponDiscount: 0,
          });
        },

        setShippingMethod: (method) => {
          const shippingCosts = {
            standard: 5.99,
            express: 14.99,
            overnight: 29.99,
            pickup: 0,
          };

          set({
            shippingMethod: method,
            shippingCost: shippingCosts[method] || 0,
          });
        },

        getSubtotal: () => {
          const { items } = get();

          return items.reduce((total, item) => {
            return total + item.price * item.quantity;
          }, 0);
        },

        getItemCount: () => {
          const { items } = get();

          return items.reduce((count, item) => count + item.quantity, 0);
        },

        getDiscountAmount: () => {
          const { couponDiscount } = get();
          return couponDiscount;
        },

        getTaxAmount: () => {
          const subtotal = get().getSubtotal();
          const discount = get().getDiscountAmount();
          const taxableAmount = subtotal - discount;

          return taxableAmount * 0.08;
        },

        getTotal: () => {
          const subtotal = get().getSubtotal();
          const discount = get().getDiscountAmount();
          const tax = get().getTaxAmount();
          const { shippingCost } = get();

          return subtotal - discount + tax + shippingCost;
        },

        isEmpty: () => {
          const { items } = get();
          return items.length === 0;
        },

        getCartSummary: () => {
          return {
            itemCount: get().getItemCount(),
            subtotal: get().getSubtotal(),
            discount: get().getDiscountAmount(),
            tax: get().getTaxAmount(),
            shipping: get().shippingCost,
            total: get().getTotal(),
            isEmpty: get().isEmpty(),
            couponApplied: !!get().couponCode,
          };
        },

        validateCart: async () => {
          const { items } = get();

          if (items.length === 0) {
            return { valid: false, error: "Cart is empty" };
          }

          try {
            const response = await fetch("/api/cart/validate", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ items }),
            });

            const data = await response.json();

            if (!data.valid) {
              return {
                valid: false,
                error: "Some items are out of stock",
                outOfStockItems: data.outOfStockItems,
              };
            }

            return { valid: true };
          } catch (error) {
            return { valid: false, error: error.message };
          }
        },

        syncCart: async (userId) => {
          const { items, couponCode, shippingMethod } = get();

          try {
            await fetch(`/api/users/${userId}/cart`, {
              method: "PUT",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ items, couponCode, shippingMethod }),
            });

            return { success: true };
          } catch (error) {
            return { success: false, error: error.message };
          }
        },
      })),
      {
        name: "cart-storage",
        partialize: (state) => ({
          items: state.items,
          couponCode: state.couponCode,
          couponDiscount: state.couponDiscount,
          shippingMethod: state.shippingMethod,
          shippingCost: state.shippingCost,
        }),
      },
    ),
    {
      name: "CartStore",
      enabled: process.env.NODE_ENV === "development",
    },
  ),
);

export const selectItems = (state) => state.items;
export const selectItemCount = (state) => state.getItemCount();
export const selectSubtotal = (state) => state.getSubtotal();
export const selectTotal = (state) => state.getTotal();
export const selectCartSummary = (state) => state.getCartSummary();
export const selectIsEmpty = (state) => state.isEmpty();
export const selectCouponCode = (state) => state.couponCode;
export const selectShippingMethod = (state) => state.shippingMethod;

export const selectItemById = (itemId) => (state) =>
  state.items.find((item) => item.id === itemId);

export const selectHasItem = (itemId) => (state) =>
  state.items.some((item) => item.id === itemId);

export default useCartStore;
