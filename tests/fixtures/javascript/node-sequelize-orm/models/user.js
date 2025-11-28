const { Model, DataTypes } = require("sequelize");
const sequelize = require("../database");

class User extends Model {}

User.init(
  {
    id: {
      type: DataTypes.INTEGER,
      primaryKey: true,
      autoIncrement: true,
    },
    username: {
      type: DataTypes.STRING(80),
      allowNull: false,
      unique: true,
    },
    email: {
      type: DataTypes.STRING(120),
      allowNull: false,
      unique: true,
    },
    passwordHash: {
      type: DataTypes.STRING(128),
      allowNull: false,
    },
  },
  {
    sequelize,
    modelName: "User",
    tableName: "users",
  },
);

User.hasMany(require("./post"), {
  foreignKey: "userId",
  as: "posts",
});

User.belongsTo(require("./role"), {
  foreignKey: "roleId",
  as: "role",
});

User.belongsToMany(require("./group"), {
  through: "UserGroups",
  foreignKey: "userId",
  otherKey: "groupId",
  as: "groups",
});

module.exports = User;
