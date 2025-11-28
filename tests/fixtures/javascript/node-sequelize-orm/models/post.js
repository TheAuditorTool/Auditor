const { Model, DataTypes } = require("sequelize");
const sequelize = require("../database");

class Post extends Model {}

Post.init(
  {
    id: {
      type: DataTypes.INTEGER,
      primaryKey: true,
      autoIncrement: true,
    },
    title: {
      type: DataTypes.STRING(200),
      allowNull: false,
    },
    content: {
      type: DataTypes.TEXT,
      allowNull: false,
    },
    userId: {
      type: DataTypes.INTEGER,
      allowNull: false,
      references: {
        model: "users",
        key: "id",
      },
    },
  },
  {
    sequelize,
    modelName: "Post",
    tableName: "posts",
  },
);

Post.belongsTo(require("./user"), {
  foreignKey: "userId",
  as: "author",
});

module.exports = Post;
