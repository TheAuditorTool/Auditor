/**
 * Migration: Create users and roles tables
 * Tests: Base schema creation with relationships
 */

'use strict';

module.exports = {
  /**
   * Apply migration
   * Tests: Table creation with constraints and indexes
   */
  async up(queryInterface, Sequelize) {
    // Create roles table first (referenced by users)
    await queryInterface.createTable('roles', {
      id: {
        type: Sequelize.INTEGER,
        primaryKey: true,
        autoIncrement: true
      },
      name: {
        type: Sequelize.STRING(50),
        allowNull: false,
        unique: true
      },
      permissions: {
        type: Sequelize.JSONB,
        defaultValue: {},
        allowNull: false
      },
      description: {
        type: Sequelize.TEXT,
        allowNull: true
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

    // Create users table
    await queryInterface.createTable('users', {
      id: {
        type: Sequelize.INTEGER,
        primaryKey: true,
        autoIncrement: true
      },
      username: {
        type: Sequelize.STRING(100),
        allowNull: false,
        unique: true
      },
      email: {
        type: Sequelize.STRING(200),
        allowNull: false,
        unique: true
      },
      password: {
        type: Sequelize.STRING(255),
        allowNull: false
      },
      status: {
        type: Sequelize.ENUM('active', 'inactive', 'suspended', 'deleted'),
        defaultValue: 'active',
        allowNull: false
      },
      lastLoginAt: {
        type: Sequelize.DATE,
        allowNull: true
      },
      loginCount: {
        type: Sequelize.INTEGER,
        defaultValue: 0,
        allowNull: false
      },
      firstName: {
        type: Sequelize.STRING(100),
        allowNull: true
      },
      lastName: {
        type: Sequelize.STRING(100),
        allowNull: true
      },
      roleId: {
        type: Sequelize.INTEGER,
        allowNull: true,
        references: {
          model: 'roles',
          key: 'id'
        },
        onDelete: 'SET NULL',
        onUpdate: 'CASCADE'
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

    // Add indexes for users
    await queryInterface.addIndex('users', ['email']);
    await queryInterface.addIndex('users', ['username']);
    await queryInterface.addIndex('users', ['status']);
    await queryInterface.addIndex('users', ['roleId']);
    await queryInterface.addIndex('users', ['createdAt']);
  },

  /**
   * Rollback migration
   * Tests: Clean table removal with dependency order
   */
  async down(queryInterface, Sequelize) {
    // Drop in reverse order (users first due to foreign key)
    await queryInterface.dropTable('users');
    await queryInterface.dropTable('roles');
  }
};
