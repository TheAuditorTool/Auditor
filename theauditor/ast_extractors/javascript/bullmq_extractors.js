/**
 * BullMQ Job Queue Extractors
 *
 * Extracts BullMQ queue definitions, workers, and job processing patterns
 * from JavaScript/TypeScript codebases.
 *
 * STABILITY: MODERATE - Changes when BullMQ API updates or new patterns emerge.
 *
 * DEPENDENCIES: core_ast_extractors.js (uses function_call_args)
 * USED BY: Indexer for job queue detection and worker analysis
 *
 * Architecture:
 * - Extracted from: framework_extractors.js (split 2025-10-31)
 * - Pattern: Detect new Queue(), new Worker(), queue.add() calls
 * - Assembly: Concatenated after sequelize_extractors.js, before batch_templates.js
 *
 * Functions:
 * 1. extractBullMQJobs() - Detect BullMQ queues, workers, and job types
 *
 * Current size: 65 lines (2025-10-31)
 */

/**
 * Extract BullMQ job queues and workers.
 * Detects: new Queue(), new Worker(), job processing patterns
 *
 * @param {Array} functions - From extractFunctions()
 * @param {Array} classes - From extractClasses()
 * @param {Array} functionCallArgs - From extractFunctionCallArgs()
 * @param {Array} imports - From extract imports
 * @returns {Object} - Object with bullmq_queues and bullmq_workers arrays
 */
function extractBullMQJobs(functions, classes, functionCallArgs, imports) {
    const queues = [];
    const workers = [];

    // Check if BullMQ is imported
    const hasBullMQ = imports && imports.some(imp => imp.module === 'bullmq');
    if (!hasBullMQ) {
        return { bullmq_queues: queues, bullmq_workers: workers };
    }

    // Detect new Queue() instantiations
    for (const call of functionCallArgs) {
        // Match: new Queue('emailQueue', { connection })
        if (call.callee_function === 'Queue' && call.argument_index === 0) {
            const queueName = call.argument_expr && call.argument_expr.replace(/['"]/g, '').trim();
            if (queueName) {
                // Extract redis config from second argument
                let redisConfig = null;
                const configCall = functionCallArgs.find(c =>
                    c.callee_function === 'Queue' &&
                    c.argument_index === 1 &&
                    c.line === call.line
                );
                if (configCall && configCall.argument_expr) {
                    redisConfig = configCall.argument_expr;
                }

                queues.push({
                    line: call.line,
                    name: queueName,  // Note: Python expects 'name' not 'queue_name' for queues
                    redis_config: redisConfig
                });
            }
        }

        // Match: new Worker('emailQueue', async (job) => { ... })
        if (call.callee_function === 'Worker' && call.argument_index === 0) {
            const queueName = call.argument_expr && call.argument_expr.replace(/['"]/g, '').trim();
            if (queueName) {
                // Try to extract worker function name from second argument
                let workerFunction = null;
                const funcCall = functionCallArgs.find(c =>
                    c.callee_function === 'Worker' &&
                    c.argument_index === 1 &&
                    c.line === call.line
                );
                if (funcCall && funcCall.argument_expr) {
                    // Check if it's an arrow function or named function
                    if (funcCall.argument_expr.includes('=>')) {
                        workerFunction = 'anonymous';
                    } else {
                        workerFunction = funcCall.argument_expr.trim();
                    }
                }

                workers.push({
                    line: call.line,
                    queue_name: queueName,
                    worker_function: workerFunction,
                    processor_path: null  // Would need more context to extract
                });
            }
        }
    }

    return {
        bullmq_queues: queues,
        bullmq_workers: workers
    };
}
