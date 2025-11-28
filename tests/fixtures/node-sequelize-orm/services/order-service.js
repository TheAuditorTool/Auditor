const { Op } = require("sequelize");

class OrderService {
  constructor(sequelize) {
    this.sequelize = sequelize;
    this.Order = sequelize.models.Order;
    this.OrderProduct = sequelize.models.OrderProduct;
    this.Product = sequelize.models.Product;
    this.User = sequelize.models.User;
  }

  async createOrder(userId, orderData, lineItems) {
    const transaction = await this.sequelize.transaction();

    try {
      const user = await this.User.findByPk(userId, { transaction });
      if (!user) {
        throw new Error("User not found");
      }

      const productIds = lineItems.map((item) => item.productId);
      const products = await this.Product.findAll({
        where: {
          id: { [Op.in]: productIds },
        },
        transaction,
        lock: transaction.LOCK.UPDATE,
      });

      if (products.length !== productIds.length) {
        throw new Error("One or more products not found");
      }

      const productMap = {};
      products.forEach((p) => {
        productMap[p.id] = p;
      });

      let subtotal = 0;
      const validatedItems = [];

      for (const item of lineItems) {
        const product = productMap[item.productId];

        if (!product.isAvailable()) {
          throw new Error(`Product ${product.name} is not available`);
        }

        if (product.stockQuantity < item.quantity) {
          throw new Error(
            `Insufficient stock for ${product.name}. Available: ${product.stockQuantity}`,
          );
        }

        const lineTotal = parseFloat(product.price) * item.quantity;
        subtotal += lineTotal;

        validatedItems.push({
          productId: item.productId,
          product: product,
          quantity: item.quantity,
          price: product.price,
          discount: item.discount || 0,
        });
      }

      const tax = subtotal * 0.08;
      const shippingCost = orderData.shippingCost || 10.0;
      const discount = orderData.discount || 0;
      const total = subtotal + tax + shippingCost - discount;

      const order = await this.Order.create(
        {
          userId,
          orderNumber: orderData.orderNumber,
          status: "pending",
          subtotal,
          tax,
          shippingCost,
          discount,
          total,
          shippingAddress: orderData.shippingAddress,
          billingAddress: orderData.billingAddress || orderData.shippingAddress,
          notes: orderData.notes || null,
        },
        { transaction },
      );

      for (const item of validatedItems) {
        await this.OrderProduct.create(
          {
            orderId: order.id,
            productId: item.productId,
            quantity: item.quantity,
            price: item.price,
            discount: item.discount,
          },
          { transaction },
        );

        await item.product.updateStock(-item.quantity);
      }

      await transaction.commit();

      return await this.getOrderWithDetails(order.id);
    } catch (error) {
      await transaction.rollback();
      throw error;
    }
  }

  async cancelOrder(orderId, reason) {
    const transaction = await this.sequelize.transaction();

    try {
      const order = await this.Order.findByPk(orderId, { transaction });

      if (!order) {
        throw new Error("Order not found");
      }

      if (order.status === "delivered") {
        throw new Error("Cannot cancel delivered order");
      }

      if (order.status === "cancelled") {
        throw new Error("Order already cancelled");
      }

      const lineItems = await this.OrderProduct.findAll({
        where: { orderId },
        include: [
          {
            model: this.Product,
            as: "product",
          },
        ],
        transaction,
      });

      for (const item of lineItems) {
        await item.product.updateStock(item.quantity);
      }

      await order.cancel(reason);

      await transaction.commit();

      return await this.getOrderWithDetails(orderId);
    } catch (error) {
      await transaction.rollback();
      throw error;
    }
  }

  async updateOrderStatus(orderId, newStatus, trackingNumber = null) {
    const transaction = await this.sequelize.transaction();

    try {
      const order = await this.Order.findByPk(orderId, { transaction });

      if (!order) {
        throw new Error("Order not found");
      }

      const validTransitions = {
        pending: ["processing", "cancelled"],
        processing: ["shipped", "cancelled"],
        shipped: ["delivered", "cancelled"],
        delivered: ["refunded"],
        cancelled: [],
        refunded: [],
      };

      const allowedStatuses = validTransitions[order.status] || [];

      if (!allowedStatuses.includes(newStatus)) {
        throw new Error(
          `Cannot transition from ${order.status} to ${newStatus}`,
        );
      }

      if (newStatus === "shipped") {
        if (!trackingNumber) {
          throw new Error("Tracking number required for shipped status");
        }
        await order.markAsShipped(trackingNumber);
      } else {
        order.status = newStatus;
        await order.save({ transaction });
      }

      await transaction.commit();

      return await this.getOrderWithDetails(orderId);
    } catch (error) {
      await transaction.rollback();
      throw error;
    }
  }

  async addItemToOrder(orderId, productId, quantity, discount = 0) {
    const transaction = await this.sequelize.transaction();

    try {
      const order = await this.Order.findByPk(orderId, { transaction });

      if (!order) {
        throw new Error("Order not found");
      }

      if (order.status !== "pending" && order.status !== "processing") {
        throw new Error("Cannot add items to order in current status");
      }

      const existing = await this.OrderProduct.findOne({
        where: { orderId, productId },
        transaction,
      });

      if (existing) {
        throw new Error(
          "Product already in order. Use updateItemQuantity instead",
        );
      }

      const product = await this.Product.findByPk(productId, {
        transaction,
        lock: transaction.LOCK.UPDATE,
      });

      if (!product) {
        throw new Error("Product not found");
      }

      if (!product.isAvailable()) {
        throw new Error("Product not available");
      }

      if (product.stockQuantity < quantity) {
        throw new Error("Insufficient stock");
      }

      await this.OrderProduct.create(
        {
          orderId,
          productId,
          quantity,
          price: product.price,
          discount,
        },
        { transaction },
      );

      await product.updateStock(-quantity);

      await order.calculateTotal();

      await transaction.commit();

      return await this.getOrderWithDetails(orderId);
    } catch (error) {
      await transaction.rollback();
      throw error;
    }
  }

