/**
 * Email Worker - Processes email jobs from the email queue
 * Tests: Worker creation, job processing, error handling, retries
 */

const { Worker } = require('bullmq');
const { getQueueConnection } = require('../config/redis');
const nodemailer = require('nodemailer');

/**
 * Email transporter configuration
 * Tests: External service configuration
 */
const transporter = nodemailer.createTransporter({
  host: process.env.SMTP_HOST || 'smtp.example.com',
  port: process.env.SMTP_PORT || 587,
  secure: false,
  auth: {
    user: process.env.SMTP_USER || 'user@example.com',
    pass: process.env.SMTP_PASS || 'password'
  }
});

/**
 * Email templates
 * Tests: Template management
 */
const emailTemplates = {
  welcome: (data) => ({
    subject: `Welcome, ${data.name}!`,
    html: `
      <h1>Welcome to our platform!</h1>
      <p>Hi ${data.name},</p>
      <p>Thank you for joining us. We're excited to have you on board.</p>
      <p>Get started by exploring our features.</p>
    `,
    text: `Welcome, ${data.name}! Thank you for joining us.`
  }),

  'password-reset': (data) => ({
    subject: 'Reset Your Password',
    html: `
      <h1>Password Reset Request</h1>
      <p>You requested a password reset. Click the link below:</p>
      <a href="https://example.com/reset?token=${data.resetToken}">Reset Password</a>
      <p>This link expires at ${new Date(data.expiresAt).toLocaleString()}</p>
      <p>If you didn't request this, please ignore this email.</p>
    `,
    text: `Reset your password: https://example.com/reset?token=${data.resetToken}`
  }),

  'order-confirmation': (data) => ({
    subject: `Order Confirmation #${data.orderNumber}`,
    html: `
      <h1>Order Confirmed!</h1>
      <p>Thank you for your order.</p>
      <h2>Order #${data.orderNumber}</h2>
      <h3>Items:</h3>
      <ul>
        ${data.items.map(item => `
          <li>${item.name} x ${item.quantity} - $${item.price}</li>
        `).join('')}
      </ul>
      <p><strong>Total: $${data.total}</strong></p>
      <h3>Shipping Address:</h3>
      <p>${data.shippingAddress.street}<br>
         ${data.shippingAddress.city}, ${data.shippingAddress.state} ${data.shippingAddress.zip}</p>
    `,
    text: `Order #${data.orderNumber} confirmed. Total: $${data.total}`
  }),

  newsletter: (data) => ({
    subject: data.subject,
    html: `
      ${data.content}
      <hr>
      <p><small><a href="https://example.com/unsubscribe?token=${data.unsubscribeToken}">Unsubscribe</a></small></p>
    `,
    text: data.content
  }),

  promotional: (data) => ({
    subject: data.subject,
    html: data.content,
    text: data.content
  }),

  'email-verification': (data) => ({
    subject: 'Verify Your Email Address',
    html: `
      <h1>Verify Your Email</h1>
      <p>Please click the link below to verify your email address:</p>
      <a href="https://example.com/verify?token=${data.verificationToken}">Verify Email</a>
      <p>This link expires in 24 hours.</p>
    `,
    text: `Verify your email: https://example.com/verify?token=${data.verificationToken}`
  }),

  transactional: (data) => {
    // Use template engine with templateData
    return {
      subject: data.subject,
      html: renderTemplate(data.template, data.templateData),
      text: data.subject
    };
  }
};

/**
 * Simple template renderer
 * Tests: Template rendering logic
 */
function renderTemplate(template, data) {
  let html = template;

  for (const [key, value] of Object.entries(data)) {
    html = html.replace(new RegExp(`{{${key}}}`, 'g'), value);
  }

  return html;
}

/**
 * Process email job
 * Tests: Main job processor with error handling
 * TAINT FLOW: job.data.to (user input) -> transporter.sendMail
 */
