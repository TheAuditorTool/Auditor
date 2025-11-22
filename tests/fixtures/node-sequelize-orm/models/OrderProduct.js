/**
 * OrderProduct junction table
 * Tests: Many-to-many relationship junction table with additional fields
 */

module.exports = (sequelize, DataTypes) => {
  const OrderProduct = sequelize.define('OrderProduct', {
    id: {
      type: DataTypes.INTEGER,
      primaryKey: true,
      autoIncrement: true
    },

    orderId: {
      type: DataTypes.INTEGER,
      allowNull: false,
      references: {
        model: 'orders',
        key: 'id'
      },
      onDelete: 'CASCADE',
      onUpdate: 'CASCADE'
    },

    productId: {
      type: DataTypes.INTEGER,
      allowNull: false,
      references: {
        model: 'products',
        key: 'id'
      },
      onDelete: 'CASCADE',
      onUpdate: 'CASCADE'
    },

    quantity: {
      type: DataTypes.INTEGER,
      allowNull: false,
      defaultValue: 1,
      validate: {
        min: {
          args: [1],
          msg: 'Quantity must be at least 1'
        },
        isInt: {
          msg: 'Quantity must be an integer'
        }
      }
    },

    price: {
      type: DataTypes.DECIMAL(10, 2),
      allowNull: false,
      comment: 'Price at time of order (snapshot)',
      validate: {
        min: {
          args: [0],
          msg: 'Price must be non-negative'
        },
        isDecimal: {
          msg: 'Price must be a decimal number'
        }
      }
    },

    discount: {
      type: DataTypes.DECIMAL(10, 2),
      allowNull: false,
      defaultValue: 0.00,
      comment: 'Discount applied to this line item',
      validate: {
        min: {
          args: [0],
          msg: 'Discount must be non-negative'
        }
      }
    },

    // Virtual field: line total
    lineTotal: {
      type: DataTypes.VIRTUAL,
      get() {
        const quantity = parseInt(this.quantity);
        const price = parseFloat(this.price);
        const discount = parseFloat(this.discount);
        return (quantity * price - discount).toFixed(2);
      }
    },

    notes: {
      type: DataTypes.TEXT,
      allowNull: true,
      comment: 'Special instructions or notes for this item'
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
    tableName: 'order_products',
    timestamps: true,

    // Hooks
    hooks: {
      /**
       * beforeCreate hook - Snapshot product price
       * Tests: Hook with external data lookup
       */
      beforeCreate: async (orderProduct, options) => {
        // If price not explicitly set, snapshot current product price
        if (!orderProduct.price) {
          const Product = sequelize.models.Product;
          const product = await Product.findByPk(orderProduct.productId);

          if (!product) {
            throw new Error('Product not found');
          }

          orderProduct.price = product.price;
        }

        // Validate quantity against stock
        const Product = sequelize.models.Product;
        const product = await Product.findByPk(orderProduct.productId);

        if (product && orderProduct.quantity > product.stockQuantity) {
          throw new Error(`Insufficient stock. Available: ${product.stockQuantity}, Requested: ${orderProduct.quantity}`);
        }
      },

      /**
       * afterCreate hook - Update product sold count
       * Tests: Hook with cascading updates
       */
      afterCreate: async (orderProduct, options) => {
        const Product = sequelize.models.Product;
        const product = await Product.findByPk(orderProduct.productId);

        if (product) {
          await product.recordSale(orderProduct.quantity);
        }
      }
    },

    // Indexes
    indexes: [
      {
        unique: true,
        fields: ['orderId', 'productId']
      },
      {
        fields: ['orderId']
      },
      {
        fields: ['productId']
      }
    ]
  });

  /**
   * Associations
   * Tests: Junction table associations
   */
  OrderProduct.associate = function(models) {
    // Junction table associations are typically defined on the main models
    // But we can add explicit associations here if needed
    OrderProduct.belongsTo(models.Order, {
      foreignKey: 'orderId',
      as: 'order'
    });

    OrderProduct.belongsTo(models.Product, {
      foreignKey: 'productId',
      as: 'product'
    });
  };

  /**
   * Instance methods
   */

  /**
   * Update quantity and recalculate
   * Tests: Instance method with validation
   */
  OrderProduct.prototype.updateQuantity = async function(newQuantity) {
    if (newQuantity < 1) {
      throw new Error('Quantity must be at least 1');
    }

    const Product = sequelize.models.Product;
    const product = await Product.findByPk(this.productId);

    const quantityDiff = newQuantity - this.quantity;

    if (product && quantityDiff > product.stockQuantity) {
      throw new Error('Insufficient stock for quantity increase');
    }

    this.quantity = newQuantity;
    await this.save();

    // Update product stock
    if (product) {
      await product.updateStock(-quantityDiff);
    }
  };

  /**
   * Apply discount
   * Tests: Instance method with business logic
   */
  OrderProduct.prototype.applyDiscount = async function(discountAmount) {
    if (discountAmount < 0) {
      throw new Error('Discount cannot be negative');
    }

    const maxDiscount = parseFloat(this.price) * this.quantity;

    if (discountAmount > maxDiscount) {
      throw new Error('Discount cannot exceed line total');
    }

    this.discount = discountAmount;
    await this.save();
  };

  /**
   * Class methods
   */

  /**
   * Get all items for an order
   * Tests: Class method with JOIN
   */
  OrderProduct.getOrderItems = async function(orderId) {
    const Product = sequelize.models.Product;

    return await this.findAll({
      where: { orderId },
      include: [{
        model: Product,
        as: 'product',
        attributes: ['id', 'sku', 'name', 'imageUrl']
      }],
      order: [['createdAt', 'ASC']]
    });
  };

  /**
   * Get orders for a product
   * Tests: Class method with JOIN
   */
  OrderProduct.getProductOrders = async function(productId) {
    const Order = sequelize.models.Order;

    return await this.findAll({
      where: { productId },
      include: [{
        model: Order,
        as: 'order',
        attributes: ['id', 'orderNumber', 'status', 'total', 'createdAt']
      }],
      order: [['createdAt', 'DESC']]
    });
  };

  return OrderProduct;
};
