/**
 * Order model.
 */

export interface Order {
  id: number;
  userId: number;
  status: string;
  createdAt?: Date;
}

export interface OrderProcessDTO {
  orderId: string;
  format: string; // TAINTED - Command Injection vector
}

export interface OrderExportDTO {
  orderId: string;
  filename: string; // TAINTED - Path Traversal vector
}
