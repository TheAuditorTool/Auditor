#!/usr/bin/env node
/**
 * purge_comments_js.js - The "Nuclear Option" comment purger for JavaScript/TypeScript.
 *
 * PURPOSE: Break the AI hallucination feedback loop by removing all comments
 * from a saturated codebase, forcing AI to read only executable logic.
 *
 * ACTIONS:
 * 1. PURGES: Removes ALL comments from JS/TS/JSX/TSX files
 * 2. GRAVEYARD: Saves ALL removed comments to a flat JSON (backup/reference)
 * 3. DEBT REPORT: Saves ONLY TODO/FIXME/etc to a separate JSON (gold mine for review)
 *
 * PRESERVES (always):
 * - Code structure and formatting (via recast)
 * - Shebang lines (#!/usr/bin/env node)
 *
 * PRESERVES (optional via flags):
 * - Semantic comments (eslint-disable, @ts-ignore, prettier-ignore, etc.)
 * - Copyright headers (copyright, license, (c), etc.)
 * - JSDoc blocks (for IDE intellisense)
 *
 * Based on jscodeshift 17.x best practices.
 *
 * Usage:
 *   node purge_comments_js.js ./src --dry-run
 *   node purge_comments_js.js ./src --preserve-semantic
 *   node purge_comments_js.js ./src --preserve-copyright
 *   node purge_comments_js.js ./src --preserve-jsdoc
 */

const fs = require("fs");
const path = require("path");

// Try to load jscodeshift - provide helpful error if not installed
let j;
try {
  j = require("jscodeshift");
} catch (e) {
  console.error("ERROR: jscodeshift not installed.");
  console.error("Run: npm install -g jscodeshift");
  console.error("Or:  npm install --save-dev jscodeshift");
  process.exit(1);
}

// =============================================================================
// CONFIGURATION
// =============================================================================

// Directories to skip by default
const DEFAULT_SKIP_DIRS = new Set([
  ".git",
  ".venv",
  "venv",
  "__pycache__",
  "node_modules",
  ".tox",
  ".mypy_cache",
  ".pytest_cache",
  "dist",
  "build",
  ".eggs",
  ".egg-info",
  ".pf",
  ".auditor_venv",
  "coverage",
  ".next",
  ".nuxt",
  ".output",
]);

// File extensions to process (including modern ES module extensions)
const JS_EXTENSIONS = new Set([
  ".js",
  ".jsx",
  ".ts",
  ".tsx",
  ".mjs",
  ".cjs",
  ".mts",
  ".cts",
]);

// Semantic markers - these are CODE INSTRUCTIONS, not human comments
// Removing these will break linters, type checkers, and bundlers
const SEMANTIC_MARKERS = [
  "eslint-disable",
  "eslint-enable",
  "@ts-ignore",
  "@ts-expect-error",
  "@ts-nocheck",
  "@ts-check",
  "prettier-ignore",
  "istanbul ignore",
  "@flow",
  "@noflow",
  "webpack",
  "webpackChunkName",
  "@jsx",
  "@jsxFrag",
  "@babel",
  "sourceMappingURL",
  "jshint",
  "jslint",
  "globals",
  "exported",
  "c8 ignore",
  "v8 ignore",
  "coverage ignore",
];

// JSDoc type annotation markers (for --preserve-jsdoc)
// These provide IDE intellisense and are often required for proper tooling
const JSDOC_MARKERS = [
  "@type",
  "@param",
  "@returns",
  "@return",
  "@typedef",
  "@template",
  "@implements",
  "@extends",
  "@augments",
  "@callback",
  "@property",
  "@prop",
  "@member",
  "@memberof",
  "@class",
  "@constructor",
  "@function",
  "@method",
  "@module",
  "@namespace",
  "@enum",
  "@const",
  "@constant",
  "@default",
  "@deprecated",
  "@description",
  "@example",
  "@throws",
  "@async",
  "@generator",
  "@yields",
  "@private",
  "@protected",
  "@public",
  "@readonly",
  "@override",
  "@satisfies",
];

