/**
 * Order repository - HOP 8: Order data access.
 *
 * Handles order database operations.
 */

import { BaseRepository } from './base.repository';
import { CommandRunner } from '../core/command.runner';

export class OrderRepository extends BaseRepository {
  private commandRunner: CommandRunner;

  constructor() {
    super();
    this.commandRunner = new CommandRunner();
  }

  /**
   * Process order with format.
   *
   * @param orderId - Order ID
   * @param format - TAINTED format
   */
  processOrder(orderId: string, format: string): any {
    return this.commandRunner.convertFormat(orderId, format);
  }

  /**
   * Export order to file.
   *
   * @param orderId - Order ID
   * @param filename - TAINTED filename
   */
  exportOrder(orderId: string, filename: string): any {
    return this.commandRunner.exportToFile(orderId, filename);
  }
}
