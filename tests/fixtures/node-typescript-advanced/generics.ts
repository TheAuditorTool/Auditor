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

function getId<T extends Entity>(entity: T): number {
  return entity.id;
}

function getProperty<T extends Entity, K extends keyof T>(
  entity: T,
  key: K,
): T[K] {
  return entity[key];
}

type DeepPartial<T> = {
  [P in keyof T]?: T[P] extends object ? DeepPartial<T[P]> : T[P];
};

type DeepReadonly<T> = {
  readonly [P in keyof T]: T[P] extends object ? DeepReadonly<T[P]> : T[P];
};

type Nullable<T> = {
  [P in keyof T]: T[P] | null;
};

function updateUser(user: User, updates: DeepPartial<User>): User {
  return { ...user, ...updates };
}

type ElementType<T> = T extends (infer U)[] ? U : never;

type PromiseValue<T> = T extends Promise<infer U> ? U : T;

type ReturnTypeOf<T> = T extends (...args: any[]) => infer R ? R : never;

function getFirstElement<T extends any[]>(
  array: T,
): ElementType<T> | undefined {
  return array[0];
}

class DataStore<T extends Entity, K extends keyof T = "id"> {
  private data: Map<T[K], T> = new Map();

  add(item: T): void {
    this.data.set(item["id"] as T[K], item);
  }

  get(key: T[K]): T | undefined {
    return this.data.get(key);
  }

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

type UserCredentials = Pick<User, "username" | "email">;

type UserWithoutDates = Omit<User, "createdAt">;

type PartialUserCredentials = Partial<Pick<User, "username" | "email">>;

function createUserCredentials(
  username: string,
  email: string,
): UserCredentials {
  return { username, email };
}

function merge<T extends object>(obj1: T, obj2: Partial<T>): T {
  return { ...obj1, ...obj2 };
}

function mapValues<T extends object, U>(
  obj: T,
  mapper: (value: T[keyof T]) => U,
): Record<keyof T, U> {
  const result = {} as Record<keyof T, U>;
  for (const key in obj) {
    if (obj.hasOwnProperty(key)) {
      result[key] = mapper(obj[key]);
    }
  }
  return result;
}

function pick<T, K extends keyof T>(obj: T, keys: K[]): Pick<T, K> {
  const result = {} as Pick<T, K>;
  for (const key of keys) {
    result[key] = obj[key];
  }
  return result;
}

interface IRepository<T extends Entity> {
  findById(id: number): Promise<T | null>;
  findAll(): Promise<T[]>;
  create(data: Omit<T, "id" | "createdAt">): Promise<T>;
  update(id: number, data: Partial<T>): Promise<T>;
  delete(id: number): Promise<boolean>;
}

class UserRepository implements IRepository<User> {
  async findById(id: number): Promise<User | null> {
    return null;
  }

  async findAll(): Promise<User[]> {
    return [];
  }

  async create(data: Omit<User, "id" | "createdAt">): Promise<User> {
    return {
      id: 0,
      createdAt: new Date(),
      ...data,
    };
  }

  async update(id: number, data: Partial<User>): Promise<User> {
    const user = await this.findById(id);
    if (!user) throw new Error("User not found");
    return { ...user, ...data };
  }

  async delete(id: number): Promise<boolean> {
    return true;
  }
}

interface TreeNode<T> {
  value: T;
  children: TreeNode<T>[];
  parent?: TreeNode<T>;
}

function traverseTree<T>(node: TreeNode<T>, visitor: (value: T) => void): void {
  visitor(node.value);
  for (const child of node.children) {
    traverseTree(child, visitor);
  }
}

function isArray<T>(value: T | T[]): value is T[] {
  return Array.isArray(value);
}

function hasId<T extends { id?: number }>(obj: T): obj is T & { id: number } {
  return typeof obj.id === "number";
}

type EventHandler<T extends string, P = any> = {
  type: T;
  payload: P;
  timestamp: Date;
};

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

function createFactory<T>(constructor: new (...args: any[]) => T) {
  return function (...args: any[]): T {
    return new constructor(...args);
  };
}

function concat<T extends any[], U extends any[]>(
  arr1: T,
  arr2: U,
): [...T, ...U] {
  return [...arr1, ...arr2];
}

function curry<T extends any[], R>(fn: (...args: T) => R): (...args: T) => R {
  return (...args: T) => fn(...args);
}

interface Dictionary<T> {
  [key: string]: T;
}

function getDictionaryKeys<T>(dict: Dictionary<T>): string[] {
  return Object.keys(dict);
}

function transformDictionary<T, U>(
  dict: Dictionary<T>,
  transformer: (value: T) => U,
): Dictionary<U> {
  const result: Dictionary<U> = {};
  for (const key in dict) {
    if (dict.hasOwnProperty(key)) {
      result[key] = transformer(dict[key]);
    }
  }
  return result;
}

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
  Container,
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
  Dictionary,
};
