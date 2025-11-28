const { Model, DataTypes, Op } = require("sequelize");
const sequelize = require("../database");

class Product extends Model {
  async calculateDiscountedPrice(customerId) {
    const customer = await this.sequelize.models.Customer.findByPk(customerId, {
      include: [
        {
          model: this.sequelize.models.CustomerGroup,
          as: "groups",
          through: {
            attributes: ["joined_at", "status"],
          },
        },
      ],
    });

    const baseDiscount = customer?.groups?.[0]?.discount || 0;
    const seasonalDiscount = await this.getSeasonalDiscount();
    return this.price * (1 - Math.max(baseDiscount, seasonalDiscount));
  }

  get profitMargin() {
    if (!this.cost || !this.price) return null;
    return (((this.price - this.cost) / this.price) * 100).toFixed(2);
  }

  static validateSKU(value) {
    if (!/^[A-Z]{3}-\d{6}$/.test(value)) {
      throw new Error("SKU must match pattern XXX-000000");
    }
  }
}

Product.init(
  {
    id: {
      type: DataTypes.UUID,
      defaultValue: DataTypes.UUIDV4,
      primaryKey: true,
    },
    sku: {
      type: DataTypes.STRING(10),
      unique: true,
      allowNull: false,
      validate: {
        isValidSKU(value) {
          Product.validateSKU(value);
        },
      },
    },
    name: {
      type: DataTypes.STRING,
      allowNull: false,
      set(value) {
        this.setDataValue("name", value.trim().replace(/\s+/g, " "));
      },
    },
    description: {
      type: DataTypes.TEXT,
      allowNull: true,
    },
    price: {
      type: DataTypes.DECIMAL(10, 2),
      allowNull: false,
      validate: {
        min: 0,
      },
    },
    cost: {
      type: DataTypes.DECIMAL(10, 2),
      allowNull: false,
      validate: {
        min: 0,
        isLessThanPrice(value) {
          if (value >= this.price) {
            throw new Error("Cost must be less than price");
          }
        },
      },
    },
    status: {
      type: DataTypes.ENUM("active", "discontinued", "out_of_stock"),
      defaultValue: "active",
    },
    metadata: {
      type: DataTypes.JSONB,
      defaultValue: {},
    },
    tags: {
      type: DataTypes.ARRAY(DataTypes.STRING),
      defaultValue: [],
    },
    profitMargin: {
      type: DataTypes.VIRTUAL,
      get() {
        return this.getDataValue("profitMargin");
      },
    },
  },
  {
    sequelize,
    modelName: "Product",
    tableName: "products",
    timestamps: true,
    paranoid: true,
    indexes: [
      {
        unique: true,
        fields: ["sku"],
      },
      {
        fields: ["status", "price"],
        name: "status_price_idx",
      },
      {
        type: "FULLTEXT",
        fields: ["name", "description"],
      },
    ],
    hooks: {
      beforeCreate: async (product, options) => {
        if (options.transaction) {
          const existingCount = await Product.count({
            where: { status: "active" },
            transaction: options.transaction,
          });
          if (existingCount >= 10000) {
            throw new Error("Maximum active products reached");
          }
        }
      },
      afterUpdate: async (product, options) => {
        await sequelize.models.AuditLog.create(
          {
            model: "Product",
            recordId: product.id,
            changes: product.changed(),
            userId: options.userId,
          },
          { transaction: options.transaction },
        );
      },
    },
    scopes: {
      active: {
        where: { status: "active" },
      },
      expensive: {
        where: {
          price: {
            [Op.gte]: 100,
          },
        },
      },
      withInventory: {
        include: [
          {
            model: sequelize.models.Inventory,
            as: "inventory",
            required: true,
            where: {
              quantity: {
                [Op.gt]: 0,
              },
            },
          },
        ],
      },
    },
  },
);

Product.belongsTo(require("./category"), {
  foreignKey: "categoryId",
  as: "category",
});

Product.belongsTo(require("./brand"), {
  foreignKey: "brandId",
  as: "brand",
});

Product.hasMany(require("./inventory"), {
  foreignKey: "productId",
  as: "inventory",
  onDelete: "CASCADE",
  hooks: true,
});

Product.belongsToMany(require("./warehouse"), {
  through: {
    model: "ProductWarehouses",
    unique: false,
    attributes: ["quantity", "location", "last_restocked"],
  },
  foreignKey: "productId",
  otherKey: "warehouseId",
  as: "warehouses",
});

Product.hasMany(require("./review"), {
  foreignKey: "reviewableId",
  constraints: false,
  scope: {
    reviewableType: "Product",
  },
  as: "reviews",
});

Product.belongsToMany(require("./image"), {
  through: {
    model: "Imageables",
    unique: false,
    scope: {
      imageableType: "Product",
    },
  },
  foreignKey: "imageableId",
  otherKey: "imageId",
  constraints: false,
  as: "images",
});

Product.belongsToMany(Product, {
  through: "RelatedProducts",
  as: "relatedProducts",
  foreignKey: "productId",
  otherKey: "relatedProductId",
});

Product.findActiveWithInventory = async function (options = {}) {
  return this.scope(["active", "withInventory"]).findAll({
    include: [
      {
        model: sequelize.models.Category,
        as: "category",
        attributes: ["id", "name", "slug"],
      },
      {
        model: sequelize.models.Brand,
        as: "brand",
        attributes: ["id", "name", "logo"],
      },
      {
        model: sequelize.models.Review,
        as: "reviews",
        attributes: ["rating", "comment"],
        include: [
          {
            model: sequelize.models.User,
            as: "user",
            attributes: ["username", "avatar"],
          },
        ],
      },
    ],
    ...options,
  });
};

Product.bulkUpdatePrices = async function (updates, userId) {
  const t = await sequelize.transaction();

  try {
    for (const update of updates) {
      await Product.update(
        { price: update.price },
        {
          where: { id: update.id },
          transaction: t,
          userId,
        },
      );
    }

    await t.commit();
    return { success: true };
  } catch (error) {
    await t.rollback();
    throw error;
  }
};

module.exports = Product;