// Copyright/license markers - legal headers that may be required
const COPYRIGHT_MARKERS = [
  "copyright",
  "license",
  "licensed",
  "spdx-license-identifier",
  "spdx-",
  "(c)",
  "all rights reserved",
  "apache license",
  "mit license",
  "bsd license",
  "gnu general public",
  "gpl",
  "lgpl",
  "mozilla public",
  "proprietary",
];

// Technical debt markers with descriptions
const DEBT_MARKERS = {
  // === CRITICAL - Address immediately ===
  FIXME: { desc: "Known bug requiring fix", priority: 1, label: "CRITICAL" },
  BUG: { desc: "Known bug", priority: 1, label: "CRITICAL" },
  BROKEN: { desc: "Known broken code", priority: 1, label: "CRITICAL" },
  NOCOMMIT: {
    desc: "Should not have been committed",
    priority: 1,
    label: "CRITICAL",
  },

  // === HIGH PRIORITY - Address soon ===
  TODO: { desc: "Deferred task", priority: 2, label: "HIGH" },
  HACK: { desc: "Temporary workaround", priority: 2, label: "HIGH" },
  XXX: { desc: "Dangerous/requires attention", priority: 2, label: "HIGH" },
  KLUDGE: { desc: "Ugly hack", priority: 2, label: "HIGH" },
  WORKAROUND: { desc: "Working around an issue", priority: 2, label: "HIGH" },

  // === MEDIUM PRIORITY - Technical debt ===
  FIX: { desc: "Needs fixing", priority: 3, label: "MEDIUM" },
  OPTIMIZE: {
    desc: "Performance improvement needed",
    priority: 3,
    label: "MEDIUM",
  },
  REFACTOR: { desc: "Needs refactoring", priority: 3, label: "MEDIUM" },
  CLEANUP: { desc: "Needs cleanup", priority: 3, label: "MEDIUM" },
  REVIEW: { desc: "Needs review", priority: 3, label: "MEDIUM" },

  // === LOW PRIORITY - Deferred work ===
  DEFER: { desc: "Explicitly deferred", priority: 4, label: "LOW" },
  DEFERRED: { desc: "Explicitly deferred", priority: 4, label: "LOW" },
  LATER: { desc: "Do later", priority: 4, label: "LOW" },
  WIP: { desc: "Work in progress", priority: 4, label: "LOW" },

  // === INFORMATIONAL - May contain gold ===
  TEMP: { desc: "Temporary code", priority: 5, label: "INFO" },
  TEMPORARY: { desc: "Temporary code", priority: 5, label: "INFO" },
  DEBUG: { desc: "Debug code left in", priority: 5, label: "INFO" },
  DEPRECATED: { desc: "Should be removed", priority: 5, label: "INFO" },
  REMOVEME: { desc: "Should be removed", priority: 5, label: "INFO" },
  NOTE: { desc: "Important note", priority: 6, label: "NOTE" },
  IMPORTANT: { desc: "Important information", priority: 6, label: "NOTE" },
};

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

/**
 * Check if comment is a semantic/linter directive.
 */
function isSemanticComment(value) {
  if (typeof value !== "string") return false;
  const valueLower = value.toLowerCase();
  return SEMANTIC_MARKERS.some((marker) =>
    valueLower.includes(marker.toLowerCase()),
  );
}

/**
 * Check if comment is a JSDoc type annotation.
 */
function isJSDocComment(value, type) {
  if (typeof value !== "string") return false;
  // JSDoc comments are block comments starting with /**
  if (type !== "CommentBlock" && type !== "Block") {
    return false;
  }
  // Check if it starts with * (the /** opener leaves the first *)
  const trimmed = value.trim();
  if (!trimmed.startsWith("*")) {
    return false;
  }
  // Check for any JSDoc markers
  const valueLower = value.toLowerCase();
  return JSDOC_MARKERS.some((marker) =>
    valueLower.includes(marker.toLowerCase()),
  );
}

/**
 * Check if comment is a copyright/license header.
 */
