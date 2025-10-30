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
 * @returns {Array} - BullMQ queue/worker records
 */
function extractBullMQJobs(functions, classes, functionCallArgs, imports) {
    const jobs = [];

    // Check if BullMQ is imported
    const hasBullMQ = imports && imports.some(imp => imp.source === 'bullmq');
    if (!hasBullMQ) {
        return jobs;
    }

    // Detect new Queue() instantiations
    for (const call of functionCallArgs) {
        // Match: new Queue('emailQueue', { connection })
        if (call.callee_function === 'Queue' && call.argument_index === 0) {
            const queueName = call.argument_expr && call.argument_expr.replace(/['"]/g, '').trim();
            if (queueName) {
                jobs.push({
                    type: 'queue',
                    name: queueName,
                    line: call.line
                });
            }
        }

        // Match: new Worker('emailQueue', async (job) => { ... })
        if (call.callee_function === 'Worker' && call.argument_index === 0) {
            const queueName = call.argument_expr && call.argument_expr.replace(/['"]/g, '').trim();
            if (queueName) {
                jobs.push({
                    type: 'worker',
                    queue_name: queueName,
                    line: call.line
                });
            }
        }

        // Detect job.add() calls to identify job types
        if (call.callee_function && call.callee_function.endsWith('.add') && call.argument_index === 0) {
            const jobType = call.argument_expr && call.argument_expr.replace(/['"]/g, '').trim();
            if (jobType && jobType.length > 0 && jobType.length < 100) {
                jobs.push({
                    type: 'job_type',
                    name: jobType,
                    line: call.line
                });
            }
        }
    }

    return jobs;
}
