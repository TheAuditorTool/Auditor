module.exports = (sequelize, DataTypes) => {
  const Role = sequelize.define(
    "Role",
    {
      id: {
        type: DataTypes.INTEGER,
        primaryKey: true,
        autoIncrement: true,
      },

      name: {
        type: DataTypes.STRING(50),
        allowNull: false,
        unique: true,
        validate: {
          notEmpty: true,
          isIn: {
            args: [["admin", "user", "moderator", "guest"]],
            msg: "Role must be one of: admin, user, moderator, guest",
          },
        },
      },

      permissions: {
        type: DataTypes.JSONB,
        defaultValue: {},
        allowNull: false,
        comment: "JSON object storing role permissions",
      },

      description: {
        type: DataTypes.TEXT,
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
      tableName: "roles",
      timestamps: true,
    },
  );

  Role.associate = function (models) {
    Role.hasMany(models.User, {
      foreignKey: "roleId",
      as: "users",
      onDelete: "SET NULL",
    });
  };

  return Role;
};
