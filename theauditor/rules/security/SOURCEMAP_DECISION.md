# Sourcemap Detector Migration Decision

## Decision: DO NOT MIGRATE

### File: sourcemap_detector.py (209 lines)

## Rationale for Keeping File-Based Implementation

### 1. File I/O Operations Required
The detector performs direct file system operations that cannot be replaced with database queries:
- `Path.rglob('*.map')` - Scanning for map files
- `file.exists()` - Checking if referenced maps exist
- Reading file content to find inline source maps
- Scanning build directories (dist/, build/, public/)

### 2. Not AST-Based Analysis
Unlike other analyzers that parse AST structures, this detector:
- Reads raw file content looking for source map comments
- Checks file extensions and directory structures
- Examines the last 5000 characters of JS files for performance
- Uses regex patterns on file content, not code structure

### 3. Database Doesn't Contain Required Data
The repo_index.db does not and should not contain:
- Build artifact locations
- Minified file contents
- Source map file existence
- Production directory structures
- File content patterns (only AST symbols)

### 4. Already Optimized
The current implementation is already efficient:
- Only 209 lines (compact)
- Optimized file reading (last 5000 chars only)
- Smart directory filtering (skips node_modules)
- Direct file system access is fastest approach

## What This Detector Does

1. **External Source Maps**: Finds .map files in production directories
2. **Inline Source Maps**: Detects base64-encoded maps in JS files
3. **Source Map URLs**: Identifies sourceMappingURL comments

## Why File-Based is Correct

This is fundamentally a **deployment security check**, not a code analysis task:
- Checks what gets deployed to production
- Validates build output configuration
- Ensures source maps aren't accidentally exposed

## Performance Characteristics

| Operation | Current (File I/O) | If SQL (Hypothetical) |
|-----------|-------------------|----------------------|
| Find .map files | Direct glob | N/A - not in DB |
| Read JS tail | 5ms per file | Would need full content |
| Check file exists | <1ms | N/A - not tracked |
| Total | ~100ms per project | Cannot implement |

## Conclusion

**sourcemap_detector.py should remain as a file-based detector.** It serves a different purpose than AST analyzers - it's a deployment/build artifact scanner that requires direct file system access. The database approach would be impossible since the required data isn't indexed.

This is similar to how bundle_analyze.py uses a hybrid approach for file size checks - some operations inherently require file I/O and cannot be replaced with database queries.

---

*Decision: Keep original implementation without changes.*