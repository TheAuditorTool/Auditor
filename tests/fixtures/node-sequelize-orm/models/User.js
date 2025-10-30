/**
 * User model with comprehensive Sequelize patterns
 *
 * Tests:
 * - Model definition with validations
 * - Hooks (beforeCreate, beforeUpdate, afterCreate)
 * - Relationships (hasMany, belongsTo, hasOne, belongsToMany)
 * - Cascade delete behavior
 * - Virtual fields and getters/setters
 * - Instance and class methods
 */

const bcrypt = require('bcrypt');

module.exports = (sequelize, DataTypes) => {
  const User = sequelize.define('User', {
    id: {
      type: DataTypes.INTEGER,
      primaryKey: true,
      autoIncrement: true
    },

    // Basic fields with validations
    username: {
      type: DataTypes.STRING(100),
      allowNull: false,
      unique: {
        msg: 'Username must be unique'
      },
      validate: {
        notEmpty: {
          msg: 'Username cannot be empty'
        },
        len: {
          args: [3, 100],
          msg: 'Username must be between 3 and 100 characters'
        },
        isAlphanumeric: {
          msg: 'Username must contain only letters and numbers'
        }
      }
    },

    email: {
      type: DataTypes.STRING(200),
      allowNull: false,
      unique: {
        msg: 'Email must be unique'
      },
      validate: {
        isEmail: {
          msg: 'Must be a valid email address'
        },
        notEmpty: true
      }
    },

    password: {
      type: DataTypes.STRING(255),
      allowNull: false,
      validate: {
        notEmpty: true,
        len: {
          args: [8, 255],
          msg: 'Password must be at least 8 characters'
        }
      }
    },

    // Status and metadata
    status: {
      type: DataTypes.ENUM('active', 'inactive', 'suspended', 'deleted'),
      defaultValue: 'active',
      allowNull: false
    },

    lastLoginAt: {
      type: DataTypes.DATE,
      allowNull: true
    },

    loginCount: {
      type: DataTypes.INTEGER,
      defaultValue: 0,
      allowNull: false
    },

    // Virtual field (not stored in database)
    fullName: {
      type: DataTypes.VIRTUAL,
      get() {
        return `${this.firstName || ''} ${this.lastName || ''}`.trim();
      }
    },

    firstName: {
      type: DataTypes.STRING(100),
      allowNull: true
    },

    lastName: {
      type: DataTypes.STRING(100),
      allowNull: true
    },

    // Timestamps
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
    tableName: 'users',
    timestamps: true,
    underscored: false,

    // Hooks (lifecycle callbacks)
    hooks: {
      /**
       * beforeCreate hook - Hash password before creating user
       * Tests: Hook extraction and taint flow (password -> bcrypt.hash)
       */
      beforeCreate: async (user, options) => {
        if (user.password) {
          // TAINT FLOW: user.password (plain text) -> bcrypt.hash -> user.password (hashed)
          user.password = await bcrypt.hash(user.password, 10);
        }
      },

      /**
       * beforeUpdate hook - Hash password if changed
       * Tests: Conditional hook execution
       */
      beforeUpdate: async (user, options) => {
        if (user.changed('password')) {
          user.password = await bcrypt.hash(user.password, 10);
        }
      },

      /**
       * afterCreate hook - Initialize related records
       * Tests: Hook with side effects
       */
      afterCreate: async (user, options) => {
        // Could initialize user profile, send welcome email, etc.
        console.log(`User ${user.username} created`);
      },

      /**
       * beforeDestroy hook - Cleanup before deletion
       * Tests: Cascade cleanup in hooks
       */
      beforeDestroy: async (user, options) => {
        // Could log deletion, archive data, etc.
        console.log(`User ${user.username} about to be deleted`);
      }
    },

    // Indexes
    indexes: [
      {
        unique: true,
        fields: ['email']
      },
      {
        unique: true,
        fields: ['username']
      },
      {
        fields: ['status']
      },
      {
        fields: ['createdAt']
      }
    ]
  });

  /**
   * Associations
   * Tests: All relationship types (hasMany, belongsTo, hasOne, belongsToMany)
   */
  User.associate = function(models) {
    // One-to-many: User has many Orders
    // Tests: orm_relationships with cascade delete
    User.hasMany(models.Order, {
      foreignKey: 'userId',
      as: 'orders',
      onDelete: 'CASCADE',
      onUpdate: 'CASCADE'
    });

    // Many-to-one: User belongs to Role
    // Tests: orm_relationships without cascade
    User.belongsTo(models.Role, {
      foreignKey: 'roleId',
      as: 'role',
      onDelete: 'SET NULL',
      onUpdate: 'CASCADE'
    });

    // One-to-one: User has one Profile
    // Tests: orm_relationships with cascade delete
    User.hasOne(models.Profile, {
      foreignKey: 'userId',
      as: 'profile',
      onDelete: 'CASCADE',
      onUpdate: 'CASCADE'
    });

    // Many-to-many: User has many Groups through UserGroups
    // Tests: orm_relationships with junction table
    User.belongsToMany(models.Group, {
      through: models.UserGroup,
      foreignKey: 'userId',
      otherKey: 'groupId',
      as: 'groups',
      onDelete: 'CASCADE'
    });

    // One-to-many: User has many Sessions
    // Tests: orm_relationships for session management
    User.hasMany(models.Session, {
      foreignKey: 'userId',
      as: 'sessions',
      onDelete: 'CASCADE'
    });
  };

  /**
   * Instance methods
   * Tests: Custom model methods
   */

  /**
   * Compare password with hash
   * Tests: Instance method with taint flow (password input -> bcrypt.compare)
   */
  User.prototype.comparePassword = async function(candidatePassword) {
    // TAINT FLOW: candidatePassword (user input) -> bcrypt.compare
    return await bcrypt.compare(candidatePassword, this.password);
  };

  /**
   * Update last login timestamp
   * Tests: Instance method with database update
   */
  User.prototype.recordLogin = async function() {
    this.lastLoginAt = new Date();
    this.loginCount += 1;
    await this.save();
  };

  /**
   * Check if user is active
   * Tests: Instance method with business logic
   */
  User.prototype.isActive = function() {
    return this.status === 'active';
  };

  /**
   * Get user's orders with products
   * Tests: Instance method with complex query
   */
  User.prototype.getOrdersWithProducts = async function() {
    const Order = sequelize.models.Order;
    const Product = sequelize.models.Product;

    return await Order.findAll({
      where: { userId: this.id },
      include: [{
        model: Product,
        as: 'products',
        through: { attributes: ['quantity', 'price'] }
      }],
      order: [['createdAt', 'DESC']]
    });
  };

  /**
   * Class methods
   * Tests: Static model methods
   */

  /**
   * Find user by email
   * Tests: Class method with query
   */
  User.findByEmail = async function(email) {
    return await this.findOne({
      where: { email },
      include: [
        { model: sequelize.models.Role, as: 'role' },
        { model: sequelize.models.Profile, as: 'profile' }
      ]
    });
  };

  /**
   * Find active users
   * Tests: Class method with filtering
   */
  User.findActiveUsers = async function() {
    return await this.findAll({
      where: { status: 'active' },
      include: [{ model: sequelize.models.Role, as: 'role' }],
      order: [['createdAt', 'DESC']]
    });
  };

  /**
   * Get users with order count
   * Tests: Class method with aggregation
   */
  User.getUsersWithOrderStats = async function() {
    const { fn, col } = sequelize;

    return await this.findAll({
      attributes: [
        'id',
        'username',
        'email',
        [fn('COUNT', col('orders.id')), 'orderCount'],
        [fn('SUM', col('orders.total')), 'totalSpent']
      ],
      include: [{
        model: sequelize.models.Order,
        as: 'orders',
        attributes: []
      }],
      group: ['User.id'],
      raw: true
    });
  };

  return User;
};