function isCopyrightComment(value) {
  if (typeof value !== "string") return false;
  const valueLower = value.toLowerCase();
  return COPYRIGHT_MARKERS.some((marker) =>
    valueLower.includes(marker.toLowerCase()),
  );
}

/**
 * Detect ALL debt markers in a comment.
 */
function detectDebtTags(commentText) {
  if (typeof commentText !== "string") return [];
  const commentUpper = commentText.toUpperCase();
  const foundTags = [];

  for (const marker of Object.keys(DEBT_MARKERS)) {
    if (commentUpper.includes(marker)) {
      foundTags.push(marker);
    }
  }

  return foundTags;
}

/**
 * Get the highest-priority marker from a list of tags.
 */
function getPriorityMarker(tags) {
  if (tags.length === 0) return "UNKNOWN";
  return tags.reduce((best, tag) => {
    const bestPriority = DEBT_MARKERS[best]?.priority ?? 99;
    const tagPriority = DEBT_MARKERS[tag]?.priority ?? 99;
    return tagPriority < bestPriority ? tag : best;
  });
}

/**
 * Get comment value (handles both line and block comments).
 */
function getCommentValue(comment) {
  const value = comment.value;
  if (typeof value === "string") return value;
  if (value === null || value === undefined) return "";
  return String(value);
}

/**
 * Clean comment text for display.
 */
function cleanCommentText(value, type) {
  // Handle edge case where value might not be a string
  if (typeof value !== "string") {
    return String(value || "");
  }
  let clean = value;
  // Remove leading/trailing whitespace and asterisks from block comments
  if (type === "CommentBlock" || type === "Block") {
    clean = clean.replace(/^\s*\*+\s?/gm, "").trim();
  }
  return clean.trim();
}

/**
 * Determine parser based on file extension.
 */
function getParser(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  if (ext === ".tsx" || ext === ".mts" || ext === ".cts") return "tsx";
  if (ext === ".ts") return "ts";
  if (ext === ".jsx") return "babel";
  return "babel";
}

/**
 * Walk directory recursively.
 */
function walkDirectory(dir, skipDirs, extensions) {
  const files = [];

  function walk(currentDir) {
    const entries = fs.readdirSync(currentDir, { withFileTypes: true });

    for (const entry of entries) {
      const fullPath = path.join(currentDir, entry.name);

      if (entry.isDirectory()) {
        if (!skipDirs.has(entry.name)) {
          walk(fullPath);
        }
      } else if (entry.isFile()) {
        const ext = path.extname(entry.name).toLowerCase();
        if (extensions.has(ext)) {
          files.push(fullPath);
        }
      }
    }
  }

  walk(dir);
  return files;
}

// =============================================================================
// TRANSFORM LOGIC (Best Practice: Use j.Comment with path.prune())
// =============================================================================

/**
 * Process a single file to remove comments.
 * Uses the optimized j.Comment traversal per jscodeshift FAQ best practices.
 */
