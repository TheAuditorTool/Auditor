// src/test_extractor.ts
// Run with: npx ts-node src/test_extractor.ts
// Or after build: node dist/test_extractor.cjs

import * as ts from "typescript";
import { z } from "zod";
import { extractObjectLiterals } from "./extractors/data_flow";
import { ObjectLiteralSchema, VariableUsageSchema } from "./schema";

console.log("Starting Sanity Check...");
console.log("=".repeat(50));

// 1. Create a fake source file in memory
const code = `
const config = {
    apiKey: "12345",
    retries: 3,
    nested: {
        deep: true
    }
};

function doSomething() {
    const inner = { foo: "bar" };
    return inner;
}
`;

const sourceFile = ts.createSourceFile("dummy.ts", code, ts.ScriptTarget.Latest, true);
const scopeMap = new Map<number, string>();
// Mock scope: line 11 is inside doSomething
scopeMap.set(11, "doSomething");
scopeMap.set(12, "doSomething");

// 2. Run the extractor
console.log("\n[TEST] Running extractObjectLiterals...");
const results = extractObjectLiterals(sourceFile, ts, scopeMap, "dummy.ts");

console.log(`[TEST] Extracted ${results.length} items`);
console.log("[TEST] Sample output:");
results.slice(0, 5).forEach((r, i) => {
    console.log(`  [${i}] ${r.variable_name}.${r.property_name} = ${r.property_value} (${r.property_type})`);
});

// 3. THE MOMENT OF TRUTH
console.log("\n[TEST] Validating against Zod schema...");
try {
    z.array(ObjectLiteralSchema).parse(results);
    console.log("[PASS] SUCCESS: Data matches ObjectLiteralSchema perfectly!");
} catch (e) {
    console.error("[FAIL] FAILURE: Schema Mismatch!");
    if (e instanceof z.ZodError) {
        console.error(JSON.stringify(e.errors, null, 2));
    } else {
        console.error(e);
    }
    process.exit(1);
}

// 4. Print schema expectations for reference
console.log("\n[INFO] Current ObjectLiteralSchema expects:");
console.log("  - file: string");
console.log("  - line: number");
console.log("  - variable_name: string");
console.log("  - property_name: string");
console.log("  - property_value: string");
console.log("  - property_type: string");
console.log("  - nested_level: number");
console.log("  - in_function: string");

console.log("\n" + "=".repeat(50));
console.log("[DONE] Sanity check complete.");
