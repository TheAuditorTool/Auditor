/**
 * Test Fixture: Intact Validation Chain
 *
 * Demonstrates a properly typed validation chain where:
 * 1. Zod validates at entry point
 * 2. Type is preserved through userService.createUser()
 * 3. Type is preserved through userRepository.insert()
 *
 * Expected: chain_status = "intact"
 */
import express, { Request, Response } from 'express';
import { z } from 'zod';

// Zod schema for user creation
const CreateUserSchema = z.object({
  email: z.string().email(),
  name: z.string().min(2),
  age: z.number().min(18),
});

// Type inference from Zod schema
type CreateUserInput = z.infer<typeof CreateUserSchema>;

// Validation middleware
function validateBody(schema: z.ZodSchema) {
  return (req: Request, res: Response, next: Function) => {
    const result = schema.safeParse(req.body);
    if (!result.success) {
      return res.status(400).json({ errors: result.error.errors });
    }
    req.body = result.data;
    next();
  };
}

// User service - preserves CreateUserInput type
class UserService {
  constructor(private repository: UserRepository) {}

  async createUser(data: CreateUserInput): Promise<User> {
    // Type preserved here
    return this.repository.insert(data);
  }
}

// User repository - preserves CreateUserInput type
class UserRepository {
  async insert(data: CreateUserInput): Promise<User> {
    // Type preserved all the way to database layer
    console.log(`Inserting user: ${data.email}`);
    return {
      id: 1,
      ...data,
      createdAt: new Date(),
    };
  }
}

interface User extends CreateUserInput {
  id: number;
  createdAt: Date;
}

// Express app setup
const app = express();
app.use(express.json());

const userRepository = new UserRepository();
const userService = new UserService(userRepository);

// Route with intact validation chain
// Entry: validateBody middleware validates with Zod
// Hop 1: userService.createUser preserves CreateUserInput type
// Hop 2: userRepository.insert preserves CreateUserInput type
app.post(
  '/api/users',
  validateBody(CreateUserSchema),
  async (req: Request, res: Response) => {
    const userData: CreateUserInput = req.body;
    const user = await userService.createUser(userData);
    res.json(user);
  }
);

export { app, CreateUserSchema, CreateUserInput };