function processFile(filePath, options) {
  const {
    preserveSemantic = false,
    preserveCopyright = false,
    preserveJSDoc = false,
    dryRun = false,
  } = options;

  const results = {
    removed: [],
    debt: [],
    preserved: [],
    error: null,
  };

  let source;
  try {
    source = fs.readFileSync(filePath, "utf-8");
  } catch (e) {
    results.error = `Read error: ${e.message}`;
    return results;
  }

  // Skip empty files (Best Practice: Early exit)
  if (!source.trim()) {
    return results;
  }

  // Skip generated files (Best Practice from FAQ Section 6.6)
  if (
    source.includes("@generated") ||
    source.includes("AUTO-GENERATED") ||
    source.includes("DO NOT EDIT")
  ) {
    return results;
  }

  const parserName = getParser(filePath);
  let root;

  try {
    // When using jscodeshift programmatically, use withParser() to set the parser
    // The { parser: 'tsx' } options syntax only works with the CLI runner
    const jWithParser = j.withParser(parserName);
    root = jWithParser(source);
  } catch (e) {
    results.error = `Parse error: ${e.message}`;
    return results;
  }

  // Track multi-line debt grouping state
  let activeDebtEntry = null;
  let lastDebtLine = -1;

  // Collect comments to process (we need to track which ones to prune)
  const commentsToPrune = [];

  /**
   * Process a single comment and determine if it should be pruned.
   * Returns true if comment should be PRESERVED (not pruned).
   */
  function processComment(commentPath) {
    const comment = commentPath.node;
    const value = getCommentValue(comment);
    const type = comment.type;
    const line = comment.loc?.start?.line || -1;
    const cleanValue = cleanCommentText(value, type);

    // Check if should preserve
    let shouldPreserve = false;
    let preserveReason = "";

    if (preserveSemantic && isSemanticComment(value)) {
      shouldPreserve = true;
      preserveReason = "semantic";
    } else if (preserveJSDoc && isJSDocComment(value, type)) {
      shouldPreserve = true;
      preserveReason = "jsdoc";
    } else if (preserveCopyright && isCopyrightComment(value)) {
      shouldPreserve = true;
      preserveReason = "copyright";
    }

    const record = {
      file: filePath.replace(/\\/g, "/"),
      line,
      type: type === "CommentLine" || type === "Line" ? "line" : "block",
      raw:
        type === "CommentLine" || type === "Line"
          ? `//${value}`
          : `/*${value}*/`,
      clean: cleanValue,
    };

    if (shouldPreserve) {
      record.preserve_reason = preserveReason;
      results.preserved.push(record);
      // Break debt chain
      activeDebtEntry = null;
      lastDebtLine = -1;
      return true; // Keep this comment
    }

    // Comment will be removed
    results.removed.push(record);

    // Debt tracking with multi-line grouping
    const tags = detectDebtTags(value);

    if (tags.length > 0) {
      // New debt marker found
      const primary = getPriorityMarker(tags);
      activeDebtEntry = {
        file: filePath.replace(/\\/g, "/"),
        line,
        primary_marker: primary,
        tags,
        category: DEBT_MARKERS[primary]?.desc || "Unknown",
        priority_label: DEBT_MARKERS[primary]?.label || "UNKNOWN",
        clean: cleanValue,
        raw: record.raw,
      };
      results.debt.push(activeDebtEntry);
      lastDebtLine = line;
    } else if (activeDebtEntry && line === lastDebtLine + 1) {
      // Continuation of previous debt entry
      activeDebtEntry.clean += ` ${cleanValue}`;
      activeDebtEntry.raw += `\n${record.raw}`;
      lastDebtLine = line;
    } else {
      // Break chain
      activeDebtEntry = null;
      lastDebtLine = -1;
    }

    return false; // Remove this comment
  }

  // Best Practice: Use j.Comment to find all comments directly
  // This is more efficient than iterating all nodes (O(comments) vs O(all nodes))
  root.find(j.Comment).forEach((commentPath) => {
    const shouldKeep = processComment(commentPath);
    if (!shouldKeep && !dryRun) {
      commentsToPrune.push(commentPath);
    }
  });

  // Prune comments (Best Practice: Use path.prune() instead of manual array manipulation)
  if (!dryRun) {
    for (const commentPath of commentsToPrune) {
      try {
        commentPath.prune();
      } catch (e) {
        // Some comments may be attached in ways that prune() doesn't handle well
        // Fall back to clearing the comment from the parent node
        const parent = commentPath.parent;
        const comment = commentPath.node;

        if (parent && parent.node) {
          const node = parent.node;

          // Remove from leadingComments
          if (node.leadingComments) {
            node.leadingComments = node.leadingComments.filter(
              (c) => c !== comment,
            );
            if (node.leadingComments.length === 0) {
              node.leadingComments = undefined;
            }
          }
          // Remove from trailingComments
          if (node.trailingComments) {
            node.trailingComments = node.trailingComments.filter(
              (c) => c !== comment,
            );
            if (node.trailingComments.length === 0) {
              node.trailingComments = undefined;
            }
          }
          // Remove from innerComments
          if (node.innerComments) {
            node.innerComments = node.innerComments.filter(
              (c) => c !== comment,
            );
            if (node.innerComments.length === 0) {
              node.innerComments = undefined;
            }
          }
          // Remove from comments array
          if (node.comments) {
            node.comments = node.comments.filter((c) => c !== comment);
            if (node.comments.length === 0) {
              node.comments = undefined;
            }
          }
        }

        // Handle orphaned comments at end of file (attached to Program node)
        // These are trailing comments not attached to any specific node
        const programNode = root.get().node;
        if (programNode && programNode.comments) {
          programNode.comments = programNode.comments.filter(
            (c) => c !== comment,
          );
          if (programNode.comments.length === 0) {
            programNode.comments = undefined;
          }
        }
      }
    }
  }

  // Write back if not dry run and we made changes
  if (!dryRun && results.removed.length > 0) {
    try {
      let output = root.toSource({
        quote: "single",
        lineTerminator: "\n",
      });

      // Shebang preservation: ensure newline after shebang if it exists
      // Removing the first comment can sometimes merge shebang with first line
      if (output.startsWith("#!")) {
        const firstNewLine = output.indexOf("\n");
        if (firstNewLine === -1) {
          // File is just a shebang with no newline
          output += "\n";
        } else {
          // Check if there's content immediately after shebang line
          const shebangLine = output.substring(0, firstNewLine);
          const afterShebang = output.substring(firstNewLine + 1);
          // Ensure there's proper separation (at least one newline after shebang)
          if (
            afterShebang.length > 0 &&
            !afterShebang.startsWith("\n") &&
            !shebangLine.endsWith("\n")
          ) {
            output = shebangLine + "\n" + afterShebang;
          }
        }
      }

      fs.writeFileSync(filePath, output, "utf-8");
    } catch (e) {
      results.error = `Write error: ${e.message}`;
    }
  }

  return results;
}

