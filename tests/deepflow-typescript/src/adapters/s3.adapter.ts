/**
 * S3 adapter - HOP 11: File storage integration.
 *
 * Handles file operations with command injection vulnerability.
 */

import { CommandRunner } from '../core/command.runner';

export class S3Adapter {
  private commandRunner: CommandRunner;

  constructor() {
    this.commandRunner = new CommandRunner();
  }

  /**
   * Convert and upload.
   *
   * HOP 11: Passes TAINTED format to command runner.
   *
   * @param orderId - Order ID
   * @param format - TAINTED format - Command Injection vector
   */
  convertAndUpload(orderId: string, format: string): any {
    // Convert using command runner (HOP 12+)
    const converted = this.commandRunner.convertFormat(orderId, format);
    return {
      status: 'uploaded',
      orderId,
      format,
      converted,
    };
  }

  /**
   * Export to file.
   *
   * @param orderId - Order ID
   * @param filename - TAINTED filename
   */
  exportFile(orderId: string, filename: string): any {
    return this.commandRunner.exportToFile(orderId, filename);
  }

  /**
   * Upload file.
   *
   * @param key - TAINTED key
   * @param content - File content
   */
  upload(key: string, content: Buffer): any {
    // Simulated S3 upload
    return { uploaded: true, key };
  }

  /**
   * Download file.
   *
   * @param key - TAINTED key
   */
  download(key: string): any {
    // Simulated S3 download
    return { content: Buffer.from(''), key };
  }
}
