const { Queue } = require("bullmq");
const { getQueueConnection } = require("../config/redis");

const imageQueue = new Queue("image", {
  ...getQueueConnection(),
  defaultJobOptions: {
    attempts: 2,
    backoff: {
      type: "fixed",
      delay: 5000,
    },
    removeOnComplete: {
      age: 1800,
      count: 500,
    },
    removeOnFail: {
      age: 24 * 3600,
    },
  },
  limiter: {
    max: 10,
    duration: 1000,
  },
});

async function resizeImage(imageUrl, dimensions) {
  return await imageQueue.add(
    "resize",
    {
      imageUrl,
      dimensions,
      outputFormats: ["thumbnail", "medium", "large"],
      sizes: {
        thumbnail: { width: 150, height: 150 },
        medium: { width: 600, height: 600 },
        large: { width: 1200, height: 1200 },
      },
    },
    {
      priority: 5,
      attempts: 2,
    },
  );
}

async function generateThumbnail(imageUrl, width = 200, height = 200) {
  return await imageQueue.add(
    "thumbnail",
    {
      imageUrl,
      width,
      height,
      format: "jpeg",
      quality: 80,
    },
    {
      priority: 3,
      attempts: 3,
      jobId: `thumbnail-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    },
  );
}

async function optimizeImageForWeb(imageUrl, options = {}) {
  return await imageQueue.add(
    "optimize",
    {
      imageUrl,
      maxWidth: options.maxWidth || 1920,
      maxHeight: options.maxHeight || 1080,
      quality: options.quality || 85,
      format: options.format || "webp",
      progressive: options.progressive !== false,
      stripMetadata: options.stripMetadata !== false,
    },
    {
      priority: 5,
      attempts: 2,
    },
  );
}

async function processBatchImages(imageUrls, operation) {
  const jobs = imageUrls.map((url, index) => ({
    name: `batch-${operation}`,
    data: {
      imageUrl: url,
      operation,
      batchId: `batch-${Date.now()}`,
      index,
    },
    opts: {
      priority: 8,
      attempts: 2,
      delay: index * 200,
    },
  }));

  return await imageQueue.addBulk(jobs);
}

async function applyWatermark(
  imageUrl,
  watermarkUrl,
  position = "bottom-right",
) {
  return await imageQueue.add(
    "watermark",
    {
      imageUrl,
      watermarkUrl,
      position,
      opacity: 0.7,
      margin: 10,
    },
    {
      priority: 6,
      attempts: 2,
    },
  );
}

async function convertImageFormat(imageUrl, fromFormat, toFormat) {
  return await imageQueue.add(
    "convert",
    {
      imageUrl,
      fromFormat,
      toFormat,
      preserveQuality: true,
    },
    {
      priority: 7,
      attempts: 2,
    },
  );
}

async function generateResponsiveImages(imageUrl) {
  return await imageQueue.add(
    "responsive",
    {
      imageUrl,
      breakpoints: [320, 640, 768, 1024, 1280, 1920],
      formats: ["webp", "jpeg"],
      quality: 85,
    },
    {
      priority: 6,
      attempts: 2,
    },
  );
}

async function blurImage(imageUrl, radius = 10) {
  return await imageQueue.add(
    "blur",
    {
      imageUrl,
      radius,
      sigma: radius / 2,
    },
    {
      priority: 5,
      attempts: 2,
    },
  );
}

async function extractImageMetadata(imageUrl) {
  return await imageQueue.add(
    "metadata",
    {
      imageUrl,
      extractExif: true,
      extractColors: true,
      extractDimensions: true,
    },
    {
      priority: 4,
      attempts: 2,
    },
  );
}

async function createCollage(imageUrls, layout = "grid") {
  return await imageQueue.add(
    "collage",
    {
      imageUrls,
      layout,
      maxWidth: 1200,
      spacing: 10,
      backgroundColor: "#ffffff",
    },
    {
      priority: 7,
      attempts: 2,
    },
  );
}

async function updateJobProgress(jobId, progress, message) {
  const job = await imageQueue.getJob(jobId);

  if (job) {
    await job.updateProgress({
      percent: progress,
      message,
    });
  }
}

async function getProcessingJobs() {
  return await imageQueue.getActive();
}

async function getImageQueueStats() {
  const [waiting, active, completed, failed, delayed] = await Promise.all([
    imageQueue.getWaitingCount(),
    imageQueue.getActiveCount(),
    imageQueue.getCompletedCount(),
    imageQueue.getFailedCount(),
    imageQueue.getDelayedCount(),
  ]);

  return {
    waiting,
    active,
    completed,
    failed,
    delayed,
    total: waiting + active + completed + failed + delayed,
    rateLimitActive: waiting > 10,
  };
}

async function cancelImageJob(jobId) {
  const job = await imageQueue.getJob(jobId);

  if (job) {
    await job.remove();
    return true;
  }

  return false;
}

async function getJobDetails(jobId) {
  const job = await imageQueue.getJob(jobId);

  if (!job) {
    return null;
  }

  const state = await job.getState();
  const progress = job.progress;
  const failedReason = job.failedReason;
  const finishedOn = job.finishedOn;
  const processedOn = job.processedOn;

  return {
    id: job.id,
    name: job.name,
    data: job.data,
    state,
    progress,
    failedReason,
    finishedOn,
    processedOn,
    attemptsMade: job.attemptsMade,
    attemptsTotal: job.opts.attempts,
  };
}

async function closeImageQueue() {
  await imageQueue.close();
}

module.exports = {
  imageQueue,
  resizeImage,
  generateThumbnail,
  optimizeImageForWeb,
  processBatchImages,
  applyWatermark,
  convertImageFormat,
  generateResponsiveImages,
  blurImage,
  extractImageMetadata,
  createCollage,
  updateJobProgress,
  getProcessingJobs,
  getImageQueueStats,
  cancelImageJob,
  getJobDetails,
  closeImageQueue,
};
