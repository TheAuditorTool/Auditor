const { Worker, Queue, QueueScheduler, FlowProducer } = require('bullmq');
const Redis = require('ioredis');
const { RateLimiterRedis } = require('rate-limiter-flexible');
const pRetry = require('p-retry');

// Redis cluster configuration for production
const redisConfig = {
  port: process.env.REDIS_PORT || 6379,
  host: process.env.REDIS_HOST || 'localhost',
  password: process.env.REDIS_PASSWORD,
  maxRetriesPerRequest: null,
  enableReadyCheck: false,
  retryStrategy: (times) => {
    const delay = Math.min(times * 50, 2000);
    return delay;
  }
};

const redis = new Redis(redisConfig);
const redisSubscriber = new Redis(redisConfig);

// Rate limiter configuration
const rateLimiter = new RateLimiterRedis({
  storeClient: redis,
  keyPrefix: 'rate_limit',
  points: 100, // Number of requests
  duration: 60, // Per 60 seconds
  blockDuration: 10, // Block for 10 seconds if exceeded
});

// Queue definitions with advanced options
const dataIngestionQueue = new Queue('data-ingestion', {
  connection: redis,
  defaultJobOptions: {
    attempts: 5,
    backoff: {
      type: 'exponential',
      delay: 2000
    },
    removeOnComplete: {
      age: 24 * 3600, // Keep completed jobs for 24 hours
      count: 1000 // Keep last 1000 completed jobs
    },
    removeOnFail: {
      age: 7 * 24 * 3600 // Keep failed jobs for 7 days
    }
  }
});

const transformationQueue = new Queue('data-transformation', {
  connection: redis,
  defaultJobOptions: {
    attempts: 3,
    backoff: {
      type: 'fixed',
      delay: 5000
    }
  }
});

const validationQueue = new Queue('data-validation', {
  connection: redis,
  defaultJobOptions: {
    attempts: 2,
    timeout: 30000 // 30 second timeout
  }
});

const storageQueue = new Queue('data-storage', {
  connection: redis,
  defaultJobOptions: {
    priority: 1,
    delay: 0
  }
});

// Flow producer for complex job dependencies
const flowProducer = new FlowProducer({ connection: redis });

// Main data pipeline worker with sandboxed processor
const pipelineWorker = new Worker(
  'data-pipeline',
  __dirname + '/processors/pipeline.processor.js',
  {
    connection: redis,
    concurrency: 10,
    limiter: {
      max: 100,
      duration: 60000 // Process max 100 jobs per minute
    },
    lockDuration: 30000,
    stalledInterval: 30000,
    maxStalledCount: 3,
    metrics: {
      maxDataPoints: MetricsTime.ONE_WEEK
    }
  }
);

// Data ingestion worker with rate limiting
const ingestionWorker = new Worker(
  'data-ingestion',
  async (job) => {
    // Check rate limit
    try {
      await rateLimiter.consume(job.data.source, 1);
    } catch (rateLimiterRes) {
      // Rate limit exceeded
      throw new Error(`Rate limit exceeded. Retry after ${rateLimiterRes.msBeforeNext}ms`);
    }

    // Process with retry logic
    const result = await pRetry(
      async () => {
        // Validate input data
        if (!job.data.source || !job.data.type) {
          throw new Error('Invalid job data: missing source or type');
        }

        // Fetch data from external source
        const data = await fetchDataFromSource(job.data.source, {
          batchSize: job.data.batchSize || 1000,
          offset: job.data.offset || 0,
          filters: job.data.filters
        });

        // Update job progress
        await job.updateProgress(50);

        // Pre-process data
        const processed = await preProcessData(data, {
          normalize: job.data.normalize !== false,
          deduplicate: job.data.deduplicate !== false,
          validate: job.data.validate !== false
        });

        await job.updateProgress(100);

        // Log metrics
        await job.log(`Processed ${processed.records.length} records`);

        return {
          recordCount: processed.records.length,
          source: job.data.source,
          timestamp: Date.now(),
          data: processed.records
        };
      },
      {
        retries: 3,
        onFailedAttempt: error => {
          console.log(`Attempt ${error.attemptNumber} failed. ${error.retriesLeft} retries left.`);
        }
      }
    );

    // Create dependent jobs
    await transformationQueue.add(
      'transform-batch',
      {
        parentJobId: job.id,
        data: result.data,
        transformations: job.data.transformations
      },
      {
        parent: {
          id: job.id,
          queue: job.queueName
        }
      }
    );

    return result;
  },
  {
    connection: redis,
    concurrency: 5,
    limiter: {
      max: 50,
      duration: 60000
    }
  }
);

// Transformation worker with parallel processing
const transformationWorker = new Worker(
  'data-transformation',
  async (job) => {
    const { data, transformations } = job.data;

    // Split data into chunks for parallel processing
    const chunks = chunkArray(data, 100);
    const transformedChunks = [];

    // Process chunks in parallel with controlled concurrency
    const parallelLimit = 5;
    for (let i = 0; i < chunks.length; i += parallelLimit) {
      const batch = chunks.slice(i, i + parallelLimit);
      const results = await Promise.all(
        batch.map(chunk => applyTransformations(chunk, transformations))
      );
      transformedChunks.push(...results);

      // Update progress
      const progress = Math.round((i + parallelLimit) / chunks.length * 100);
      await job.updateProgress(Math.min(progress, 100));
    }

    // Merge results
    const merged = mergeTransformedData(transformedChunks);

    // Add validation job
    await validationQueue.add('validate-batch', {
      parentJobId: job.id,
      data: merged,
      rules: job.data.validationRules
    });

    return {
      recordCount: merged.length,
      transformationsApplied: transformations.length
    };
  },
  {
    connection: redis,
    concurrency: 8
  }
);

