# Taint Analysis Spatial Index Design Decisions

**Status**: 🔴 DRAFT

---

## 1. Spatial Index Architecture

### 1.1 Line Blocking Strategy

**Decision**: Use 100-line blocks for spatial grouping

**Rationale**:
- Functions typically 10-200 lines → 1-2 blocks per function
- Balance between memory overhead and lookup efficiency
- Allows O(1) lookup for most queries (check current block + 1-2 adjacent)

**Alternative Considered**: 50-line blocks
**Rejected**: Higher memory overhead (~2x) for minimal benefit

---

## 2. Index Data Structures

### 2.1 symbols_by_type

```python
Dict[str, List[Dict]]
# Example: {'property': [...], 'function': [...]}
```

**Decision**: Simple dict, no nesting

**Rationale**:
- Discovery phase queries by type only (no file filtering)
- Flat structure = O(1) lookup
- Memory: ~500KB for 100K symbols (negligible)

### 2.2 symbols_by_file_line

```python
Dict[str, Dict[int, List[Dict]]]
# Example: {'src/main.py': {0: [...], 100: [...], 200: [...]}}
```

**Decision**: Two-level nested dict (file → line_block → symbols)

**Rationale**:
- Analysis phase queries by file AND line range
- Two-level nesting enables O(1) file lookup + O(1) block lookup
- Memory: ~2-3MB for 100K symbols (acceptable)

**Alternative Considered**: Triple-level dict (file → function → line_block)
**Rejected**: Functions overlap (nested functions), complicates logic

### 2.3 successors_by_block (Adjacency List)

```python
Dict[str, List[str]]
# Example: {'block_123': ['block_124', 'block_125']}
```

**Decision**: Simple adjacency list (block_id → successor_block_ids)

**Rationale**:
- CFG traversal is O(n²) nested loop currently (50M ops)
- Adjacency list is standard graph representation → O(1) successor lookup
- Memory: ~1MB for 10K blocks (negligible)

**Alternative Considered**: Adjacency matrix
**Rejected**: Sparse graph (avg 2 successors per block) → matrix wastes memory

---

## 3. Performance Analysis

### 3.1 Operation Count Reduction

| Function | Before | After | Improvement |
|----------|--------|-------|-------------|
| `_get_containing_function` | 100M | 1K | 100,000x |
| `_propagate_through_block` | 500M | 500K | 1,000x |
| `_get_calls_in_block` | 500M | 500K | 1,000x |
| `_get_block_successors` | 50M | O(1) | 50,000,000x |
| Discovery phase | 500K | 1K | 500x |
| **TOTAL** | 165M-20B | 1M | 100-1000x |

### 3.2 Memory Overhead

| Index | Size (100K symbols) | Justification |
|-------|---------------------|---------------|
| `symbols_by_type` | 500KB | Flat dict, minimal overhead |
| `symbols_by_file_line` | 2-3MB | Two-level nesting, 100-line blocks |
| `assignments_by_location` | 2-3MB | Same structure as symbols_by_file_line |
| `calls_by_location` | 2-3MB | Same structure |
| `successors_by_block` | 1MB | Adjacency list for CFG |
| `blocks_by_id` | 500KB | Block lookup table |
| **TOTAL** | ~10-15MB | Acceptable (< 10% of baseline) |

---

## 4. Edge Cases

### 4.1 Functions Spanning Block Boundaries

**Problem**: Function starts at line 95, ends at line 105 (spans blocks 0 and 100)

**Solution**: When querying line 100, check 3 blocks: [0, 100, 200]
- Current block (100)
- Previous block (0) - catches functions starting before boundary
- Next block (200) - catches functions ending after boundary

**Complexity**: O(3 × symbols_per_block) = still O(1) constant time

### 4.2 Empty Files

**Problem**: File has no symbols, no assignments, no calls

**Solution**: Return empty list from `.get(file, {})` - no special handling needed

### 4.3 Very Large Functions (10,000+ LOC)

**Problem**: Function spans 100+ blocks (lines 0-10000)

**Solution**: Query still O(1) - lookup current block only, range check handles rest
- Spatial index doesn't scan all blocks, just returns symbols in current block
- Range check `start_line <= line <= end_line` filters correctly

---

## 5. Implementation Notes

### 5.1 Index Building Complexity

**Time Complexity**: O(n) where n = number of symbols/assignments/calls
- Single pass through each table
- No nested loops in index building

**Space Complexity**: O(n)
- Each symbol/assignment/call stored in 1-2 index entries
- No duplication (just dict references)

### 5.2 Lookup Complexity

| Operation | Before | After |
|-----------|--------|-------|
| Get symbols by type | O(n) | O(1) |
| Get symbols in line range | O(n) | O(1) |
| Get CFG successors | O(n²) | O(1) |

**After** column assumes average case (symbols distributed evenly across blocks)

---

## 6. Future Optimizations (Out of Scope)

### 6.1 Incremental Index Updates

**Current**: Rebuild entire index on every `aud full`

**Future**: Update only changed files
- Track file modifications
- Rebuild only affected file's index entries
- Would enable 10-100x faster incremental indexing

**Decision**: Out of scope for this proposal (database regenerated fresh every run)

### 6.2 On-Disk Index Caching

**Current**: In-memory only (rebuild on every load)

**Future**: Serialize spatial indexes to disk (SQLite table or pickle)
- Load indexes in <100ms instead of rebuilding in ~2 seconds
- Would enable near-instant taint analysis startup

**Decision**: Out of scope (2-second rebuild is acceptable for now)

---

**Status**: 🔴 DRAFT - Awaiting implementation
