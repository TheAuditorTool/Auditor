/**
 * UserGroup junction table
 * Tests: Many-to-many relationship junction table with role-based access
 */

module.exports = (sequelize, DataTypes) => {
  const UserGroup = sequelize.define('UserGroup', {
    id: {
      type: DataTypes.INTEGER,
      primaryKey: true,
      autoIncrement: true
    },

    userId: {
      type: DataTypes.INTEGER,
      allowNull: false,
      references: {
        model: 'users',
        key: 'id'
      },
      onDelete: 'CASCADE',
      onUpdate: 'CASCADE'
    },

    groupId: {
      type: DataTypes.INTEGER,
      allowNull: false,
      references: {
        model: 'groups',
        key: 'id'
      },
      onDelete: 'CASCADE',
      onUpdate: 'CASCADE'
    },

    role: {
      type: DataTypes.ENUM('owner', 'admin', 'moderator', 'member', 'guest'),
      defaultValue: 'member',
      allowNull: false,
      validate: {
        isIn: {
          args: [['owner', 'admin', 'moderator', 'member', 'guest']],
          msg: 'Invalid role'
        }
      }
    },

    status: {
      type: DataTypes.ENUM('active', 'invited', 'pending', 'banned'),
      defaultValue: 'active',
      allowNull: false
    },

    joinedAt: {
      type: DataTypes.DATE,
      allowNull: false,
      defaultValue: DataTypes.NOW
    },

    invitedBy: {
      type: DataTypes.INTEGER,
      allowNull: true,
      references: {
        model: 'users',
        key: 'id'
      },
      comment: 'User ID who invited this member'
    },

    invitedAt: {
      type: DataTypes.DATE,
      allowNull: true
    },

    lastActivityAt: {
      type: DataTypes.DATE,
      allowNull: true,
      defaultValue: DataTypes.NOW
    },

    permissions: {
      type: DataTypes.JSONB,
      defaultValue: {},
      allowNull: false,
      comment: 'Additional user-specific permissions in this group'
    },

    metadata: {
      type: DataTypes.JSONB,
      defaultValue: {},
      allowNull: false,
      comment: 'Additional membership metadata'
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
    tableName: 'user_groups',
    timestamps: true,

    // Hooks
    hooks: {
      /**
       * beforeCreate hook - Set joinedAt timestamp
       * Tests: Hook with timestamp initialization
       */
      beforeCreate: async (userGroup, options) => {
        if (userGroup.status === 'active' && !userGroup.joinedAt) {
          userGroup.joinedAt = new Date();
        }

        if (userGroup.status === 'invited' && !userGroup.invitedAt) {
          userGroup.invitedAt = new Date();
        }
      },

      /**
       * afterCreate hook - Increment group member count
       * Tests: Hook with cascading updates
       */
      afterCreate: async (userGroup, options) => {
        if (userGroup.status === 'active') {
          const Group = sequelize.models.Group;
          const group = await Group.findByPk(userGroup.groupId);

          if (group) {
            group.memberCount += 1;
            await group.save();
          }

          console.log(`User ${userGroup.userId} joined group ${userGroup.groupId} as ${userGroup.role}`);
        }
      },

      /**
       * afterDestroy hook - Decrement group member count
       * Tests: Hook with cleanup
       */
      afterDestroy: async (userGroup, options) => {
        if (userGroup.status === 'active') {
          const Group = sequelize.models.Group;
          const group = await Group.findByPk(userGroup.groupId);

          if (group) {
            group.memberCount = Math.max(0, group.memberCount - 1);
            await group.save();
          }

          console.log(`User ${userGroup.userId} left group ${userGroup.groupId}`);
        }
      },

      /**
       * beforeUpdate hook - Handle status transitions
       * Tests: Hook with state transitions
       */
      beforeUpdate: async (userGroup, options) => {
        if (userGroup.changed('status')) {
          const oldStatus = userGroup._previousDataValues.status;
          const newStatus = userGroup.status;

          // If transitioning from invited/pending to active
          if ((oldStatus === 'invited' || oldStatus === 'pending') && newStatus === 'active') {
            if (!userGroup.joinedAt) {
              userGroup.joinedAt = new Date();
            }

            // Increment group member count
            const Group = sequelize.models.Group;
            const group = await Group.findByPk(userGroup.groupId);
            if (group) {
              group.memberCount += 1;
              await group.save();
            }
          }

          // If transitioning from active to banned/inactive
          if (oldStatus === 'active' && (newStatus === 'banned' || newStatus === 'pending')) {
            // Decrement group member count
            const Group = sequelize.models.Group;
            const group = await Group.findByPk(userGroup.groupId);
            if (group) {
              group.memberCount = Math.max(0, group.memberCount - 1);
              await group.save();
            }
          }
        }
      }
    },

    // Indexes
    indexes: [
      {
        unique: true,
        fields: ['userId', 'groupId']
      },
      {
        fields: ['userId']
      },
      {
        fields: ['groupId']
      },
      {
        fields: ['role']
      },
      {
        fields: ['status']
      },
      {
        fields: ['joinedAt']
      }
    ]
  });

  /**
   * Associations
   * Tests: Junction table associations
   */
  UserGroup.associate = function(models) {
    UserGroup.belongsTo(models.User, {
      foreignKey: 'userId',
      as: 'user'
    });

    UserGroup.belongsTo(models.Group, {
      foreignKey: 'groupId',
      as: 'group'
    });

    UserGroup.belongsTo(models.User, {
      foreignKey: 'invitedBy',
      as: 'inviter'
    });
  };

  /**
   * Instance methods
   */

  /**
   * Accept invitation
   * Tests: Instance method with status transition
   */
  UserGroup.prototype.acceptInvitation = async function() {
    if (this.status !== 'invited') {
      throw new Error('Can only accept invitations');
    }

    this.status = 'active';
    this.joinedAt = new Date();
    await this.save();
  };

  /**
   * Promote member to role
   * Tests: Instance method with role management
   */
  UserGroup.prototype.promoteToRole = async function(newRole) {
    const validRoles = ['owner', 'admin', 'moderator', 'member', 'guest'];

    if (!validRoles.includes(newRole)) {
      throw new Error('Invalid role');
    }

    const roleHierarchy = { owner: 5, admin: 4, moderator: 3, member: 2, guest: 1 };
    const currentLevel = roleHierarchy[this.role];
    const newLevel = roleHierarchy[newRole];

    if (newLevel <= currentLevel) {
      throw new Error('Can only promote to higher role');
    }

    this.role = newRole;
    await this.save();
  };

  /**
   * Demote member to role
   * Tests: Instance method with role management
   */
  UserGroup.prototype.demoteToRole = async function(newRole) {
    const validRoles = ['owner', 'admin', 'moderator', 'member', 'guest'];

    if (!validRoles.includes(newRole)) {
      throw new Error('Invalid role');
    }

    const roleHierarchy = { owner: 5, admin: 4, moderator: 3, member: 2, guest: 1 };
    const currentLevel = roleHierarchy[this.role];
    const newLevel = roleHierarchy[newRole];

    if (newLevel >= currentLevel) {
      throw new Error('Can only demote to lower role');
    }

    this.role = newRole;
    await this.save();
  };

  /**
   * Ban member
   * Tests: Instance method with status change
   */
  UserGroup.prototype.ban = async function() {
    this.status = 'banned';
    await this.save();
  };

  /**
   * Unban member
   * Tests: Instance method with status change
   */
  UserGroup.prototype.unban = async function() {
    if (this.status !== 'banned') {
      throw new Error('User is not banned');
    }

    this.status = 'active';
    await this.save();
  };

  /**
   * Update last activity
   * Tests: Instance method with timestamp update
   */
  UserGroup.prototype.updateActivity = async function() {
    this.lastActivityAt = new Date();
    await this.save();
  };

  /**
   * Check if has permission
   * Tests: Instance method with permission checking
   */
  UserGroup.prototype.hasPermission = function(permission) {
    const rolePermissions = {
      owner: ['all'],
      admin: ['manage_members', 'manage_posts', 'manage_settings', 'moderate'],
      moderator: ['manage_posts', 'moderate'],
      member: ['create_post', 'comment'],
      guest: ['view']
    };

    const permissions = rolePermissions[this.role] || [];

    if (permissions.includes('all')) {
      return true;
    }

    return permissions.includes(permission) || (this.permissions && this.permissions[permission]);
  };

  /**
   * Class methods
   */

  /**
   * Find by user and group
   * Tests: Class method with composite query
   */
  UserGroup.findMembership = async function(userId, groupId) {
    return await this.findOne({
      where: { userId, groupId }
    });
  };

  /**
   * Find user's groups
   * Tests: Class method with filtering
   */
  UserGroup.findUserGroups = async function(userId, options = {}) {
    const where = { userId };

    if (options.status) {
      where.status = options.status;
    }

    return await this.findAll({
      where,
      include: [{
        model: sequelize.models.Group,
        as: 'group'
      }],
      order: [['joinedAt', 'DESC']]
    });
  };

  /**
   * Find group members
   * Tests: Class method with filtering
   */
  UserGroup.findGroupMembers = async function(groupId, options = {}) {
    const where = { groupId };

    if (options.role) {
      where.role = options.role;
    }

    if (options.status) {
      where.status = options.status;
    }

    return await this.findAll({
      where,
      include: [{
        model: sequelize.models.User,
        as: 'user',
        attributes: ['id', 'username', 'email', 'firstName', 'lastName']
      }],
      order: [['joinedAt', 'DESC']]
    });
  };

  /**
   * Find pending invitations
   * Tests: Class method with filtering
   */
  UserGroup.findPendingInvitations = async function(userId) {
    return await this.findAll({
      where: {
        userId,
        status: 'invited'
      },
      include: [
        {
          model: sequelize.models.Group,
          as: 'group'
        },
        {
          model: sequelize.models.User,
          as: 'inviter',
          attributes: ['id', 'username']
        }
      ],
      order: [['invitedAt', 'DESC']]
    });
  };

  /**
   * Get group admins
   * Tests: Class method with role filtering
   */
  UserGroup.findGroupAdmins = async function(groupId) {
    const { Op } = sequelize;

    return await this.findAll({
      where: {
        groupId,
        role: {
          [Op.in]: ['owner', 'admin']
        },
        status: 'active'
      },
      include: [{
        model: sequelize.models.User,
        as: 'user',
        attributes: ['id', 'username', 'email']
      }]
    });
  };

  return UserGroup;
};