async function processEmailJob(job) {
  const { to, name, timestamp } = job.data;
  const jobType = job.name;

  console.log(`Processing ${jobType} email job ${job.id} for ${to}`);

  try {
    // Get email template
    const templateFn = emailTemplates[jobType];

    if (!templateFn) {
      throw new Error(`Unknown email template: ${jobType}`);
    }

    const emailContent = templateFn(job.data);

    // Update progress
    await job.updateProgress(25);

    // Send email via SMTP
    // TAINT FLOW: job.data.to -> transporter.sendMail
    const info = await transporter.sendMail({
      from: '"Our Platform" <noreply@example.com>',
      to: to,
      subject: emailContent.subject,
      text: emailContent.text,
      html: emailContent.html
    });

    // Update progress
    await job.updateProgress(75);

    // Log email sent
    console.log(`Email sent: ${info.messageId}`);

    // Update progress to complete
    await job.updateProgress(100);

    // Return result
    return {
      messageId: info.messageId,
      recipient: to,
      jobType,
      sentAt: new Date().toISOString()
    };
  } catch (error) {
    console.error(`Failed to send ${jobType} email to ${to}:`, error);

    // Log error details for debugging
    await job.log(`Error: ${error.message}`);

    // Rethrow to trigger retry
    throw error;
  }
}

/**
 * Email Worker
 * Tests: Worker instantiation with concurrency and error handling
 */
const emailWorker = new Worker(
  'email',
  processEmailJob,
  {
    ...getQueueConnection(),
    concurrency: 5, // Process up to 5 jobs concurrently
    limiter: {
      max: 100, // Max 100 emails
      duration: 60000 // per minute
    },
    lockDuration: 30000, // 30 seconds to process each job
    maxStalledCount: 2, // Retry stalled jobs twice
    stalledInterval: 30000 // Check for stalled jobs every 30s
  }
);

/**
 * Worker event handlers
 * Tests: Event listener attachment
 */

// Job completed successfully
emailWorker.on('completed', (job, result) => {
  console.log(`Job ${job.id} completed:`, result);
});

// Job failed after all retries
emailWorker.on('failed', (job, error) => {
  console.error(`Job ${job.id} failed after ${job.attemptsMade} attempts:`, error.message);

  // Could send alert to monitoring system here
  if (job.attemptsMade >= job.opts.attempts) {
    console.error(`Job ${job.id} exhausted all retries. Manual intervention required.`);
  }
});

// Job progress updated
emailWorker.on('progress', (job, progress) => {
  console.log(`Job ${job.id} progress:`, progress);
});

// Worker error (not job-specific)
emailWorker.on('error', (error) => {
  console.error('Worker error:', error);
});

// Worker active (processing jobs)
emailWorker.on('active', (job) => {
  console.log(`Job ${job.id} is now active`);
});

// Worker stalled
emailWorker.on('stalled', (jobId) => {
  console.warn(`Job ${jobId} has stalled`);
});

// Worker drained (no more jobs)
emailWorker.on('drained', () => {
  console.log('Email queue drained - no more jobs to process');
});

/**
 * Graceful shutdown
 * Tests: Worker cleanup on shutdown
 */
async function shutdown() {
  console.log('Shutting down email worker...');

  await emailWorker.close();

  console.log('Email worker shut down gracefully');
  process.exit(0);
}

// Handle termination signals
process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);

/**
 * Health check
 * Tests: Worker health monitoring
 */
async function healthCheck() {
  if (emailWorker.isRunning()) {
    return {
      status: 'healthy',
      worker: 'email',
      running: true,
      concurrency: 5
    };
  }

  return {
    status: 'unhealthy',
    worker: 'email',
    running: false
  };
}

module.exports = {
  emailWorker,
  processEmailJob,
  healthCheck,
  shutdown
};

// Start worker if run directly
if (require.main === module) {
  console.log('Email worker started');
  console.log('Concurrency: 5');
  console.log('Rate limit: 100 emails per minute');
  console.log('Press Ctrl+C to stop');
}
