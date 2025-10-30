/**
 * Deep Nesting and Inheritance Fixture (TypeScript)
 *
 * Tests extraction of:
 * - 3+ level class inheritance chains (extends keyword)
 * - 3+ level nested classes
 * - Interface extension chains
 * - Abstract classes with inheritance
 * - Generic classes with constraints
 *
 * Validates TypeScript-specific patterns have parity with Python extraction.
 */

// ==============================================================================
// Deep Class Inheritance Chains (3+ levels)
// ==============================================================================

/**
 * Base entity class - Root of hierarchy
 */
abstract class BaseEntity {
  id?: number;

  /**
   * Base save method
   */
  save(): string {
    return `Saving ${this.constructor.name}`;
  }

  /**
   * Abstract validation method - must be implemented by subclasses
   */
  abstract validate(): boolean;

  /**
   * Static factory method
   */
  static create<T extends BaseEntity>(this: new () => T): T {
    return new this();
  }
}

/**
 * Timestamped entity - Level 1 inheritance
 */
class TimestampedEntity extends BaseEntity {
  createdAt?: Date;
  updatedAt?: Date;

  /**
   * Override save with timestamp logic
   */
  save(): string {
    this.updatedAt = new Date();
    return super.save();
  }

  /**
   * Implement abstract validation
   */
  validate(): boolean {
    return true;
  }

  /**
   * New method introduced at this level
   */
  getAge(): string {
    if (!this.createdAt) return "unknown";
    const now = new Date();
    const diff = now.getTime() - this.createdAt.getTime();
    return `${Math.floor(diff / 1000 / 60 / 60 / 24)} days`;
  }
}

/**
 * Soft deletable entity - Level 2 inheritance
 * Tests: Parent-of-parent resolution (BaseEntity -> TimestampedEntity -> SoftDeletableEntity)
 */
class SoftDeletableEntity extends TimestampedEntity {
  deletedAt?: Date;
  isDeleted: boolean = false;

  /**
   * Override save with soft-delete logic
   */
  save(): string {
    if (this.isDeleted) {
      this.deletedAt = new Date();
    }
    return super.save();
  }

  /**
   * Soft delete method
   */
  softDelete(): string {
    this.isDeleted = true;
    return this.save();
  }

  /**
   * Restore soft-deleted entity
   */
  restore(): void {
    this.isDeleted = false;
    this.deletedAt = undefined;
  }
}

/**
 * User entity - Level 3 inheritance (3 levels deep!)
 * Tests: Deep inheritance chain resolution
 */
class User extends SoftDeletableEntity {
  username?: string;
  email?: string;
  passwordHash?: string;

  /**
   * Override save with user-specific validation
   */
  save(): string {
    if (!this.validateEmail()) {
      throw new Error("Invalid email");
    }
    return super.save();
  }

  /**
   * Override validation with user rules
   */
  validate(): boolean {
    if (!this.username || !this.email) {
      return false;
    }
    return super.validate();
  }

  /**
   * User-specific email validation
   */
  private validateEmail(): boolean {
    return this.email ? this.email.includes("@") : false;
  }

  /**
   * Get display name
   */
  getDisplayName(): string {
    return this.username || "Unknown";
  }
}

/**
 * Admin user - Level 4 inheritance (4 levels deep!)
 * Tests: Extreme depth validation
 */
class AdminUser extends User {
  adminLevel?: number;
  permissions: string[] = [];

  /**
   * Override save with admin logging
   */
  save(): string {
    const result = super.save();
    this.logAdminAction("save");
    return result;
  }

  /**
   * Admin-specific logging
   */
  private logAdminAction(action: string): void {
    console.log(`Admin action: ${action} by ${this.username}`);
  }

  /**
   * Grant permission to admin
   */
  grantPermission(permission: string): void {
    if (!this.permissions.includes(permission)) {
      this.permissions.push(permission);
    }
  }
}

/**
 * Super admin user - Level 5 inheritance (5 levels deep!)
 * Tests: EXTREME depth - inherits from 5 ancestors
 */
class SuperAdminUser extends AdminUser {
  canDeleteUsers: boolean = true;

  /**
   * Super admin save with extra logging
   */
  save(): string {
    console.log(`SuperAdmin ${this.username} saving`);
    return super.save();
  }

  /**
   * Super admin privilege - delete other users
   */
  deleteUser(user: User): void {
    if (this.canDeleteUsers) {
      user.softDelete();
    }
  }
}

// ==============================================================================
// Interface Extension Chains (3+ levels)
// ==============================================================================

/**
 * Base identifiable interface
 */
interface IIdentifiable {
  id: number;
}

/**
 * Timestampable interface - Level 1 extension
 */
interface ITimestampable extends IIdentifiable {
  createdAt: Date;
  updatedAt: Date;
}

/**
 * Auditable interface - Level 2 extension
 * Tests: Interface inheritance chain resolution
 */
interface IAuditable extends ITimestampable {
  createdBy: number;
  updatedBy: number;
  auditLog: string[];
}

/**
 * Versioned interface - Level 3 extension (3 levels deep!)
 * Tests: Deep interface inheritance
 */
interface IVersioned extends IAuditable {
  version: number;
  versionHistory: Array<{ version: number; timestamp: Date }>;
}

/**
 * Class implementing deep interface chain
 */
class VersionedDocument implements IVersioned {
  id: number = 0;
  createdAt: Date = new Date();
  updatedAt: Date = new Date();
  createdBy: number = 0;
  updatedBy: number = 0;
  auditLog: string[] = [];
  version: number = 1;
  versionHistory: Array<{ version: number; timestamp: Date }> = [];

