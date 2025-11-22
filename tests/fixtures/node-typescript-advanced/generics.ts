/**
 * TypeScript Generics and Advanced Type System Fixture
 *
 * Tests extraction of:
 * - Generic type parameters with constraints (<T extends User>)
 * - Nested generics (Partial<Record<keyof T, string>>)
 * - Mapped types (DeepPartial<T>, Readonly<T>)
 * - Conditional types (T extends U ? X : Y)
 * - Infer keyword in conditional types
 * - Utility types (Pick, Omit, Exclude, Extract)
 * - Generic constraints (extends, keyof)
 *
 * Validates TypeScript's advanced type system extraction.
 */

// ==============================================================================
// Basic Generic Constraints
// ==============================================================================

interface Entity {
  id: number;
  createdAt: Date;
}

interface User extends Entity {
  username: string;
  email: string;
}

interface Post extends Entity {
  title: string;
  content: string;
  authorId: number;
}

/**
 * Generic function with extends constraint.
 * Tests: <T extends Entity> constraint extraction.
 */
function getId<T extends Entity>(entity: T): number {
  return entity.id;
}

/**
 * Generic function with multiple constraints.
 * Tests: <T extends Entity, K extends keyof T>
 */
function getProperty<T extends Entity, K extends keyof T>(
  entity: T,
  key: K
): T[K] {
  return entity[key];
}

// ==============================================================================
// Mapped Types
// ==============================================================================

/**
 * DeepPartial mapped type - makes all properties optional recursively.
 * Tests: Recursive mapped type with conditional.
 */
type DeepPartial<T> = {
  [P in keyof T]?: T[P] extends object ? DeepPartial<T[P]> : T[P];
};

/**
 * DeepReadonly mapped type - makes all properties readonly recursively.
 * Tests: Recursive mapped type.
 */
type DeepReadonly<T> = {
  readonly [P in keyof T]: T[P] extends object ? DeepReadonly<T[P]> : T[P];
};

/**
 * Nullable mapped type - makes all properties nullable.
 * Tests: Mapped type with union.
 */
type Nullable<T> = {
  [P in keyof T]: T[P] | null;
};

/**
 * Function using DeepPartial.
 * Tests: Complex mapped type usage.
 */
function updateUser(user: User, updates: DeepPartial<User>): User {
  return { ...user, ...updates };
}

// ==============================================================================
// Conditional Types
// ==============================================================================

/**
 * Extract array element type.
 * Tests: Conditional type with infer.
 */
type ElementType<T> = T extends (infer U)[] ? U : never;

/**
 * Extract promise value type.
 * Tests: Conditional type with Promise.
 */
type PromiseValue<T> = T extends Promise<infer U> ? U : T;

/**
 * Extract function return type.
 * Tests: Conditional type with function.
 */
type ReturnTypeOf<T> = T extends (...args: any[]) => infer R ? R : never;

/**
 * Function using conditional type.
 * Tests: Usage of ElementType.
 */
function getFirstElement<T extends any[]>(
  array: T
): ElementType<T> | undefined {
  return array[0];
}

// ==============================================================================
// Advanced Generic Constraints
// ==============================================================================

/**
 * Generic class with multiple constraints.
 * Tests: Class with complex generic constraints.
 */
class DataStore<T extends Entity, K extends keyof T = 'id'> {
  private data: Map<T[K], T> = new Map();

  /**
   * Add item to store.
   */
  add(item: T): void {
    this.data.set(item['id'] as T[K], item);
  }

  /**
   * Get item by key.
   */
  get(key: T[K]): T | undefined {
    return this.data.get(key);
  }

  /**
   * Find items matching predicate.
   */
  find(predicate: (item: T) => boolean): T[] {
    const results: T[] = [];
    for (const item of this.data.values()) {
      if (predicate(item)) {
        results.push(item);
      }
    }
    return results;
  }
}

// ==============================================================================
// Utility Type Compositions
// ==============================================================================

/**
 * Pick specific properties from type.
 * Tests: Pick<T, K> utility type.
 */
