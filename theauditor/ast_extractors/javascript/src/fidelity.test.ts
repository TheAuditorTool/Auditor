import {
  createManifest,
  attachManifest,
  FidelityManifest,
} from "./fidelity.js";

let passed = 0;
let failed = 0;
const failures: string[] = [];

function test(name: string, fn: () => void): void {
  try {
    fn();
    passed++;
    console.log(`  [PASS] ${name}`);
  } catch (err) {
    failed++;
    const msg = err instanceof Error ? err.message : String(err);
    failures.push(`${name}: ${msg}`);
    console.log(`  [FAIL] ${name}`);
    console.log(`         ${msg}`);
  }
}

function assertEqual<T>(actual: T, expected: T, msg?: string): void {
  const actualStr = JSON.stringify(actual);
  const expectedStr = JSON.stringify(expected);
  if (actualStr !== expectedStr) {
    throw new Error(msg || `Expected ${expectedStr}, got ${actualStr}`);
  }
}

function assertArrayEqual<T>(actual: T[], expected: T[], msg?: string): void {
  if (actual.length !== expected.length) {
    throw new Error(
      msg ||
        `Array length mismatch: expected ${expected.length}, got ${actual.length}`,
    );
  }
  for (let i = 0; i < actual.length; i++) {
    if (actual[i] !== expected[i]) {
      throw new Error(
        msg ||
          `Array mismatch at index ${i}: expected ${expected[i]}, got ${actual[i]}`,
      );
    }
  }
}

function assertTrue(condition: boolean, msg: string): void {
  if (!condition) {
    throw new Error(msg);
  }
}

function assertFalsy(value: unknown, msg: string): void {
  if (value) {
    throw new Error(msg);
  }
}

function assertTruthy(value: unknown, msg: string): void {
  if (!value) {
    throw new Error(msg);
  }
}

console.log("\n=== SECTION 1: createManifest() Basic Token Generation ===\n");

test("createManifest returns all required fields", () => {
  const rows = [
    { name: "foo", type: "function", line: 10 },
    { name: "bar", type: "class", line: 20 },
  ];
  const manifest = createManifest(rows);

  assertTrue("tx_id" in manifest, "Missing tx_id field");
  assertTrue("columns" in manifest, "Missing columns field");
  assertTrue("count" in manifest, "Missing count field");
  assertTrue("bytes" in manifest, "Missing bytes field");
});

test("createManifest tx_id is valid UUID format", () => {
  const rows = [{ name: "test", value: 123 }];
  const manifest = createManifest(rows);

  const uuidRegex =
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  assertTrue(
    uuidRegex.test(manifest.tx_id),
    `Invalid UUID format: ${manifest.tx_id}`,
  );
});

test("createManifest columns are sorted alphabetically", () => {
  const rows = [{ zebra: 1, alpha: 2, mike: 3 }];
  const manifest = createManifest(rows);

  assertArrayEqual(manifest.columns, ["alpha", "mike", "zebra"]);
});

test("createManifest count matches row count", () => {
  const rows = [{ a: 1 }, { a: 2 }, { a: 3 }, { a: 4 }, { a: 5 }];
  const manifest = createManifest(rows);

  assertEqual(manifest.count, 5);
});

test("createManifest generates unique tx_id per call", () => {
  const rows = [{ a: 1 }];
  const manifest1 = createManifest(rows);
  const manifest2 = createManifest(rows);

  assertTrue(
    manifest1.tx_id !== manifest2.tx_id,
    "tx_id should be unique per call",
  );
});

console.log("\n=== SECTION 2: createManifest() Byte Calculation ===\n");

test("createManifest bytes from simple string values", () => {
  const rows = [{ name: "hello", count: 100 }];
  const manifest = createManifest(rows);

  assertEqual(manifest.bytes, 8, "Byte calculation mismatch");
});

test("createManifest bytes from multiple rows", () => {
  const rows = [
    { name: "a", val: 1 },
    { name: "bb", val: 22 },
  ];
  const manifest = createManifest(rows);

  assertEqual(manifest.bytes, 6, "Multi-row byte calculation mismatch");
});

