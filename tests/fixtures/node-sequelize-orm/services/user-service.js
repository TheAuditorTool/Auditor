const { Op } = require("sequelize");
const bcrypt = require("bcrypt");

class UserService {
  constructor(sequelize) {
    this.sequelize = sequelize;
    this.User = sequelize.models.User;
    this.Profile = sequelize.models.Profile;
    this.Role = sequelize.models.Role;
    this.Session = sequelize.models.Session;
    this.Order = sequelize.models.Order;
    this.Group = sequelize.models.Group;
    this.UserGroup = sequelize.models.UserGroup;
  }

  async createUserWithProfile(userData, profileData) {
    const transaction = await this.sequelize.transaction();

    try {
      const user = await this.User.create(
        {
          username: userData.username,
          email: userData.email,
          password: userData.password,
          firstName: userData.firstName,
          lastName: userData.lastName,
          roleId: userData.roleId || null,
        },
        { transaction },
      );

      const profile = await this.Profile.create(
        {
          userId: user.id,
          bio: profileData.bio || null,
          avatar: profileData.avatar || null,
          phone: profileData.phone || null,
          timezone: profileData.timezone || "UTC",
        },
        { transaction },
      );

      await transaction.commit();

      return {
        user,
        profile,
      };
    } catch (error) {
      await transaction.rollback();
      throw error;
    }
  }

  async updateUserAndProfile(userId, userData, profileData) {
    const transaction = await this.sequelize.transaction();

    try {
      const user = await this.User.findByPk(userId, { transaction });

      if (!user) {
        throw new Error("User not found");
      }

      if (userData) {
        await user.update(userData, { transaction });
      }

      if (profileData) {
        let profile = await this.Profile.findOne({
          where: { userId },
          transaction,
        });

        if (!profile) {
          profile = await this.Profile.create(
            {
              userId,
              ...profileData,
            },
            { transaction },
          );
        } else {
          await profile.update(profileData, { transaction });
        }
      }

      await transaction.commit();

      return await this.getUserWithProfile(userId);
    } catch (error) {
      await transaction.rollback();
      throw error;
    }
  }

  async deleteUser(userId, options = { soft: false }) {
    const transaction = await this.sequelize.transaction();

    try {
      const user = await this.User.findByPk(userId, { transaction });

      if (!user) {
        throw new Error("User not found");
      }

      if (options.soft) {
        await user.update({ status: "deleted" }, { transaction });

        await this.Session.revokeAllUserSessions(userId, "user_deleted");
      } else {
        await user.destroy({ transaction });
      }

      await transaction.commit();

      return { success: true, userId };
    } catch (error) {
      await transaction.rollback();
      throw error;
    }
  }

  async authenticateAndCreateSession(credentials, sessionInfo) {
    const transaction = await this.sequelize.transaction();

    try {
      const user = await this.User.findOne({
        where: {
          [Op.or]: [
            { email: credentials.identifier },
            { username: credentials.identifier },
          ],
        },
        transaction,
      });

      if (!user) {
        throw new Error("Invalid credentials");
      }

      if (!user.isActive()) {
        throw new Error("User account is not active");
      }

      const isValidPassword = await user.comparePassword(credentials.password);

      if (!isValidPassword) {
        throw new Error("Invalid credentials");
      }

      const session = await this.Session.create(
        {
          userId: user.id,
          ipAddress: sessionInfo.ipAddress,
          userAgent: sessionInfo.userAgent,
          device: sessionInfo.device,
          platform: sessionInfo.platform,
          browser: sessionInfo.browser,
          location: sessionInfo.location || null,
        },
        { transaction },
      );

      await transaction.commit();

      return {
        user: {
          id: user.id,
          username: user.username,
          email: user.email,
          status: user.status,
        },
        session: {
          token: session.token,
          refreshToken: session.refreshToken,
          expiresAt: session.expiresAt,
        },
      };
    } catch (error) {
      await transaction.rollback();
      throw error;
    }
  }

  async getUserWithProfile(userId) {
    return await this.User.findByPk(userId, {
      include: [
        {
          model: this.Profile,
          as: "profile",
        },
        {
          model: this.Role,
          as: "role",
        },
      ],
    });
  }

  async getUserDashboard(userId) {
    const user = await this.User.findByPk(userId, {
      include: [
        {
          model: this.Profile,
          as: "profile",
        },
        {
          model: this.Role,
          as: "role",
        },
        {
          model: this.Order,
          as: "orders",
          limit: 5,
          order: [["createdAt", "DESC"]],
          separate: true,
        },
        {
          model: this.Session,
          as: "sessions",
          where: {
            isActive: true,
            isRevoked: false,
          },
          required: false,
        },
      ],
    });

    if (!user) {
      throw new Error("User not found");
    }

    const orderStats = await this.Order.findAll({
      attributes: [
        [this.sequelize.fn("COUNT", this.sequelize.col("id")), "totalOrders"],
        [this.sequelize.fn("SUM", this.sequelize.col("total")), "totalSpent"],
        [
          this.sequelize.fn("AVG", this.sequelize.col("total")),
          "avgOrderValue",
        ],
      ],
      where: {
        userId,
        status: {
          [Op.notIn]: ["cancelled", "refunded"],
        },
      },
      raw: true,
    });

    const groups = await this.UserGroup.findAll({
      where: {
        userId,
        status: "active",
      },
      include: [
        {
          model: this.Group,
          as: "group",
        },
      ],
    });

    return {
      user: user.toJSON(),
      stats: orderStats[0] || {
        totalOrders: 0,
        totalSpent: 0,
        avgOrderValue: 0,
      },
      groups: groups.map((ug) => ug.group),
      activeSessions: user.sessions.length,
    };
  }

