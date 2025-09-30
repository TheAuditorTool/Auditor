"""JavaScript/TypeScript semantic parser using the TypeScript Compiler API.

This module replaces Tree-sitter's syntactic parsing with true semantic analysis
using the TypeScript compiler, enabling accurate type analysis, symbol resolution,
and cross-file understanding for JavaScript and TypeScript projects.
"""

import json
import os
import platform
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, Optional, Any, List, Tuple

# Import our custom temp manager to avoid WSL2/Windows issues
try:
    from theauditor.utils.temp_manager import TempManager
except ImportError:
    # Fallback to regular tempfile if custom manager not available
    TempManager = None

# Windows compatibility for subprocess calls
IS_WINDOWS = platform.system() == "Windows"

# Module-level cache for resolver (it's stateless now)
_module_resolver_cache = None


class JSSemanticParser:
    """Semantic parser for JavaScript/TypeScript using the TypeScript Compiler API."""
    
    def __init__(self, project_root: str = None):
        """Initialize the semantic parser.
        
        Args:
            project_root: Absolute path to project root. If not provided, uses current directory.
        """
        self.project_root = Path(project_root).resolve() if project_root else Path.cwd().resolve()
        self.using_windows_node = False  # Track if we're using Windows node.exe from WSL
        self.tsc_path = None  # Path to TypeScript compiler
        self.node_modules_path = None  # Path to sandbox node_modules
        
        # CRITICAL: Reuse cached ModuleResolver (stateless, database-driven)
        global _module_resolver_cache
        if _module_resolver_cache is None:
            from theauditor.module_resolver import ModuleResolver
            _module_resolver_cache = ModuleResolver()  # No project_root needed!
            print("[DEBUG] Created singleton ModuleResolver instance")
        
        self.module_resolver = _module_resolver_cache
        
        # CRITICAL FIX: Find the sandboxed node executable (like linters do)
        # Platform-agnostic: Check multiple possible locations
        sandbox_base = self.project_root / ".auditor_venv" / ".theauditor_tools"
        node_runtime = sandbox_base / "node-runtime"
        
        # Check all possible node locations (Windows or Unix layout)
        possible_node_paths = [
            node_runtime / "node.exe",     # Windows binary in root
            node_runtime / "node",          # Unix binary in root  
            node_runtime / "bin" / "node",  # Unix binary in bin/
            node_runtime / "bin" / "node.exe",  # Windows binary in bin/ (unusual but possible)
        ]
        
        self.node_exe = None
        for node_path in possible_node_paths:
            if node_path.exists():
                self.node_exe = node_path
                # Track if we're using Windows node on WSL
                self.using_windows_node = str(node_path).endswith('.exe') and str(node_path).startswith('/')
                break
        
        # If not found, will trigger proper error messages
        
        self.tsc_available = self._check_tsc_availability()
        self.helper_script = self._create_helper_script()
        self.batch_helper_script = self._create_batch_helper_script()  # NEW: Batch processing helper
    
    def _convert_path_for_node(self, path: Path) -> str:
        """Convert path to appropriate format for node execution.
        
        If using Windows node.exe from WSL, converts to Windows path.
        Otherwise returns the path as-is.
        """
        path_str = str(path)
        if self.using_windows_node:
            try:
                import subprocess as sp
                result = sp.run(['wslpath', '-w', path_str], 
                              capture_output=True, text=True, timeout=2)
                if result.returncode == 0:
                    return result.stdout.strip()
            except:
                pass  # Fall back to original path
        return path_str
        
    def _check_tsc_availability(self) -> bool:
        """Check if TypeScript compiler is available in our sandbox.
        
        CRITICAL: We ONLY use our own sandboxed TypeScript installation.
        We do not check or use any user-installed versions.
        """
        # Check our sandbox location ONLY - no invasive checking of user's environment
        # CRITICAL: Use absolute path from project root to avoid finding wrong sandboxes
        sandbox_base = self.project_root / ".auditor_venv" / ".theauditor_tools" / "node_modules"
        
        # Check if sandbox exists at the absolute location
        sandbox_locations = [sandbox_base]
        
        for sandbox_base in sandbox_locations:
            if not sandbox_base.exists():
                continue
                
            # Check for TypeScript in sandbox
            tsc_paths = [
                sandbox_base / ".bin" / "tsc",
                sandbox_base / ".bin" / "tsc.cmd",  # Windows
            ]
            
            # Also check for the actual TypeScript compiler JS file
            tsc_js_path = sandbox_base / "typescript" / "lib" / "tsc.js"
            
            # If we have node and the TypeScript compiler JS file, we can use it
            if self.node_exe and tsc_js_path.exists():
                try:
                    # Verify it actually works by running through node
                    # CRITICAL: Use absolute path for NODE_PATH
                    absolute_sandbox = sandbox_base.resolve()
                    # Use temp files to avoid buffer overflow
                    if TempManager:
                        stdout_path, stderr_path = TempManager.create_temp_files_for_subprocess(
                            str(self.project_root), "tsc_verify"
                        )
                        with open(stdout_path, 'w+', encoding='utf-8') as stdout_fp, \
                             open(stderr_path, 'w+', encoding='utf-8') as stderr_fp:
                            pass  # File handles created, will be used below
                    else:
                        # Fallback to regular tempfile
                        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='_stdout.txt', encoding='utf-8') as stdout_fp, \
                             tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='_stderr.txt', encoding='utf-8') as stderr_fp:
                            stdout_path = stdout_fp.name
                            stderr_path = stderr_fp.name
                    
                    with open(stdout_path, 'w+', encoding='utf-8') as stdout_fp, \
                         open(stderr_path, 'w+', encoding='utf-8') as stderr_fp:
                        
                        # Convert paths for Windows node if needed
                        tsc_path_str = self._convert_path_for_node(tsc_js_path)
                        
                        # Run TypeScript through node.exe
                        result = subprocess.run(
                            [str(self.node_exe), tsc_path_str, "--version"],
                            stdout=stdout_fp,
                            stderr=stderr_fp,
                            text=True,
                            timeout=5,
                            env={**os.environ, "NODE_PATH": str(absolute_sandbox)},
                            shell=False  # Never use shell when we have full path
                        )
                        
                        with open(stdout_path, 'r', encoding='utf-8') as f:
                            result.stdout = f.read()
                        with open(stderr_path, 'r', encoding='utf-8') as f:
                            result.stderr = f.read()
                        
                    os.unlink(stdout_path)
                    os.unlink(stderr_path)
                    if result.returncode == 0:
                        self.tsc_path = tsc_js_path  # Store the JS file path, not the shell script
                        self.node_modules_path = absolute_sandbox  # Store absolute path
                        return True
                except (subprocess.SubprocessError, FileNotFoundError, OSError):
                    pass  # TypeScript check failed
        
        # No sandbox TypeScript found - this is expected on first run
        return False
    
    def _extract_vue_blocks(self, content: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract script and template blocks from Vue SFC content.
        
        Args:
            content: The raw Vue SFC file content
            
        Returns:
            Tuple of (script_content, template_content) or (None, None) if not found
        """
        # Extract <script> block (handles both <script> and <script setup>)
        # Supports optional attributes like lang="ts" or setup
        script_pattern = r'<script(?:\s+[^>]*)?>(.+?)</script>'
        script_match = re.search(script_pattern, content, re.DOTALL | re.IGNORECASE)
        script_content = script_match.group(1).strip() if script_match else None
        
        # Extract <template> block for future analysis
        template_pattern = r'<template(?:\s+[^>]*)?>(.+?)</template>'
        template_match = re.search(template_pattern, content, re.DOTALL | re.IGNORECASE)
        template_content = template_match.group(1).strip() if template_match else None
        
        return script_content, template_content
    
    def _create_helper_script(self) -> Path:
        """Create a Node.js helper script for TypeScript AST extraction.
        
        Returns:
            Path to the created helper script
        """
        # CRITICAL: Create helper script with relative path resolution
        # Always create in project root's .pf directory
        pf_dir = self.project_root / ".pf"
        pf_dir.mkdir(exist_ok=True)
        
        helper_path = pf_dir / "tsc_ast_helper.js"
        
        # Check if TypeScript module exists in our sandbox
        typescript_exists = False
        if self.node_modules_path:
            # The TypeScript module is at node_modules/typescript/lib/typescript.js
            ts_path = self.node_modules_path / "typescript" / "lib" / "typescript.js"
            typescript_exists = ts_path.exists()
        
        # Write the helper script that uses TypeScript Compiler API
        # CRITICAL: Use relative path from helper script location to find TypeScript
        helper_content = '''
// Use TypeScript from our sandbox location with RELATIVE PATH
// This is portable - works on any machine in any location
const path = require('path');
const fs = require('fs');

// Find project root by going up from .pf directory
const projectRoot = path.resolve(__dirname, '..');

// Build path to TypeScript module relative to project root
const tsPath = path.join(projectRoot, '.auditor_venv', '.theauditor_tools', 'node_modules', 'typescript', 'lib', 'typescript.js');

// Try to load TypeScript with helpful error message
let ts;
try {
    if (!fs.existsSync(tsPath)) {
        throw new Error(`TypeScript not found at expected location: ${tsPath}. Run 'aud setup-claude' to install tools.`);
    }
    ts = require(tsPath);
} catch (error) {
    console.error(JSON.stringify({
        success: false,
        error: `Failed to load TypeScript: ${error.message}`,
        expectedPath: tsPath,
        projectRoot: projectRoot
    }));
    process.exit(1);
}

// Get file path and output path from command line arguments
const filePath = process.argv[2];
const outputPath = process.argv[3];

if (!filePath || !outputPath) {
    console.error(JSON.stringify({ error: "File path and output path required" }));
    process.exit(1);
}

try {
    // Read the source file
    const sourceCode = fs.readFileSync(filePath, 'utf8');
    
    // Create a source file object
    const sourceFile = ts.createSourceFile(
        filePath,
        sourceCode,
        ts.ScriptTarget.Latest,
        true,  // setParentNodes - important for full AST traversal
        ts.ScriptKind.TSX  // Support both TS and TSX
    );
    
    // Helper function to serialize AST nodes
    function serializeNode(node, depth = 0) {
        if (depth > 100) {  // Prevent infinite recursion
            return { kind: "TooDeep" };
        }
        
        const result = {
            kind: node.kind !== undefined ? (ts.SyntaxKind[node.kind] || node.kind) : 'Unknown',
            kindValue: node.kind || 0,
            pos: node.pos || 0,
            end: node.end || 0,
            flags: node.flags || 0
        };
        
        // Add text content for leaf nodes
        if (node.text !== undefined) {
            result.text = node.text;
        }
        
        // Add identifier name
        if (node.name) {
            if (typeof node.name === 'object') {
                // Handle both escapedName and regular name
                if (node.name.escapedText !== undefined) {
                    result.name = node.name.escapedText;
                } else if (node.name.text !== undefined) {
                    result.name = node.name.text;
                } else {
                    result.name = serializeNode(node.name, depth + 1);
                }
            } else {
                result.name = node.name;
            }
        }
        
        // Add type information if available
        if (node.type) {
            result.type = serializeNode(node.type, depth + 1);
        }
        
        // Add children - handle nodes with members property
        const children = [];
        if (node.members && Array.isArray(node.members)) {
            // Handle nodes with members (interfaces, enums, etc.)
            node.members.forEach(member => {
                if (member) children.push(serializeNode(member, depth + 1));
            });
        }
        ts.forEachChild(node, child => {
            if (child) children.push(serializeNode(child, depth + 1));
        });
        
        if (children.length > 0) {
            result.children = children;
        }
        
        // Get line and column information
        // CRITICAL FIX: Use getStart() to exclude leading trivia for accurate line numbers
        const actualStart = node.getStart ? node.getStart(sourceFile) : node.pos;
        const { line, character } = sourceFile.getLineAndCharacterOfPosition(actualStart);
        result.line = line + 1;  // Convert to 1-indexed
        result.column = character;
        
        // RESTORED: Text extraction needed for accurate symbol names in taint analysis
        result.text = sourceCode.substring(node.pos, node.end).trim();
        
        return result;
    }
    
    // Collect diagnostics (errors, warnings)
    const diagnostics = [];
    const program = ts.createProgram([filePath], {
        target: ts.ScriptTarget.Latest,
        module: ts.ModuleKind.ESNext,
        jsx: ts.JsxEmit.Preserve,
        allowJs: true,
        checkJs: false,
        noEmit: true,
        skipLibCheck: true  // Skip checking .d.ts files for speed
    });
    
    const allDiagnostics = ts.getPreEmitDiagnostics(program);
    allDiagnostics.forEach(diagnostic => {
        const message = ts.flattenDiagnosticMessageText(diagnostic.messageText, '\\n');
        const location = diagnostic.file && diagnostic.start
            ? diagnostic.file.getLineAndCharacterOfPosition(diagnostic.start)
            : null;
            
        diagnostics.push({
            message,
            category: ts.DiagnosticCategory[diagnostic.category],
            code: diagnostic.code,
            line: location ? location.line + 1 : null,
            column: location ? location.character : null
        });
    });
    
    // Collect symbols and type information
    const checker = program.getTypeChecker();
    const symbols = [];
    
    // Visit nodes to collect symbols
    function visit(node) {
        try {
            const symbol = checker.getSymbolAtLocation(node);
            if (symbol && symbol.getName) {
                const type = checker.getTypeOfSymbolAtLocation(symbol, node);
                const typeString = checker.typeToString(type);
                
                symbols.push({
                    name: symbol.getName ? symbol.getName() : 'anonymous',
                    kind: symbol.flags ? (ts.SymbolFlags[symbol.flags] || symbol.flags) : 0,
                    type: typeString || 'unknown',
                    line: node.pos !== undefined ? sourceFile.getLineAndCharacterOfPosition(node.pos).line + 1 : 0
                });
            }
        } catch (e) {
            // Log error for debugging
            console.error(`[ERROR] Symbol extraction failed at ${filePath}:${node.pos}: ${e.message}`);
        }
        
        ts.forEachChild(node, visit);
    }
    
    visit(sourceFile);
    
    // Log symbol extraction results
    console.error(`[INFO] Found ${symbols.length} symbols in ${filePath}`);
    
    // Output the complete AST with metadata
    const result = {
        success: true,
        fileName: filePath,
        languageVersion: ts.ScriptTarget[sourceFile.languageVersion],
        ast: serializeNode(sourceFile),
        diagnostics: diagnostics,
        symbols: symbols,
        nodeCount: 0,
        hasTypes: symbols.some(s => s.type && s.type !== 'any')
    };
    
    // Count nodes
    function countNodes(node) {
        if (!node) return;
        result.nodeCount++;
        if (node.children && Array.isArray(node.children)) {
            node.children.forEach(countNodes);
        }
    }
    if (result.ast) countNodes(result.ast);
    
    // Write output to file instead of stdout to avoid pipe buffer limits
    fs.writeFileSync(outputPath, JSON.stringify(result, null, 2), 'utf8');
    process.exit(0);  // CRITICAL: Ensure clean exit on success
    
} catch (error) {
    console.error(JSON.stringify({
        success: false,
        error: error.message,
        stack: error.stack
    }));
    process.exit(1);
}
'''
        
        helper_path.write_text(helper_content, encoding='utf-8')
        return helper_path
    
    def _create_batch_helper_script(self) -> Path:
        """Create a Node.js helper script for batch TypeScript AST extraction.
        
        This script processes multiple files in a single TypeScript program,
        dramatically improving performance by reusing the dependency cache.
        
        Returns:
            Path to the created batch helper script
        """
        pf_dir = self.project_root / ".pf"
        pf_dir.mkdir(exist_ok=True)
        
        batch_helper_path = pf_dir / "tsc_batch_helper.js"
        
        batch_helper_content = '''
// Batch TypeScript AST extraction - processes multiple files in one program
const path = require('path');
const fs = require('fs');

// Find project root by going up from .pf directory
const projectRoot = path.resolve(__dirname, '..');

// Build path to TypeScript module
const tsPath = path.join(projectRoot, '.auditor_venv', '.theauditor_tools', 'node_modules', 'typescript', 'lib', 'typescript.js');

// Load TypeScript
let ts;
try {
    if (!fs.existsSync(tsPath)) {
        throw new Error(`TypeScript not found at: ${tsPath}`);
    }
    ts = require(tsPath);
} catch (error) {
    console.error(JSON.stringify({
        success: false,
        error: `Failed to load TypeScript: ${error.message}`
    }));
    process.exit(1);
}

// Get request and output paths from command line
const requestPath = process.argv[2];
const outputPath = process.argv[3];

if (!requestPath || !outputPath) {
    console.error(JSON.stringify({ error: "Request and output paths required" }));
    process.exit(1);
}

try {
    // Read batch request
    const request = JSON.parse(fs.readFileSync(requestPath, 'utf8'));
    const filePaths = request.files || [];
    
    if (filePaths.length === 0) {
        fs.writeFileSync(outputPath, JSON.stringify({}), 'utf8');
        process.exit(0);
    }
    
    // Create a SINGLE TypeScript program with ALL files
    // This is the key optimization - TypeScript will parse dependencies ONCE
    const program = ts.createProgram(filePaths, {
        target: ts.ScriptTarget.Latest,
        module: ts.ModuleKind.ESNext,
        jsx: ts.JsxEmit.Preserve,
        allowJs: true,
        checkJs: false,
        noEmit: true,
        skipLibCheck: true,  // Skip checking .d.ts files for speed
        moduleResolution: ts.ModuleResolutionKind.NodeJs
    });
    
    const checker = program.getTypeChecker();
    const results = {};
    
    // Process each file using the SHARED program
    for (const filePath of filePaths) {
        try {
            const sourceFile = program.getSourceFile(filePath);
            if (!sourceFile) {
                results[filePath] = {
                    success: false,
                    error: `Could not load source file: ${filePath}`
                };
                continue;
            }
            
            const sourceCode = sourceFile.text;
            
            // Helper function to serialize AST nodes (same as single-file version)
            function serializeNode(node, depth = 0) {
                if (depth > 100) return { kind: "TooDeep" };
                
                const result = {
                    kind: node.kind !== undefined ? (ts.SyntaxKind[node.kind] || node.kind) : 'Unknown',
                    kindValue: node.kind || 0,
                    pos: node.pos || 0,
                    end: node.end || 0,
                    flags: node.flags || 0
                };
                
                if (node.text !== undefined) result.text = node.text;
                
                if (node.name) {
                    if (typeof node.name === 'object') {
                        if (node.name.escapedText !== undefined) {
                            result.name = node.name.escapedText;
                        } else if (node.name.text !== undefined) {
                            result.name = node.name.text;
                        } else {
                            result.name = serializeNode(node.name, depth + 1);
                        }
                    } else {
                        result.name = node.name;
                    }
                }
                
                if (node.type) {
                    result.type = serializeNode(node.type, depth + 1);
                }
                
                const children = [];
                if (node.members && Array.isArray(node.members)) {
                    node.members.forEach(member => {
                        if (member) children.push(serializeNode(member, depth + 1));
                    });
                }
                ts.forEachChild(node, child => {
                    if (child) children.push(serializeNode(child, depth + 1));
                });
                
                if (children.length > 0) {
                    result.children = children;
                }
                
                // CRITICAL FIX: Use getStart() to exclude leading trivia for accurate line numbers
                const actualStart = node.getStart ? node.getStart(sourceFile) : node.pos;
                const { line, character } = sourceFile.getLineAndCharacterOfPosition(actualStart);
                result.line = line + 1;
                result.column = character;
                // RESTORED: Text extraction needed for accurate symbol names in taint analysis
                result.text = sourceCode.substring(node.pos, node.end).trim();
                
                return result;
            }
            
            // Collect diagnostics for this file
            const diagnostics = [];
            const fileDiagnostics = ts.getPreEmitDiagnostics(program, sourceFile);
            fileDiagnostics.forEach(diagnostic => {
                const message = ts.flattenDiagnosticMessageText(diagnostic.messageText, '\\n');
                const location = diagnostic.file && diagnostic.start
                    ? diagnostic.file.getLineAndCharacterOfPosition(diagnostic.start)
                    : null;
                
                diagnostics.push({
                    message,
                    category: ts.DiagnosticCategory[diagnostic.category],
                    code: diagnostic.code,
                    line: location ? location.line + 1 : null,
                    column: location ? location.character : null
                });
            });
            
            // Collect symbols for this file
            const symbols = [];
            function visit(node) {
                try {
                    const symbol = checker.getSymbolAtLocation(node);
                    if (symbol && symbol.getName) {
                        const type = checker.getTypeOfSymbolAtLocation(symbol, node);
                        const typeString = checker.typeToString(type);
                        
                        symbols.push({
                            name: symbol.getName ? symbol.getName() : 'anonymous',
                            kind: symbol.flags ? (ts.SymbolFlags[symbol.flags] || symbol.flags) : 0,
                            type: typeString || 'unknown',
                            line: node.pos !== undefined ? sourceFile.getLineAndCharacterOfPosition(node.pos).line + 1 : 0
                        });
                    }
                } catch (e) {
                    // Log error for debugging
                    console.error(`[ERROR] Symbol extraction failed at ${filePath}:${node.pos}: ${e.message}`);
                }
                ts.forEachChild(node, visit);
            }
            visit(sourceFile);
            
            // Log symbol extraction results
            console.error(`[INFO] Found ${symbols.length} symbols in ${filePath}`);
            
            // Build result for this file
            const result = {
                success: true,
                fileName: filePath,
                languageVersion: ts.ScriptTarget[sourceFile.languageVersion],
                ast: serializeNode(sourceFile),
                diagnostics: diagnostics,
                symbols: symbols,
                nodeCount: 0,
                hasTypes: symbols.some(s => s.type && s.type !== 'any')
            };
            
            // Count nodes
            function countNodes(node) {
                if (!node) return;
                result.nodeCount++;
                if (node.children && Array.isArray(node.children)) {
                    node.children.forEach(countNodes);
                }
            }
            if (result.ast) countNodes(result.ast);
            
            results[filePath] = result;
            
        } catch (error) {
            results[filePath] = {
                success: false,
                error: `Error processing file: ${error.message}`,
                ast: null,
                diagnostics: [],
                symbols: []
            };
        }
    }
    
    // Write all results to output file
    fs.writeFileSync(outputPath, JSON.stringify(results, null, 2), 'utf8');
    process.exit(0);
    
} catch (error) {
    console.error(JSON.stringify({
        success: false,
        error: error.message,
        stack: error.stack
    }));
    process.exit(1);
}
'''
        
        batch_helper_path.write_text(batch_helper_content, encoding='utf-8')
        return batch_helper_path
    
    def get_semantic_ast_batch(self, file_paths: List[str]) -> Dict[str, Dict[str, Any]]:
        """Get semantic ASTs for multiple JavaScript/TypeScript files in a single process.
        
        This dramatically improves performance by reusing the TypeScript program
        and dependency cache across multiple files.
        
        Args:
            file_paths: List of paths to JavaScript or TypeScript files to parse
            
        Returns:
            Dictionary mapping file paths to their AST results
        """
        # Validate all files exist
        results = {}
        valid_files = []
        
        for file_path in file_paths:
            file = Path(file_path).resolve()
            if not file.exists():
                results[file_path] = {
                    "success": False,
                    "error": f"File not found: {file_path}",
                    "ast": None,
                    "diagnostics": [],
                    "symbols": []
                }
            elif file.suffix.lower() not in ['.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs', '.vue']:
                results[file_path] = {
                    "success": False,
                    "error": f"Not a JavaScript/TypeScript file: {file_path}",
                    "ast": None,
                    "diagnostics": [],
                    "symbols": []
                }
            else:
                valid_files.append(str(file.resolve()))
        
        if not valid_files:
            return results
        
        if not self.tsc_available:
            for file_path in valid_files:
                results[file_path] = {
                    "success": False,
                    "error": "TypeScript compiler not available in TheAuditor sandbox. Run 'aud setup-claude' to install tools.",
                    "ast": None,
                    "diagnostics": [],
                    "symbols": []
                }
            return results
        
        try:
            # Create batch request
            batch_request = {
                "files": valid_files,
                "projectRoot": str(self.project_root)
            }
            
            # Write batch request to temp file
            if TempManager:
                request_path, req_fd = TempManager.create_temp_file(str(self.project_root), suffix='_request.json')
                os.close(req_fd)
                output_path, out_fd = TempManager.create_temp_file(str(self.project_root), suffix='_output.json')
                os.close(out_fd)
            else:
                # Fallback to regular tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as tmp_req:
                    request_path = tmp_req.name
                with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False, encoding='utf-8') as tmp_out:
                    output_path = tmp_out.name
            
            # Write batch request data
            with open(request_path, 'w', encoding='utf-8') as f:
                json.dump(batch_request, f)
            
            # Calculate timeout based on batch size
            # 5 seconds base + 2 seconds per file
            dynamic_timeout = min(5 + (len(valid_files) * 2), 120)
            
            try:
                # Run batch helper script
                # Convert paths for Windows node if needed
                helper_path = self._convert_path_for_node(self.batch_helper_script.resolve())
                request_path_converted = self._convert_path_for_node(Path(request_path))
                output_path_converted = self._convert_path_for_node(Path(output_path))
                
                # CRITICAL FIX: Use sandboxed node executable, not system "node"
                if not self.node_exe:
                    raise RuntimeError("Node.js runtime not found. Run 'aud setup-claude' to install tools.")
                
                result = subprocess.run(
                    [str(self.node_exe), helper_path, request_path_converted, output_path_converted],
                    capture_output=False,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=dynamic_timeout,
                    cwd=self.project_root,
                    shell=IS_WINDOWS  # Windows compatibility fix
                )
                
                if result.returncode != 0:
                    error_msg = f"Batch TypeScript compiler failed (exit code {result.returncode})"
                    if result.stderr:
                        error_msg += f": {result.stderr.strip()[:500]}"
                    
                    for file_path in valid_files:
                        results[file_path] = {
                            "success": False,
                            "error": error_msg,
                            "ast": None,
                            "diagnostics": [],
                            "symbols": []
                        }
                else:
                    # Read batch results
                    if Path(output_path).exists():
                        with open(output_path, 'r', encoding='utf-8') as f:
                            batch_results = json.load(f)
                        
                        # Map results back to original file paths
                        for file_path in file_paths:
                            resolved_path = str(Path(file_path).resolve())
                            if resolved_path in batch_results:
                                results[file_path] = batch_results[resolved_path]
                            elif file_path not in results:
                                results[file_path] = {
                                    "success": False,
                                    "error": "File not processed in batch",
                                    "ast": None,
                                    "diagnostics": [],
                                    "symbols": []
                                }
                    else:
                        for file_path in valid_files:
                            results[file_path] = {
                                "success": False,
                                "error": "Batch output file not created",
                                "ast": None,
                                "diagnostics": [],
                                "symbols": []
                            }
            finally:
                # Clean up temp files
                for temp_path in [request_path, output_path]:
                    if Path(temp_path).exists():
                        Path(temp_path).unlink()
            
        except subprocess.TimeoutExpired:
            for file_path in valid_files:
                results[file_path] = {
                    "success": False,
                    "error": f"Batch timeout: Files too large or complex to parse within {dynamic_timeout:.0f} seconds",
                    "ast": None,
                    "diagnostics": [],
                    "symbols": []
                }
        except Exception as e:
            for file_path in valid_files:
                results[file_path] = {
                    "success": False,
                    "error": f"Unexpected error in batch processing: {e}",
                    "ast": None,
                    "diagnostics": [],
                    "symbols": []
                }
        
        return results
    
    def get_semantic_ast(self, file_path: str) -> Dict[str, Any]:
        """Get semantic AST for a JavaScript/TypeScript file using the TypeScript compiler.
        
        Args:
            file_path: Path to the JavaScript or TypeScript file to parse
            
        Returns:
            Dictionary containing the semantic AST and metadata:
            - success: Boolean indicating if parsing was successful
            - ast: The full AST tree with semantic information
            - diagnostics: List of errors/warnings from TypeScript
            - symbols: List of symbols with type information
            - nodeCount: Total number of AST nodes
            - hasTypes: Boolean indicating if type information is available
            - error: Error message if parsing failed
        """
        # Validate file exists
        file = Path(file_path).resolve()
        if not file.exists():
            return {
                "success": False,
                "error": f"File not found: {file_path}",
                "ast": None,
                "diagnostics": [],
                "symbols": []
            }
        
        # Check if it's a JavaScript, TypeScript, or Vue file
        if file.suffix.lower() not in ['.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs', '.vue']:
            return {
                "success": False,
                "error": f"Not a JavaScript/TypeScript file: {file_path}",
                "ast": None,
                "diagnostics": [],
                "symbols": []
            }
        
        # CRITICAL: No fallbacks allowed - fail fast with clear error
        if not self.tsc_available:
            return {
                "success": False,
                "error": "TypeScript compiler not available in TheAuditor sandbox. Run 'aud setup-claude' to install tools.",
                "ast": None,
                "diagnostics": [],
                "symbols": []
            }
        
        try:
            # CRITICAL: No automatic installation - user must install TypeScript manually
            # This enforces fail-fast philosophy
            
            # Handle Vue SFC files specially
            actual_file_to_parse = file_path
            vue_metadata = None
            temp_file = None
            
            if file.suffix.lower() == '.vue':
                # Read Vue SFC content
                vue_content = file.read_text(encoding='utf-8')
                script_content, template_content = self._extract_vue_blocks(vue_content)
                
                if script_content is None:
                    return {
                        "success": False,
                        "error": "No <script> block found in Vue SFC",
                        "ast": None,
                        "diagnostics": [],
                        "symbols": [],
                        "vueMetadata": {
                            "hasTemplate": template_content is not None,
                            "hasScript": False
                        }
                    }
                
                # Create a temporary file with the extracted script content
                with tempfile.NamedTemporaryFile(mode='w', suffix='.ts', delete=False, encoding='utf-8') as tmp:
                    tmp.write(script_content)
                    temp_file = Path(tmp.name)
                    actual_file_to_parse = temp_file
                
                # Store Vue metadata for the response
                vue_metadata = {
                    "originalFile": str(file_path),
                    "hasTemplate": template_content is not None,
                    "hasScript": True,
                    "scriptLines": script_content.count('\n') + 1
                }
            
            # Run the helper script with Node.js - use POSIX paths for Windows compatibility
            # NO LONGER NEED NODE_PATH - we use absolute paths in the helper script
            
            # CRITICAL: Use absolute path for helper script since cwd changes
            # On Windows, use forward slashes for Node.js paths
            helper_absolute = str(self.helper_script.resolve()).replace('\\', '/')
            
            # Calculate dynamic timeout based on file size
            # Base timeout of 10 seconds + 1 second per 10KB
            file_size_kb = Path(actual_file_to_parse).stat().st_size / 1024
            dynamic_timeout = min(10 + (file_size_kb / 10), 60)  # Cap at 60 seconds
            
            # Create temporary file for output to avoid pipe buffer limits
            if TempManager:
                tmp_output_path, out_fd = TempManager.create_temp_file(str(self.project_root), suffix='_ast_output.json')
                os.close(out_fd)
            else:
                # Fallback to regular tempfile
                with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False, encoding='utf-8') as tmp_out:
                    tmp_output_path = tmp_out.name
            
            try:
                # CRITICAL FIX: Use sandboxed node executable, not system "node"
                if not self.node_exe:
                    return {
                        "success": False,
                        "error": "Node.js runtime not found. Run 'aud setup-claude' to install tools.",
                        "ast": None,
                        "diagnostics": [],
                        "symbols": []
                    }
                
                # Convert paths for Windows node if needed
                helper_path_converted = self._convert_path_for_node(Path(helper_absolute))
                file_path_converted = self._convert_path_for_node(Path(actual_file_to_parse).resolve())
                output_path_converted = self._convert_path_for_node(Path(tmp_output_path))
                
                result = subprocess.run(
                    [str(self.node_exe), helper_path_converted, file_path_converted, output_path_converted],
                    capture_output=False,  # Don't capture stdout - writing to file instead
                    stderr=subprocess.PIPE,  # Still capture stderr for error messages
                    text=True,
                    timeout=dynamic_timeout,  # Dynamic timeout based on file size
                    cwd=file.parent,  # Run in the file's directory for proper module resolution
                    shell=IS_WINDOWS  # Windows compatibility fix
                )
            finally:
                # Clean up temporary file if created for Vue
                if temp_file and temp_file.exists():
                    temp_file.unlink()
            
            # Handle the result - read from file instead of stdout
            try:
                if result.returncode != 0:
                    # Consolidate error information from stderr (stdout is not captured)
                    error_json = None
                    
                    # Try to parse error output as JSON from stderr
                    if result.stderr and result.stderr.strip():
                        try:
                            error_json = json.loads(result.stderr)
                        except json.JSONDecodeError:
                            # Not JSON, will use as plain text
                            pass
                    
                    if error_json and isinstance(error_json, dict):
                        error_msg = error_json.get("error", "Unknown error from TypeScript compiler")
                    else:
                        # Build detailed error message from stderr
                        error_details = []
                        if result.stderr and result.stderr.strip():
                            error_details.append(f"stderr: {result.stderr.strip()[:500]}")
                        if not error_details:
                            error_details.append("No error output from TypeScript compiler")
                        
                        error_msg = f"TypeScript compiler failed (exit code {result.returncode}). " + " | ".join(error_details)
                    
                    return {
                        "success": False,
                        "error": error_msg,
                        "ast": None,
                        "diagnostics": [],
                        "symbols": []
                    }
                else:
                    # Read output from file
                    if not Path(tmp_output_path).exists():
                        return {
                            "success": False,
                            "error": "TypeScript compiler succeeded but output file was not created",
                            "ast": None,
                            "diagnostics": [],
                            "symbols": []
                        }
                    
                    try:
                        with open(tmp_output_path, 'r', encoding='utf-8') as f:
                            ast_data = json.load(f)
                        
                        # Add Vue metadata if this was a Vue file
                        if vue_metadata:
                            ast_data["vueMetadata"] = vue_metadata
                        return ast_data
                    except json.JSONDecodeError as e:
                        # Include file size in error for debugging
                        file_size = Path(tmp_output_path).stat().st_size
                        return {
                            "success": False,
                            "error": f"Failed to parse TypeScript AST output: {e}. Output file size: {file_size} bytes",
                            "ast": None,
                            "diagnostics": [],
                            "symbols": []
                        }
            finally:
                # Clean up temporary output file
                if Path(tmp_output_path).exists():
                    Path(tmp_output_path).unlink()
                
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Timeout: File too large or complex to parse within {dynamic_timeout:.0f} seconds",
                "ast": None,
                "diagnostics": [],
                "symbols": []
            }
        except subprocess.SubprocessError as e:
            return {
                "success": False,
                "error": f"Subprocess error: {e}",
                "ast": None,
                "diagnostics": [],
                "symbols": []
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error: {e}",
                "ast": None,
                "diagnostics": [],
                "symbols": []
            }
    
    
    def resolve_imports(self, ast_data: Dict[str, Any], current_file: str) -> Dict[str, str]:
        """Resolve import statements in the AST using ModuleResolver.
        
        Args:
            ast_data: The AST data returned by get_semantic_ast
            current_file: Path to the current file being analyzed
            
        Returns:
            Dictionary mapping import statements to resolved file paths
        """
        resolved_imports = {}
        
        if not ast_data.get("success") or not ast_data.get("ast"):
            return resolved_imports
        
        # Extract import statements from AST
        def find_imports(node, depth=0):
            if depth > 100 or not isinstance(node, dict):
                return
            
            kind = node.get("kind")
            
            # Check for import declarations
            if kind == "ImportDeclaration":
                # Extract module specifier
                module_specifier = node.get("moduleSpecifier", {})
                if isinstance(module_specifier, dict):
                    import_path = module_specifier.get("text", "")
                    if import_path:
                        # Resolve the import using ModuleResolver
                        resolved = self.module_resolver.resolve(import_path, current_file)
                        if resolved:
                            resolved_imports[import_path] = resolved
                        elif os.environ.get("THEAUDITOR_DEBUG"):
                            print(f"[RESOLVER_DEBUG] Failed to resolve '{import_path}' from '{current_file}'", file=sys.stderr)
            
            # Check for require calls
            elif kind == "CallExpression":
                expression = node.get("expression", {})
                if isinstance(expression, dict) and expression.get("text") == "require":
                    arguments = node.get("arguments", [])
                    if arguments and isinstance(arguments[0], dict):
                        import_path = arguments[0].get("text", "")
                        if import_path:
                            # Resolve the require using ModuleResolver
                            resolved = self.module_resolver.resolve(import_path, current_file)
                            if resolved:
                                resolved_imports[import_path] = resolved
                            elif os.environ.get("THEAUDITOR_DEBUG"):
                                print(f"[RESOLVER_DEBUG] Failed to resolve require('{import_path}') from '{current_file}'", file=sys.stderr)
            
            # Recurse through children
            for child in node.get("children", []):
                find_imports(child, depth + 1)
        
        find_imports(ast_data.get("ast", {}))
        
        if os.environ.get("THEAUDITOR_DEBUG") and resolved_imports:
            print(f"[RESOLVER_DEBUG] Resolved {len(resolved_imports)} imports in {current_file}", file=sys.stderr)
            for imp, resolved in list(resolved_imports.items())[:3]:  # Show first 3
                print(f"[RESOLVER_DEBUG]   '{imp}' -> '{resolved}'", file=sys.stderr)
        
        return resolved_imports
    
    def extract_type_issues(self, ast_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract type-related issues from the semantic AST.
        
        Args:
            ast_data: The AST data returned by get_semantic_ast
            
        Returns:
            List of type issues found (any types, type suppressions, unsafe casts)
        """
        issues = []
        
        if not ast_data.get("success") or not ast_data.get("ast"):
            return issues
        
        # Check symbols for 'any' types
        for symbol in ast_data.get("symbols", []):
            if symbol.get("type") == "any":
                issues.append({
                    "type": "any_type",
                    "name": symbol.get("name"),
                    "line": symbol.get("line"),
                    "severity": "warning",
                    "message": f"Symbol '{symbol.get('name')}' has type 'any'"
                })
        
        # Check diagnostics for type errors
        for diagnostic in ast_data.get("diagnostics", []):
            if diagnostic.get("category") == "Error":
                issues.append({
                    "type": "type_error",
                    "line": diagnostic.get("line"),
                    "column": diagnostic.get("column"),
                    "severity": "error",
                    "message": diagnostic.get("message"),
                    "code": diagnostic.get("code")
                })
        
        # Recursively search AST for problematic patterns
        def search_ast(node, depth=0):
            if depth > 100 or not isinstance(node, dict):
                return
            
            # Check for 'any' keyword
            if node.get("kind") == "AnyKeyword":
                issues.append({
                    "type": "any_type",
                    "line": node.get("line"),
                    "column": node.get("column"),
                    "severity": "warning",
                    "message": "Explicit 'any' type annotation",
                    "text": node.get("text", "")[:100]
                })
            
            # Check for type assertions (as any, as unknown)
            if node.get("kind") == "AsExpression":
                type_node = node.get("type", {})
                if type_node.get("kind") in ["AnyKeyword", "UnknownKeyword"]:
                    issues.append({
                        "type": "unsafe_cast",
                        "line": node.get("line"),
                        "column": node.get("column"),
                        "severity": "warning",
                        "message": f"Unsafe type assertion to '{type_node.get('kind')}'",
                        "text": node.get("text", "")[:100]
                    })
            
            # Check for @ts-ignore and @ts-nocheck comments
            text = node.get("text", "")
            if "@ts-ignore" in text or "@ts-nocheck" in text:
                issues.append({
                    "type": "type_suppression",
                    "line": node.get("line"),
                    "column": node.get("column"),
                    "severity": "warning",
                    "message": "TypeScript error suppression comment",
                    "text": text[:100]
                })
            
            # Recursively check children
            for child in node.get("children", []):
                search_ast(child, depth + 1)
        
        search_ast(ast_data.get("ast", {}))
        
        return issues


# Module-level function for direct usage
def get_semantic_ast(file_path: str, project_root: str = None) -> Dict[str, Any]:
    """Get semantic AST for a JavaScript/TypeScript file.
    
    This is a convenience function that creates a parser instance
    and calls its get_semantic_ast method.
    
    Args:
        file_path: Path to the JavaScript or TypeScript file to parse
        project_root: Absolute path to project root. If not provided, uses current directory.
        
    Returns:
        Dictionary containing the semantic AST and metadata
    """
    parser = JSSemanticParser(project_root=project_root)
    return parser.get_semantic_ast(file_path)


def get_semantic_ast_batch(file_paths: List[str], project_root: str = None) -> Dict[str, Dict[str, Any]]:
    """Get semantic ASTs for multiple JavaScript/TypeScript files in batch.
    
    This is a convenience function that creates a parser instance
    and calls its get_semantic_ast_batch method.
    
    Args:
        file_paths: List of paths to JavaScript or TypeScript files to parse
        project_root: Absolute path to project root. If not provided, uses current directory.
        
    Returns:
        Dictionary mapping file paths to their AST results
    """
    parser = JSSemanticParser(project_root=project_root)
    return parser.get_semantic_ast_batch(file_paths)