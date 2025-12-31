/**
 * Command runner - HOP 13: Shell command execution.
 *
 * This is the COMMAND INJECTION SINK. Tainted user input is
 * concatenated into shell commands and executed.
 */

import { exec } from 'child_process';
import { cleanWhitespace } from '../utils/string.utils';

export class CommandRunner {
  private tempDir = '/tmp/orders';

  /**
   * Convert content to specified format.
   *
   * COMMAND INJECTION SINK.
   *
   * @param orderId - Order ID
   * @param format - TAINTED format string
   *
   * VULNERABILITY: exec() with user input allows command injection.
   * Payload: pdf; rm -rf / #
   */
  convertFormat(orderId: string, format: string): Promise<any> {
    return new Promise((resolve, reject) => {
      // Clean whitespace but NOT dangerous chars
      const cleanedFormat = cleanWhitespace(format);

      // VULNERABLE: User-controlled format in command
      const inputFile = `${this.tempDir}/${orderId}.html`;
      const outputFile = `${this.tempDir}/${orderId}.${cleanedFormat}`;
      const cmd = `wkhtmltopdf ${inputFile} ${outputFile} --format ${cleanedFormat}`;

      // COMMAND INJECTION SINK
      exec(cmd, (error, stdout, stderr) => {
        if (error) {
          resolve({ error: error.message, cmd });
        } else {
          resolve({ status: 'converted', outputFile, cmd });
        }
      });
    });
  }

  /**
   * Export to file.
   *
   * COMMAND INJECTION SINK.
   *
   * @param orderId - Order ID
   * @param filename - TAINTED filename
   */
  exportToFile(orderId: string, filename: string): Promise<any> {
    return new Promise((resolve, reject) => {
      // VULNERABLE: User-controlled filename in command
      const cmd = `cp ${this.tempDir}/${orderId}.pdf ${filename}`;

      // COMMAND INJECTION SINK
      exec(cmd, (error, stdout, stderr) => {
        if (error) {
          resolve({ error: error.message });
        } else {
          resolve({ status: 'exported', filename });
        }
      });
    });
  }

  /**
   * Run shell script.
   *
   * COMMAND INJECTION SINK.
   *
   * @param scriptName - Script name
   * @param args - TAINTED arguments
   */
  runScript(scriptName: string, args: string): Promise<any> {
    return new Promise((resolve, reject) => {
      // VULNERABLE: User-controlled arguments
      const cmd = `./scripts/${scriptName} ${args}`;

      // COMMAND INJECTION SINK
      exec(cmd, (error, stdout, stderr) => {
        resolve({ stdout, stderr, error: error?.message });
      });
    });
  }
}
