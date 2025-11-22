/**
 * Image Processing Queue - CPU-intensive image operations
 * Tests: Rate limiting, concurrency control, job progress tracking
 */

const { Queue } = require('bullmq');
const { getQueueConnection } = require('../config/redis');

/**
 * Image Processing Queue
 * Tests: Queue with rate limiter configuration
 */
const imageQueue = new Queue('image', {
  ...getQueueConnection(),
  defaultJobOptions: {
    attempts: 2,
    backoff: {
      type: 'fixed',
      delay: 5000
    },
    removeOnComplete: {
      age: 1800, // Keep completed jobs for 30 minutes
      count: 500
    },
    removeOnFail: {
      age: 24 * 3600 // Keep failed jobs for 24 hours
    }
  },
  limiter: {
    max: 10, // Max 10 jobs
    duration: 1000 // per second
  }
});

/**
 * Resize image job
 * Tests: Job with multiple output formats
 * TAINT FLOW: imageUrl (user input) -> job data
 */
async function resizeImage(imageUrl, dimensions) {
  return await imageQueue.add(
    'resize',
    {
      imageUrl,
      dimensions,
      outputFormats: ['thumbnail', 'medium', 'large'],
      sizes: {
        thumbnail: { width: 150, height: 150 },
        medium: { width: 600, height: 600 },
        large: { width: 1200, height: 1200 }
      }
    },
    {
      priority: 5,
      attempts: 2
    }
  );
}

/**
 * Generate thumbnail job
 * Tests: Quick image processing with progress tracking
 */
async function generateThumbnail(imageUrl, width = 200, height = 200) {
  return await imageQueue.add(
    'thumbnail',
    {
      imageUrl,
      width,
      height,
      format: 'jpeg',
      quality: 80
    },
    {
      priority: 3,
      attempts: 3,
      jobId: `thumbnail-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
    }
  );
}

/**
 * Optimize image for web
 * Tests: Job with quality settings and format conversion
 */
async function optimizeImageForWeb(imageUrl, options = {}) {
  return await imageQueue.add(
    'optimize',
    {
      imageUrl,
      maxWidth: options.maxWidth || 1920,
      maxHeight: options.maxHeight || 1080,
      quality: options.quality || 85,
      format: options.format || 'webp',
      progressive: options.progressive !== false,
      stripMetadata: options.stripMetadata !== false
    },
    {
      priority: 5,
      attempts: 2
    }
  );
}

/**
 * Batch image processing
 * Tests: Bulk job creation with rate limiting
 */
async function processBatchImages(imageUrls, operation) {
  const jobs = imageUrls.map((url, index) => ({
    name: `batch-${operation}`,
    data: {
      imageUrl: url,
      operation,
      batchId: `batch-${Date.now()}`,
      index
    },
    opts: {
      priority: 8,
      attempts: 2,
      delay: index * 200 // Stagger jobs to respect rate limit
    }
  }));

  return await imageQueue.addBulk(jobs);
}

/**
 * Apply watermark to image
 * Tests: Job with external resource dependency
 * TAINT FLOW: imageUrl, watermarkUrl (user input) -> job data
 */
async function applyWatermark(imageUrl, watermarkUrl, position = 'bottom-right') {
  return await imageQueue.add(
    'watermark',
    {
      imageUrl,
      watermarkUrl,
      position,
      opacity: 0.7,
      margin: 10
    },
    {
      priority: 6,
      attempts: 2
    }
  );
}

/**
 * Convert image format
 * Tests: Format conversion job
 */
async function convertImageFormat(imageUrl, fromFormat, toFormat) {
  return await imageQueue.add(
    'convert',
    {
      imageUrl,
      fromFormat,
      toFormat,
      preserveQuality: true
    },
    {
      priority: 7,
      attempts: 2
    }
  );
}

/**
 * Generate responsive image set
 * Tests: Job creating multiple outputs
 */
async function generateResponsiveImages(imageUrl) {
  return await imageQueue.add(
    'responsive',
    {
      imageUrl,
      breakpoints: [320, 640, 768, 1024, 1280, 1920],
      formats: ['webp', 'jpeg'],
      quality: 85
    },
    {
      priority: 6,
      attempts: 2
    }
  );
}

/**
 * Blur image for preview
 * Tests: Image effect application
 */
async function blurImage(imageUrl, radius = 10) {
  return await imageQueue.add(
    'blur',
    {
      imageUrl,
      radius,
      sigma: radius / 2
    },
    {
      priority: 5,
      attempts: 2
    }
  );
}

/**
 * Extract image metadata
 * Tests: Metadata extraction job
 */
async function extractImageMetadata(imageUrl) {
  return await imageQueue.add(
    'metadata',
    {
      imageUrl,
      extractExif: true,
      extractColors: true,
      extractDimensions: true
    },
    {
      priority: 4,
      attempts: 2
    }
  );
}

/**
 * Create image collage
 * Tests: Complex multi-image operation
 * TAINT FLOW: imageUrls array (user input) -> job data
 */
async function createCollage(imageUrls, layout = 'grid') {
  return await imageQueue.add(
    'collage',
    {
      imageUrls,
      layout,
      maxWidth: 1200,
      spacing: 10,
      backgroundColor: '#ffffff'
    },
    {
      priority: 7,
      attempts: 2
    }
  );
}

/**
 * Update job progress
 * Tests: Progress tracking
 */
async function updateJobProgress(jobId, progress, message) {
  const job = await imageQueue.getJob(jobId);

  if (job) {
    await job.updateProgress({
      percent: progress,
      message
    });
  }
}

/**
 * Get processing jobs
 * Tests: Active job retrieval
 */
async function getProcessingJobs() {
  return await imageQueue.getActive();
}

/**
 * Get queue statistics with rate limit info
 * Tests: Queue metrics with rate limiting
 */
async function getImageQueueStats() {
  const [waiting, active, completed, failed, delayed] = await Promise.all([
    imageQueue.getWaitingCount(),
    imageQueue.getActiveCount(),
    imageQueue.getCompletedCount(),
    imageQueue.getFailedCount(),
    imageQueue.getDelayedCount()
  ]);

  return {
    waiting,
    active,
    completed,
    failed,
    delayed,
    total: waiting + active + completed + failed + delayed,
    rateLimitActive: waiting > 10 // Based on limiter config
  };
}

/**
 * Cancel job
 * Tests: Job cancellation
 */
async function cancelImageJob(jobId) {
  const job = await imageQueue.getJob(jobId);

  if (job) {
    await job.remove();
    return true;
  }

  return false;
}

/**
 * Get job by ID with full details
 * Tests: Job detail retrieval
 */
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
    attemptsTotal: job.opts.attempts
  };
}

/**
 * Close queue connection
 * Tests: Resource cleanup
 */
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
  closeImageQueue
};
