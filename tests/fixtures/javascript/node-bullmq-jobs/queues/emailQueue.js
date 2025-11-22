const { Queue, Worker } = require('bullmq');

// Queue definition
const emailQueue = new Queue('emailQueue', {
  connection: {
    host: process.env.REDIS_HOST || 'localhost',
    port: process.env.REDIS_PORT || 6379
  }
});

// Worker definition
const emailWorker = new Worker('emailQueue', async (job) => {
  const { to, subject, body } = job.data;
  console.log(`Sending email to ${to}: ${subject}`);
  // Send email logic here
  return { sent: true, messageId: 'abc123' };
});

// Job producer
async function sendEmail(to, subject, body) {
  await emailQueue.add('sendEmail', { to, subject, body });
}

module.exports = { emailQueue, sendEmail };