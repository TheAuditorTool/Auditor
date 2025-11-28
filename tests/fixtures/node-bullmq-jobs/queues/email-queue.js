const { Queue } = require("bullmq");
const { getQueueConnection } = require("../config/redis");

const emailQueue = new Queue("email", {
  ...getQueueConnection(),
  defaultJobOptions: {
    attempts: 3,
    backoff: {
      type: "exponential",
      delay: 1000,
    },
    removeOnComplete: {
      age: 3600,
      count: 1000,
    },
    removeOnFail: {
      age: 7 * 24 * 3600,
    },
  },
});

async function sendWelcomeEmail(userData) {
  return await emailQueue.add(
    "welcome",
    {
      to: userData.email,
      name: userData.name,
      userId: userData.userId,
      timestamp: new Date().toISOString(),
    },
    {
      priority: 1,
      attempts: 5,
      backoff: {
        type: "exponential",
        delay: 2000,
      },
    },
  );
}

async function sendPasswordResetEmail(email, resetToken, expiresAt) {
  return await emailQueue.add(
    "password-reset",
    {
      to: email,
      resetToken,
      expiresAt,
      timestamp: new Date().toISOString(),
    },
    {
      priority: 1,
      attempts: 3,
      removeOnComplete: true,
    },
  );
}

async function sendOrderConfirmationEmail(orderData) {
  return await emailQueue.add(
    "order-confirmation",
    {
      to: orderData.customerEmail,
      orderNumber: orderData.orderNumber,
      items: orderData.items,
      total: orderData.total,
      shippingAddress: orderData.shippingAddress,
      timestamp: new Date().toISOString(),
    },
    {
      priority: 2,
      attempts: 3,
    },
  );
}

async function sendNewsletter(newsletterData, subscriberEmails) {
  const jobs = subscriberEmails.map((email, index) => ({
    name: "newsletter",
    data: {
      to: email,
      subject: newsletterData.subject,
      content: newsletterData.content,
      unsubscribeToken: newsletterData.unsubscribeTokens[index],
    },
    opts: {
      priority: 10,
      attempts: 2,
      delay: index * 100,
    },
  }));

  return await emailQueue.addBulk(jobs);
}

async function schedulePromotionalEmail(emailData, sendAt) {
  const delay = sendAt.getTime() - Date.now();

  return await emailQueue.add(
    "promotional",
    {
      to: emailData.recipients,
      subject: emailData.subject,
      content: emailData.content,
      campaignId: emailData.campaignId,
    },
    {
      priority: 5,
      delay: Math.max(0, delay),
      attempts: 3,
    },
  );
}

async function sendEmailVerification(email, verificationToken) {
  return await emailQueue.add(
    "email-verification",
    {
      to: email,
      verificationToken,
      expiresAt: Date.now() + 24 * 60 * 60 * 1000,
    },
    {
      priority: 1,
      attempts: 5,
      removeOnComplete: true,
    },
  );
}

async function sendTransactionalEmails(emailsData) {
  const jobs = emailsData.map((email) => ({
    name: "transactional",
    data: {
      to: email.recipient,
      subject: email.subject,
      template: email.template,
      templateData: email.data,
      trackingId: email.trackingId,
    },
    opts: {
      priority: 2,
      attempts: 3,
    },
  }));

  return await emailQueue.addBulk(jobs);
}

async function retryFailedEmail(jobId) {
  const job = await emailQueue.getJob(jobId);

  if (job && (await job.isFailed())) {
    return await job.retry();
  }

  throw new Error("Job not found or not failed");
}

async function getEmailQueueStats() {
  const [waiting, active, completed, failed, delayed] = await Promise.all([
    emailQueue.getWaitingCount(),
    emailQueue.getActiveCount(),
    emailQueue.getCompletedCount(),
    emailQueue.getFailedCount(),
    emailQueue.getDelayedCount(),
  ]);

  return {
    waiting,
    active,
    completed,
    failed,
    delayed,
    total: waiting + active + completed + failed + delayed,
  };
}

async function cleanCompletedJobs(ageInHours = 24) {
  const grace = ageInHours * 60 * 60 * 1000;
  const timestamp = Date.now() - grace;

  return await emailQueue.clean(timestamp, 1000, "completed");
}

async function pauseEmailQueue() {
  return await emailQueue.pause();
}

async function resumeEmailQueue() {
  return await emailQueue.resume();
}

async function getFailedJobs(limit = 100) {
  return await emailQueue.getFailed(0, limit);
}

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
  closeEmailQueue,
};
