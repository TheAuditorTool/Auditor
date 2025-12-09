/**
 * Order service - HOP 3: Business logic for orders.
 *
 * Handles order processing with command injection vulnerability.
 */

import { DataTransformer } from '../processors/data.transformer';

export class OrderService {
  private transformer: DataTransformer;

  constructor() {
    this.transformer = new DataTransformer();
  }

  /**
   * Process order with custom format.
   *
   * HOP 3: Passes tainted format to processor.
   *
   * @param orderId - Order identifier
   * @param outputFormat - TAINTED format - Command Injection vector
   */
  async process(orderId: string, outputFormat: string): Promise<any> {
    return this.transformer.prepareOrderProcess(orderId, outputFormat);
  }

  /**
   * Export order to file.
   *
   * @param orderId - Order identifier
   * @param filename - TAINTED filename
   */
  async export(orderId: string, filename: string): Promise<any> {
    return this.transformer.prepareOrderExport(orderId, filename);
  }

  /**
   * Get order status.
   *
   * @param orderId - Order identifier
   */
  async getStatus(orderId: string): Promise<any> {
    return this.transformer.prepareStatusQuery(orderId);
  }
}
