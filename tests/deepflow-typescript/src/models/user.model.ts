/**
 * User model.
 */

export interface User {
  id: number;
  name: string;
  email: string;
  createdAt?: Date;
}

export interface UserCreateDTO {
  name: string;
  email: string;
}

export interface UserUpdateDTO {
  name?: string;
  email?: string;
  settings?: any; // TAINTED - Prototype Pollution vector
}
