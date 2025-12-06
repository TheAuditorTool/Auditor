import * as ts from "typescript";
import type { BullMQQueue, BullMQWorker } from "../schema.js";

interface ExtractBullMQResult {
  bullmq_queues: BullMQQueue[];
  bullmq_workers: BullMQWorker[];
}

export function extractBullMQQueueWorkers(
  sourceFile: ts.SourceFile,
  filePath: string,
): ExtractBullMQResult {
  const bullmq_queues: BullMQQueue[] = [];
  const bullmq_workers: BullMQWorker[] = [];

  const processedQueues = new Set<string>();
  const processedWorkers = new Set<string>();

  function visit(node: ts.Node): void {
    if (ts.isNewExpression(node)) {
      const expr = node.expression;
      if (ts.isIdentifier(expr) && expr.text === "Queue") {
        if (node.arguments && node.arguments.length > 0) {
          const queueNameArg = node.arguments[0];
          let queueName = "unknown";

          if (ts.isStringLiteral(queueNameArg)) {
            queueName = queueNameArg.text;
          } else if (ts.isIdentifier(queueNameArg)) {
            queueName = queueNameArg.text;
          }

          if (!processedQueues.has(queueName)) {
            processedQueues.add(queueName);

            let redisConfig: string | null = null;

            if (
              node.arguments.length > 1 &&
              ts.isObjectLiteralExpression(node.arguments[1])
            ) {
              const optionsObj = node.arguments[1];
              for (const prop of optionsObj.properties) {
                if (
                  ts.isPropertyAssignment(prop) &&
                  ts.isIdentifier(prop.name)
                ) {
                  if (
                    prop.name.text === "connection" ||
                    prop.name.text === "redis"
                  ) {
                    redisConfig = prop.initializer.getText(sourceFile);
                  }
                }
              }
            }

            bullmq_queues.push({
              file: filePath,
              line:
                sourceFile.getLineAndCharacterOfPosition(node.getStart()).line +
                1,
              queue_name: queueName,
              redis_config: redisConfig,
            });
          }
        }
      }

      if (ts.isIdentifier(expr) && expr.text === "Worker") {
        if (node.arguments && node.arguments.length >= 2) {
          const queueNameArg = node.arguments[0];
          const processorArg = node.arguments[1];

          let queueName = "unknown";
          if (ts.isStringLiteral(queueNameArg)) {
            queueName = queueNameArg.text;
          } else if (ts.isIdentifier(queueNameArg)) {
            queueName = queueNameArg.text;
          }

          const workerKey = `${queueName}:${sourceFile.getLineAndCharacterOfPosition(node.getStart()).line}`;
          if (!processedWorkers.has(workerKey)) {
            processedWorkers.add(workerKey);

            let workerFunction: string | null = null;
            let processorPath: string | null = null;

            if (
              ts.isArrowFunction(processorArg) ||
              ts.isFunctionExpression(processorArg)
            ) {
              workerFunction = "inline";
            } else if (ts.isStringLiteral(processorArg)) {
              processorPath = processorArg.text;
            } else if (ts.isIdentifier(processorArg)) {
              workerFunction = processorArg.text;
            }

            bullmq_workers.push({
              file: filePath,
              line:
                sourceFile.getLineAndCharacterOfPosition(node.getStart()).line +
                1,
              queue_name: queueName,
              worker_function: workerFunction,
              processor_path: processorPath,
            });
          }
        }
      }
    }

    if (ts.isCallExpression(node)) {
      const expr = node.expression;
      if (ts.isIdentifier(expr)) {
        const fnName = expr.text.toLowerCase();
        if (fnName.includes("queue") && fnName.includes("create")) {
          if (node.arguments.length > 0) {
            const queueNameArg = node.arguments[0];
            let queueName = "unknown";

            if (ts.isStringLiteral(queueNameArg)) {
              queueName = queueNameArg.text;
            }

            if (!processedQueues.has(queueName)) {
              processedQueues.add(queueName);

              bullmq_queues.push({
                file: filePath,
                line:
                  sourceFile.getLineAndCharacterOfPosition(node.getStart())
                    .line + 1,
                queue_name: queueName,
                redis_config: null,
              });
            }
          }
        }
      }

      if (ts.isPropertyAccessExpression(expr) && expr.name.text === "process") {
        const queueExpr = expr.expression;
        let queueName = "unknown";

        if (ts.isIdentifier(queueExpr)) {
          queueName = queueExpr.text;
        }

        if (node.arguments.length > 0) {
          const processorArg = node.arguments[0];
          const workerKey = `${queueName}:process:${sourceFile.getLineAndCharacterOfPosition(node.getStart()).line}`;

          if (!processedWorkers.has(workerKey)) {
            processedWorkers.add(workerKey);

            let workerFunction: string | null = null;
            let processorPath: string | null = null;

            if (
              ts.isArrowFunction(processorArg) ||
              ts.isFunctionExpression(processorArg)
            ) {
              workerFunction = "inline";
            } else if (ts.isStringLiteral(processorArg)) {
              processorPath = processorArg.text;
            } else if (ts.isIdentifier(processorArg)) {
              workerFunction = processorArg.text;
            }

            bullmq_workers.push({
              file: filePath,
              line:
                sourceFile.getLineAndCharacterOfPosition(node.getStart()).line +
                1,
              queue_name: queueName,
              worker_function: workerFunction,
              processor_path: processorPath,
            });
          }
        }
      }
    }

    ts.forEachChild(node, visit);
  }

  visit(sourceFile);

  return { bullmq_queues, bullmq_workers };
}

export { ExtractBullMQResult };