// =============================================================================
// MAIN
// =============================================================================

function main() {
  const args = process.argv.slice(2);

  // Parse arguments
  let targetDir = ".";
  let dryRun = false;
  let extractOnly = false;
  let preserveSemantic = false;
  let preserveCopyright = false;
  let preserveJSDoc = false;
  let graveyardFile = "comment_graveyard_js.json";
  let debtFile = "technical_debt_js.json";
  const extraSkipDirs = [];
  let noConfirm = false;

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];

    if (arg === "--dry-run" || arg === "-d") {
      dryRun = true;
    } else if (arg === "--extract-only") {
      extractOnly = true;
    } else if (arg === "--preserve-semantic") {
      preserveSemantic = true;
    } else if (arg === "--preserve-copyright") {
      preserveCopyright = true;
    } else if (arg === "--preserve-jsdoc") {
      preserveJSDoc = true;
    } else if (arg.startsWith("--graveyard=")) {
      graveyardFile = arg.split("=")[1];
    } else if (arg.startsWith("--debt-file=")) {
      debtFile = arg.split("=")[1];
    } else if (arg.startsWith("--skip=")) {
      extraSkipDirs.push(...arg.split("=")[1].split(","));
    } else if (arg === "--no-confirm") {
      noConfirm = true;
    } else if (arg === "--help" || arg === "-h") {
      console.log(`
purge_comments_js.js - Nuclear comment purger for JavaScript/TypeScript

Usage:
  node purge_comments_js.js [directory] [options]

Options:
  --dry-run, -d         Preview changes without modifying files
  --extract-only        Extract comments to JSON without modifying source
  --preserve-semantic   Keep linter directives (eslint-disable, @ts-ignore, etc.)
  --preserve-copyright  Keep copyright/license headers
  --preserve-jsdoc      Keep JSDoc type annotations (@param, @returns, @type, etc.)
  --graveyard=FILE      Output file for ALL removed comments (default: comment_graveyard_js.json)
  --debt-file=FILE      Output file for debt markers only (default: technical_debt_js.json)
  --skip=DIRS           Additional directories to skip (comma-separated)
  --no-confirm          Skip confirmation prompt
  --help, -h            Show this help

Auto-skipped files:
  - Files containing @generated, AUTO-GENERATED, or DO NOT EDIT

Examples:
  node purge_comments_js.js ./src --dry-run
  node purge_comments_js.js ./src --preserve-semantic --no-confirm
  node purge_comments_js.js ./src --preserve-jsdoc --preserve-semantic
  node purge_comments_js.js . --extract-only
`);
      process.exit(0);
    } else if (!arg.startsWith("-")) {
      targetDir = arg;
    }
  }

  // Build skip set
  const skipDirs = new Set([...DEFAULT_SKIP_DIRS, ...extraSkipDirs]);

  // Validate directory
  if (!fs.existsSync(targetDir)) {
    console.error(`ERROR: Directory not found: ${targetDir}`);
    process.exit(1);
  }

  const absDir = path.resolve(targetDir);

  // Confirmation
  if (!noConfirm && !dryRun && !extractOnly) {
    console.log("=".repeat(60));
    console.log("WARNING: NUCLEAR OPTION");
    console.log("This will DELETE ALL comments from JS/TS files.");
    if (preserveSemantic) {
      console.log(
        "KEEPING: Semantic comments (eslint-disable, @ts-ignore, etc.)",
      );
    }
    if (preserveJSDoc) {
      console.log("KEEPING: JSDoc type annotations (@param, @returns, etc.)");
    }
    if (preserveCopyright) {
      console.log("KEEPING: Copyright/license headers");
    }
    console.log("=".repeat(60));
    console.log("");
    console.log("Run with --no-confirm to skip this prompt.");
    console.log("Or use --dry-run to preview changes first.");
    process.exit(1);
  }

  // Mode string
  let modeStr = "";
  if (dryRun) modeStr = "[DRY RUN] ";
  else if (extractOnly) modeStr = "[EXTRACT ONLY] ";

  console.log(`${modeStr}NUCLEAR COMMENT PURGE (JavaScript/TypeScript)`);
  console.log(`Target: ${absDir}`);
  console.log(`Skipping: ${Array.from(skipDirs).sort().join(", ")}`);
  console.log(`Extensions: ${Array.from(JS_EXTENSIONS).sort().join(", ")}`);
  console.log(
    `Debt markers: ${Object.keys(DEBT_MARKERS).length} types tracked`,
  );
  if (preserveSemantic) {
    console.log(
      "PRESERVING: Semantic comments (@ts-ignore, eslint-disable, etc.)",
    );
  }
  if (preserveJSDoc) {
    console.log(
      "PRESERVING: JSDoc type annotations (@param, @returns, @type, etc.)",
    );
  }
  if (preserveCopyright) {
    console.log("PRESERVING: Copyright/license headers");
  }
  console.log("");

  // Collect files
  const files = walkDirectory(absDir, skipDirs, JS_EXTENSIONS);

  if (files.length === 0) {
    console.log("No JavaScript/TypeScript files found.");
    process.exit(0);
  }

  // Process files
  const startTime = Date.now();
  const allRemoved = [];
  const allDebt = [];
  const allPreserved = [];
  let filesModified = 0;
  let filesSkipped = 0;
  let errorCount = 0;

  for (const filePath of files) {
    const results = processFile(filePath, {
      preserveSemantic,
      preserveCopyright,
      preserveJSDoc,
      dryRun: dryRun || extractOnly,
    });

    if (results.error) {
      console.log(`  ! ERROR in ${filePath}: ${results.error}`);
      errorCount++;
      continue;
    }

    if (results.removed.length > 0) {
      allRemoved.push(...results.removed);
      allDebt.push(...results.debt);
      allPreserved.push(...results.preserved);
      filesModified++;

      const parts = [`${results.removed.length} removed`];
      if (results.debt.length > 0) {
        parts.push(`${results.debt.length} debt`);
      }
      if (results.preserved.length > 0) {
        parts.push(`${results.preserved.length} kept`);
      }

      const relPath = path.relative(absDir, filePath).replace(/\\/g, "/");
      console.log(`  - ${parts.join(", ")} : ./${relPath}`);
    } else if (results.preserved.length > 0) {
      // File had only preserved comments
      allPreserved.push(...results.preserved);
    }
  }

  // Write output files
  if (!dryRun) {
    if (allRemoved.length > 0) {
      fs.writeFileSync(
        graveyardFile,
        JSON.stringify(allRemoved, null, 2),
        "utf-8",
      );
    }

    if (allDebt.length > 0) {
      // Sort by priority, then file, then line
      const sortedDebt = allDebt.sort((a, b) => {
        const aPriority = DEBT_MARKERS[a.primary_marker]?.priority ?? 99;
        const bPriority = DEBT_MARKERS[b.primary_marker]?.priority ?? 99;
        if (aPriority !== bPriority) return aPriority - bPriority;
        if (a.file !== b.file) return a.file.localeCompare(b.file);
        return a.line - b.line;
      });
      fs.writeFileSync(debtFile, JSON.stringify(sortedDebt, null, 2), "utf-8");
    }
  }

  const duration = ((Date.now() - startTime) / 1000).toFixed(2);

  // Summary
  console.log("");
  console.log("=".repeat(60));
  console.log(`${modeStr}COMPLETED in ${duration}s`);
  console.log(`Files Processed: ${files.length}`);
  console.log(`Files Modified: ${filesModified}`);
  console.log(`Comments Removed: ${allRemoved.length}`);
  console.log(`Comments Preserved: ${allPreserved.length}`);
  console.log(`Technical Debt Found: ${allDebt.length}`);
  if (errorCount > 0) {
    console.log(`Errors: ${errorCount}`);
  }

  // Debt breakdown
  if (allDebt.length > 0) {
    console.log("");
    console.log("=== TECHNICAL DEBT BREAKDOWN ===");
    const debtByMarker = {};
    for (const item of allDebt) {
      const marker = item.primary_marker;
      debtByMarker[marker] = (debtByMarker[marker] || 0) + 1;
    }

    const sortedMarkers = Object.entries(debtByMarker).sort((a, b) => {
      const aPriority = DEBT_MARKERS[a[0]]?.priority ?? 99;
      const bPriority = DEBT_MARKERS[b[0]]?.priority ?? 99;
      if (aPriority !== bPriority) return aPriority - bPriority;
      return b[1] - a[1];
    });

    for (const [marker, count] of sortedMarkers) {
      const info = DEBT_MARKERS[marker] || { desc: "Unknown", label: "" };
      console.log(
        `  ${marker.padEnd(12)} : ${String(count).padStart(4)}  [${info.label.padEnd(8)}] ${info.desc}`,
      );
    }
  }

  // Preserved breakdown
  if (allPreserved.length > 0) {
    console.log("");
    console.log("=== PRESERVED COMMENTS ===");
    const byReason = {};
    for (const item of allPreserved) {
      const reason = item.preserve_reason || "unknown";
      byReason[reason] = (byReason[reason] || 0) + 1;
    }
    for (const [reason, count] of Object.entries(byReason).sort()) {
      console.log(`  ${reason.padEnd(12)} : ${String(count).padStart(4)}`);
    }
  }

  // Output files
  if (!dryRun) {
    console.log("");
    console.log("OUTPUT FILES:");
    if (allRemoved.length > 0) {
      console.log(`  ${graveyardFile}`);
      console.log(`    -> ${allRemoved.length} comments (backup dump)`);
    }
    if (allDebt.length > 0) {
      console.log(`  ${debtFile}`);
      console.log(`    -> ${allDebt.length} items (REVIEW THIS FOR GOLD)`);
    }
  }
  console.log("=".repeat(60));

  // Next steps
  if (allRemoved.length > 0 && !dryRun) {
    console.log("");
    console.log("NEXT STEPS:");
    console.log("  1. Run your formatter:");
    console.log("     npx prettier --write .");
    console.log("     # or: npx eslint --fix .");
    console.log("");
    if (allDebt.length > 0) {
      console.log("  2. Mine the gold:");
      console.log(`     cat ${debtFile}`);
      console.log("");
      console.log("  3. Address by priority:");
      console.log("     - CRITICAL first (FIXME, BUG, BROKEN)");
      console.log("     - Then HIGH (TODO, HACK, XXX)");
    }
  }
}

main();
