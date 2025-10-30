/**
 * Group model
 * Tests: Many-to-many relationship (Group has many Users through UserGroups)
 */

module.exports = (sequelize, DataTypes) => {
  const Group = sequelize.define('Group', {
    id: {
      type: DataTypes.INTEGER,
      primaryKey: true,
      autoIncrement: true
    },

    name: {
      type: DataTypes.STRING(100),
      allowNull: false,
      unique: {
        msg: 'Group name must be unique'
      },
      validate: {
        notEmpty: {
          msg: 'Group name cannot be empty'
        },
        len: {
          args: [3, 100],
          msg: 'Group name must be between 3 and 100 characters'
        }
      }
    },

    slug: {
      type: DataTypes.STRING(100),
      allowNull: false,
      unique: {
        msg: 'Group slug must be unique'
      },
      validate: {
        is: {
          args: /^[a-z0-9\-]+$/,
          msg: 'Slug must contain only lowercase letters, numbers, and hyphens'
        }
      }
    },

    description: {
      type: DataTypes.TEXT,
      allowNull: true,
      validate: {
        len: {
          args: [0, 1000],
          msg: 'Description must be less than 1000 characters'
        }
      }
    },

    type: {
      type: DataTypes.ENUM('public', 'private', 'invite_only'),
      defaultValue: 'public',
      allowNull: false,
      validate: {
        isIn: {
          args: [['public', 'private', 'invite_only']],
          msg: 'Group type must be public, private, or invite_only'
        }
      }
    },

    category: {
      type: DataTypes.STRING(50),
      allowNull: true,
      validate: {
        isIn: {
          args: [['technology', 'business', 'education', 'social', 'other']],
          msg: 'Invalid category'
        }
      }
    },

    maxMembers: {
      type: DataTypes.INTEGER,
      allowNull: true,
      comment: 'NULL = unlimited members',
      validate: {
        min: {
          args: [1],
          msg: 'Max members must be at least 1'
        }
      }
    },

    isActive: {
      type: DataTypes.BOOLEAN,
      defaultValue: true,
      allowNull: false
    },

    settings: {
      type: DataTypes.JSONB,
      defaultValue: {
        allowMemberPosts: true,
        moderationRequired: false,
        allowInvites: true
      },
      allowNull: false,
      comment: 'Group settings and permissions'
    },

    metadata: {
      type: DataTypes.JSONB,
      defaultValue: {},
      allowNull: false,
      comment: 'Additional group metadata'
    },

    avatar: {
      type: DataTypes.STRING(500),
      allowNull: true,
      validate: {
        isUrl: {
          msg: 'Avatar must be a valid URL'
        }
      }
    },

    banner: {
      type: DataTypes.STRING(500),
      allowNull: true,
      validate: {
        isUrl: {
          msg: 'Banner must be a valid URL'
        }
      }
    },

    // Stats
    memberCount: {
      type: DataTypes.INTEGER,
      defaultValue: 0,
      allowNull: false
    },

    postCount: {
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
    tableName: 'groups',
    timestamps: true,

    // Hooks
    hooks: {
      /**
       * beforeCreate hook - Generate slug from name
       * Tests: Hook with data transformation
       */
      beforeCreate: async (group, options) => {
        if (!group.slug && group.name) {
          // Generate slug from name
          group.slug = group.name
            .toLowerCase()
            .replace(/[^a-z0-9\s-]/g, '')
            .replace(/\s+/g, '-')
            .replace(/-+/g, '-')
            .trim();

          // Ensure uniqueness by appending number if needed
          const existingGroup = await sequelize.models.Group.findOne({
            where: { slug: group.slug }
          });

          if (existingGroup) {
            group.slug = `${group.slug}-${Date.now()}`;
          }
        }
      },

      /**
       * afterCreate hook - Initialize default settings
       * Tests: Hook with initialization
       */
      afterCreate: async (group, options) => {
        console.log(`Group ${group.name} created with slug: ${group.slug}`);
      },

      /**
       * beforeUpdate hook - Validate member count against max
       * Tests: Hook with validation
       */
      beforeUpdate: async (group, options) => {
        if (group.changed('memberCount') && group.maxMembers) {
          if (group.memberCount > group.maxMembers) {
            throw new Error(`Group cannot exceed max members: ${group.maxMembers}`);
          }
        }
      }
    },

    // Indexes
    indexes: [
      {
        unique: true,
        fields: ['name']
      },
      {
        unique: true,
        fields: ['slug']
      },
      {
        fields: ['type']
      },
      {
        fields: ['category']
      },
      {
        fields: ['isActive']
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
  Group.associate = function(models) {
    // Many-to-many: Group has many Users through UserGroups
    Group.belongsToMany(models.User, {
      through: models.UserGroup,
      foreignKey: 'groupId',
      otherKey: 'userId',
      as: 'members',
      onDelete: 'CASCADE'
    });
  };

  /**
   * Instance methods
   */

  /**
   * Add member to group
   * Tests: Instance method with many-to-many relationship
   */
  Group.prototype.addMember = async function(userId, role = 'member') {
    const UserGroup = sequelize.models.UserGroup;

    // Check if already a member
    const existing = await UserGroup.findOne({
      where: { groupId: this.id, userId }
    });

    if (existing) {
      throw new Error('User is already a member of this group');
    }

    // Check max members limit
    if (this.maxMembers && this.memberCount >= this.maxMembers) {
      throw new Error(`Group has reached max members: ${this.maxMembers}`);
    }

    // Add member
    await UserGroup.create({
      groupId: this.id,
      userId,
      role
    });

    // Update member count
    this.memberCount += 1;
    await this.save();
  };

  /**
   * Remove member from group
   * Tests: Instance method with many-to-many relationship
   */
  Group.prototype.removeMember = async function(userId) {
    const UserGroup = sequelize.models.UserGroup;

    const deleted = await UserGroup.destroy({
      where: { groupId: this.id, userId }
    });

    if (deleted > 0) {
      this.memberCount = Math.max(0, this.memberCount - 1);
      await this.save();
    }

    return deleted > 0;
  };

  /**
   * Check if user is member
   * Tests: Instance method with relationship query
   */
  Group.prototype.hasMember = async function(userId) {
    const UserGroup = sequelize.models.UserGroup;

    const membership = await UserGroup.findOne({
      where: { groupId: this.id, userId }
    });

    return !!membership;
  };

  /**
   * Get all members with details
   * Tests: Instance method with complex query
   */
  Group.prototype.getMembers = async function(options = {}) {
    const User = sequelize.models.User;
    const UserGroup = sequelize.models.UserGroup;

    const whereClause = { groupId: this.id };

    if (options.role) {
      whereClause.role = options.role;
    }

    return await UserGroup.findAll({
      where: whereClause,
      include: [{
        model: User,
        as: 'user',
        attributes: ['id', 'username', 'email', 'firstName', 'lastName']
      }],
      order: [['joinedAt', 'DESC']]
    });
  };

  /**
   * Update settings
   * Tests: Instance method with JSON field update
   */
  Group.prototype.updateSettings = async function(newSettings) {
    this.settings = {
      ...this.settings,
      ...newSettings
    };
    await this.save();
  };

  /**
   * Check if group is full
   * Tests: Instance method with business logic
   */
  Group.prototype.isFull = function() {
    return this.maxMembers && this.memberCount >= this.maxMembers;
  };

  /**
   * Check if user can join
   * Tests: Instance method with complex validation
   */
  Group.prototype.canJoin = async function(userId) {
    if (!this.isActive) {
      return { allowed: false, reason: 'Group is not active' };
    }

    if (this.isFull()) {
      return { allowed: false, reason: 'Group is full' };
    }

    if (await this.hasMember(userId)) {
      return { allowed: false, reason: 'Already a member' };
    }

    if (this.type === 'invite_only') {
      return { allowed: false, reason: 'Invite only' };
    }

    return { allowed: true };
  };

  /**
   * Class methods
   */

  /**
   * Find public groups
   * Tests: Class method with filtering
   */
  Group.findPublicGroups = async function() {
    return await this.findAll({
      where: {
        type: 'public',
        isActive: true
      },
      order: [['memberCount', 'DESC']]
    });
  };

  /**
   * Find groups by category
   * Tests: Class method with filtering
   */
  Group.findByCategory = async function(category) {
    return await this.findAll({
      where: {
        category,
        isActive: true
      },
      order: [['createdAt', 'DESC']]
    });
  };

  /**
   * Search groups by name or description
   * Tests: Class method with text search
   */
  Group.search = async function(query) {
    const { Op } = sequelize;

    return await this.findAll({
      where: {
        [Op.or]: [
          { name: { [Op.iLike]: `%${query}%` } },
          { description: { [Op.iLike]: `%${query}%` } }
        ],
        isActive: true
      },
      order: [['memberCount', 'DESC']]
    });
  };

  /**
   * Get popular groups
   * Tests: Class method with ordering
   */
  Group.getPopular = async function(limit = 10) {
    return await this.findAll({
      where: {
        isActive: true,
        type: 'public'
      },
      order: [['memberCount', 'DESC']],
      limit
    });
  };

  /**
   * Get group statistics
   * Tests: Class method with aggregation
   */
  Group.getStatistics = async function() {
    const { fn, col } = sequelize;

    return await this.findAll({
      attributes: [
        'category',
        [fn('COUNT', col('id')), 'groupCount'],
        [fn('SUM', col('memberCount')), 'totalMembers'],
        [fn('AVG', col('memberCount')), 'avgMembers']
      ],
      where: { isActive: true },
      group: ['category'],
      raw: true
    });
  };

  return Group;
};
