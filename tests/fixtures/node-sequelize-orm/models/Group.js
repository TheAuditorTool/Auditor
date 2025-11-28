module.exports = (sequelize, DataTypes) => {
  const Group = sequelize.define(
    "Group",
    {
      id: {
        type: DataTypes.INTEGER,
        primaryKey: true,
        autoIncrement: true,
      },

      name: {
        type: DataTypes.STRING(100),
        allowNull: false,
        unique: {
          msg: "Group name must be unique",
        },
        validate: {
          notEmpty: {
            msg: "Group name cannot be empty",
          },
          len: {
            args: [3, 100],
            msg: "Group name must be between 3 and 100 characters",
          },
        },
      },

      slug: {
        type: DataTypes.STRING(100),
        allowNull: false,
        unique: {
          msg: "Group slug must be unique",
        },
        validate: {
          is: {
            args: /^[a-z0-9\-]+$/,
            msg: "Slug must contain only lowercase letters, numbers, and hyphens",
          },
        },
      },

      description: {
        type: DataTypes.TEXT,
        allowNull: true,
        validate: {
          len: {
            args: [0, 1000],
            msg: "Description must be less than 1000 characters",
          },
        },
      },

      type: {
        type: DataTypes.ENUM("public", "private", "invite_only"),
        defaultValue: "public",
        allowNull: false,
        validate: {
          isIn: {
            args: [["public", "private", "invite_only"]],
            msg: "Group type must be public, private, or invite_only",
          },
        },
      },

      category: {
        type: DataTypes.STRING(50),
        allowNull: true,
        validate: {
          isIn: {
            args: [["technology", "business", "education", "social", "other"]],
            msg: "Invalid category",
          },
        },
      },

      maxMembers: {
        type: DataTypes.INTEGER,
        allowNull: true,
        comment: "NULL = unlimited members",
        validate: {
          min: {
            args: [1],
            msg: "Max members must be at least 1",
          },
        },
      },

      isActive: {
        type: DataTypes.BOOLEAN,
        defaultValue: true,
        allowNull: false,
      },

      settings: {
        type: DataTypes.JSONB,
        defaultValue: {
          allowMemberPosts: true,
          moderationRequired: false,
          allowInvites: true,
        },
        allowNull: false,
        comment: "Group settings and permissions",
      },

      metadata: {
        type: DataTypes.JSONB,
        defaultValue: {},
        allowNull: false,
        comment: "Additional group metadata",
      },

      avatar: {
        type: DataTypes.STRING(500),
        allowNull: true,
        validate: {
          isUrl: {
            msg: "Avatar must be a valid URL",
          },
        },
      },

      banner: {
        type: DataTypes.STRING(500),
        allowNull: true,
        validate: {
          isUrl: {
            msg: "Banner must be a valid URL",
          },
        },
      },

      memberCount: {
        type: DataTypes.INTEGER,
        defaultValue: 0,
        allowNull: false,
      },

      postCount: {
        type: DataTypes.INTEGER,
        defaultValue: 0,
        allowNull: false,
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
      tableName: "groups",
      timestamps: true,

      hooks: {
        beforeCreate: async (group, options) => {
          if (!group.slug && group.name) {
            group.slug = group.name
              .toLowerCase()
              .replace(/[^a-z0-9\s-]/g, "")
              .replace(/\s+/g, "-")
              .replace(/-+/g, "-")
              .trim();

            const existingGroup = await sequelize.models.Group.findOne({
              where: { slug: group.slug },
            });

            if (existingGroup) {
              group.slug = `${group.slug}-${Date.now()}`;
            }
          }
        },

        afterCreate: async (group, options) => {
          console.log(`Group ${group.name} created with slug: ${group.slug}`);
        },

        beforeUpdate: async (group, options) => {
          if (group.changed("memberCount") && group.maxMembers) {
            if (group.memberCount > group.maxMembers) {
              throw new Error(
                `Group cannot exceed max members: ${group.maxMembers}`,
              );
            }
          }
        },
      },

      indexes: [
        {
          unique: true,
          fields: ["name"],
        },
        {
          unique: true,
          fields: ["slug"],
        },
        {
          fields: ["type"],
        },
        {
          fields: ["category"],
        },
        {
          fields: ["isActive"],
        },
        {
          fields: ["createdAt"],
        },
      ],
    },
  );

  Group.associate = function (models) {
    Group.belongsToMany(models.User, {
      through: models.UserGroup,
      foreignKey: "groupId",
      otherKey: "userId",
      as: "members",
      onDelete: "CASCADE",
    });
  };

  Group.prototype.addMember = async function (userId, role = "member") {
    const UserGroup = sequelize.models.UserGroup;

    const existing = await UserGroup.findOne({
      where: { groupId: this.id, userId },
    });

    if (existing) {
      throw new Error("User is already a member of this group");
    }

    if (this.maxMembers && this.memberCount >= this.maxMembers) {
      throw new Error(`Group has reached max members: ${this.maxMembers}`);
    }

    await UserGroup.create({
      groupId: this.id,
      userId,
      role,
    });

    this.memberCount += 1;
    await this.save();
  };

  Group.prototype.removeMember = async function (userId) {
    const UserGroup = sequelize.models.UserGroup;

    const deleted = await UserGroup.destroy({
      where: { groupId: this.id, userId },
    });

    if (deleted > 0) {
      this.memberCount = Math.max(0, this.memberCount - 1);
      await this.save();
    }

    return deleted > 0;
  };

  Group.prototype.hasMember = async function (userId) {
    const UserGroup = sequelize.models.UserGroup;

    const membership = await UserGroup.findOne({
      where: { groupId: this.id, userId },
    });

    return !!membership;
  };

  Group.prototype.getMembers = async function (options = {}) {
    const User = sequelize.models.User;
    const UserGroup = sequelize.models.UserGroup;

    const whereClause = { groupId: this.id };

    if (options.role) {
      whereClause.role = options.role;
    }

    return await UserGroup.findAll({
      where: whereClause,
      include: [
        {
          model: User,
          as: "user",
          attributes: ["id", "username", "email", "firstName", "lastName"],
        },
      ],
      order: [["joinedAt", "DESC"]],
    });
  };

  Group.prototype.updateSettings = async function (newSettings) {
    this.settings = {
      ...this.settings,
      ...newSettings,
    };
    await this.save();
  };

  Group.prototype.isFull = function () {
    return this.maxMembers && this.memberCount >= this.maxMembers;
  };

  Group.prototype.canJoin = async function (userId) {
    if (!this.isActive) {
      return { allowed: false, reason: "Group is not active" };
    }

    if (this.isFull()) {
      return { allowed: false, reason: "Group is full" };
    }

    if (await this.hasMember(userId)) {
      return { allowed: false, reason: "Already a member" };
    }

    if (this.type === "invite_only") {
      return { allowed: false, reason: "Invite only" };
    }

    return { allowed: true };
  };

  Group.findPublicGroups = async function () {
    return await this.findAll({
      where: {
        type: "public",
        isActive: true,
      },
      order: [["memberCount", "DESC"]],
    });
  };

  Group.findByCategory = async function (category) {
    return await this.findAll({
      where: {
        category,
        isActive: true,
      },
      order: [["createdAt", "DESC"]],
    });
  };

  Group.search = async function (query) {
    const { Op } = sequelize;

    return await this.findAll({
      where: {
        [Op.or]: [
          { name: { [Op.iLike]: `%${query}%` } },
          { description: { [Op.iLike]: `%${query}%` } },
        ],
        isActive: true,
      },
      order: [["memberCount", "DESC"]],
    });
  };

  Group.getPopular = async function (limit = 10) {
    return await this.findAll({
      where: {
        isActive: true,
        type: "public",
      },
      order: [["memberCount", "DESC"]],
      limit,
    });
  };

  Group.getStatistics = async function () {
    const { fn, col } = sequelize;

    return await this.findAll({
      attributes: [
        "category",
        [fn("COUNT", col("id")), "groupCount"],
        [fn("SUM", col("memberCount")), "totalMembers"],
        [fn("AVG", col("memberCount")), "avgMembers"],
      ],
      where: { isActive: true },
      group: ["category"],
      raw: true,
    });
  };

  return Group;
};
