import { randomUUID } from "crypto";
import { logger } from "./utils/logger.js";

export interface FidelityManifest {
  tx_id: string;
  columns: string[];
  count: number;
  bytes: number;
}

export function createManifest(rows: unknown[]): FidelityManifest {
  if (!Array.isArray(rows) || rows.length === 0) {
    return {
      tx_id: "",
      columns: [],
      count: 0,
      bytes: 0,
    };
  }

  const firstRow = rows[0] as Record<string, unknown>;
  const columns =
    typeof firstRow === "object" && firstRow !== null
      ? Object.keys(firstRow).sort()
      : [];

  let bytes = 0;
  for (const row of rows) {
    if (typeof row === "object" && row !== null) {
      for (const val of Object.values(row as Record<string, unknown>)) {
        if (val !== null && val !== undefined) {
          bytes += String(val).length;
        }
      }
    }
  }

  return {
    tx_id: randomUUID(),
    columns: columns,
    count: rows.length,
    bytes: bytes,
  };
}

export function attachManifest(
  results: Record<string, any>,
): Record<string, any> {
  for (const [filePath, fileResult] of Object.entries(results)) {
    if (!fileResult.success || !fileResult.extracted_data) {
      continue;
    }

    const manifest: Record<string, FidelityManifest> = {};

    for (const [tableName, rows] of Object.entries(fileResult.extracted_data)) {
      if (tableName.startsWith("_") || !Array.isArray(rows)) {
        continue;
      }

      if (rows.length > 0 && typeof rows[0] === "object" && rows[0] !== null) {
        manifest[tableName] = createManifest(rows as Record<string, unknown>[]);
      }
    }

    fileResult.extracted_data._extraction_manifest = manifest;
    logger.debug(
      { file: filePath, tables: Object.keys(manifest).length },
      "Attached fidelity manifest",
    );
  }

  return results;
}
