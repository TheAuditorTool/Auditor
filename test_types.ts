// Test file for TypeScript type extraction

// Basic types
const str: string = "hello";
let num: number = 42;
const arr: string[] = [];
const tuple: [string, number] = ["test", 1];

// Any and unknown types
let dangerous: any = {};
let safer: unknown = {};

// Generic types
const list: Array<string> = [];
const map: Map<string, number> = new Map();

// Function with types
function test(a: string, b?: number): boolean {
    return a.length > 0;
}

// Arrow function with types
const arrow = (x: string): string => x.toUpperCase();

// Interface
interface User {
    id: number;
    name: string;
    email?: string;
}

// Type alias
type Status = "pending" | "approved" | "rejected";

// Class with types
class Service {
    private apiKey: string;
    public endpoint: string = "https://api.example.com";

    constructor(key: string) {
        this.apiKey = key;
    }

    async fetch<T>(path: string): Promise<T> {
        const response = await fetch(this.endpoint + path);
        return response.json() as T;
    }
}

// Generic function
function identity<T>(x: T): T {
    return x;
}

// Complex nested types
interface ApiResponse<T> {
    data: T;
    status: number;
    error?: {
        code: string;
        message: string;
    };
}

// Type with extends
interface Admin extends User {
    permissions: string[];
}

// Express-like request/response for testing taint
import { Request, Response } from 'express';

function handler(req: Request, res: Response): void {
    const userInput = req.body.name; // Source
    res.send(userInput); // Sink - should be detected
}