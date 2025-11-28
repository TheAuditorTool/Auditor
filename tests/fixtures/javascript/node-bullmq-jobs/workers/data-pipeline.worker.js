const { Worker, Queue, QueueScheduler, FlowProducer } = require("bullmq");
const Redis = require("ioredis");
const { RateLimiterRedis } = require("rate-limiter-flexible");
const pRetry = require("p-retry");

const redisConfig = {
  port: process.env.REDIS_PORT || 6379,
  host: process.env.REDIS_HOST || "localhost",
  password: process.env.REDIS_PASSWORD,
  maxRetriesPerRequest: null,
  enableReadyCheck: false,
  retryStrategy: (times) => {
    const delay = Math.min(times * 50, 2000);
    return delay;
  },
};

const redis = new Redis(redisConfig);
const redisSubscriber = new Redis(redisConfig);

const rateLimiter = new RateLimiterRedis({
  storeClient: redis,
  keyPrefix: "rate_limit",
  points: 100,
  duration: 60,
  blockDuration: 10,
});

const dataIngestionQueue = new Queue("data-ingestion", {
  connection: redis,
  defaultJobOptions: {
    attempts: 5,
    backoff: {
      type: "exponential",
      delay: 2000,
    },
    removeOnComplete: {
      age: 24 * 3600,
      count: 1000,
    },
    removeOnFail: {
      age: 7 * 24 * 3600,
    },
  },
});

const transformationQueue = new Queue("data-transformation", {
  connection: redis,
  defaultJobOptions: {
    attempts: 3,
    backoff: {
      type: "fixed",
      delay: 5000,
    },
  },
});

const validationQueue = new Queue("data-validation", {
  connection: redis,
  defaultJobOptions: {
    attempts: 2,
    timeout: 30000,
  },
});

const storageQueue = new Queue("data-storage", {
  connection: redis,
  defaultJobOptions: {
    priority: 1,
    delay: 0,
  },
});

const flowProducer = new FlowProducer({ connection: redis });

const pipelineWorker = new Worker(
  "data-pipeline",
  __dirname + "/processors/pipeline.processor.js",
  {
    connection: redis,
    concurrency: 10,
    limiter: {
      max: 100,
      duration: 60000,
    },
    lockDuration: 30000,
    stalledInterval: 30000,
    maxStalledCount: 3,
    metrics: {
      maxDataPoints: MetricsTime.ONE_WEEK,
    },
  },
);

const ingestionWorker = new Worker(
  "data-ingestion",
  async (job) => {
    try {
      await rateLimiter.consume(job.data.source, 1);
    } catch (rateLimiterRes) {
      throw new Error(
        `Rate limit exceeded. Retry after ${rateLimiterRes.msBeforeNext}ms`,
      );
    }

    const result = await pRetry(
      async () => {
        if (!job.data.source || !job.data.type) {
          throw new Error("Invalid job data: missing source or type");
        }

        const data = await fetchDataFromSource(job.data.source, {
          batchSize: job.data.batchSize || 1000,
          offset: job.data.offset || 0,
          filters: job.data.filters,
        });

        await job.updateProgress(50);

        const processed = await preProcessData(data, {
          normalize: job.data.normalize !== false,
          deduplicate: job.data.deduplicate !== false,
          validate: job.data.validate !== false,
        });

        await job.updateProgress(100);

        await job.log(`Processed ${processed.records.length} records`);

        return {
          recordCount: processed.records.length,
          source: job.data.source,
          timestamp: Date.now(),
          data: processed.records,
        };
      },
      {
        retries: 3,
        onFailedAttempt: (error) => {
          console.log(
            `Attempt ${error.attemptNumber} failed. ${error.retriesLeft} retries left.`,
          );
        },
      },
    );

    await transformationQueue.add(
      "transform-batch",
      {
        parentJobId: job.id,
        data: result.data,
        transformations: job.data.transformations,
      },
      {
        parent: {
          id: job.id,
          queue: job.queueName,
        },
      },
    );

    return result;
  },
  {
    connection: redis,
    concurrency: 5,
    limiter: {
      max: 50,
      duration: 60000,
    },
  },
);

const transformationWorker = new Worker(
  "data-transformation",
  async (job) => {
    const { data, transformations } = job.data;

    const chunks = chunkArray(data, 100);
    const transformedChunks = [];

    const parallelLimit = 5;
    for (let i = 0; i < chunks.length; i += parallelLimit) {
      const batch = chunks.slice(i, i + parallelLimit);
      const results = await Promise.all(
        batch.map((chunk) => applyTransformations(chunk, transformations)),
      );
      transformedChunks.push(...results);

      const progress = Math.round(((i + parallelLimit) / chunks.length) * 100);
      await job.updateProgress(Math.min(progress, 100));
    }

    const merged = mergeTransformedData(transformedChunks);

    await validationQueue.add("validate-batch", {
      parentJobId: job.id,
      data: merged,
      rules: job.data.validationRules,
    });

    return {
      recordCount: merged.length,
      transformationsApplied: transformations.length,
    };
  },
  {
    connection: redis,
    concurrency: 8,
  },
);

