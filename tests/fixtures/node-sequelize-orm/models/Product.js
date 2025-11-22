/**
 * Product model with inventory management
 * Tests: Many-to-many relationship (Product belongs to many Orders)
 */

module.exports = (sequelize, DataTypes) => {
  const Product = sequelize.define('Product', {
    id: {
      type: DataTypes.INTEGER,
      primaryKey: true,
      autoIncrement: true
    },

    sku: {
      type: DataTypes.STRING(50),
      allowNull: false,
      unique: {
        msg: 'SKU must be unique'
      },
      validate: {
        notEmpty: true,
        is: {
          args: /^[A-Z0-9\-]{6,50}$/,
          msg: 'SKU must be 6-50 characters (uppercase letters, numbers, hyphens only)'
        }
      }
    },

    name: {
      type: DataTypes.STRING(200),
      allowNull: false,
      validate: {
        notEmpty: {
          msg: 'Product name cannot be empty'
        },
        len: {
          args: [3, 200],
          msg: 'Product name must be between 3 and 200 characters'
        }
      }
    },

    description: {
      type: DataTypes.TEXT,
      allowNull: true
    },

    price: {
      type: DataTypes.DECIMAL(10, 2),
      allowNull: false,
      validate: {
        min: {
          args: [0.01],
          msg: 'Price must be greater than 0'
        },
        isDecimal: {
          msg: 'Price must be a decimal number'
        }
      }
    },

    cost: {
      type: DataTypes.DECIMAL(10, 2),
      allowNull: false,
      defaultValue: 0.00,
      validate: {
        min: {
          args: [0],
          msg: 'Cost must be non-negative'
        }
      }
    },

    // Virtual field: profit margin
    profitMargin: {
      type: DataTypes.VIRTUAL,
      get() {
        const price = parseFloat(this.price);
        const cost = parseFloat(this.cost);
        if (!price || price === 0) return 0;
        return ((price - cost) / price * 100).toFixed(2);
      }
    },

    stockQuantity: {
      type: DataTypes.INTEGER,
      allowNull: false,
      defaultValue: 0,
      validate: {
        min: {
          args: [0],
          msg: 'Stock quantity cannot be negative'
        },
        isInt: {
          msg: 'Stock quantity must be an integer'
        }
      }
    },

    lowStockThreshold: {
      type: DataTypes.INTEGER,
      allowNull: false,
      defaultValue: 10,
      validate: {
        min: {
          args: [0],
          msg: 'Low stock threshold cannot be negative'
        }
      }
    },

    // Virtual field: is low stock
    isLowStock: {
      type: DataTypes.VIRTUAL,
      get() {
        return this.stockQuantity <= this.lowStockThreshold;
      }
    },

    weight: {
      type: DataTypes.DECIMAL(8, 2),
      allowNull: true,
      comment: 'Weight in kilograms',
      validate: {
        min: {
          args: [0],
          msg: 'Weight must be non-negative'
        }
      }
    },

    dimensions: {
      type: DataTypes.JSONB,
      allowNull: true,
      comment: 'JSON object: {length, width, height} in centimeters',
      validate: {
        isValidDimensions(value) {
          if (value && (!value.length || !value.width || !value.height)) {
            throw new Error('Dimensions must contain length, width, and height');
          }
        }
      }
    },

    category: {
      type: DataTypes.STRING(100),
      allowNull: true,
      validate: {
        len: {
          args: [2, 100],
          msg: 'Category must be between 2 and 100 characters'
        }
      }
    },

    tags: {
      type: DataTypes.ARRAY(DataTypes.STRING),
      allowNull: true,
      defaultValue: []
    },

    status: {
      type: DataTypes.ENUM('active', 'inactive', 'discontinued', 'out_of_stock'),
      defaultValue: 'active',
      allowNull: false
    },

    featured: {
      type: DataTypes.BOOLEAN,
      defaultValue: false,
      allowNull: false
    },

    imageUrl: {
      type: DataTypes.STRING(500),
      allowNull: true,
      validate: {
        isUrl: {
          msg: 'Image URL must be a valid URL'
        }
      }
    },

    metadata: {
      type: DataTypes.JSONB,
      defaultValue: {},
      allowNull: false,
      comment: 'Additional product metadata'
    },

    viewCount: {
      type: DataTypes.INTEGER,
      defaultValue: 0,
      allowNull: false
    },

    soldCount: {
      type: DataTypes.INTEGER,
      defaultValue: 0,
      allowNull: false
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
    tableName: 'products',
    timestamps: true,

    // Hooks
    hooks: {
      /**
       * beforeCreate hook - Normalize SKU
       * Tests: Hook with data transformation
       */
      beforeCreate: async (product, options) => {
        if (product.sku) {
          product.sku = product.sku.toUpperCase().trim();
        }

        // Set status based on stock quantity
        if (product.stockQuantity === 0) {
          product.status = 'out_of_stock';
        }
      },

      /**
       * beforeUpdate hook - Update status based on stock
       * Tests: Conditional hook execution
       */
      beforeUpdate: async (product, options) => {
        if (product.changed('stockQuantity')) {
          if (product.stockQuantity === 0 && product.status === 'active') {
            product.status = 'out_of_stock';
          } else if (product.stockQuantity > 0 && product.status === 'out_of_stock') {
            product.status = 'active';
          }
        }
      },

      /**
       * afterUpdate hook - Log significant price changes
       * Tests: Hook with external side effects
       */
      afterUpdate: async (product, options) => {
        if (product.changed('price')) {
          const oldPrice = product._previousDataValues.price;
          const newPrice = product.price;
          const changePercent = ((newPrice - oldPrice) / oldPrice * 100).toFixed(2);
          console.log(`Product ${product.sku} price changed by ${changePercent}%: $${oldPrice} → $${newPrice}`);
        }
      }
    },

    // Indexes
    indexes: [
      {
        unique: true,
        fields: ['sku']
      },
      {
        fields: ['name']
      },
      {
        fields: ['category']
      },
      {
        fields: ['status']
      },
      {
        fields: ['featured']
      },
      {
        fields: ['price']
      },
      {
        fields: ['stockQuantity']
      },
      {
        fields: ['createdAt']
      }
    ]
  });

  /**
   * Associations
   * Tests: Many-to-many relationship
   */
  Product.associate = function(models) {
    // Many-to-many: Product belongs to many Orders through OrderProducts
    Product.belongsToMany(models.Order, {
      through: models.OrderProduct,
      foreignKey: 'productId',
      otherKey: 'orderId',
      as: 'orders',
      onDelete: 'CASCADE'
    });
  };

  /**
   * Instance methods
   */

  /**
   * Update stock quantity
   * Tests: Instance method with validation
   */
  Product.prototype.updateStock = async function(quantity) {
    if (typeof quantity !== 'number') {
      throw new Error('Quantity must be a number');
    }

    const newQuantity = this.stockQuantity + quantity;

    if (newQuantity < 0) {
      throw new Error('Insufficient stock');
    }

    this.stockQuantity = newQuantity;
    await this.save();

    return this.stockQuantity;
  };

  /**
   * Increment view count
   * Tests: Instance method with simple update
   */
  Product.prototype.incrementViewCount = async function() {
    this.viewCount += 1;
    await this.save();
  };

  /**
   * Increment sold count
   * Tests: Instance method with stock update
   */
  Product.prototype.recordSale = async function(quantity) {
    this.soldCount += quantity;
    await this.updateStock(-quantity);
  };

  /**
   * Check if product is available
   * Tests: Instance method with business logic
   */
  Product.prototype.isAvailable = function() {
    return this.status === 'active' && this.stockQuantity > 0;
  };

  /**
   * Get product with sales stats
   * Tests: Instance method with complex query
   */
  Product.prototype.getSalesStats = async function() {
    const { fn, col } = sequelize;
    const OrderProduct = sequelize.models.OrderProduct;

    const stats = await OrderProduct.findAll({
      attributes: [
        [fn('COUNT', col('orderId')), 'orderCount'],
        [fn('SUM', col('quantity')), 'totalQuantitySold'],
        [fn('SUM', fn('*', col('quantity'), col('price'))), 'totalRevenue']
      ],
      where: { productId: this.id },
      raw: true
    });

    return stats[0] || { orderCount: 0, totalQuantitySold: 0, totalRevenue: 0 };
  };

  /**
   * Class methods
   */

  /**
   * Find low stock products
   * Tests: Class method with filtering
   */
  Product.findLowStock = async function() {
    const { Op } = sequelize;

    return await this.findAll({
      where: {
        stockQuantity: {
          [Op.lte]: sequelize.col('lowStockThreshold')
        },
        status: 'active'
      },
      order: [['stockQuantity', 'ASC']]
    });
  };

  /**
   * Find out of stock products
   * Tests: Class method with filtering
   */
  Product.findOutOfStock = async function() {
    return await this.findAll({
      where: {
        stockQuantity: 0
      },
      order: [['updatedAt', 'DESC']]
    });
  };

  /**
   * Find products by category
   * Tests: Class method with filtering
   */
  Product.findByCategory = async function(category) {
    return await this.findAll({
      where: { category },
      order: [['name', 'ASC']]
    });
  };

  /**
   * Search products by name or description
   * Tests: Class method with text search
   */
  Product.search = async function(query) {
    const { Op } = sequelize;

    return await this.findAll({
      where: {
        [Op.or]: [
          { name: { [Op.iLike]: `%${query}%` } },
          { description: { [Op.iLike]: `%${query}%` } }
        ],
        status: 'active'
      },
      order: [['name', 'ASC']]
    });
  };

  /**
   * Get top selling products
   * Tests: Class method with ordering
   */
  Product.getTopSelling = async function(limit = 10) {
    return await this.findAll({
      where: { status: 'active' },
      order: [['soldCount', 'DESC']],
      limit
    });
  };

  /**
   * Get featured products
   * Tests: Class method with filtering
   */
  Product.getFeatured = async function() {
    return await this.findAll({
      where: {
        featured: true,
        status: 'active'
      },
      order: [['createdAt', 'DESC']]
    });
  };

  /**
   * Get inventory value
   * Tests: Class method with aggregation
   */
  Product.getInventoryValue = async function() {
    const { fn, col } = sequelize;

    const result = await this.findAll({
      attributes: [
        [fn('SUM', fn('*', col('stockQuantity'), col('cost'))), 'totalCost'],
        [fn('SUM', fn('*', col('stockQuantity'), col('price'))), 'totalRetailValue'],
        [fn('COUNT', col('id')), 'productCount'],
        [fn('SUM', col('stockQuantity')), 'totalUnits']
      ],
      where: {
        status: {
          [sequelize.Op.notIn]: ['discontinued']
        }
      },
      raw: true
    });

    return result[0];
  };

  return Product;
};
