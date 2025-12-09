/**
 * Database configuration.
 */

export const config = {
  database: {
    host: process.env.DB_HOST || 'localhost',
    port: parseInt(process.env.DB_PORT || '5432'),
    name: process.env.DB_NAME || 'deepflow',
    user: process.env.DB_USER || 'postgres',
    password: process.env.DB_PASSWORD || 'postgres',
  },
  redis: {
    url: process.env.REDIS_URL || 'redis://localhost:6379',
  },
  elasticsearch: {
    node: process.env.ES_NODE || 'http://localhost:9200',
  },
  s3: {
    bucket: process.env.S3_BUCKET || 'deepflow-uploads',
    region: process.env.AWS_REGION || 'us-east-1',
  },
};