test("createManifest bytes handles nested objects", () => {
  const rows = [{ data: { nested: true } }];
  const manifest = createManifest(rows);

  assertEqual(manifest.bytes, 15, "Nested object byte calculation");
});

test("createManifest bytes handles null and undefined", () => {
  const rows = [{ a: null, b: undefined, c: "test" }];
  const manifest = createManifest(rows);

  assertEqual(manifest.bytes, 4, "Null/undefined should be skipped");
});

test("createManifest bytes handles arrays", () => {
  const rows = [{ arr: [1, 2, 3] }];
  const manifest = createManifest(rows);

  assertEqual(manifest.bytes, 5, "Array byte calculation");
});

test("createManifest bytes handles boolean", () => {
  const rows = [{ a: true, b: false }];
  const manifest = createManifest(rows);

  assertEqual(manifest.bytes, 9, "Boolean byte calculation");
});

console.log("\n=== SECTION 3: createManifest() Edge Cases ===\n");

test("createManifest empty array returns zero token", () => {
  const manifest = createManifest([]);

  assertEqual(manifest.count, 0);
  assertArrayEqual(manifest.columns, []);
  assertEqual(manifest.tx_id, "");
  assertEqual(manifest.bytes, 0);
});

test("createManifest non-array returns zero token", () => {
  const manifest = createManifest(null as any);

  assertEqual(manifest.count, 0);
  assertEqual(manifest.bytes, 0);
});

test("createManifest array of primitives has empty columns", () => {
  const rows = [1, 2, 3] as any;
  const manifest = createManifest(rows);

  assertArrayEqual(manifest.columns, []);
});

test("createManifest handles empty object rows", () => {
  const rows = [{}, {}, {}];
  const manifest = createManifest(rows);

  assertEqual(manifest.count, 3);
  assertArrayEqual(manifest.columns, []);
  assertEqual(manifest.bytes, 0);
});

console.log("\n=== SECTION 4: attachManifest() Integration ===\n");

test("attachManifest adds _extraction_manifest to results", () => {
  const results = {
    "/test/file.ts": {
      success: true,
      extracted_data: {
        symbols: [{ name: "foo", type: "func" }],
        imports: [{ module: "os" }],
      },
    },
  };

  const withManifest = attachManifest(results);

  assertTrue(
    "_extraction_manifest" in withManifest["/test/file.ts"].extracted_data,
    "Missing _extraction_manifest",
  );
});

test("attachManifest creates manifest for each table", () => {
  const results = {
    "/test/file.ts": {
      success: true,
      extracted_data: {
        symbols: [{ name: "foo" }],
        imports: [{ module: "bar" }],
      },
    },
  };

  const withManifest = attachManifest(results);
  const manifest =
    withManifest["/test/file.ts"].extracted_data._extraction_manifest;

  assertTrue("symbols" in manifest, "Missing symbols in manifest");
  assertTrue("imports" in manifest, "Missing imports in manifest");
});

test("attachManifest skips private keys (underscore prefix)", () => {
  const results = {
    "/test/file.ts": {
      success: true,
      extracted_data: {
        symbols: [{ name: "foo" }],
        _internal: [{ secret: "data" }],
      },
    },
  };

  const withManifest = attachManifest(results);
  const manifest =
    withManifest["/test/file.ts"].extracted_data._extraction_manifest;

  assertTrue("symbols" in manifest, "Should include symbols");
  assertFalsy("_internal" in manifest, "_internal should be skipped");
});

test("attachManifest skips non-array values", () => {
  const results = {
    "/test/file.ts": {
      success: true,
      extracted_data: {
        symbols: [{ name: "foo" }],
        metadata: { version: "1.0" },
        count: 42,
      },
    },
  };

  const withManifest = attachManifest(results);
  const manifest =
    withManifest["/test/file.ts"].extracted_data._extraction_manifest;

  assertTrue("symbols" in manifest, "Should include symbols");
  assertFalsy("metadata" in manifest, "metadata should be skipped");
  assertFalsy("count" in manifest, "count should be skipped");
});

