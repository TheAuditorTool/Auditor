/**
 * Session model
 * Tests: One-to-many relationship (Session belongs to User), session management patterns
 */

const crypto = require('crypto');

module.exports = (sequelize, DataTypes) => {
  const Session = sequelize.define('Session', {
    id: {
      type: DataTypes.INTEGER,
      primaryKey: true,
      autoIncrement: true
    },

    token: {
      type: DataTypes.STRING(255),
      allowNull: false,
      unique: {
        msg: 'Session token must be unique'
      },
      validate: {
        notEmpty: true,
        len: {
          args: [32, 255],
          msg: 'Session token must be at least 32 characters'
        }
      }
    },

    refreshToken: {
      type: DataTypes.STRING(255),
      allowNull: true,
      unique: true,
      validate: {
        len: {
          args: [32, 255],
          msg: 'Refresh token must be at least 32 characters'
        }
      }
    },

    ipAddress: {
      type: DataTypes.STRING(45),
      allowNull: true,
      comment: 'IPv4 or IPv6 address',
      validate: {
        isIP: {
          msg: 'Must be a valid IP address'
        }
      }
    },

    userAgent: {
      type: DataTypes.TEXT,
      allowNull: true,
      comment: 'Browser/client user agent string'
    },

    device: {
      type: DataTypes.STRING(100),
      allowNull: true,
      comment: 'Device type: desktop, mobile, tablet'
    },

    platform: {
      type: DataTypes.STRING(100),
      allowNull: true,
      comment: 'Operating system: Windows, macOS, Linux, iOS, Android'
    },

    browser: {
      type: DataTypes.STRING(100),
      allowNull: true,
      comment: 'Browser name and version'
    },

    location: {
      type: DataTypes.JSONB,
      allowNull: true,
      comment: 'Geolocation data: {country, city, lat, lon}',
      validate: {
        isValidLocation(value) {
          if (value && (!value.country)) {
            throw new Error('Location must contain at least country');
          }
        }
      }
    },

    expiresAt: {
      type: DataTypes.DATE,
      allowNull: false,
      validate: {
        isDate: true,
        isFuture(value) {
          if (new Date(value) < new Date()) {
            throw new Error('Expiration date must be in the future');
          }
        }
      }
    },

    lastActivityAt: {
      type: DataTypes.DATE,
      allowNull: false,
      defaultValue: DataTypes.NOW
    },

    isActive: {
      type: DataTypes.BOOLEAN,
      defaultValue: true,
      allowNull: false
    },

    isRevoked: {
      type: DataTypes.BOOLEAN,
      defaultValue: false,
      allowNull: false
    },

    revokedAt: {
      type: DataTypes.DATE,
      allowNull: true
    },

    revokeReason: {
      type: DataTypes.STRING(255),
      allowNull: true,
      validate: {
        isIn: {
          args: [['logout', 'security', 'expired', 'replaced', 'admin_action']],
          msg: 'Invalid revoke reason'
        }
      }
    },

    // Virtual field: is expired
    isExpired: {
      type: DataTypes.VIRTUAL,
      get() {
        return new Date() > new Date(this.expiresAt);
      }
    },

    // Virtual field: time until expiry (in minutes)
    minutesUntilExpiry: {
      type: DataTypes.VIRTUAL,
      get() {
        const now = new Date();
        const expiry = new Date(this.expiresAt);
        return Math.max(0, Math.floor((expiry - now) / (1000 * 60)));
      }
    },

    metadata: {
      type: DataTypes.JSONB,
      defaultValue: {},
      allowNull: false,
      comment: 'Additional session metadata'
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
    tableName: 'sessions',
    timestamps: true,

    // Hooks
    hooks: {
      /**
       * beforeCreate hook - Generate session tokens
       * Tests: Hook with cryptographic token generation
       */
      beforeCreate: async (session, options) => {
        // Generate secure token if not provided
        if (!session.token) {
          session.token = crypto.randomBytes(32).toString('hex');
        }

        // Generate refresh token if not provided
        if (!session.refreshToken) {
          session.refreshToken = crypto.randomBytes(32).toString('hex');
        }

        // Set default expiration (24 hours)
        if (!session.expiresAt) {
          const expiresAt = new Date();
          expiresAt.setHours(expiresAt.getHours() + 24);
          session.expiresAt = expiresAt;
        }

        // Parse user agent for device/browser info
        if (session.userAgent && !session.device) {
          session.device = parseDeviceFromUserAgent(session.userAgent);
          session.platform = parsePlatformFromUserAgent(session.userAgent);
          session.browser = parseBrowserFromUserAgent(session.userAgent);
        }
      },

      /**
       * beforeUpdate hook - Handle revocation
       * Tests: Hook with status transition
       */
      beforeUpdate: async (session, options) => {
        if (session.changed('isRevoked') && session.isRevoked && !session.revokedAt) {
          session.revokedAt = new Date();
          session.isActive = false;
        }
      },

      /**
       * afterCreate hook - Update user login tracking
       * Tests: Hook with cascading updates
       */
      afterCreate: async (session, options) => {
        const User = sequelize.models.User;
        const user = await User.findByPk(session.userId);

        if (user) {
          await user.recordLogin();
        }

        console.log(`New session created for user ${session.userId} from ${session.ipAddress}`);
      },

      /**
       * afterDestroy hook - Cleanup
       * Tests: Hook with cleanup logic
       */
      afterDestroy: async (session, options) => {
        console.log(`Session ${session.id} destroyed for user ${session.userId}`);
      }
    },

    // Indexes
    indexes: [
      {
        unique: true,
        fields: ['token']
      },
      {
        unique: true,
        fields: ['refreshToken']
      },
      {
        fields: ['userId']
      },
      {
        fields: ['isActive']
      },
      {
        fields: ['expiresAt']
      },
      {
        fields: ['ipAddress']
      },
      {
        fields: ['lastActivityAt']
      }
    ]
  });

  /**
   * Associations
   * Tests: One-to-many relationship
   */
  Session.associate = function(models) {
    // Many-to-one: Session belongs to User
    Session.belongsTo(models.User, {
      foreignKey: 'userId',
      as: 'user',
      onDelete: 'CASCADE',
      onUpdate: 'CASCADE'
    });
  };

  /**
   * Instance methods
   */

  /**
   * Revoke session
   * Tests: Instance method with status change
   */
  Session.prototype.revoke = async function(reason = 'logout') {
    this.isRevoked = true;
    this.isActive = false;
    this.revokedAt = new Date();
    this.revokeReason = reason;
    await this.save();
  };

  /**
   * Refresh session
   * Tests: Instance method with token rotation
   */
  Session.prototype.refresh = async function() {
    if (this.isRevoked) {
      throw new Error('Cannot refresh revoked session');
    }

    if (this.isExpired) {
      throw new Error('Cannot refresh expired session');
    }

    // Generate new tokens
    this.token = crypto.randomBytes(32).toString('hex');
    this.refreshToken = crypto.randomBytes(32).toString('hex');

    // Extend expiration
    const expiresAt = new Date();
    expiresAt.setHours(expiresAt.getHours() + 24);
    this.expiresAt = expiresAt;

    this.lastActivityAt = new Date();

    await this.save();

    return {
      token: this.token,
      refreshToken: this.refreshToken,
      expiresAt: this.expiresAt
    };
  };

  /**
   * Update last activity
   * Tests: Instance method with timestamp update
   */
  Session.prototype.updateActivity = async function() {
    this.lastActivityAt = new Date();
    await this.save();
  };

  /**
   * Extend expiration
   * Tests: Instance method with expiration management
   */
  Session.prototype.extendExpiration = async function(hours = 24) {
    if (this.isRevoked) {
      throw new Error('Cannot extend revoked session');
    }

    const expiresAt = new Date();
    expiresAt.setHours(expiresAt.getHours() + hours);
    this.expiresAt = expiresAt;

    await this.save();
  };

  /**
   * Check if session is valid
   * Tests: Instance method with validation logic
   */
  Session.prototype.isValid = function() {
    return this.isActive && !this.isRevoked && !this.isExpired;
  };

  /**
   * Get session details
   * Tests: Instance method with formatted output
   */
  Session.prototype.getDetails = function() {
    return {
      id: this.id,
      device: this.device,
      platform: this.platform,
      browser: this.browser,
      ipAddress: this.ipAddress,
      location: this.location,
      createdAt: this.createdAt,
      lastActivityAt: this.lastActivityAt,
      expiresAt: this.expiresAt,
      isActive: this.isActive,
      isExpired: this.isExpired
    };
  };

  /**
   * Class methods
   */

  /**
   * Find active sessions for user
   * Tests: Class method with filtering
   */
  Session.findActiveSessions = async function(userId) {
    return await this.findAll({
      where: {
        userId,
        isActive: true,
        isRevoked: false
      },
      order: [['lastActivityAt', 'DESC']]
    });
  };

  /**
   * Find session by token
   * Tests: Class method with token lookup
   */
  Session.findByToken = async function(token) {
    return await this.findOne({
      where: { token },
      include: [{
        model: sequelize.models.User,
        as: 'user',
        attributes: ['id', 'username', 'email', 'status']
      }]
    });
  };

  /**
   * Find session by refresh token
   * Tests: Class method with token lookup
   */
  Session.findByRefreshToken = async function(refreshToken) {
    return await this.findOne({
      where: { refreshToken },
      include: [{
        model: sequelize.models.User,
        as: 'user',
        attributes: ['id', 'username', 'email', 'status']
      }]
    });
  };

  /**
   * Cleanup expired sessions
   * Tests: Class method with batch deletion
   */
  Session.cleanupExpired = async function() {
    const { Op } = sequelize;

    const deleted = await this.destroy({
      where: {
        expiresAt: {
          [Op.lt]: new Date()
        }
      }
    });

    console.log(`Cleaned up ${deleted} expired sessions`);
    return deleted;
  };

  /**
   * Revoke all user sessions
   * Tests: Class method with batch update
   */
  Session.revokeAllUserSessions = async function(userId, reason = 'security') {
    const updated = await this.update(
      {
        isRevoked: true,
        isActive: false,
        revokedAt: new Date(),
        revokeReason: reason
      },
      {
        where: {
          userId,
          isRevoked: false
        }
      }
    );

    return updated[0]; // Number of affected rows
  };

  /**
   * Get active sessions count by device
   * Tests: Class method with aggregation
   */
  Session.getSessionStatsByDevice = async function() {
    const { fn, col } = sequelize;

    return await this.findAll({
      attributes: [
        'device',
        [fn('COUNT', col('id')), 'sessionCount']
      ],
      where: {
        isActive: true,
        isRevoked: false
      },
      group: ['device'],
      raw: true
    });
  };

  /**
   * Find sessions by IP address
   * Tests: Class method with security monitoring
   */
  Session.findByIpAddress = async function(ipAddress, includeRevoked = false) {
    const where = { ipAddress };

    if (!includeRevoked) {
      where.isRevoked = false;
    }

    return await this.findAll({
      where,
      include: [{
        model: sequelize.models.User,
        as: 'user',
        attributes: ['id', 'username', 'email']
      }],
      order: [['createdAt', 'DESC']]
    });
  };

  return Session;
};

/**
 * Helper functions for user agent parsing
 * Tests: Utility functions for device detection
 */

function parseDeviceFromUserAgent(userAgent) {
  const ua = userAgent.toLowerCase();

  if (/mobile|android|iphone|ipad|ipod/i.test(ua)) {
    if (/ipad|tablet/i.test(ua)) {
      return 'tablet';
    }
    return 'mobile';
  }

  return 'desktop';
}

function parsePlatformFromUserAgent(userAgent) {
  const ua = userAgent.toLowerCase();

  if (/windows/i.test(ua)) return 'Windows';
  if (/macintosh|mac os x/i.test(ua)) return 'macOS';
  if (/linux/i.test(ua)) return 'Linux';
  if (/android/i.test(ua)) return 'Android';
  if (/iphone|ipad|ipod/i.test(ua)) return 'iOS';

  return 'Unknown';
}

function parseBrowserFromUserAgent(userAgent) {
  const ua = userAgent.toLowerCase();

  if (/edg/i.test(ua)) return 'Edge';
  if (/chrome/i.test(ua)) return 'Chrome';
  if (/firefox/i.test(ua)) return 'Firefox';
  if (/safari/i.test(ua)) return 'Safari';
  if (/opera|opr/i.test(ua)) return 'Opera';

  return 'Unknown';
}
