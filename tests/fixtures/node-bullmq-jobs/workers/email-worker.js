const { Worker } = require("bullmq");
const { getQueueConnection } = require("../config/redis");
const nodemailer = require("nodemailer");

const transporter = nodemailer.createTransporter({
  host: process.env.SMTP_HOST || "smtp.example.com",
  port: process.env.SMTP_PORT || 587,
  secure: false,
  auth: {
    user: process.env.SMTP_USER || "user@example.com",
    pass: process.env.SMTP_PASS || "password",
  },
});

const emailTemplates = {
  welcome: (data) => ({
    subject: `Welcome, ${data.name}!`,
    html: `
      <h1>Welcome to our platform!</h1>
      <p>Hi ${data.name},</p>
      <p>Thank you for joining us. We're excited to have you on board.</p>
      <p>Get started by exploring our features.</p>
    `,
    text: `Welcome, ${data.name}! Thank you for joining us.`,
  }),

  "password-reset": (data) => ({
    subject: "Reset Your Password",
    html: `
      <h1>Password Reset Request</h1>
      <p>You requested a password reset. Click the link below:</p>
      <a href="https://example.com/reset?token=${data.resetToken}">Reset Password</a>
      <p>This link expires at ${new Date(data.expiresAt).toLocaleString()}</p>
      <p>If you didn't request this, please ignore this email.</p>
    `,
    text: `Reset your password: https://example.com/reset?token=${data.resetToken}`,
  }),

  "order-confirmation": (data) => ({
    subject: `Order Confirmation #${data.orderNumber}`,
    html: `
      <h1>Order Confirmed!</h1>
      <p>Thank you for your order.</p>
      <h2>Order #${data.orderNumber}</h2>
      <h3>Items:</h3>
      <ul>
        ${data.items
          .map(
            (item) => `
          <li>${item.name} x ${item.quantity} - $${item.price}</li>
        `,
          )
          .join("")}
      </ul>
      <p><strong>Total: $${data.total}</strong></p>
      <h3>Shipping Address:</h3>
      <p>${data.shippingAddress.street}<br>
         ${data.shippingAddress.city}, ${data.shippingAddress.state} ${data.shippingAddress.zip}</p>
    `,
    text: `Order #${data.orderNumber} confirmed. Total: $${data.total}`,
  }),

  newsletter: (data) => ({
    subject: data.subject,
    html: `
      ${data.content}
      <hr>
      <p><small><a href="https://example.com/unsubscribe?token=${data.unsubscribeToken}">Unsubscribe</a></small></p>
    `,
    text: data.content,
  }),

  promotional: (data) => ({
    subject: data.subject,
    html: data.content,
    text: data.content,
  }),

  "email-verification": (data) => ({
    subject: "Verify Your Email Address",
    html: `
      <h1>Verify Your Email</h1>
      <p>Please click the link below to verify your email address:</p>
      <a href="https://example.com/verify?token=${data.verificationToken}">Verify Email</a>
      <p>This link expires in 24 hours.</p>
    `,
    text: `Verify your email: https://example.com/verify?token=${data.verificationToken}`,
  }),

  transactional: (data) => {
    return {
      subject: data.subject,
      html: renderTemplate(data.template, data.templateData),
      text: data.subject,
    };
  },
};

function renderTemplate(template, data) {
  let html = template;

  for (const [key, value] of Object.entries(data)) {
    html = html.replace(new RegExp(`{{${key}}}`, "g"), value);
  }

  return html;
}

async function processEmailJob(job) {
  const { to, name, timestamp } = job.data;
  const jobType = job.name;

  console.log(`Processing ${jobType} email job ${job.id} for ${to}`);

  try {
    const templateFn = emailTemplates[jobType];

    if (!templateFn) {
      throw new Error(`Unknown email template: ${jobType}`);
    }

    const emailContent = templateFn(job.data);

    await job.updateProgress(25);

    const info = await transporter.sendMail({
      from: '"Our Platform" <noreply@example.com>',
      to: to,
      subject: emailContent.subject,
      text: emailContent.text,
      html: emailContent.html,
    });

    await job.updateProgress(75);

    console.log(`Email sent: ${info.messageId}`);

    await job.updateProgress(100);

    return {
      messageId: info.messageId,
      recipient: to,
      jobType,
      sentAt: new Date().toISOString(),
    };
  } catch (error) {
    console.error(`Failed to send ${jobType} email to ${to}:`, error);

    await job.log(`Error: ${error.message}`);

    throw error;
  }
}

const emailWorker = new Worker("email", processEmailJob, {
  ...getQueueConnection(),
  concurrency: 5,
  limiter: {
    max: 100,
    duration: 60000,
  },
  lockDuration: 30000,
  maxStalledCount: 2,
  stalledInterval: 30000,
});

emailWorker.on("completed", (job, result) => {
  console.log(`Job ${job.id} completed:`, result);
});

emailWorker.on("failed", (job, error) => {
  console.error(
    `Job ${job.id} failed after ${job.attemptsMade} attempts:`,
    error.message,
  );

  if (job.attemptsMade >= job.opts.attempts) {
    console.error(
      `Job ${job.id} exhausted all retries. Manual intervention required.`,
    );
  }
});

emailWorker.on("progress", (job, progress) => {
  console.log(`Job ${job.id} progress:`, progress);
});

emailWorker.on("error", (error) => {
  console.error("Worker error:", error);
});

emailWorker.on("active", (job) => {
  console.log(`Job ${job.id} is now active`);
});

emailWorker.on("stalled", (jobId) => {
  console.warn(`Job ${jobId} has stalled`);
});

emailWorker.on("drained", () => {
  console.log("Email queue drained - no more jobs to process");
});

async function shutdown() {
  console.log("Shutting down email worker...");

  await emailWorker.close();

  console.log("Email worker shut down gracefully");
  process.exit(0);
}

process.on("SIGTERM", shutdown);
process.on("SIGINT", shutdown);

async function healthCheck() {
  if (emailWorker.isRunning()) {
    return {
      status: "healthy",
      worker: "email",
      running: true,
      concurrency: 5,
    };
  }

  return {
    status: "unhealthy",
    worker: "email",
    running: false,
  };
}

module.exports = {
  emailWorker,
  processEmailJob,
  healthCheck,
  shutdown,
};

if (require.main === module) {
  console.log("Email worker started");
  console.log("Concurrency: 5");
  console.log("Rate limit: 100 emails per minute");
  console.log("Press Ctrl+C to stop");
}