  async removeItemFromOrder(orderId, productId) {
    const transaction = await this.sequelize.transaction();

    try {
      const order = await this.Order.findByPk(orderId, { transaction });

      if (!order) {
        throw new Error("Order not found");
      }

      if (order.status !== "pending" && order.status !== "processing") {
        throw new Error("Cannot remove items from order in current status");
      }

      const orderProduct = await this.OrderProduct.findOne({
        where: { orderId, productId },
        include: [
          {
            model: this.Product,
            as: "product",
          },
        ],
        transaction,
      });

      if (!orderProduct) {
        throw new Error("Product not in order");
      }

      await orderProduct.product.updateStock(orderProduct.quantity);

      await orderProduct.destroy({ transaction });

      await order.calculateTotal();

      await transaction.commit();

      return await this.getOrderWithDetails(orderId);
    } catch (error) {
      await transaction.rollback();
      throw error;
    }
  }

  async getOrderWithDetails(orderId) {
    return await this.Order.findByPk(orderId, {
      include: [
        {
          model: this.User,
          as: "user",
          attributes: ["id", "username", "email", "firstName", "lastName"],
        },
        {
          model: this.Product,
          as: "products",
          through: {
            model: this.OrderProduct,
            attributes: ["quantity", "price", "discount", "notes"],
          },
        },
      ],
    });
  }

  async getUserOrders(userId, options = {}) {
    const where = { userId };

    if (options.status) {
      where.status = options.status;
    }

    if (options.dateFrom) {
      where.createdAt = { [Op.gte]: new Date(options.dateFrom) };
    }

    if (options.dateTo) {
      where.createdAt = {
        ...where.createdAt,
        [Op.lte]: new Date(options.dateTo),
      };
    }

    const limit = options.limit || 20;
    const offset = options.offset || 0;

    const { count, rows } = await this.Order.findAndCountAll({
      where,
      include: [
        {
          model: this.Product,
          as: "products",
          through: {
            attributes: ["quantity", "price", "discount"],
          },
        },
      ],
      order: [["createdAt", "DESC"]],
      limit,
      offset,
    });

    return {
      orders: rows,
      total: count,
      page: Math.floor(offset / limit) + 1,
      pages: Math.ceil(count / limit),
    };
  }

  async getOrderStatistics(dateRange = {}) {
    const where = {};

    if (dateRange.start) {
      where.createdAt = { [Op.gte]: new Date(dateRange.start) };
    }

    if (dateRange.end) {
      where.createdAt = {
        ...where.createdAt,
        [Op.lte]: new Date(dateRange.end),
      };
    }

    const overall = await this.Order.findAll({
      attributes: [
        [this.sequelize.fn("COUNT", this.sequelize.col("id")), "totalOrders"],
        [this.sequelize.fn("SUM", this.sequelize.col("total")), "totalRevenue"],
        [
          this.sequelize.fn("AVG", this.sequelize.col("total")),
          "avgOrderValue",
        ],
        [
          this.sequelize.fn("MAX", this.sequelize.col("total")),
          "maxOrderValue",
        ],
        [
          this.sequelize.fn("MIN", this.sequelize.col("total")),
          "minOrderValue",
        ],
      ],
      where: {
        ...where,
        status: {
          [Op.notIn]: ["cancelled", "refunded"],
        },
      },
      raw: true,
    });

    const byStatus = await this.Order.findAll({
      attributes: [
        "status",
        [this.sequelize.fn("COUNT", this.sequelize.col("id")), "count"],
        [this.sequelize.fn("SUM", this.sequelize.col("total")), "revenue"],
      ],
      where,
      group: ["status"],
      raw: true,
    });

    const byDay = await this.Order.findAll({
      attributes: [
        [this.sequelize.fn("DATE", this.sequelize.col("createdAt")), "date"],
        [this.sequelize.fn("COUNT", this.sequelize.col("id")), "orders"],
        [this.sequelize.fn("SUM", this.sequelize.col("total")), "revenue"],
      ],
      where,
      group: [this.sequelize.fn("DATE", this.sequelize.col("createdAt"))],
      order: [
        [this.sequelize.fn("DATE", this.sequelize.col("createdAt")), "ASC"],
      ],
      raw: true,
    });

    return {
      overall: overall[0] || {},
      byStatus,
      byDay,
    };
  }

  async processBulkOrders(orderIds, action) {
    const transaction = await this.sequelize.transaction();

    try {
      const orders = await this.Order.findAll({
        where: {
          id: { [Op.in]: orderIds },
        },
        transaction,
      });

      if (orders.length === 0) {
        throw new Error("No orders found");
      }

      const results = [];

      for (const order of orders) {
        try {
          if (action === "ship" && order.status === "processing") {
            await order.update({ status: "shipped" }, { transaction });
            results.push({ orderId: order.id, success: true });
          } else if (action === "cancel" && order.status !== "delivered") {
            await this.cancelOrder(order.id, "Bulk cancellation");
            results.push({ orderId: order.id, success: true });
          } else {
            results.push({
              orderId: order.id,
              success: false,
              error: "Invalid action for order status",
            });
          }
        } catch (error) {
          results.push({
            orderId: order.id,
            success: false,
            error: error.message,
          });
        }
      }

      await transaction.commit();

      return results;
    } catch (error) {
      await transaction.rollback();
      throw error;
    }
  }
}

module.exports = OrderService;
