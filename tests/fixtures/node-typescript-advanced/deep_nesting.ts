abstract class BaseEntity {
  id?: number;

  save(): string {
    return `Saving ${this.constructor.name}`;
  }

  abstract validate(): boolean;

  static create<T extends BaseEntity>(this: new () => T): T {
    return new this();
  }
}

class TimestampedEntity extends BaseEntity {
  createdAt?: Date;
  updatedAt?: Date;

  save(): string {
    this.updatedAt = new Date();
    return super.save();
  }

  validate(): boolean {
    return true;
  }

  getAge(): string {
    if (!this.createdAt) return "unknown";
    const now = new Date();
    const diff = now.getTime() - this.createdAt.getTime();
    return `${Math.floor(diff / 1000 / 60 / 60 / 24)} days`;
  }
}

class SoftDeletableEntity extends TimestampedEntity {
  deletedAt?: Date;
  isDeleted: boolean = false;

  save(): string {
    if (this.isDeleted) {
      this.deletedAt = new Date();
    }
    return super.save();
  }

  softDelete(): string {
    this.isDeleted = true;
    return this.save();
  }

  restore(): void {
    this.isDeleted = false;
    this.deletedAt = undefined;
  }
}

class User extends SoftDeletableEntity {
  username?: string;
  email?: string;
  passwordHash?: string;

  save(): string {
    if (!this.validateEmail()) {
      throw new Error("Invalid email");
    }
    return super.save();
  }

  validate(): boolean {
    if (!this.username || !this.email) {
      return false;
    }
    return super.validate();
  }

  private validateEmail(): boolean {
    return this.email ? this.email.includes("@") : false;
  }

  getDisplayName(): string {
    return this.username || "Unknown";
  }
}

class AdminUser extends User {
  adminLevel?: number;
  permissions: string[] = [];

  save(): string {
    const result = super.save();
    this.logAdminAction("save");
    return result;
  }

  private logAdminAction(action: string): void {
    console.log(`Admin action: ${action} by ${this.username}`);
  }

  grantPermission(permission: string): void {
    if (!this.permissions.includes(permission)) {
      this.permissions.push(permission);
    }
  }
}

class SuperAdminUser extends AdminUser {
  canDeleteUsers: boolean = true;

  save(): string {
    console.log(`SuperAdmin ${this.username} saving`);
    return super.save();
  }

  deleteUser(user: User): void {
    if (this.canDeleteUsers) {
      user.softDelete();
    }
  }
}

interface IIdentifiable {
  id: number;
}

interface ITimestampable extends IIdentifiable {
  createdAt: Date;
  updatedAt: Date;
}

interface IAuditable extends ITimestampable {
  createdBy: number;
  updatedBy: number;
  auditLog: string[];
}

interface IVersioned extends IAuditable {
  version: number;
  versionHistory: Array<{ version: number; timestamp: Date }>;
}

class VersionedDocument implements IVersioned {
  id: number = 0;
  createdAt: Date = new Date();
  updatedAt: Date = new Date();
  createdBy: number = 0;
  updatedBy: number = 0;
  auditLog: string[] = [];
  version: number = 1;
  versionHistory: Array<{ version: number; timestamp: Date }> = [];

  incrementVersion(): void {
    this.version++;
    this.versionHistory.push({
      version: this.version,
      timestamp: new Date(),
    });
  }
}

class OuterContainer {
  outerAttribute: string = "outer";

  outerMethod(): string {
    return "outer method";
  }

  static MiddleContainer = class {
    middleAttribute: string = "middle";

    middleMethod(): string {
      return "middle method";
    }

    static InnerContainer = class {
      innerAttribute: string = "inner";

      innerMethod(): string {
        return "inner method";
      }

      static DeepNested = class {
        deepAttribute: string = "deep";

        deepMethod(): string {
          return "deep method";
        }

        accessAncestors(): void {
          const outer = new OuterContainer();
          const middle = new OuterContainer.MiddleContainer();
          const inner = new OuterContainer.MiddleContainer.InnerContainer();
          console.log(outer, middle, inner);
        }
      };
    };
  };
}

namespace Application {
  export class BaseService {
    serviceName: string = "base";

    execute(): string {
      return "executing base service";
    }
  }

  export namespace Core {
    export class CoreService extends BaseService {
      serviceName: string = "core";

      execute(): string {
        return `${super.execute()} + core`;
      }
    }

    export namespace Advanced {
      export class AdvancedService extends CoreService {
        serviceName: string = "advanced";

        execute(): string {
          return `${super.execute()} + advanced`;
        }
      }
    }
  }
}

class Repository<T extends BaseEntity> {
  protected modelClass?: new () => T;

  findById(id: number): string {
    return `Finding ${this.modelClass?.name || "Entity"} by ID ${id}`;
  }

  findAll(): string {
    return `Finding all ${this.modelClass?.name || "Entities"}`;
  }

  create(data: Partial<T>): T | undefined {
    if (this.modelClass) {
      const instance = new this.modelClass();
      Object.assign(instance, data);
      return instance;
    }
    return undefined;
  }
}

class UserRepository extends Repository<User> {
  modelClass = User;

  findByUsername(username: string): string {
    return `Finding user by username: ${username}`;
  }

  findActiveUsers(): string {
    return `Finding active users`;
  }
}

class AdminUserRepository extends UserRepository {
  modelClass = AdminUser;

  findAdminsWithLevel(level: number): string {
    return `Finding admins with level ${level}`;
  }
}

abstract class AbstractService {
  execute(): string {
    this.validateInput();
    const result = this.perform();
    this.cleanup();
    return result;
  }

  protected validateInput(): void {}

  protected abstract perform(): string;

  protected cleanup(): void {}
}

class UserService extends AbstractService {
  protected validateInput(): void {
    console.log("Validating user input");
  }

  protected perform(): string {
    return "Performing user operation";
  }

  protected cleanup(): void {
    console.log("Cleaning up user resources");
  }
}

class EnhancedUserService extends UserService {
  protected perform(): string {
    const baseResult = super.perform();
    return `${baseResult} with enhancements`;
  }
}

type Constructor<T = {}> = new (...args: any[]) => T;

function Loggable<TBase extends Constructor>(Base: TBase) {
  return class extends Base {
    log(message: string): void {
      console.log(`[${this.constructor.name}] ${message}`);
    }
  };
}

function Cacheable<TBase extends Constructor>(Base: TBase) {
  return class extends Base {
    private cache: Map<string, any> = new Map();

    getCacheKey(): string {
      return `cache:${this.constructor.name}`;
    }

    invalidateCache(): void {
      this.cache.clear();
    }
  };
}

class MixedEntity extends Loggable(Cacheable(BaseEntity)) {
  validate(): boolean {
    this.log("Validating entity");
    return true;
  }

  save(): string {
    this.log("Saving entity");
    this.invalidateCache();
    return super.save();
  }
}

export {
  BaseEntity,
  TimestampedEntity,
  SoftDeletableEntity,
  User,
  AdminUser,
  SuperAdminUser,
  IVersioned,
  VersionedDocument,
  OuterContainer,
  Application,
  Repository,
  UserRepository,
  AdminUserRepository,
  AbstractService,
  UserService,
  EnhancedUserService,
  MixedEntity,
};
