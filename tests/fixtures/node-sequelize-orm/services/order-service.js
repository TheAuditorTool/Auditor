/**
 * Order Service with complex transactions
 * Tests: Multi-table transactions, inventory management, order processing
 */

const { Op } = require('sequelize');

class OrderService {
  constructor(sequelize) {
    this.sequelize = sequelize;
    this.Order = sequelize.models.Order;
    this.OrderProduct = sequelize.models.OrderProduct;
    this.Product = sequelize.models.Product;
    this.User = sequelize.models.User;
  }

  /**
   * Create order with line items (complex transaction)
   * Tests: Multi-table transaction, stock validation, inventory updates
   * TAINT FLOW: orderData (user input) -> Order.create
   */
  async createOrder(userId, orderData, lineItems) {
    const transaction = await this.sequelize.transaction();

    try {
      // Verify user exists
      const user = await this.User.findByPk(userId, { transaction });
      if (!user) {
        throw new Error('User not found');
      }

      // Validate all products exist and have sufficient stock
      const productIds = lineItems.map(item => item.productId);
      const products = await this.Product.findAll({
        where: {
          id: { [Op.in]: productIds }
        },
        transaction,
        lock: transaction.LOCK.UPDATE // Lock for update to prevent race conditions
      });

      if (products.length !== productIds.length) {
        throw new Error('One or more products not found');
      }

      // Build product map for quick lookup
      const productMap = {};
      products.forEach(p => {
        productMap[p.id] = p;
      });

      // Validate stock and calculate totals
      let subtotal = 0;
      const validatedItems = [];

      for (const item of lineItems) {
        const product = productMap[item.productId];

        if (!product.isAvailable()) {
          throw new Error(`Product ${product.name} is not available`);
        }

        if (product.stockQuantity < item.quantity) {
          throw new Error(`Insufficient stock for ${product.name}. Available: ${product.stockQuantity}`);
        }

        const lineTotal = parseFloat(product.price) * item.quantity;
        subtotal += lineTotal;

        validatedItems.push({
          productId: item.productId,
          product: product,
          quantity: item.quantity,
          price: product.price,
          discount: item.discount || 0
        });
      }

      // Calculate order totals
      const tax = subtotal * 0.08; // 8% tax
      const shippingCost = orderData.shippingCost || 10.00;
      const discount = orderData.discount || 0;
      const total = subtotal + tax + shippingCost - discount;

      // Create order
      const order = await this.Order.create({
        userId,
        orderNumber: orderData.orderNumber,
        status: 'pending',
        subtotal,
        tax,
        shippingCost,
        discount,
        total,
        shippingAddress: orderData.shippingAddress,
        billingAddress: orderData.billingAddress || orderData.shippingAddress,
        notes: orderData.notes || null
      }, { transaction });

      // Create order line items and update product stock
      for (const item of validatedItems) {
        // Create order product
        await this.OrderProduct.create({
          orderId: order.id,
          productId: item.productId,
          quantity: item.quantity,
          price: item.price,
          discount: item.discount
        }, { transaction });

        // Update product stock (using instance method)
        await item.product.updateStock(-item.quantity);
      }

      await transaction.commit();

      // Return order with line items
      return await this.getOrderWithDetails(order.id);
    } catch (error) {
      await transaction.rollback();
      throw error;
    }
  }

  /**
   * Cancel order and restore inventory
   * Tests: Cascading updates, inventory restoration
   */
  async cancelOrder(orderId, reason) {
    const transaction = await this.sequelize.transaction();

    try {
      const order = await this.Order.findByPk(orderId, { transaction });

      if (!order) {
        throw new Error('Order not found');
      }

      if (order.status === 'delivered') {
        throw new Error('Cannot cancel delivered order');
      }

      if (order.status === 'cancelled') {
        throw new Error('Order already cancelled');
      }

      // Get order line items
      const lineItems = await this.OrderProduct.findAll({
        where: { orderId },
        include: [{
          model: this.Product,
          as: 'product'
        }],
        transaction
      });

      // Restore product stock
      for (const item of lineItems) {
        await item.product.updateStock(item.quantity);
      }

      // Update order status
      await order.cancel(reason);

      await transaction.commit();

      return await this.getOrderWithDetails(orderId);
    } catch (error) {
      await transaction.rollback();
      throw error;
    }
  }