type UserCredentials = Pick<User, 'username' | 'email'>;

/**
 * Omit specific properties from type.
 * Tests: Omit<T, K> utility type.
 */
type UserWithoutDates = Omit<User, 'createdAt'>;

/**
 * Partial + Pick composition.
 * Tests: Nested utility types.
 */
type PartialUserCredentials = Partial<Pick<User, 'username' | 'email'>>;

/**
 * Function using utility types.
 */
function createUserCredentials(
  username: string,
  email: string
): UserCredentials {
  return { username, email };
}

// ==============================================================================
// Constrained Generic Functions
// ==============================================================================

/**
 * Merge two objects of same type.
 * Tests: Generic function with constraint.
 */
function merge<T extends object>(obj1: T, obj2: Partial<T>): T {
  return { ...obj1, ...obj2 };
}

/**
 * Map object values with transformation.
 * Tests: Complex generic with keyof and mapped type.
 */
function mapValues<T extends object, U>(
  obj: T,
  mapper: (value: T[keyof T]) => U
): Record<keyof T, U> {
  const result = {} as Record<keyof T, U>;
  for (const key in obj) {
    if (obj.hasOwnProperty(key)) {
      result[key] = mapper(obj[key]);
    }
  }
  return result;
}

/**
 * Pick properties from object dynamically.
 * Tests: Generic with array of keys.
 */
function pick<T, K extends keyof T>(obj: T, keys: K[]): Pick<T, K> {
  const result = {} as Pick<T, K>;
  for (const key of keys) {
    result[key] = obj[key];
  }
  return result;
}

// ==============================================================================
// Generic Interfaces with Constraints
// ==============================================================================

/**
 * Repository interface with generic constraints.
 * Tests: Interface with generic constraints.
 */
interface IRepository<T extends Entity> {
  findById(id: number): Promise<T | null>;
  findAll(): Promise<T[]>;
  create(data: Omit<T, 'id' | 'createdAt'>): Promise<T>;
  update(id: number, data: Partial<T>): Promise<T>;
  delete(id: number): Promise<boolean>;
}

/**
 * User repository implementing generic interface.
 * Tests: Class implementing generic interface.
 */
class UserRepository implements IRepository<User> {
  async findById(id: number): Promise<User | null> {
    // Implementation
    return null;
  }

  async findAll(): Promise<User[]> {
    return [];
  }

  async create(data: Omit<User, 'id' | 'createdAt'>): Promise<User> {
    return {
      id: 0,
      createdAt: new Date(),
      ...data
    };
  }

  async update(id: number, data: Partial<User>): Promise<User> {
    const user = await this.findById(id);
    if (!user) throw new Error('User not found');
    return { ...user, ...data };
  }

  async delete(id: number): Promise<boolean> {
    return true;
  }
}

// ==============================================================================
// Recursive Generic Types
// ==============================================================================

/**
 * Tree node with generic payload.
 * Tests: Recursive generic type.
 */
interface TreeNode<T> {
  value: T;
  children: TreeNode<T>[];
  parent?: TreeNode<T>;
}

/**
 * Traverse tree recursively.
 * Tests: Function with recursive generic type.
 */
function traverseTree<T>(
  node: TreeNode<T>,
  visitor: (value: T) => void
): void {
  visitor(node.value);
  for (const child of node.children) {
    traverseTree(child, visitor);
  }
}

// ==============================================================================
// Generic Type Guards
// ==============================================================================

/**
 * Type guard for arrays.
 * Tests: Generic type guard function.
 */
function isArray<T>(value: T | T[]): value is T[] {
  return Array.isArray(value);
}

/**
 * Type guard with constraint.
 * Tests: Generic type guard with extends.
 */
function hasId<T extends { id?: number }>(obj: T): obj is T & { id: number } {
  return typeof obj.id === 'number';
}

// ==============================================================================
// Complex Generic Compositions
// ==============================================================================

/**
 * Event handler type with generics.
 * Tests: Complex generic type alias.
 */
