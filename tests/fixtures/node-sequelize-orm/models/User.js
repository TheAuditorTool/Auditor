const bcrypt = require("bcrypt");

module.exports = (sequelize, DataTypes) => {
  const User = sequelize.define(
    "User",
    {
      id: {
        type: DataTypes.INTEGER,
        primaryKey: true,
        autoIncrement: true,
      },

      username: {
        type: DataTypes.STRING(100),
        allowNull: false,
        unique: {
          msg: "Username must be unique",
        },
        validate: {
          notEmpty: {
            msg: "Username cannot be empty",
          },
          len: {
            args: [3, 100],
            msg: "Username must be between 3 and 100 characters",
          },
          isAlphanumeric: {
            msg: "Username must contain only letters and numbers",
          },
        },
      },

      email: {
        type: DataTypes.STRING(200),
        allowNull: false,
        unique: {
          msg: "Email must be unique",
        },
        validate: {
          isEmail: {
            msg: "Must be a valid email address",
          },
          notEmpty: true,
        },
      },

      password: {
        type: DataTypes.STRING(255),
        allowNull: false,
        validate: {
          notEmpty: true,
          len: {
            args: [8, 255],
            msg: "Password must be at least 8 characters",
          },
        },
      },

      status: {
        type: DataTypes.ENUM("active", "inactive", "suspended", "deleted"),
        defaultValue: "active",
        allowNull: false,
      },

      lastLoginAt: {
        type: DataTypes.DATE,
        allowNull: true,
      },

      loginCount: {
        type: DataTypes.INTEGER,
        defaultValue: 0,
        allowNull: false,
      },

      fullName: {
        type: DataTypes.VIRTUAL,
        get() {
          return `${this.firstName || ""} ${this.lastName || ""}`.trim();
        },
      },

      firstName: {
        type: DataTypes.STRING(100),
        allowNull: true,
      },

      lastName: {
        type: DataTypes.STRING(100),
        allowNull: true,
      },

      createdAt: {
        type: DataTypes.DATE,
        allowNull: false,
        defaultValue: DataTypes.NOW,
      },

      updatedAt: {
        type: DataTypes.DATE,
        allowNull: false,
        defaultValue: DataTypes.NOW,
      },
    },
    {
      tableName: "users",
      timestamps: true,
      underscored: false,

      hooks: {
        beforeCreate: async (user, options) => {
          if (user.password) {
            user.password = await bcrypt.hash(user.password, 10);
          }
        },

        beforeUpdate: async (user, options) => {
          if (user.changed("password")) {
            user.password = await bcrypt.hash(user.password, 10);
          }
        },

        afterCreate: async (user, options) => {
          console.log(`User ${user.username} created`);
        },

        beforeDestroy: async (user, options) => {
          console.log(`User ${user.username} about to be deleted`);
        },
      },

      indexes: [
        {
          unique: true,
          fields: ["email"],
        },
        {
          unique: true,
          fields: ["username"],
        },
        {
          fields: ["status"],
        },
        {
          fields: ["createdAt"],
        },
      ],
    },
  );

  User.associate = function (models) {
    User.hasMany(models.Order, {
      foreignKey: "userId",
      as: "orders",
      onDelete: "CASCADE",
      onUpdate: "CASCADE",
    });

    User.belongsTo(models.Role, {
      foreignKey: "roleId",
      as: "role",
      onDelete: "SET NULL",
      onUpdate: "CASCADE",
    });

    User.hasOne(models.Profile, {
      foreignKey: "userId",
      as: "profile",
      onDelete: "CASCADE",
      onUpdate: "CASCADE",
    });

    User.belongsToMany(models.Group, {
      through: models.UserGroup,
      foreignKey: "userId",
      otherKey: "groupId",
      as: "groups",
      onDelete: "CASCADE",
    });

    User.hasMany(models.Session, {
      foreignKey: "userId",
      as: "sessions",
      onDelete: "CASCADE",
    });
  };

  User.prototype.comparePassword = async function (candidatePassword) {
    return await bcrypt.compare(candidatePassword, this.password);
  };

  User.prototype.recordLogin = async function () {
    this.lastLoginAt = new Date();
    this.loginCount += 1;
    await this.save();
  };

  User.prototype.isActive = function () {
    return this.status === "active";
  };

  User.prototype.getOrdersWithProducts = async function () {
    const Order = sequelize.models.Order;
    const Product = sequelize.models.Product;

    return await Order.findAll({
      where: { userId: this.id },
      include: [
        {
          model: Product,
          as: "products",
          through: { attributes: ["quantity", "price"] },
        },
      ],
      order: [["createdAt", "DESC"]],
    });
  };

  User.findByEmail = async function (email) {
    return await this.findOne({
      where: { email },
      include: [
        { model: sequelize.models.Role, as: "role" },
        { model: sequelize.models.Profile, as: "profile" },
      ],
    });
  };

  User.findActiveUsers = async function () {
    return await this.findAll({
      where: { status: "active" },
      include: [{ model: sequelize.models.Role, as: "role" }],
      order: [["createdAt", "DESC"]],
    });
  };

  User.getUsersWithOrderStats = async function () {
    const { fn, col } = sequelize;

    return await this.findAll({
      attributes: [
        "id",
        "username",
        "email",
        [fn("COUNT", col("orders.id")), "orderCount"],
        [fn("SUM", col("orders.total")), "totalSpent"],
      ],
      include: [
        {
          model: sequelize.models.Order,
          as: "orders",
          attributes: [],
        },
      ],
      group: ["User.id"],
      raw: true,
    });
  };

  return User;
};