  async searchUsers(filters = {}, pagination = {}) {
    const where = {};
    const include = [];

    if (filters.search) {
      where[Op.or] = [
        { username: { [Op.iLike]: `%${filters.search}%` } },
        { email: { [Op.iLike]: `%${filters.search}%` } },
        { firstName: { [Op.iLike]: `%${filters.search}%` } },
        { lastName: { [Op.iLike]: `%${filters.search}%` } },
      ];
    }

    if (filters.status) {
      where.status = filters.status;
    }

    if (filters.roleId) {
      where.roleId = filters.roleId;
    }

    if (filters.createdAfter) {
      where.createdAt = { [Op.gte]: new Date(filters.createdAfter) };
    }

    if (filters.createdBefore) {
      where.createdAt = {
        ...where.createdAt,
        [Op.lte]: new Date(filters.createdBefore),
      };
    }

    if (filters.includeProfile) {
      include.push({ model: this.Profile, as: "profile" });
    }

    if (filters.includeRole) {
      include.push({ model: this.Role, as: "role" });
    }

    const limit = pagination.limit || 20;
    const offset = pagination.offset || 0;
    const order = pagination.orderBy || [["createdAt", "DESC"]];

    const { count, rows } = await this.User.findAndCountAll({
      where,
      include,
      limit,
      offset,
      order,
      distinct: true,
    });

    return {
      users: rows,
      total: count,
      page: Math.floor(offset / limit) + 1,
      pages: Math.ceil(count / limit),
    };
  }

  async bulkUpdateUsers(userIds, updates) {
    const transaction = await this.sequelize.transaction();

    try {
      const result = await this.User.update(updates, {
        where: {
          id: {
            [Op.in]: userIds,
          },
        },
        transaction,
      });

      await transaction.commit();

      return {
        updated: result[0],
        userIds,
      };
    } catch (error) {
      await transaction.rollback();
      throw error;
    }
  }

  async transferOrders(fromUserId, toUserId, orderIds) {
    const transaction = await this.sequelize.transaction();

    try {
      const [fromUser, toUser] = await Promise.all([
        this.User.findByPk(fromUserId, { transaction }),
        this.User.findByPk(toUserId, { transaction }),
      ]);

      if (!fromUser || !toUser) {
        throw new Error("User not found");
      }

      const result = await this.Order.update(
        { userId: toUserId },
        {
          where: {
            id: { [Op.in]: orderIds },
            userId: fromUserId,
          },
          transaction,
        },
      );

      await transaction.commit();

      return {
        transferred: result[0],
        fromUserId,
        toUserId,
      };
    } catch (error) {
      await transaction.rollback();
      throw error;
    }
  }

  async getUserActivitySummary(userId, dateRange = {}) {
    const where = { userId };

    if (dateRange.start) {
      where.createdAt = { [Op.gte]: new Date(dateRange.start) };
    }

    if (dateRange.end) {
      where.createdAt = {
        ...where.createdAt,
        [Op.lte]: new Date(dateRange.end),
      };
    }

    const orderActivity = await this.Order.findAll({
      attributes: [
        [this.sequelize.fn("DATE", this.sequelize.col("createdAt")), "date"],
        [this.sequelize.fn("COUNT", this.sequelize.col("id")), "orderCount"],
        [this.sequelize.fn("SUM", this.sequelize.col("total")), "totalSpent"],
      ],
      where,
      group: [this.sequelize.fn("DATE", this.sequelize.col("createdAt"))],
      order: [
        [this.sequelize.fn("DATE", this.sequelize.col("createdAt")), "ASC"],
      ],
      raw: true,
    });

    const sessionActivity = await this.Session.findAll({
      attributes: [
        [this.sequelize.fn("DATE", this.sequelize.col("createdAt")), "date"],
        [this.sequelize.fn("COUNT", this.sequelize.col("id")), "loginCount"],
      ],
      where,
      group: [this.sequelize.fn("DATE", this.sequelize.col("createdAt"))],
      order: [
        [this.sequelize.fn("DATE", this.sequelize.col("createdAt")), "ASC"],
      ],
      raw: true,
    });

    return {
      orders: orderActivity,
      sessions: sessionActivity,
    };
  }
}

module.exports = UserService;