  /**
   * Increment version
   */
  incrementVersion(): void {
    this.version++;
    this.versionHistory.push({
      version: this.version,
      timestamp: new Date()
    });
  }
}

// ==============================================================================
// Deeply Nested Classes (3+ levels)
// ==============================================================================

/**
 * Outer container class - Level 0
 */
class OuterContainer {
  outerAttribute: string = "outer";

  /**
   * Outer method
   */
  outerMethod(): string {
    return "outer method";
  }

  /**
   * Middle nested class - Level 1
   * Symbol path should be: OuterContainer.MiddleContainer
   */
  static MiddleContainer = class {
    middleAttribute: string = "middle";

    /**
     * Middle method
     */
    middleMethod(): string {
      return "middle method";
    }

    /**
     * Inner nested class - Level 2
     * Symbol path should be: OuterContainer.MiddleContainer.InnerContainer
     */
    static InnerContainer = class {
      innerAttribute: string = "inner";

      /**
       * Inner method
       */
      innerMethod(): string {
        return "inner method";
      }

      /**
       * Deep nested class - Level 3 (children-of-children resolution!)
       * Symbol path should be: OuterContainer.MiddleContainer.InnerContainer.DeepNested
       */
      static DeepNested = class {
        deepAttribute: string = "deep";

        /**
         * Deep method
         */
        deepMethod(): string {
          return "deep method";
        }

        /**
         * Access ancestor classes
         */
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

// ==============================================================================
// Nested Namespaces with Classes (TypeScript-specific)
// ==============================================================================

namespace Application {
  /**
   * Base namespace class
   */
  export class BaseService {
    serviceName: string = "base";

    execute(): string {
      return "executing base service";
    }
  }

  /**
   * Nested namespace - Level 1
   */
  export namespace Core {
    /**
     * Core service extending base
     */
    export class CoreService extends BaseService {
      serviceName: string = "core";

      execute(): string {
        return `${super.execute()} + core`;
      }
    }

    /**
     * Deeper nested namespace - Level 2
     */
    export namespace Advanced {
      /**
       * Advanced service - 2 levels of inheritance within namespaces
       */
      export class AdvancedService extends CoreService {
        serviceName: string = "advanced";

        execute(): string {
          return `${super.execute()} + advanced`;
        }
      }
    }
  }
}

// ==============================================================================
// Generic Classes with Constraints and Inheritance
// ==============================================================================

/**
 * Generic repository base
 */
class Repository<T extends BaseEntity> {
  protected modelClass?: new () => T;

  /**
   * Find by ID
   */
  findById(id: number): string {
    return `Finding ${this.modelClass?.name || "Entity"} by ID ${id}`;
  }

  /**
   * Find all entities
   */
  findAll(): string {
    return `Finding all ${this.modelClass?.name || "Entities"}`;
  }

  /**
   * Create entity
   */
  create(data: Partial<T>): T | undefined {
    if (this.modelClass) {
      const instance = new this.modelClass();
      Object.assign(instance, data);
      return instance;
    }
    return undefined;
  }
}

/**
 * User repository extending generic base
 */
class UserRepository extends Repository<User> {
  modelClass = User;

  /**
   * User-specific finder
   */
  findByUsername(username: string): string {
    return `Finding user by username: ${username}`;
  }

  /**
   * Find active users
   */
  findActiveUsers(): string {
    return `Finding active users`;
  }
}

/**
 * Admin repository - 2 levels of generic inheritance
 */
class AdminUserRepository extends UserRepository {
  modelClass = AdminUser;

  /**
   * Admin-specific query
   */
  findAdminsWithLevel(level: number): string {
    return `Finding admins with level ${level}`;
  }
}

// ==============================================================================
// Abstract Class Patterns with Inheritance
// ==============================================================================

/**
 * Abstract service base with template method pattern
 */
abstract class AbstractService {
  /**
   * Template method
   */
  execute(): string {
    this.validateInput();
    const result = this.perform();
    this.cleanup();
    return result;
  }

  /**
   * Hook method - can be overridden
   */
  protected validateInput(): void {
    // Default implementation
  }

  /**
   * Abstract method - must be implemented
   */
  protected abstract perform(): string;

  /**
   * Hook method - can be overridden
   */
  protected cleanup(): void {
    // Default implementation
  }
}

/**
 * Concrete service implementing abstract methods
 */
class UserService extends AbstractService {
  /**
   * Override validation
   */
  protected validateInput(): void {
    console.log("Validating user input");
  }

  /**
   * Implement abstract perform method
   */
  protected perform(): string {
    return "Performing user operation";
  }

  /**
   * Override cleanup
   */
  protected cleanup(): void {
    console.log("Cleaning up user resources");
  }
}

/**
 * Enhanced service - 2 levels deep from abstract base
 */
class EnhancedUserService extends UserService {
  /**
   * Enhanced implementation
   */
  protected perform(): string {
    const baseResult = super.perform();
    return `${baseResult} with enhancements`;
  }
}

// ==============================================================================
// Mixin Pattern (TypeScript-specific)
// ==============================================================================

/**
 * Loggable mixin
 */
type Constructor<T = {}> = new (...args: any[]) => T;

function Loggable<TBase extends Constructor>(Base: TBase) {
  return class extends Base {
    log(message: string): void {
      console.log(`[${this.constructor.name}] ${message}`);
    }
  };
}

/**
 * Cacheable mixin
 */
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

/**
 * Entity with multiple mixins applied
 */
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

// ==============================================================================
// Export for testing
// ==============================================================================

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
  MixedEntity
};
