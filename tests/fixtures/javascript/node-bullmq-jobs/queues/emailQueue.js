const { Queue, Worker } = require("bullmq");

const emailQueue = new Queue("emailQueue", {
  connection: {
    host: process.env.REDIS_HOST || "localhost",
    port: process.env.REDIS_PORT || 6379,
  },
});

const emailWorker = new Worker("emailQueue", async (job) => {
  const { to, subject, body } = job.data;
  console.log(`Sending email to ${to}: ${subject}`);
  return { sent: true, messageId: "abc123" };
});

async function sendEmail(to, subject, body) {
  await emailQueue.add("sendEmail", { to, subject, body });
}

module.exports = { emailQueue, sendEmail };
