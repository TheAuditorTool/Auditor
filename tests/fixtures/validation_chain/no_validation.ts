/**
 * Test Fixture: No Validation Chain
 *
 * Demonstrates an endpoint with NO validation:
 * 1. No middleware validation
 * 2. No type checks on req.body
 * 3. Raw data passed directly to service layer
 *
 * Expected: chain_status = "no_validation"
 */
import express, { Request, Response } from 'express';

// No Zod schema - direct typing without runtime validation
interface CommentInput {
  postId: string;
  authorId: string;
  content: string;
}

// Comment service - takes typed input but no validation at entry
class CommentService {
  constructor(private repository: CommentRepository) {}

  async addComment(data: CommentInput): Promise<Comment> {
    // Assumes data is valid, but no runtime check was done
    return this.repository.save(data);
  }
}

// Comment repository
class CommentRepository {
  private comments: Comment[] = [];
  private nextId = 1;

  async save(data: CommentInput): Promise<Comment> {
    const comment: Comment = {
      id: this.nextId++,
      ...data,
      createdAt: new Date(),
    };
    this.comments.push(comment);
    return comment;
  }
}

interface Comment extends CommentInput {
  id: number;
  createdAt: Date;
}

// Express app setup
const app = express();
app.use(express.json());

const commentRepository = new CommentRepository();
const commentService = new CommentService(commentRepository);

// Route with NO validation
// Entry: No middleware - req.body used directly
// Hop 1: commentService.addComment - typed but not validated
// Hop 2: commentRepository.save - typed but not validated
//
// SECURITY ISSUE: Any malformed JSON can reach the database
// Example attack: { "postId": "<script>alert('xss')</script>" }
app.post(
  '/api/comments',
  async (req: Request, res: Response) => {
    // req.body is typed as `any` here - no validation
    const commentData: CommentInput = req.body;
    const comment = await commentService.addComment(commentData);
    res.status(201).json(comment);
  }
);

// Another endpoint without validation - demonstrates multiple issues
app.put(
  '/api/comments/:id',
  async (req: Request, res: Response) => {
    // No param validation, no body validation
    const id = parseInt(req.params.id, 10);
    const updateData = req.body;

    // Direct database update without any checks
    console.log(`Updating comment ${id} with:`, updateData);
    res.json({ id, ...updateData, updated: true });
  }
);

// DELETE without auth check - security boundary issue
app.delete(
  '/api/comments/:id',
  async (req: Request, res: Response) => {
    // No authentication, no authorization, no validation
    const id = req.params.id;
    console.log(`Deleting comment: ${id}`);
    res.status(204).send();
  }
);

export { app, CommentInput };