type EventHandler<T extends string, P = any> = {
  type: T;
  payload: P;
  timestamp: Date;
};

/**
 * Event emitter with generic events.
 * Tests: Class with complex generic event system.
 */
class EventEmitter<T extends string> {
  private handlers: Map<T, Array<(payload: any) => void>> = new Map();

  on<P>(event: T, handler: (payload: P) => void): void {
    if (!this.handlers.has(event)) {
      this.handlers.set(event, []);
    }
    this.handlers.get(event)!.push(handler);
  }

  emit<P>(event: T, payload: P): void {
    const handlers = this.handlers.get(event);
    if (handlers) {
      for (const handler of handlers) {
        handler(payload);
      }
    }
  }
}

// ==============================================================================
// Generic Builders and Factories
// ==============================================================================

/**
 * Builder pattern with generics.
 * Tests: Builder pattern with type safety.
 */
class Builder<T> {
  private data: Partial<T> = {};

  set<K extends keyof T>(key: K, value: T[K]): Builder<T> {
    this.data[key] = value;
    return this;
  }

  build(): T {
    return this.data as T;
  }
}

/**
 * Generic factory function.
 * Tests: Factory with type parameter.
 */
function createFactory<T>(constructor: new (...args: any[]) => T) {
  return function(...args: any[]): T {
    return new constructor(...args);
  };
}

// ==============================================================================
// Variadic Tuple Types
// ==============================================================================

/**
 * Function with variadic tuples.
 * Tests: Rest parameters with tuple types.
 */
function concat<T extends any[], U extends any[]>(
  arr1: T,
  arr2: U
): [...T, ...U] {
  return [...arr1, ...arr2];
}

/**
 * Curry function with tuple types.
 * Tests: Complex tuple manipulation.
 */
function curry<T extends any[], R>(
  fn: (...args: T) => R
): (...args: T) => R {
  return (...args: T) => fn(...args);
}

// ==============================================================================
// Index Signatures with Generics
// ==============================================================================

/**
 * Dictionary type with generic value.
 * Tests: Index signature with generic.
 */
interface Dictionary<T> {
  [key: string]: T;
}

/**
 * Function operating on dictionary.
 * Tests: Generic function with index signature type.
 */
function getDictionaryKeys<T>(dict: Dictionary<T>): string[] {
  return Object.keys(dict);
}

/**
 * Transform dictionary values.
 * Tests: Dictionary transformation with generics.
 */
function transformDictionary<T, U>(
  dict: Dictionary<T>,
  transformer: (value: T) => U
): Dictionary<U> {
  const result: Dictionary<U> = {};
  for (const key in dict) {
    if (dict.hasOwnProperty(key)) {
      result[key] = transformer(dict[key]);
    }
  }
  return result;
}

// ==============================================================================
// Generic Class with Static Methods
// ==============================================================================

/**
 * Generic class with static factory methods.
 * Tests: Static methods in generic class.
 */
class Container<T> {
  constructor(private value: T) {}

  getValue(): T {
    return this.value;
  }

  static of<U>(value: U): Container<U> {
    return new Container(value);
  }

  static empty<U>(): Container<U | null> {
    return new Container<U | null>(null);
  }

  map<U>(fn: (value: T) => U): Container<U> {
    return new Container(fn(this.value));
  }
}

// ==============================================================================
// Export for testing
// ==============================================================================

export {
  getId,
  getProperty,
  updateUser,
  getFirstElement,
  DataStore,
  createUserCredentials,
  merge,
  mapValues,
  pick,
  UserRepository,
  traverseTree,
  isArray,
  hasId,
  EventEmitter,
  Builder,
  createFactory,
  concat,
  curry,
  getDictionaryKeys,
  transformDictionary,
  Container
};

export type {
  Entity,
  User,
  Post,
  DeepPartial,
  DeepReadonly,
  Nullable,
  ElementType,
  PromiseValue,
  ReturnTypeOf,
  UserCredentials,
  UserWithoutDates,
  IRepository,
  TreeNode,
  EventHandler,
  Dictionary
};
