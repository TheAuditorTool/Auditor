/**
 * Order model with relationships and transactions
 * Tests: Many-to-one (Order belongs to User), many-to-many (Order has many Products)
 */

module.exports = (sequelize, DataTypes) => {
  const Order = sequelize.define('Order', {
    id: {
      type: DataTypes.INTEGER,
      primaryKey: true,
      autoIncrement: true
    },

    orderNumber: {
      type: DataTypes.STRING(50),
      allowNull: false,
      unique: {
        msg: 'Order number must be unique'
      },
      validate: {
        notEmpty: true,
        is: {
          args: /^ORD-\d{8}-[A-Z0-9]{6}$/,
          msg: 'Order number must match format: ORD-YYYYMMDD-XXXXXX'
        }
      }
    },

    status: {
      type: DataTypes.ENUM('pending', 'processing', 'shipped', 'delivered', 'cancelled', 'refunded'),
      defaultValue: 'pending',
      allowNull: false,
      validate: {
        isIn: {
          args: [['pending', 'processing', 'shipped', 'delivered', 'cancelled', 'refunded']],
          msg: 'Invalid order status'
        }
      }
    },

    total: {
      type: DataTypes.DECIMAL(10, 2),
      allowNull: false,
      defaultValue: 0.00,
      validate: {
        min: {
          args: [0],
          msg: 'Total must be non-negative'
        },
        isDecimal: {
          msg: 'Total must be a decimal number'
        }
      }
    },

    subtotal: {
      type: DataTypes.DECIMAL(10, 2),
      allowNull: false,
      defaultValue: 0.00
    },

    tax: {
      type: DataTypes.DECIMAL(10, 2),
      allowNull: false,
      defaultValue: 0.00
    },

    shippingCost: {
      type: DataTypes.DECIMAL(10, 2),
      allowNull: false,
      defaultValue: 0.00
    },

    discount: {
      type: DataTypes.DECIMAL(10, 2),
      allowNull: false,
      defaultValue: 0.00
    },

    // Shipping information
    shippingAddress: {
      type: DataTypes.JSONB,
      allowNull: false,
      validate: {
        isValidAddress(value) {
          if (!value.street || !value.city || !value.country) {
            throw new Error('Shipping address must contain street, city, and country');
          }
        }
      }
    },

    billingAddress: {
      type: DataTypes.JSONB,
      allowNull: true
    },

    trackingNumber: {
      type: DataTypes.STRING(100),
      allowNull: true,
      validate: {
        len: {
          args: [10, 100],
          msg: 'Tracking number must be between 10 and 100 characters'
        }
      }
    },

    shippedAt: {
      type: DataTypes.DATE,
      allowNull: true
    },

    deliveredAt: {
      type: DataTypes.DATE,
      allowNull: true
    },

    cancelledAt: {
      type: DataTypes.DATE,
      allowNull: true
    },

    cancellationReason: {
      type: DataTypes.TEXT,
      allowNull: true
    },

    notes: {
      type: DataTypes.TEXT,
      allowNull: true
    },

    // Virtual field: days since order
    daysSinceOrder: {
      type: DataTypes.VIRTUAL,
      get() {
        if (!this.createdAt) return null;
        const now = new Date();
        const created = new Date(this.createdAt);
        return Math.floor((now - created) / (1000 * 60 * 60 * 24));
      }
    },

    createdAt: {
      type: DataTypes.DATE,
      allowNull: false,
      defaultValue: DataTypes.NOW
    },

    updatedAt: {
      type: DataTypes.DATE,
      allowNull: false,
      defaultValue: DataTypes.NOW
    }
  }, {
    tableName: 'orders',
    timestamps: true,

    // Hooks
    hooks: {
      /**
       * beforeCreate hook - Generate order number
       * Tests: Hook with side effects
       */
      beforeCreate: async (order, options) => {
        if (!order.orderNumber) {
          const date = new Date();
          const dateStr = date.toISOString().slice(0, 10).replace(/-/g, '');
          const random = Math.random().toString(36).substring(2, 8).toUpperCase();
          order.orderNumber = `ORD-${dateStr}-${random}`;
        }

        // Calculate total if not provided
        if (!order.total || order.total === 0) {
          order.total = parseFloat(order.subtotal) + parseFloat(order.tax) +
                       parseFloat(order.shippingCost) - parseFloat(order.discount);
        }
      },

      /**
       * beforeUpdate hook - Update timestamps for status changes
       * Tests: Conditional hook execution
       */
      beforeUpdate: async (order, options) => {
        if (order.changed('status')) {
          const now = new Date();

          if (order.status === 'shipped' && !order.shippedAt) {
            order.shippedAt = now;
          }

          if (order.status === 'delivered' && !order.deliveredAt) {
            order.deliveredAt = now;
          }

          if (order.status === 'cancelled' && !order.cancelledAt) {
            order.cancelledAt = now;
          }
        }
      },

      /**
       * afterCreate hook - Send order confirmation
       * Tests: Hook with external side effects
       */
      afterCreate: async (order, options) => {
        console.log(`Order ${order.orderNumber} created - Total: $${order.total}`);
      }
    },

    // Indexes
    indexes: [
      {
        unique: true,
        fields: ['orderNumber']
      },
      {
        fields: ['userId']
      },
      {
        fields: ['status']
      },
      {
        fields: ['createdAt']
      },
      {
        fields: ['shippedAt']
      }
    ]
  });

  /**
   * Associations
   * Tests: Many-to-one and many-to-many relationships
   */
  Order.associate = function(models) {
    // Many-to-one: Order belongs to User
    Order.belongsTo(models.User, {
      foreignKey: 'userId',
      as: 'user',
      onDelete: 'CASCADE',
      onUpdate: 'CASCADE'
    });

    // Many-to-many: Order has many Products through OrderProducts
    Order.belongsToMany(models.Product, {
      through: models.OrderProduct,
      foreignKey: 'orderId',
      otherKey: 'productId',
      as: 'products',
      onDelete: 'CASCADE'
    });
  };

  /**
   * Instance methods
   */

  /**
   * Calculate order total from line items
   * Tests: Instance method with aggregation
   */
  Order.prototype.calculateTotal = async function() {
    const OrderProduct = sequelize.models.OrderProduct;

    const items = await OrderProduct.findAll({
      where: { orderId: this.id }
    });

    const subtotal = items.reduce((sum, item) => {
      return sum + (parseFloat(item.price) * parseInt(item.quantity));
    }, 0);

    this.subtotal = subtotal;
    this.total = subtotal + parseFloat(this.tax) +
                parseFloat(this.shippingCost) - parseFloat(this.discount);

    await this.save();
    return this.total;
  };

  /**
   * Mark order as shipped
   * Tests: Instance method with status transition
   */
  Order.prototype.markAsShipped = async function(trackingNumber) {
    this.status = 'shipped';
    this.shippedAt = new Date();
    this.trackingNumber = trackingNumber;
    await this.save();
  };

  /**
   * Cancel order with reason
   * Tests: Instance method with validation
   */
  Order.prototype.cancel = async function(reason) {
    if (this.status === 'delivered') {
      throw new Error('Cannot cancel a delivered order');
    }

    this.status = 'cancelled';
    this.cancelledAt = new Date();
    this.cancellationReason = reason;
    await this.save();
  };

  /**
   * Get order details with products
   * Tests: Instance method with complex query
   */
  Order.prototype.getDetails = async function() {
    const Product = sequelize.models.Product;
    const OrderProduct = sequelize.models.OrderProduct;

    return await Order.findByPk(this.id, {
      include: [{
        model: Product,
        as: 'products',
        through: {
          model: OrderProduct,
          attributes: ['quantity', 'price', 'discount']
        }
      }]
    });
  };

  /**
   * Class methods
   */

  /**
   * Find orders by status
   * Tests: Class method with filtering
   */
  Order.findByStatus = async function(status) {
    return await this.findAll({
      where: { status },
      include: [
        { model: sequelize.models.User, as: 'user' }
      ],
      order: [['createdAt', 'DESC']]
    });
  };

  /**
   * Find pending orders older than days
   * Tests: Class method with date comparison
   */
  Order.findPendingOlderThan = async function(days) {
    const { Op } = sequelize;
    const cutoffDate = new Date();
    cutoffDate.setDate(cutoffDate.getDate() - days);

    return await this.findAll({
      where: {
        status: 'pending',
        createdAt: {
          [Op.lt]: cutoffDate
        }
      },
      include: [{ model: sequelize.models.User, as: 'user' }]
    });
  };

  /**
   * Get revenue statistics
   * Tests: Class method with aggregation
   */
  Order.getRevenueStats = async function(startDate, endDate) {
    const { fn, col, Op } = sequelize;

    return await this.findAll({
      attributes: [
        [fn('COUNT', col('id')), 'orderCount'],
        [fn('SUM', col('total')), 'totalRevenue'],
        [fn('AVG', col('total')), 'averageOrderValue'],
        [fn('MAX', col('total')), 'largestOrder']
      ],
      where: {
        status: {
          [Op.notIn]: ['cancelled', 'refunded']
        },
        createdAt: {
          [Op.between]: [startDate, endDate]
        }
      },
      raw: true
    });
  };

  return Order;
};
