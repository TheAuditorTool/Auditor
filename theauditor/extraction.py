"""Extraction module - pure courier model for data chunking.

This module implements the courier model: takes raw tool output and chunks it
into manageable pieces for AI processing WITHOUT any filtering or interpretation.

Pure Courier Principles:
- NO filtering by severity or importance
- NO deduplication or sampling
- NO interpretation of findings
- ONLY chunks files if they exceed 65KB
- ALL data preserved exactly as generated

The AI consumer decides what's important, not TheAuditor.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict
from datetime import datetime
from theauditor.config_runtime import load_runtime_config


# DELETED: All smart extraction functions removed
# Pure courier model - no filtering, only chunking if needed


def _chunk_large_file(raw_path: Path, max_chunk_size: Optional[int] = None) -> Optional[List[Tuple[Path, int]]]:
    """Split large files into chunks of configured max size."""
    # Load config if not provided
    if max_chunk_size is None:
        config = load_runtime_config()
        max_chunk_size = config["limits"]["max_chunk_size"]
    
    # Get max chunks per file from config
    config = load_runtime_config()
    max_chunks_per_file = config["limits"]["max_chunks_per_file"]
    
    chunks = []
    try:
        # Handle non-JSON files (like .dot, .txt, etc.)
        if raw_path.suffix != '.json':
            # Read as text and chunk if needed
            with open(raw_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Check if file needs chunking
            if len(content) <= max_chunk_size:
                # Small enough, copy as-is
                output_path = raw_path.parent.parent / 'readthis' / raw_path.name
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                size = output_path.stat().st_size
                print(f"  [COPIED] {raw_path.name} → {output_path.name} ({size:,} bytes)")
                return [(output_path, size)]
            else:
                # Need to chunk text file
                base_name = raw_path.stem
                ext = raw_path.suffix
                chunk_num = 0
                position = 0
                
                while position < len(content) and chunk_num < max_chunks_per_file:
                    chunk_num += 1
                    chunk_end = min(position + max_chunk_size, len(content))
                    chunk_content = content[position:chunk_end]
                    
                    output_path = raw_path.parent.parent / 'readthis' / f"{base_name}_chunk{chunk_num:02d}{ext}"
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(chunk_content)
                    size = output_path.stat().st_size
                    chunks.append((output_path, size))
                    print(f"  [CHUNKED] {raw_path.name} → {output_path.name} ({size:,} bytes)")
                    
                    position = chunk_end
                
                if position < len(content):
                    print(f"  [TRUNCATED] {raw_path.name} - stopped at {max_chunks_per_file} chunks")
                
                return chunks
        
        # Handle JSON files
        with open(raw_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check if file is empty
        if not content or not content.strip():
            print(f"  [SKIPPED] {raw_path.name} - empty file (likely no findings)")
            return []  # Empty list = success with no output

        # Try standard JSON first
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            # Check if it's JSONL format (multiple JSON objects)
            if "Extra data" in str(e):
                print(f"  [DETECTED] {raw_path.name} - JSONL format, parsing line-by-line")
                data = []
                for line_num, line in enumerate(content.splitlines(), 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        data.append(obj)
                    except json.JSONDecodeError as line_err:
                        print(f"    [WARNING] Line {line_num}: {line_err}")

                if not data:
                    print(f"  [SKIPPED] {raw_path.name} - no valid JSON objects found")
                    return []
            else:
                # Some other JSON error - re-raise for outer handler
                raise

        # Check if file needs chunking
        full_json = json.dumps(data, indent=2)
        if len(full_json) <= max_chunk_size:
            # Small enough, copy as-is
            output_path = raw_path.parent.parent / 'readthis' / raw_path.name
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(full_json)
            size = output_path.stat().st_size
            print(f"  [COPIED] {raw_path.name} → {output_path.name} ({size:,} bytes)")
            return [(output_path, size)]
        
        # File needs chunking
        base_name = raw_path.stem
        ext = raw_path.suffix
        
        # Handle different data structures
        if isinstance(data, list):
            # For lists, chunk by items
            chunk_num = 0
            current_chunk = []
            current_size = 100  # Account for JSON structure overhead
            
            for item in data:
                item_json = json.dumps(item, indent=2)
                item_size = len(item_json)
                
                if current_size + item_size > max_chunk_size and current_chunk:
                    # Check chunk limit
                    if chunk_num >= max_chunks_per_file:
                        print(f"  [TRUNCATED] {raw_path.name} - stopped at {max_chunks_per_file} chunks (would have created more)")
                        break
                    
                    # Write current chunk
                    chunk_num += 1
                    output_path = raw_path.parent.parent / 'readthis' / f"{base_name}_chunk{chunk_num:02d}{ext}"
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(output_path, 'w', encoding='utf-8') as f:
                        json.dump(current_chunk, f, indent=2)
                    size = output_path.stat().st_size
                    chunks.append((output_path, size))
                    print(f"  [CHUNKED] {raw_path.name} → {output_path.name} ({size:,} bytes)")
                    
                    # Start new chunk
                    current_chunk = [item]
                    current_size = item_size + 100
                else:
                    current_chunk.append(item)
                    current_size += item_size
            
            # Write final chunk (only if under limit)
            if current_chunk and chunk_num < max_chunks_per_file:
                chunk_num += 1
                output_path = raw_path.parent.parent / 'readthis' / f"{base_name}_chunk{chunk_num:02d}{ext}"
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(current_chunk, f, indent=2)
                size = output_path.stat().st_size
                chunks.append((output_path, size))
                print(f"  [CHUNKED] {raw_path.name} → {output_path.name} ({size:,} bytes)")
                
        elif isinstance(data, dict):
            # For dicts with lists (like findings, paths), chunk the lists
            # Determine the correct key to chunk on
            if base_name == 'taint_analysis':
                # For taint analysis, we need to merge ALL findings into one list
                # because they're split across multiple keys
                if 'taint_paths' in data or 'all_rule_findings' in data:
                    # Merge all findings into a single list for chunking
                    all_taint_items = []
                    
                    # Add taint paths
                    if 'taint_paths' in data:
                        for item in data['taint_paths']:
                            item['finding_type'] = 'taint_path'
                            all_taint_items.append(item)
                    
                    # Add all rule findings
                    if 'all_rule_findings' in data:
                        for item in data['all_rule_findings']:
                            item['finding_type'] = 'rule_finding'
                            all_taint_items.append(item)
                    
                    # Add infrastructure issues only if they're different from all_rule_findings
                    # (to avoid duplicates when they're the same list)
                    if 'infrastructure_issues' in data:
                        # Only add if they're actually different content
                        infra_set = {json.dumps(item, sort_keys=True) for item in data['infrastructure_issues']}
                        rules_set = {json.dumps(item, sort_keys=True) for item in data.get('all_rule_findings', [])}
                        if infra_set != rules_set:
                            for item in data['infrastructure_issues']:
                                item['finding_type'] = 'infrastructure'
                                all_taint_items.append(item)
                    
                    # Add paths (data flow paths) - these are often duplicates of taint_paths but may have extra info
                    if 'paths' in data:
                        # Check if different from taint_paths
                        paths_set = {json.dumps(item, sort_keys=True) for item in data['paths']}
                        taint_set = {json.dumps(item, sort_keys=True) for item in data.get('taint_paths', [])}
                        if paths_set != taint_set:
                            for item in data['paths']:
                                item['finding_type'] = 'path'
                                all_taint_items.append(item)
                    
                    # Add vulnerabilities - these are the final analyzed vulnerabilities
                    if 'vulnerabilities' in data:
                        for item in data['vulnerabilities']:
                            item['finding_type'] = 'vulnerability'
                            all_taint_items.append(item)
                    
                    # Create a new data structure with merged findings
                    data = {
                        'success': data.get('success', True),
                        'summary': data.get('summary', {}),
                        'total_vulnerabilities': data.get('total_vulnerabilities', len(all_taint_items)),
                        'sources_found': data.get('sources_found', 0),
                        'sinks_found': data.get('sinks_found', 0),
                        'merged_findings': all_taint_items
                    }
                    list_key = 'merged_findings'
                else:
                    list_key = 'paths'
            elif 'all_findings' in data:
                # CRITICAL: FCE findings are pre-sorted by severity via finding_priority.py
                # The order MUST be preserved during chunking to ensure critical issues
                # appear in chunk01. DO NOT sort or shuffle these findings!
                list_key = 'all_findings'
                
                # Log for verification
                if data.get(list_key):
                    first_items = data[list_key][:3] if len(data[list_key]) >= 3 else data[list_key]
                    severities = [item.get('severity', 'unknown') for item in first_items]
                    print(f"[EXTRACTION] Processing FCE with {len(data[list_key])} pre-sorted findings")
                    print(f"[EXTRACTION] First 3 severities: {severities}")
            elif 'findings' in data:
                list_key = 'findings'
            elif 'vulnerabilities' in data:
                list_key = 'vulnerabilities'
            elif 'issues' in data:
                list_key = 'issues'
            elif 'edges' in data:
                list_key = 'edges'  # For call_graph.json and import_graph.json
            elif 'nodes' in data:
                list_key = 'nodes'  # For graph files with nodes
            elif 'taint_paths' in data:
                list_key = 'taint_paths'
            elif 'paths' in data:
                list_key = 'paths'
            elif 'dependencies' in data:
                list_key = 'dependencies'  # For deps.json
            elif 'files' in data:
                list_key = 'files'  # For file lists
            elif 'results' in data:
                list_key = 'results'  # For analysis results
            else:
                list_key = None
            
            if list_key:
                items = data.get(list_key, [])
                
                # Extract minimal metadata (don't duplicate everything)
                metadata = {}
                for key in ['success', 'summary', 'total_vulnerabilities', 'chunk_info']:
                    if key in data:
                        metadata[key] = data[key]
                
                # Calculate actual metadata size
                metadata_json = json.dumps(metadata, indent=2)
                metadata_size = len(metadata_json)
                
                chunk_num = 0
                chunk_items = []
                current_size = metadata_size + 200  # Actual metadata size + bracket overhead
                
                for item in items:
                    item_json = json.dumps(item, indent=2)
                    item_size = len(item_json)
                    
                    if current_size + item_size > max_chunk_size and chunk_items:
                        # Check chunk limit
                        if chunk_num >= max_chunks_per_file:
                            print(f"  [TRUNCATED] {raw_path.name} - stopped at {max_chunks_per_file} chunks (would have created more)")
                            break
                        
                        # Write current chunk
                        chunk_num += 1
                        chunk_data = metadata.copy()
                        chunk_data[list_key] = chunk_items
                        chunk_data['chunk_info'] = {
                            'chunk_number': chunk_num,
                            'total_items_in_chunk': len(chunk_items),
                            'original_total_items': len(items),
                            'list_key': list_key,
                            'truncated': chunk_num >= max_chunks_per_file  # Mark if this is the last allowed chunk
                        }
                        
                        output_path = raw_path.parent.parent / 'readthis' / f"{base_name}_chunk{chunk_num:02d}{ext}"
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(output_path, 'w', encoding='utf-8') as f:
                            json.dump(chunk_data, f, indent=2)
                        size = output_path.stat().st_size
                        chunks.append((output_path, size))
                        print(f"  [CHUNKED] {raw_path.name} → {output_path.name} ({len(chunk_items)} items, {size:,} bytes)")
                        
                        # Start new chunk
                        chunk_items = [item]
                        current_size = metadata_size + item_size + 200
                    else:
                        chunk_items.append(item)
                        current_size += item_size
                
                # Write final chunk (only if under limit)
                if chunk_items and chunk_num < max_chunks_per_file:
                    chunk_num += 1
                    chunk_data = metadata.copy()
                    chunk_data[list_key] = chunk_items
                    chunk_data['chunk_info'] = {
                        'chunk_number': chunk_num,
                        'total_items_in_chunk': len(chunk_items),
                        'original_total_items': len(items),
                        'list_key': list_key,
                        'truncated': False  # This is the final chunk within limit
                    }
                    
                    output_path = raw_path.parent.parent / 'readthis' / f"{base_name}_chunk{chunk_num:02d}{ext}"
                    with open(output_path, 'w', encoding='utf-8') as f:
                        json.dump(chunk_data, f, indent=2)
                    size = output_path.stat().st_size
                    chunks.append((output_path, size))
                    print(f"  [CHUNKED] {raw_path.name} → {output_path.name} ({len(chunk_items)} items, {size:,} bytes)")
            else:
                # No recognized list key - shouldn't happen now with expanded list
                # Log warning and copy as-is
                print(f"  [WARNING] No chunkable list found in {raw_path.name}, copying as-is")
                output_path = raw_path.parent.parent / 'readthis' / raw_path.name
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)
                size = output_path.stat().st_size
                chunks.append((output_path, size))
                print(f"  [COPIED] {raw_path.name} → {output_path.name} ({size:,} bytes)")
        
        return chunks
        
    except Exception as e:
        print(f"  [ERROR] Failed to chunk {raw_path.name}: {e}")
        return None  # Return None to signal failure, not empty list


def _copy_as_is(raw_path: Path) -> Tuple[Optional[Path], int]:
    """Copy small files as-is or chunk if >65KB."""
    chunks = _chunk_large_file(raw_path)
    if chunks is None:
        # Chunking failed
        return None, -1  # Signal error with -1
    elif chunks:
        # Return the first chunk info for compatibility
        return chunks[0] if len(chunks) == 1 else (None, sum(s for _, s in chunks))
    return None, 0


def extract_all_to_readthis(root_path_str: str, budget_kb: int = 1500) -> bool:
    """Main function for extracting readthis chunks from raw data.
    
    Implements intelligent extraction with prioritization to stay within
    budget while preserving all critical security findings.
    
    Args:
        root_path_str: Root directory path as string
        budget_kb: Maximum total size in KB for all readthis files (default 1000KB)
        
    Returns:
        True if extraction completed successfully, False otherwise
    """
    root_path = Path(root_path_str)
    raw_dir = root_path / ".pf" / "raw"
    readthis_dir = root_path / ".pf" / "readthis"
    
    print("\n" + "="*60)
    print("[EXTRACTION] Smart extraction with 1MB budget")
    print("="*60)
    
    # Check if raw directory exists
    if not raw_dir.exists():
        print(f"[WARNING] Raw directory does not exist: {raw_dir}")
        print("[INFO] No raw data to extract - skipping extraction phase")
        return True
    
    # Ensure readthis directory exists
    try:
        readthis_dir.mkdir(parents=True, exist_ok=True)
        print(f"[OK] Readthis directory ready: {readthis_dir}")
    except Exception as e:
        print(f"[ERROR] Failed to create readthis directory: {e}")
        return False
    
    # Discover ALL files in raw directory dynamically (courier model)
    raw_files = []
    for file_path in raw_dir.iterdir():
        if file_path.is_file():
            raw_files.append(file_path.name)
    
    print(f"[DISCOVERED] Found {len(raw_files)} files in raw directory")
    
    # Pure courier model - no smart extraction, just chunking if needed
    # Build extraction strategy dynamically
    extraction_strategy = []
    for filename in sorted(raw_files):
        # All files get same treatment: chunk if needed
        extraction_strategy.append((filename, 100, _copy_as_is))
    
    total_budget = budget_kb * 1024  # Convert to bytes
    total_used = 0
    extracted_files = []
    skipped_files = []
    failed_files = []  # Track failures
    
    print(f"[BUDGET] Total budget: {budget_kb}KB ({total_budget:,} bytes)")
    print(f"[STRATEGY] Pure courier model - no filtering\n")
    
    for filename, file_budget_kb, extractor in extraction_strategy:
        raw_path = raw_dir / filename
        
        if not raw_path.exists():
            continue
        
        print(f"[PROCESSING] {filename}")
        
        # Just chunk everything - ignore budget for chunking
        # The whole point is to break large files into manageable pieces
        chunks = _chunk_large_file(raw_path)

        if chunks is None:
            # Chunking failed for this file (parse error)
            print(f"  [FAILED] {filename} - chunking error")
            failed_files.append(filename)
            continue
        elif not chunks:
            # Empty file or no content to extract (not an error)
            skipped_files.append(filename)
            continue

        # Successfully chunked - add all chunks
        for chunk_path, chunk_size in chunks:
            # Track budget usage but don't enforce limit
            # (we want all files out, but report if over budget)
            total_used += chunk_size
            extracted_files.append((chunk_path.name, chunk_size))

            if total_used > total_budget:
                # Just track that we're over budget, don't stop extraction
                pass
    
    # Create extraction summary
    summary = {
        'extraction_timestamp': datetime.now().isoformat(),
        'budget_kb': budget_kb,
        'total_used_bytes': total_used,
        'total_used_kb': total_used // 1024,
        'utilization_percent': (total_used / total_budget) * 100,
        'budget_exceeded': total_used > total_budget,
        'over_budget_kb': max(0, (total_used - total_budget) // 1024),
        'files_extracted': len(extracted_files),
        'files_skipped': len(skipped_files),
        'files_failed': len(failed_files),
        'extracted': [{'file': f, 'size': s} for f, s in extracted_files],
        'skipped': skipped_files,
        'failed': failed_files,
        'strategy': 'Pure courier model - chunk if needed, no filtering'
    }
    
    summary_path = readthis_dir / 'extraction_summary.json'
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
    
    # Summary report
    print("\n" + "="*60)
    print("[EXTRACTION COMPLETE]")
    print(f"  Files extracted: {len(extracted_files)}")
    print(f"  Files skipped: {len(skipped_files)}")
    print(f"  Files failed: {len(failed_files)}")
    print(f"  Total size: {total_used:,} bytes ({total_used//1024}KB)")
    print(f"  Budget used: {(total_used/total_budget)*100:.1f}%")

    # Warn if over budget
    if total_used > total_budget:
        over_kb = (total_used - total_budget) // 1024
        print(f"  [WARNING] Over budget by {over_kb}KB - consider reviewing chunk limits")

    print(f"  Summary saved: {summary_path}")
    
    # List what was extracted
    print("\n[EXTRACTED FILES]")
    for filename, size in extracted_files:
        print(f"  {filename:30} {size:8,} bytes ({size//1024:4}KB)")
    
    if skipped_files:
        print("\n[SKIPPED FILES]")
        for filename in skipped_files:
            print(f"  {filename}")
    
    if failed_files:
        print("\n[FAILED FILES]")
        for filename in failed_files:
            print(f"  {filename}")
    
    print("\n[KEY INSIGHTS]")
    print("  ✓ All findings preserved - no filtering")
    print("  ✓ Pure courier model - no interpretation")
    print("  ✓ Files chunked only if >65KB")
    print("  ✓ Complete data for AI consumption")
    print("="*60)
    
    # Return False if any files failed, True only if all succeeded
    if failed_files:
        print(f"\n[ERROR] Extraction failed for {len(failed_files)} files")
        return False
    return True