test("attachManifest skips failed extractions", () => {
  const results = {
    "/test/good.ts": {
      success: true,
      extracted_data: {
        symbols: [{ name: "foo" }],
      },
    },
    "/test/bad.ts": {
      success: false,
      error: "Parse failed",
    },
  };

  const withManifest = attachManifest(results);

  assertTrue(
    "_extraction_manifest" in withManifest["/test/good.ts"].extracted_data,
    "Good file should have manifest",
  );
  assertFalsy(
    withManifest["/test/bad.ts"].extracted_data,
    "Bad file should not have extracted_data",
  );
});

test("attachManifest handles multiple files", () => {
  const results = {
    "/file1.ts": {
      success: true,
      extracted_data: {
        symbols: [{ name: "a" }],
      },
    },
    "/file2.ts": {
      success: true,
      extracted_data: {
        symbols: [{ name: "b" }, { name: "c" }],
      },
    },
  };

  const withManifest = attachManifest(results);

  const manifest1 =
    withManifest["/file1.ts"].extracted_data._extraction_manifest;
  const manifest2 =
    withManifest["/file2.ts"].extracted_data._extraction_manifest;

  assertEqual(manifest1.symbols.count, 1);
  assertEqual(manifest2.symbols.count, 2);
});

console.log("\n=== SECTION 5: Manifest Token Content Validation ===\n");

test("manifest token has correct structure for reconciliation", () => {
  const results = {
    "/test/file.ts": {
      success: true,
      extracted_data: {
        symbols: [
          { name: "foo", type: "function", line: 10 },
          { name: "bar", type: "class", line: 20 },
        ],
      },
    },
  };

  const withManifest = attachManifest(results);
  const token =
    withManifest["/test/file.ts"].extracted_data._extraction_manifest.symbols;

  assertTrue(typeof token.tx_id === "string", "tx_id should be string");
  assertTrue(Array.isArray(token.columns), "columns should be array");
  assertTrue(typeof token.count === "number", "count should be number");
  assertTrue(typeof token.bytes === "number", "bytes should be number");

  assertEqual(token.count, 2);
  assertArrayEqual(token.columns, ["line", "name", "type"]);
});

test("manifest columns reflect first row schema", () => {
  const results = {
    "/test/file.ts": {
      success: true,
      extracted_data: {
        data: [
          { id: 1, email: "a@b.com", role: "admin" },
          { id: 2, email: "c@d.com", role: "user" },
        ],
      },
    },
  };

  const withManifest = attachManifest(results);
  const token =
    withManifest["/test/file.ts"].extracted_data._extraction_manifest.data;

  assertArrayEqual(token.columns, ["email", "id", "role"]);
});

console.log("\n=== SECTION 6: Python Parity Verification ===\n");

test("byte calculation matches Python FidelityToken.create_manifest", () => {
  const rows = [
    { name: "hello", type: "function", line: 10 },
    { name: "world", type: "class", line: 20 },
  ];

  const manifest = createManifest(rows);

  assertEqual(manifest.bytes, 27, "Byte calculation should match Python");
});

test("empty string values contribute 0 bytes", () => {
  const rows = [{ name: "", value: "" }];
  const manifest = createManifest(rows);

  assertEqual(manifest.bytes, 0);
});

test("numeric values stringified correctly", () => {
  const rows = [{ int_val: 12345, float_val: 3.14159 }];
  const manifest = createManifest(rows);

  assertEqual(manifest.bytes, 12);
});

console.log("\n========================================");
console.log("TEST RESULTS SUMMARY");
console.log("========================================");
console.log(`Total:  ${passed + failed}`);
console.log(`Passed: ${passed}`);
console.log(`Failed: ${failed}`);

if (failures.length > 0) {
  console.log("\nFailed tests:");
  failures.forEach((f, i) => console.log(`  ${i + 1}. ${f}`));
  process.exit(1);
} else {
  console.log("\nAll tests passed!");
  process.exit(0);
}