// Validation worker with schema validation
const validationWorker = new Worker(
  'data-validation',
  async (job) => {
    const { data, rules } = job.data;
    const errors = [];
    const valid = [];

    for (const record of data) {
      const validationResult = await validateRecord(record, rules);
      if (validationResult.valid) {
        valid.push(record);
      } else {
        errors.push({
          record,
          errors: validationResult.errors
        });
      }
    }

    // Handle validation errors
    if (errors.length > 0) {
      await handleValidationErrors(errors, job.id);

      if (errors.length / data.length > 0.1) { // More than 10% errors
        throw new Error(`Validation failed: ${errors.length} errors out of ${data.length} records`);
      }
    }

    // Add storage job for valid records
    if (valid.length > 0) {
      await storageQueue.add('store-batch', {
        parentJobId: job.id,
        data: valid,
        destination: job.data.destination
      }, {
        priority: valid.length > 1000 ? 2 : 1 // Higher priority for large batches
      });
    }

    return {
      validCount: valid.length,
      errorCount: errors.length
    };
  },
  {
    connection: redis,
    concurrency: 10
  }
);

// Storage worker with transaction support
const storageWorker = new Worker(
  'data-storage',
  async (job) => {
    const { data, destination } = job.data;

    // Begin transaction
    const transaction = await beginTransaction(destination);

    try {
      // Batch insert with progress tracking
      const batchSize = 100;
      for (let i = 0; i < data.length; i += batchSize) {
        const batch = data.slice(i, i + batchSize);
        await insertBatch(transaction, batch, destination);

        // Update progress
        const progress = Math.round((i + batchSize) / data.length * 100);
        await job.updateProgress(Math.min(progress, 100));
      }

      // Commit transaction
      await commitTransaction(transaction);

      return {
        recordsStored: data.length,
        destination,
        timestamp: Date.now()
      };
    } catch (error) {
      // Rollback on error
      await rollbackTransaction(transaction);
      throw error;
    }
  },
  {
    connection: redis,
    concurrency: 3 // Limited concurrency for database writes
  }
);

// Event handlers for monitoring and alerting
pipelineWorker.on('completed', (job, result) => {
  console.log(`Pipeline job ${job.id} completed:`, result);
  // Send metrics to monitoring service
  sendMetrics('pipeline.completed', result);
});

pipelineWorker.on('failed', (job, err) => {
  console.error(`Pipeline job ${job.id} failed:`, err);
  // Send alert
  sendAlert('Pipeline job failed', {
    jobId: job.id,
    error: err.message,
    data: job.data
  });
});

ingestionWorker.on('stalled', (job) => {
  console.warn(`Ingestion job ${job.id} stalled`);
  // Attempt recovery
  recoverStalledJob(job);
});

// Graceful shutdown
process.on('SIGTERM', async () => {
  console.log('SIGTERM received, closing workers...');

  await Promise.all([
    pipelineWorker.close(),
    ingestionWorker.close(),
    transformationWorker.close(),
    validationWorker.close(),
    storageWorker.close()
  ]);

  await redis.disconnect();
  await redisSubscriber.disconnect();

  process.exit(0);
});

// Create complex job flows
async function createDataPipelineFlow(sourceConfig) {
  const flow = await flowProducer.add({
    name: 'data-pipeline-flow',
    queueName: 'data-pipeline',
    data: sourceConfig,
    children: [
      {
        name: 'ingest',
        queueName: 'data-ingestion',
        data: {
          source: sourceConfig.source,
          batchSize: 1000
        },
        children: [
          {
            name: 'transform',
            queueName: 'data-transformation',
            data: {
              transformations: sourceConfig.transformations
            },
            children: [
              {
                name: 'validate',
                queueName: 'data-validation',
                data: {
                  rules: sourceConfig.validationRules
                },
                children: [
                  {
                    name: 'store',
                    queueName: 'data-storage',
                    data: {
                      destination: sourceConfig.destination
                    }
                  }
                ]
              }
            ]
          }
        ]
      }
    ]
  });

  return flow;
}

// Helper functions (simplified implementations)
async function fetchDataFromSource(source, options) {
  // Implementation would fetch from actual data source
  return { records: [] };
}

async function preProcessData(data, options) {
  // Implementation would process data
  return { records: data.records };
}

function chunkArray(array, size) {
  const chunks = [];
  for (let i = 0; i < array.length; i += size) {
    chunks.push(array.slice(i, i + size));
  }
  return chunks;
}

async function applyTransformations(data, transformations) {
  // Apply transformations to data
  return data;
}

function mergeTransformedData(chunks) {
  return chunks.flat();
}

async function validateRecord(record, rules) {
  // Validate record against rules
  return { valid: true, errors: [] };
}

async function handleValidationErrors(errors, jobId) {
  // Log errors to error queue or database
  console.error(`Validation errors for job ${jobId}:`, errors);
}

async function beginTransaction(destination) {
  // Begin database transaction
  return {};
}

async function insertBatch(transaction, batch, destination) {
  // Insert batch into database
}

async function commitTransaction(transaction) {
  // Commit database transaction
}

async function rollbackTransaction(transaction) {
  // Rollback database transaction
}

function sendMetrics(metric, data) {
  // Send to monitoring service
}

function sendAlert(message, data) {
  // Send alert notification
}

async function recoverStalledJob(job) {
  // Attempt to recover stalled job
}

module.exports = {
  pipelineWorker,
  ingestionWorker,
  transformationWorker,
  validationWorker,
  storageWorker,
  createDataPipelineFlow
};