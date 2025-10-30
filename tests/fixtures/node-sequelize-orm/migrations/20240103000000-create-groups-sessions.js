/**
 * Migration: Create groups, user_groups, and sessions tables
 * Tests: Many-to-many with junction table and session management
 */

'use strict';

module.exports = {
  async up(queryInterface, Sequelize) {
    // Create groups table
    await queryInterface.createTable('groups', {
      id: {
        type: Sequelize.INTEGER,
        primaryKey: true,
        autoIncrement: true
      },
      name: {
        type: Sequelize.STRING(100),
        allowNull: false,
        unique: true
      },
      slug: {
        type: Sequelize.STRING(100),
        allowNull: false,
        unique: true
      },
      description: {
        type: Sequelize.TEXT,
        allowNull: true
      },
      type: {
        type: Sequelize.ENUM('public', 'private', 'invite_only'),
        defaultValue: 'public',
        allowNull: false
      },
      category: {
        type: Sequelize.STRING(50),
        allowNull: true
      },
      maxMembers: {
        type: Sequelize.INTEGER,
        allowNull: true
      },
      isActive: {
        type: Sequelize.BOOLEAN,
        defaultValue: true,
        allowNull: false
      },
      settings: {
        type: Sequelize.JSONB,
        defaultValue: {},
        allowNull: false
      },
      metadata: {
        type: Sequelize.JSONB,
        defaultValue: {},
        allowNull: false
      },
      avatar: {
        type: Sequelize.STRING(500),
        allowNull: true
      },
      banner: {
        type: Sequelize.STRING(500),
        allowNull: true
      },
      memberCount: {
        type: Sequelize.INTEGER,
        defaultValue: 0,
        allowNull: false
      },
      postCount: {
        type: Sequelize.INTEGER,
        defaultValue: 0,
        allowNull: false
      },
      createdAt: {
        type: Sequelize.DATE,
        allowNull: false,
        defaultValue: Sequelize.literal('CURRENT_TIMESTAMP')
      },
      updatedAt: {
        type: Sequelize.DATE,
        allowNull: false,
        defaultValue: Sequelize.literal('CURRENT_TIMESTAMP')
      }
    });

    // Create user_groups junction table (many-to-many)
    await queryInterface.createTable('user_groups', {
      id: {
        type: Sequelize.INTEGER,
        primaryKey: true,
        autoIncrement: true
      },
      userId: {
        type: Sequelize.INTEGER,
        allowNull: false,
        references: {
          model: 'users',
          key: 'id'
        },
        onDelete: 'CASCADE',
        onUpdate: 'CASCADE'
      },
      groupId: {
        type: Sequelize.INTEGER,
        allowNull: false,
        references: {
          model: 'groups',
          key: 'id'
        },
        onDelete: 'CASCADE',
        onUpdate: 'CASCADE'
      },
      role: {
        type: Sequelize.ENUM('owner', 'admin', 'moderator', 'member', 'guest'),
        defaultValue: 'member',
        allowNull: false
      },
      status: {
        type: Sequelize.ENUM('active', 'invited', 'pending', 'banned'),
        defaultValue: 'active',
        allowNull: false
      },
      joinedAt: {
        type: Sequelize.DATE,
        allowNull: false,
        defaultValue: Sequelize.literal('CURRENT_TIMESTAMP')
      },
      invitedBy: {
        type: Sequelize.INTEGER,
        allowNull: true,
        references: {
          model: 'users',
          key: 'id'
        }
      },
      invitedAt: {
        type: Sequelize.DATE,
        allowNull: true
      },
      lastActivityAt: {
        type: Sequelize.DATE,
        allowNull: true,
        defaultValue: Sequelize.literal('CURRENT_TIMESTAMP')
      },
      permissions: {
        type: Sequelize.JSONB,
        defaultValue: {},
        allowNull: false
      },
      metadata: {
        type: Sequelize.JSONB,
        defaultValue: {},
        allowNull: false
      },
      createdAt: {
        type: Sequelize.DATE,
        allowNull: false,
        defaultValue: Sequelize.literal('CURRENT_TIMESTAMP')
      },
      updatedAt: {
        type: Sequelize.DATE,
        allowNull: false,
        defaultValue: Sequelize.literal('CURRENT_TIMESTAMP')
      }
    });

    // Create sessions table
    await queryInterface.createTable('sessions', {
      id: {
        type: Sequelize.INTEGER,
        primaryKey: true,
        autoIncrement: true
      },
      userId: {
        type: Sequelize.INTEGER,
        allowNull: false,
        references: {
          model: 'users',
          key: 'id'
        },
        onDelete: 'CASCADE',
        onUpdate: 'CASCADE'
      },
      token: {
        type: Sequelize.STRING(255),
        allowNull: false,
        unique: true
      },
      refreshToken: {
        type: Sequelize.STRING(255),
        allowNull: true,
        unique: true
      },
      ipAddress: {
        type: Sequelize.STRING(45),
        allowNull: true
      },
      userAgent: {
        type: Sequelize.TEXT,
        allowNull: true
      },
      device: {
        type: Sequelize.STRING(100),
        allowNull: true
      },
      platform: {
        type: Sequelize.STRING(100),
        allowNull: true
      },
      browser: {
        type: Sequelize.STRING(100),
        allowNull: true
      },
      location: {
        type: Sequelize.JSONB,
        allowNull: true
      },
      expiresAt: {
        type: Sequelize.DATE,
        allowNull: false
      },
      lastActivityAt: {
        type: Sequelize.DATE,
        allowNull: false,
        defaultValue: Sequelize.literal('CURRENT_TIMESTAMP')
      },
      isActive: {
        type: Sequelize.BOOLEAN,
        defaultValue: true,
        allowNull: false
      },
      isRevoked: {
        type: Sequelize.BOOLEAN,
        defaultValue: false,
        allowNull: false
      },
      revokedAt: {
        type: Sequelize.DATE,
        allowNull: true
      },
      revokeReason: {
        type: Sequelize.STRING(255),
        allowNull: true
      },
      metadata: {
        type: Sequelize.JSONB,
        defaultValue: {},
        allowNull: false
      },
      createdAt: {
        type: Sequelize.DATE,
        allowNull: false,
        defaultValue: Sequelize.literal('CURRENT_TIMESTAMP')
      },
      updatedAt: {
        type: Sequelize.DATE,
        allowNull: false,
        defaultValue: Sequelize.literal('CURRENT_TIMESTAMP')
      }
    });

    // Add indexes
    await queryInterface.addIndex('groups', ['name']);
    await queryInterface.addIndex('groups', ['slug']);
    await queryInterface.addIndex('groups', ['type']);
    await queryInterface.addIndex('groups', ['category']);
    await queryInterface.addIndex('groups', ['isActive']);

    await queryInterface.addIndex('user_groups', ['userId']);
    await queryInterface.addIndex('user_groups', ['groupId']);
    await queryInterface.addIndex('user_groups', ['userId', 'groupId'], { unique: true });
    await queryInterface.addIndex('user_groups', ['role']);
    await queryInterface.addIndex('user_groups', ['status']);

    await queryInterface.addIndex('sessions', ['userId']);
    await queryInterface.addIndex('sessions', ['token']);
    await queryInterface.addIndex('sessions', ['refreshToken']);
    await queryInterface.addIndex('sessions', ['isActive']);
    await queryInterface.addIndex('sessions', ['expiresAt']);
    await queryInterface.addIndex('sessions', ['ipAddress']);
  },

  async down(queryInterface, Sequelize) {
    await queryInterface.dropTable('sessions');
    await queryInterface.dropTable('user_groups');
    await queryInterface.dropTable('groups');
  }
};