  /**
   * Update order status with business logic
   * Tests: Status transitions, validation
   */
  async updateOrderStatus(orderId, newStatus, trackingNumber = null) {
    const transaction = await this.sequelize.transaction();

    try {
      const order = await this.Order.findByPk(orderId, { transaction });

      if (!order) {
        throw new Error('Order not found');
      }

      // Validate status transition
      const validTransitions = {
        'pending': ['processing', 'cancelled'],
        'processing': ['shipped', 'cancelled'],
        'shipped': ['delivered', 'cancelled'],
        'delivered': ['refunded'],
        'cancelled': [],
        'refunded': []
      };

      const allowedStatuses = validTransitions[order.status] || [];

      if (!allowedStatuses.includes(newStatus)) {
        throw new Error(`Cannot transition from ${order.status} to ${newStatus}`);
      }

      // Apply status-specific logic
      if (newStatus === 'shipped') {
        if (!trackingNumber) {
          throw new Error('Tracking number required for shipped status');
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

  /**
   * Add item to existing order
   * Tests: Adding to existing transaction, stock validation
   */
  async addItemToOrder(orderId, productId, quantity, discount = 0) {
    const transaction = await this.sequelize.transaction();

    try {
      const order = await this.Order.findByPk(orderId, { transaction });

      if (!order) {
        throw new Error('Order not found');
      }

      if (order.status !== 'pending' && order.status !== 'processing') {
        throw new Error('Cannot add items to order in current status');
      }

      // Check if product already in order
      const existing = await this.OrderProduct.findOne({
        where: { orderId, productId },
        transaction
      });

      if (existing) {
        throw new Error('Product already in order. Use updateItemQuantity instead');
      }

      // Get product and validate stock
      const product = await this.Product.findByPk(productId, {
        transaction,
        lock: transaction.LOCK.UPDATE
      });

      if (!product) {
        throw new Error('Product not found');
      }

      if (!product.isAvailable()) {
        throw new Error('Product not available');
      }

      if (product.stockQuantity < quantity) {
        throw new Error('Insufficient stock');
      }

      // Create order product
      await this.OrderProduct.create({
        orderId,
        productId,
        quantity,
        price: product.price,
        discount
      }, { transaction });

      // Update product stock
      await product.updateStock(-quantity);

      // Recalculate order total
      await order.calculateTotal();

      await transaction.commit();

      return await this.getOrderWithDetails(orderId);
    } catch (error) {
      await transaction.rollback();
      throw error;
    }
  }

  /**
   * Remove item from order
   * Tests: Removing from transaction, inventory restoration
   */
  async removeItemFromOrder(orderId, productId) {
    const transaction = await this.sequelize.transaction();

    try {
      const order = await this.Order.findByPk(orderId, { transaction });

      if (!order) {
        throw new Error('Order not found');
      }

      if (order.status !== 'pending' && order.status !== 'processing') {
        throw new Error('Cannot remove items from order in current status');
      }

      const orderProduct = await this.OrderProduct.findOne({
        where: { orderId, productId },
        include: [{
          model: this.Product,
          as: 'product'
        }],
        transaction
      });

      if (!orderProduct) {
        throw new Error('Product not in order');
      }

      // Restore product stock
      await orderProduct.product.updateStock(orderProduct.quantity);

      // Remove order product
      await orderProduct.destroy({ transaction });

      // Recalculate order total
      await order.calculateTotal();

      await transaction.commit();

      return await this.getOrderWithDetails(orderId);
    } catch (error) {
      await transaction.rollback();
      throw error;
    }
  }

  /**
   * Get order with full details
   * Tests: Complex JOIN with multiple relationships
   */
  async getOrderWithDetails(orderId) {
    return await this.Order.findByPk(orderId, {
      include: [
        {
          model: this.User,
          as: 'user',
          attributes: ['id', 'username', 'email', 'firstName', 'lastName']
        },
        {
          model: this.Product,
          as: 'products',
          through: {
            model: this.OrderProduct,
            attributes: ['quantity', 'price', 'discount', 'notes']
          }
        }
      ]
    });
  }

  /**
   * Get user orders with pagination
   * Tests: Pagination, filtering, ordering
   */
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
        [Op.lte]: new Date(options.dateTo)
      };
    }

    const limit = options.limit || 20;
    const offset = options.offset || 0;

    const { count, rows } = await this.Order.findAndCountAll({
      where,
      include: [{
        model: this.Product,
        as: 'products',
        through: {
          attributes: ['quantity', 'price', 'discount']
        }
      }],
      order: [['createdAt', 'DESC']],
      limit,
      offset
    });

    return {
      orders: rows,
      total: count,
      page: Math.floor(offset / limit) + 1,
      pages: Math.ceil(count / limit)
    };
  }

  /**
   * Get order statistics
   * Tests: Aggregations with GROUP BY
   */
  async getOrderStatistics(dateRange = {}) {
    const where = {};

    if (dateRange.start) {
      where.createdAt = { [Op.gte]: new Date(dateRange.start) };
    }

    if (dateRange.end) {
      where.createdAt = {
        ...where.createdAt,
        [Op.lte]: new Date(dateRange.end)
      };
    }

    // Overall statistics
    const overall = await this.Order.findAll({
      attributes: [
        [this.sequelize.fn('COUNT', this.sequelize.col('id')), 'totalOrders'],
        [this.sequelize.fn('SUM', this.sequelize.col('total')), 'totalRevenue'],
        [this.sequelize.fn('AVG', this.sequelize.col('total')), 'avgOrderValue'],
        [this.sequelize.fn('MAX', this.sequelize.col('total')), 'maxOrderValue'],
        [this.sequelize.fn('MIN', this.sequelize.col('total')), 'minOrderValue']
      ],
      where: {
        ...where,
        status: {
          [Op.notIn]: ['cancelled', 'refunded']
        }
      },
      raw: true
    });

    // By status
    const byStatus = await this.Order.findAll({
      attributes: [
        'status',
        [this.sequelize.fn('COUNT', this.sequelize.col('id')), 'count'],
        [this.sequelize.fn('SUM', this.sequelize.col('total')), 'revenue']
      ],
      where,
      group: ['status'],
      raw: true
    });

    // By day
    const byDay = await this.Order.findAll({
      attributes: [
        [this.sequelize.fn('DATE', this.sequelize.col('createdAt')), 'date'],
        [this.sequelize.fn('COUNT', this.sequelize.col('id')), 'orders'],
        [this.sequelize.fn('SUM', this.sequelize.col('total')), 'revenue']
      ],
      where,
      group: [this.sequelize.fn('DATE', this.sequelize.col('createdAt'))],
      order: [[this.sequelize.fn('DATE', this.sequelize.col('createdAt')), 'ASC']],
      raw: true
    });

    return {
      overall: overall[0] || {},
      byStatus,
      byDay
    };
  }

  /**
   * Process bulk orders
   * Tests: Bulk operations with transaction
   */
  async processBulkOrders(orderIds, action) {
    const transaction = await this.sequelize.transaction();

    try {
      const orders = await this.Order.findAll({
        where: {
          id: { [Op.in]: orderIds }
        },
        transaction
      });

      if (orders.length === 0) {
        throw new Error('No orders found');
      }

      const results = [];

      for (const order of orders) {
        try {
          if (action === 'ship' && order.status === 'processing') {
            await order.update({ status: 'shipped' }, { transaction });
            results.push({ orderId: order.id, success: true });
          } else if (action === 'cancel' && order.status !== 'delivered') {
            await this.cancelOrder(order.id, 'Bulk cancellation');
            results.push({ orderId: order.id, success: true });
          } else {
            results.push({
              orderId: order.id,
              success: false,
              error: 'Invalid action for order status'
            });
          }
        } catch (error) {
          results.push({
            orderId: order.id,
            success: false,
            error: error.message
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
