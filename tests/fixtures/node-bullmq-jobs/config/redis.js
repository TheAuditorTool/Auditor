/**
 * Redis configuration for BullMQ
 * Tests: Redis connection setup for job queues
 */

const Redis = require('ioredis');

// Redis connection configuration
const redisConfig = {
  host: process.env.REDIS_HOST || 'localhost',
  port: process.env.REDIS_PORT || 6379,
  password: process.env.REDIS_PASSWORD || null,
  db: process.env.REDIS_DB || 0,
  maxRetriesPerRequest: null, // Required for BullMQ
  enableReadyCheck: false,
  retryStrategy: (times) => {
    const delay = Math.min(times * 50, 2000);
    return delay;
  }
};

/**
 * Create Redis connection
 * Tests: Redis client instantiation
 */
function createRedisConnection() {
  const connection = new Redis(redisConfig);

  connection.on('connect', () => {
    console.log('Redis connected');
  });

  connection.on('error', (err) => {
    console.error('Redis connection error:', err);
  });

  return connection;
}

/**
 * Get Redis configuration for BullMQ queues
 * Tests: Configuration export
 */
function getQueueConnection() {
  return {
    connection: redisConfig
  };
}

module.exports = {
  redisConfig,
  createRedisConnection,
  getQueueConnection
};
