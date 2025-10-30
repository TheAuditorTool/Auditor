/**
 * Profile model
 * Tests: One-to-one relationship (Profile belongs to User)
 */

module.exports = (sequelize, DataTypes) => {
  const Profile = sequelize.define('Profile', {
    id: {
      type: DataTypes.INTEGER,
      primaryKey: true,
      autoIncrement: true
    },

    bio: {
      type: DataTypes.TEXT,
      allowNull: true,
      validate: {
        len: {
          args: [0, 2000],
          msg: 'Bio must be less than 2000 characters'
        }
      }
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

    phone: {
      type: DataTypes.STRING(20),
      allowNull: true,
      validate: {
        is: {
          args: /^\+?[1-9]\d{1,14}$/,
          msg: 'Phone must be a valid international phone number'
        }
      }
    },

    dateOfBirth: {
      type: DataTypes.DATEONLY,
      allowNull: true,
      validate: {
        isDate: {
          msg: 'Date of birth must be a valid date'
        },
        isValidAge(value) {
          if (value) {
            const today = new Date();
            const birthDate = new Date(value);
            const age = today.getFullYear() - birthDate.getFullYear();

            if (age < 13) {
              throw new Error('User must be at least 13 years old');
            }

            if (age > 150) {
              throw new Error('Invalid date of birth');
            }
          }
        }
      }
    },

    // Virtual field: age
    age: {
      type: DataTypes.VIRTUAL,
      get() {
        if (!this.dateOfBirth) return null;

        const today = new Date();
        const birthDate = new Date(this.dateOfBirth);
        let age = today.getFullYear() - birthDate.getFullYear();
        const monthDiff = today.getMonth() - birthDate.getMonth();

        if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birthDate.getDate())) {
          age--;
        }

        return age;
      }
    },

    address: {
      type: DataTypes.JSONB,
      allowNull: true,
      comment: 'JSON object: {street, city, state, country, postalCode}',
      validate: {
        isValidAddress(value) {
          if (value && (!value.street || !value.city || !value.country)) {
            throw new Error('Address must contain at least street, city, and country');
          }
        }
      }
    },

    timezone: {
      type: DataTypes.STRING(50),
      allowNull: true,
      defaultValue: 'UTC',
      validate: {
        isValidTimezone(value) {
          const validTimezones = ['UTC', 'America/New_York', 'America/Los_Angeles', 'Europe/London', 'Asia/Tokyo'];
          if (value && !validTimezones.includes(value)) {
            // In a real app, you'd check against a comprehensive list
            console.warn(`Timezone ${value} may not be valid`);
          }
        }
      }
    },

    locale: {
      type: DataTypes.STRING(10),
      allowNull: true,
      defaultValue: 'en-US',
      validate: {
        is: {
          args: /^[a-z]{2}-[A-Z]{2}$/,
          msg: 'Locale must be in format: xx-XX (e.g., en-US)'
        }
      }
    },

    // Social media links
    socialLinks: {
      type: DataTypes.JSONB,
      defaultValue: {},
      allowNull: false,
      comment: 'JSON object: {twitter, linkedin, github, etc.}',
      validate: {
        isValidSocialLinks(value) {
          if (value) {
            const validKeys = ['twitter', 'linkedin', 'github', 'facebook', 'instagram'];
            for (const key in value) {
              if (!validKeys.includes(key)) {
                console.warn(`Unknown social link type: ${key}`);
              }
              // Basic URL validation
              if (typeof value[key] !== 'string' || !value[key].startsWith('http')) {
                throw new Error(`Social link ${key} must be a valid URL`);
              }
            }
          }
        }
      }
    },

    preferences: {
      type: DataTypes.JSONB,
      defaultValue: {
        emailNotifications: true,
        smsNotifications: false,
        theme: 'light',
        language: 'en'
      },
      allowNull: false,
      comment: 'User preferences and settings'
    },

    // Privacy settings
    isPublic: {
      type: DataTypes.BOOLEAN,
      defaultValue: true,
      allowNull: false
    },

    showEmail: {
      type: DataTypes.BOOLEAN,
      defaultValue: false,
      allowNull: false
    },

    showPhone: {
      type: DataTypes.BOOLEAN,
      defaultValue: false,
      allowNull: false
    },

    // Stats
    profileViews: {
      type: DataTypes.INTEGER,
      defaultValue: 0,
      allowNull: false
    },

    lastProfileUpdate: {
      type: DataTypes.DATE,
      allowNull: true
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
    tableName: 'profiles',
    timestamps: true,

    // Hooks
    hooks: {
      /**
       * beforeUpdate hook - Track profile updates
       * Tests: Hook with timestamp tracking
       */
      beforeUpdate: async (profile, options) => {
        // Track when profile content changes (not just timestamps)
        const changedFields = Object.keys(profile._changed);
        const contentFields = ['bio', 'avatar', 'phone', 'dateOfBirth', 'address', 'socialLinks'];

        const hasContentChange = changedFields.some(field => contentFields.includes(field));

        if (hasContentChange) {
          profile.lastProfileUpdate = new Date();
        }
      },

      /**
       * afterCreate hook - Initialize default preferences
       * Tests: Hook with default initialization
       */
      afterCreate: async (profile, options) => {
        console.log(`Profile created for userId: ${profile.userId}`);
      }
    },

    // Indexes
    indexes: [
      {
        unique: true,
        fields: ['userId']
      },
      {
        fields: ['isPublic']
      },
      {
        fields: ['createdAt']
      }
    ]
  });

  /**
   * Associations
   * Tests: One-to-one relationship
   */
  Profile.associate = function(models) {
    // One-to-one: Profile belongs to User
    Profile.belongsTo(models.User, {
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
   * Update preferences
   * Tests: Instance method with JSON field update
   */
  Profile.prototype.updatePreferences = async function(newPreferences) {
    this.preferences = {
      ...this.preferences,
      ...newPreferences
    };
    await this.save();
  };

  /**
   * Add social link
   * Tests: Instance method with JSON field update
   */
  Profile.prototype.addSocialLink = async function(platform, url) {
    if (!url.startsWith('http')) {
      throw new Error('URL must start with http or https');
    }

    this.socialLinks = {
      ...this.socialLinks,
      [platform]: url
    };
    await this.save();
  };

  /**
   * Remove social link
   * Tests: Instance method with JSON field update
   */
  Profile.prototype.removeSocialLink = async function(platform) {
    const links = { ...this.socialLinks };
    delete links[platform];
    this.socialLinks = links;
    await this.save();
  };

  /**
   * Increment profile view count
   * Tests: Instance method with counter update
   */
  Profile.prototype.incrementViews = async function() {
    this.profileViews += 1;
    await this.save();
  };

  /**
   * Check if profile is complete
   * Tests: Instance method with validation logic
   */
  Profile.prototype.isComplete = function() {
    const requiredFields = ['bio', 'avatar', 'phone', 'dateOfBirth', 'address'];
    return requiredFields.every(field => {
      const value = this[field];
      return value !== null && value !== undefined && value !== '';
    });
  };

  /**
   * Get profile completion percentage
   * Tests: Instance method with calculation
   */
  Profile.prototype.getCompletionPercentage = function() {
    const fields = ['bio', 'avatar', 'phone', 'dateOfBirth', 'address', 'socialLinks'];
    let completed = 0;

    fields.forEach(field => {
      const value = this[field];
      if (value !== null && value !== undefined && value !== '') {
        if (typeof value === 'object' && Object.keys(value).length === 0) {
          // Empty object doesn't count
          return;
        }
        completed++;
      }
    });

    return Math.round((completed / fields.length) * 100);
  };

  /**
   * Class methods
   */

  /**
   * Find public profiles
   * Tests: Class method with filtering
   */
  Profile.findPublicProfiles = async function() {
    return await this.findAll({
      where: { isPublic: true },
      include: [{
        model: sequelize.models.User,
        as: 'user',
        attributes: ['id', 'username', 'firstName', 'lastName']
      }],
      order: [['createdAt', 'DESC']]
    });
  };

  /**
   * Find profiles by timezone
   * Tests: Class method with filtering
   */
  Profile.findByTimezone = async function(timezone) {
    return await this.findAll({
      where: { timezone },
      include: [{
        model: sequelize.models.User,
        as: 'user',
        attributes: ['id', 'username']
      }]
    });
  };

  /**
   * Find incomplete profiles
   * Tests: Class method with complex filtering
   */
  Profile.findIncompleteProfiles = async function() {
    const { Op } = sequelize;

    return await this.findAll({
      where: {
        [Op.or]: [
          { bio: { [Op.is]: null } },
          { avatar: { [Op.is]: null } },
          { phone: { [Op.is]: null } },
          { dateOfBirth: { [Op.is]: null } }
        ]
      },
      include: [{
        model: sequelize.models.User,
        as: 'user',
        attributes: ['id', 'username', 'email']
      }]
    });
  };

  return Profile;
};
