function extractBullMQJobs(functions, classes, functionCallArgs, imports) {
  const queues = [];
  const workers = [];

  const hasBullMQ = imports && imports.some((imp) => imp.module === "bullmq");
  if (!hasBullMQ) {
    return { bullmq_queues: queues, bullmq_workers: workers };
  }

  for (const call of functionCallArgs) {
    if (call.callee_function === "Queue" && call.argument_index === 0) {
      const queueName =
        call.argument_expr && call.argument_expr.replace(/['"]/g, "").trim();
      if (queueName) {
        let redisConfig = null;
        const configCall = functionCallArgs.find(
          (c) =>
            c.callee_function === "Queue" &&
            c.argument_index === 1 &&
            c.line === call.line,
        );
        if (configCall && configCall.argument_expr) {
          redisConfig = configCall.argument_expr;
        }

        queues.push({
          line: call.line,
          name: queueName,
          redis_config: redisConfig,
        });
      }
    }

    if (call.callee_function === "Worker" && call.argument_index === 0) {
      const queueName =
        call.argument_expr && call.argument_expr.replace(/['"]/g, "").trim();
      if (queueName) {
        let workerFunction = null;
        const funcCall = functionCallArgs.find(
          (c) =>
            c.callee_function === "Worker" &&
            c.argument_index === 1 &&
            c.line === call.line,
        );
        if (funcCall && funcCall.argument_expr) {
          if (funcCall.argument_expr.includes("=>")) {
            workerFunction = "anonymous";
          } else {
            workerFunction = funcCall.argument_expr.trim();
          }
        }

        workers.push({
          line: call.line,
          queue_name: queueName,
          worker_function: workerFunction,
          processor_path: null,
        });
      }
    }
  }

  return {
    bullmq_queues: queues,
    bullmq_workers: workers,
  };
}
