/**
 * Notification service - Additional service layer.
 *
 * Handles notifications and callbacks.
 */

export class NotificationService {
  /**
   * Send callback to URL.
   *
   * @param url - TAINTED URL - SSRF vector
   * @param payload - Data to send
   */
  async sendCallback(url: string, payload: any): Promise<any> {
    // Would flow to external API adapter
    return { status: 'sent', url, payload };
  }

  /**
   * Notify user.
   *
   * @param userId - User identifier
   * @param message - TAINTED message
   */
  async notifyUser(userId: string, message: string): Promise<any> {
    return { status: 'notified', userId, message };
  }
}
