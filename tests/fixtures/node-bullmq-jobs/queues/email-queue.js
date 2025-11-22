/**
 * Email Queue - Comprehensive email job processing
 * Tests: Queue creation, job scheduling, priority, delays, retries
 */

const { Queue } = require('bullmq');
const { getQueueConnection } = require('../config/redis');

/**
 * Email Queue
 * Tests: Queue instantiation with configuration
 */
const emailQueue = new Queue('email', {
  ...getQueueConnection(),
  defaultJobOptions: {
    attempts: 3,
    backoff: {
      type: 'exponential',
      delay: 1000
    },
    removeOnComplete: {
      age: 3600, // Keep completed jobs for 1 hour
      count: 1000
    },
    removeOnFail: {
      age: 7 * 24 * 3600 // Keep failed jobs for 7 days
    }
  }
});

/**
 * Send welcome email job
 * Tests: Basic job creation with data
 * TAINT FLOW: userData (user input) -> email job data
 */
async function sendWelcomeEmail(userData) {
  return await emailQueue.add(
    'welcome',
    {
      to: userData.email,
      name: userData.name,
      userId: userData.userId,
      timestamp: new Date().toISOString()
    },
    {
      priority: 1, // High priority
      attempts: 5,
      backoff: {
        type: 'exponential',
        delay: 2000
      }
    }
  );
}

/**
 * Send password reset email
 * Tests: Job with sensitive data, high priority
 * TAINT FLOW: resetToken (sensitive) -> email job data
 */
async function sendPasswordResetEmail(email, resetToken, expiresAt) {
  return await emailQueue.add(
    'password-reset',
    {
      to: email,
      resetToken,
      expiresAt,
      timestamp: new Date().toISOString()
    },
    {
      priority: 1, // High priority
      attempts: 3,
      removeOnComplete: true // Remove immediately for security
    }
  );
}

/**
 * Send order confirmation email
 * Tests: Job with nested data structures
 * TAINT FLOW: orderData (user input) -> email job data
 */
async function sendOrderConfirmationEmail(orderData) {
  return await emailQueue.add(
    'order-confirmation',
    {
      to: orderData.customerEmail,
      orderNumber: orderData.orderNumber,
      items: orderData.items,
      total: orderData.total,
      shippingAddress: orderData.shippingAddress,
      timestamp: new Date().toISOString()
    },
    {
      priority: 2, // Medium priority
      attempts: 3
    }
  );
}

/**
 * Send newsletter to subscribers
 * Tests: Bulk job creation, low priority
 */
async function sendNewsletter(newsletterData, subscriberEmails) {
  const jobs = subscriberEmails.map((email, index) => ({
    name: 'newsletter',
    data: {
      to: email,
      subject: newsletterData.subject,
      content: newsletterData.content,
      unsubscribeToken: newsletterData.unsubscribeTokens[index]
    },
    opts: {
      priority: 10, // Low priority
      attempts: 2,
      delay: index * 100 // Stagger emails to avoid rate limits
    }
  }));

  return await emailQueue.addBulk(jobs);
}

/**
 * Schedule promotional email
 * Tests: Delayed job execution
 */
async function schedulePromotionalEmail(emailData, sendAt) {
  const delay = sendAt.getTime() - Date.now();

  return await emailQueue.add(
    'promotional',
    {
      to: emailData.recipients,
      subject: emailData.subject,
      content: emailData.content,
      campaignId: emailData.campaignId
    },
    {
      priority: 5,
      delay: Math.max(0, delay), // Schedule for future
      attempts: 3
    }
  );
}

/**
 * Send email verification
 * Tests: Job with expiration
 */
async function sendEmailVerification(email, verificationToken) {
  return await emailQueue.add(
    'email-verification',
    {
      to: email,
      verificationToken,
      expiresAt: Date.now() + (24 * 60 * 60 * 1000) // 24 hours
    },
    {
      priority: 1,
      attempts: 5,
      removeOnComplete: true
    }
  );
}

/**
 * Send batch of transactional emails
 * Tests: Bulk job creation with different data
 */
async function sendTransactionalEmails(emailsData) {
  const jobs = emailsData.map(email => ({
    name: 'transactional',
    data: {
      to: email.recipient,
      subject: email.subject,
      template: email.template,
      templateData: email.data,
      trackingId: email.trackingId
    },
    opts: {
      priority: 2,
      attempts: 3
    }
  }));

  return await emailQueue.addBulk(jobs);
}

/**
 * Retry failed email job
 * Tests: Manual job retry
 */
async function retryFailedEmail(jobId) {
  const job = await emailQueue.getJob(jobId);

  if (job && await job.isFailed()) {
    return await job.retry();
  }

  throw new Error('Job not found or not failed');
}

/**
 * Get queue statistics
 * Tests: Queue metrics retrieval
 */
async function getEmailQueueStats() {
  const [waiting, active, completed, failed, delayed] = await Promise.all([
    emailQueue.getWaitingCount(),
    emailQueue.getActiveCount(),
    emailQueue.getCompletedCount(),
    emailQueue.getFailedCount(),
    emailQueue.getDelayedCount()
  ]);

  return {
    waiting,
    active,
    completed,
    failed,
    delayed,
    total: waiting + active + completed + failed + delayed
  };
}

/**
 * Clean old completed jobs
 * Tests: Queue maintenance
 */
async function cleanCompletedJobs(ageInHours = 24) {
  const grace = ageInHours * 60 * 60 * 1000;
  const timestamp = Date.now() - grace;

  return await emailQueue.clean(timestamp, 1000, 'completed');
}

/**
 * Pause queue processing
 * Tests: Queue flow control
 */
async function pauseEmailQueue() {
  return await emailQueue.pause();
}

/**
 * Resume queue processing
 * Tests: Queue flow control
 */
async function resumeEmailQueue() {
  return await emailQueue.resume();
}

/**
 * Get failed jobs for analysis
 * Tests: Error analysis
 */
async function getFailedJobs(limit = 100) {
  return await emailQueue.getFailed(0, limit);
}

/**
 * Close queue connection
 * Tests: Resource cleanup
 */
async function closeEmailQueue() {
  await emailQueue.close();
}

module.exports = {
  emailQueue,
  sendWelcomeEmail,
  sendPasswordResetEmail,
  sendOrderConfirmationEmail,
  sendNewsletter,
  schedulePromotionalEmail,
  sendEmailVerification,
  sendTransactionalEmails,
  retryFailedEmail,
  getEmailQueueStats,
  cleanCompletedJobs,
  pauseEmailQueue,
  resumeEmailQueue,
  getFailedJobs,
  closeEmailQueue
};