const validationWorker = new Worker(
  "data-validation",
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
          errors: validationResult.errors,
        });
      }
    }

    if (errors.length > 0) {
      await handleValidationErrors(errors, job.id);

      if (errors.length / data.length > 0.1) {
        throw new Error(
          `Validation failed: ${errors.length} errors out of ${data.length} records`,
        );
      }
    }

    if (valid.length > 0) {
      await storageQueue.add(
        "store-batch",
        {
          parentJobId: job.id,
          data: valid,
          destination: job.data.destination,
        },
        {
          priority: valid.length > 1000 ? 2 : 1,
        },
      );
    }

    return {
      validCount: valid.length,
      errorCount: errors.length,
    };
  },
  {
    connection: redis,
    concurrency: 10,
  },
);

const storageWorker = new Worker(
  "data-storage",
  async (job) => {
    const { data, destination } = job.data;

    const transaction = await beginTransaction(destination);

    try {
      const batchSize = 100;
      for (let i = 0; i < data.length; i += batchSize) {
        const batch = data.slice(i, i + batchSize);
        await insertBatch(transaction, batch, destination);

        const progress = Math.round(((i + batchSize) / data.length) * 100);
        await job.updateProgress(Math.min(progress, 100));
      }

      await commitTransaction(transaction);

      return {
        recordsStored: data.length,
        destination,
        timestamp: Date.now(),
      };
    } catch (error) {
      await rollbackTransaction(transaction);
      throw error;
    }
  },
  {
    connection: redis,
    concurrency: 3,
  },
);

pipelineWorker.on("completed", (job, result) => {
  console.log(`Pipeline job ${job.id} completed:`, result);
  sendMetrics("pipeline.completed", result);
});

pipelineWorker.on("failed", (job, err) => {
  console.error(`Pipeline job ${job.id} failed:`, err);
  sendAlert("Pipeline job failed", {
    jobId: job.id,
    error: err.message,
    data: job.data,
  });
});

ingestionWorker.on("stalled", (job) => {
  console.warn(`Ingestion job ${job.id} stalled`);
  recoverStalledJob(job);
});

process.on("SIGTERM", async () => {
  console.log("SIGTERM received, closing workers...");

  await Promise.all([
    pipelineWorker.close(),
    ingestionWorker.close(),
    transformationWorker.close(),
    validationWorker.close(),
    storageWorker.close(),
  ]);

  await redis.disconnect();
  await redisSubscriber.disconnect();

  process.exit(0);
});

async function createDataPipelineFlow(sourceConfig) {
  const flow = await flowProducer.add({
    name: "data-pipeline-flow",
    queueName: "data-pipeline",
    data: sourceConfig,
    children: [
      {
        name: "ingest",
        queueName: "data-ingestion",
        data: {
          source: sourceConfig.source,
          batchSize: 1000,
        },
        children: [
          {
            name: "transform",
            queueName: "data-transformation",
            data: {
              transformations: sourceConfig.transformations,
            },
            children: [
              {
                name: "validate",
                queueName: "data-validation",
                data: {
                  rules: sourceConfig.validationRules,
                },
                children: [
                  {
                    name: "store",
                    queueName: "data-storage",
                    data: {
                      destination: sourceConfig.destination,
                    },
                  },
                ],
              },
            ],
          },
        ],
      },
    ],
  });

  return flow;
}

async function fetchDataFromSource(source, options) {
  return { records: [] };
}

async function preProcessData(data, options) {
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
  return data;
}

function mergeTransformedData(chunks) {
  return chunks.flat();
}

async function validateRecord(record, rules) {
  return { valid: true, errors: [] };
}

async function handleValidationErrors(errors, jobId) {
  console.error(`Validation errors for job ${jobId}:`, errors);
}

async function beginTransaction(destination) {
  return {};
}

async function insertBatch(transaction, batch, destination) {}

async function commitTransaction(transaction) {}

async function rollbackTransaction(transaction) {}

function sendMetrics(metric, data) {}

function sendAlert(message, data) {}

async function recoverStalledJob(job) {}

module.exports = {
  pipelineWorker,
  ingestionWorker,
  transformationWorker,
  validationWorker,
  storageWorker,
  createDataPipelineFlow,
};
