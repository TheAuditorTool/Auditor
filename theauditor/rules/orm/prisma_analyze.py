"""
Prisma ORM Analyzer - SQL-based implementation.

This module detects Prisma ORM anti-patterns and performance issues
using TheAuditor's indexed database.

Migration from: prisma_detector.py (325 lines -> ~280 lines)
Performance: ~10x faster using direct SQL queries
"""

import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from theauditor.utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class StandardRuleContext:
    """Standard context for rule execution."""
    db_path: Path
    project_root: Path
    exclusions: List[str]
    workset_files: Optional[List[str]] = None
    

@dataclass 
class StandardFinding:
    """Standard finding format for all rules."""
    file: str
    line: int
    pattern: str
    message: str
    confidence: float
    severity: str
    category: str
    snippet: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "file": self.file,
            "line": self.line,
            "pattern": self.pattern,
            "message": self.message,
            "confidence": self.confidence,
            "severity": self.severity,
            "category": self.category,
            "snippet": self.snippet
        }


class PrismaAnalyzer:
    """Analyzer for Prisma ORM anti-patterns using SQL queries."""
    
    def __init__(self, context: StandardRuleContext):
        """Initialize with standard context."""
        self.context = context
        self.conn = sqlite3.connect(context.db_path)
        self.cursor = self.conn.cursor()
        
        # Prisma methods that modify data
        self.write_methods = [
            'create', 'createMany', 'update', 'updateMany', 
            'delete', 'deleteMany', 'upsert'
        ]
        
        # Methods that throw errors
        self.throwing_methods = ['findUniqueOrThrow', 'findFirstOrThrow']
    
    def analyze(self) -> List[StandardFinding]:
        """Run all Prisma ORM checks."""
        findings = []
        
        try:
            # Check if orm_queries table exists
            self.cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='orm_queries'"
            )
            if not self.cursor.fetchone():
                logger.info("No orm_queries table found, skipping Prisma analysis")
                return findings
            
            # Run each analysis
            findings.extend(self._detect_unbounded_queries())
            findings.extend(self._detect_n_plus_one())
            findings.extend(self._detect_missing_transactions())
            findings.extend(self._detect_unhandled_throws())
            findings.extend(self._detect_raw_queries())
            findings.extend(self._detect_missing_indexes())
            findings.extend(self._detect_connection_pool_issues())
            
            logger.info(f"Found {len(findings)} Prisma ORM issues")
            
        except Exception as e:
            logger.error(f"Error during Prisma analysis: {e}")
        finally:
            self.conn.close()
            
        return findings
    
    def _detect_unbounded_queries(self) -> List[StandardFinding]:
        """Detect findMany queries without pagination."""
        findings = []
        
        query = """
        SELECT file, line, query_type
        FROM orm_queries
        WHERE query_type LIKE '%.findMany'
          AND has_limit = 0
        """
        
        self.cursor.execute(query)
        for row in self.cursor.fetchall():
            file, line, query_type = row
            model = query_type.split('.')[0] if '.' in query_type else 'unknown'
            
            findings.append(StandardFinding(
                file=file,
                line=line,
                pattern="prisma_unbounded_query",
                message=f"Unbounded findMany on {model} - missing take/skip pagination",
                confidence=0.90,
                severity="HIGH",
                category="orm_performance",
                snippet=f"prisma.{query_type}() without pagination"
            ))
        
        return findings
    
    def _detect_n_plus_one(self) -> List[StandardFinding]:
        """Detect potential N+1 query patterns."""
        findings = []
        
        query = """
        SELECT file, line, query_type
        FROM orm_queries
        WHERE query_type LIKE '%.findMany'
          AND (includes IS NULL OR includes = '[]' OR includes = '{}')
        """
        
        self.cursor.execute(query)
        for row in self.cursor.fetchall():
            file, line, query_type = row
            model = query_type.split('.')[0] if '.' in query_type else 'unknown'
            
            findings.append(StandardFinding(
                file=file,
                line=line,
                pattern="prisma_n_plus_one",
                message=f"Potential N+1: findMany on {model} without includes",
                confidence=0.75,
                severity="MEDIUM",
                category="orm_performance",
                snippet=f"prisma.{query_type}() without eager loading"
            ))
        
        return findings
    
    def _detect_missing_transactions(self) -> List[StandardFinding]:
        """Detect multiple write operations without transactions."""
        findings = []
        
        # Get all write operations grouped by file
        query = """
        SELECT file, line, query_type, has_transaction
        FROM orm_queries
        WHERE query_type LIKE '%.create%' 
           OR query_type LIKE '%.update%'
           OR query_type LIKE '%.delete%'
           OR query_type LIKE '%.upsert%'
        ORDER BY file, line
        """
        
        self.cursor.execute(query)
        
        # Group by file
        file_ops = {}
        for row in self.cursor.fetchall():
            file, line, query_type, has_transaction = row
            if file not in file_ops:
                file_ops[file] = []
            file_ops[file].append({
                'line': line,
                'query': query_type,
                'has_transaction': has_transaction
            })
        
        # Check for close operations without transactions
        for file, operations in file_ops.items():
            for i in range(len(operations) - 1):
                op1 = operations[i]
                op2 = operations[i + 1]
                
                # Operations within 30 lines without transaction
                if (op2['line'] - op1['line'] <= 30 and 
                    not op1['has_transaction'] and 
                    not op2['has_transaction']):
                    
                    findings.append(StandardFinding(
                        file=file,
                        line=op1['line'],
                        pattern="prisma_missing_transaction",
                        message=f"Multiple writes without transaction: {op1['query']} and {op2['query']}",
                        confidence=0.85,
                        severity="HIGH",
                        category="orm_data_integrity",
                        snippet="Multiple operations need $transaction()"
                    ))
                    break  # One finding per cluster
        
        return findings
    
    def _detect_unhandled_throws(self) -> List[StandardFinding]:
        """Detect OrThrow methods that might not have error handling."""
        findings = []
        
        query = """
        SELECT file, line, query_type
        FROM orm_queries
        WHERE query_type LIKE '%.findUniqueOrThrow'
           OR query_type LIKE '%.findFirstOrThrow'
        """
        
        self.cursor.execute(query)
        for row in self.cursor.fetchall():
            file, line, query_type = row
            
            # Check if there's try-catch nearby
            check_query = """
            SELECT COUNT(*) FROM symbols
            WHERE file = ?
              AND ABS(line - ?) <= 5
              AND (name LIKE '%try%' OR name LIKE '%catch%')
            """
            
            self.cursor.execute(check_query, (file, line))
            has_error_handling = self.cursor.fetchone()[0] > 0
            
            if not has_error_handling:
                findings.append(StandardFinding(
                    file=file,
                    line=line,
                    pattern="prisma_unhandled_throw",
                    message=f"OrThrow method without visible error handling: {query_type}",
                    confidence=0.70,
                    severity="LOW",
                    category="orm_error_handling",
                    snippet=f"prisma.{query_type}() may throw"
                ))
        
        return findings
    
    def _detect_raw_queries(self) -> List[StandardFinding]:
        """Detect potentially unsafe raw SQL queries."""
        findings = []
        
        # Look for raw query methods
        query = """
        SELECT DISTINCT f.file, f.line, f.callee_function, f.args_json
        FROM function_call_args f
        WHERE f.callee_function LIKE '%$queryRaw%'
           OR f.callee_function LIKE '%$executeRaw%'
           OR f.callee_function LIKE '%queryRawUnsafe%'
           OR f.callee_function LIKE '%executeRawUnsafe%'
        """
        
        self.cursor.execute(query)
        for row in self.cursor.fetchall():
            file, line, func, args_json = row
            
            # Check if using unsafe variant or has user input
            is_unsafe = 'Unsafe' in func
            severity = "CRITICAL" if is_unsafe else "HIGH"
            
            # Check for template literal or concatenation
            if args_json:
                has_interpolation = '${' in args_json or '+' in args_json
                if has_interpolation:
                    findings.append(StandardFinding(
                        file=file,
                        line=line,
                        pattern="prisma_sql_injection",
                        message=f"Potential SQL injection in {func} with string interpolation",
                        confidence=0.85 if is_unsafe else 0.75,
                        severity=severity,
                        category="orm_security",
                        snippet=f"{func}({args_json[:50]}...)" if len(args_json or '') > 50 else f"{func}({args_json})"
                    ))
        
        return findings
    
    def _detect_missing_indexes(self) -> List[StandardFinding]:
        """Detect queries potentially missing database indexes."""
        findings = []
        
        # Check if prisma_models table exists
        self.cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='prisma_models'"
        )
        if not self.cursor.fetchone():
            return findings
        
        # Get models with very few indexes
        query = """
        SELECT model_name, COUNT(DISTINCT field_name) as indexed_count
        FROM prisma_models
        WHERE is_indexed = 1 OR is_unique = 1
        GROUP BY model_name
        HAVING indexed_count < 2
        """
        
        self.cursor.execute(query)
        poorly_indexed_models = {row[0] for row in self.cursor.fetchall()}
        
        if poorly_indexed_models:
            # Find queries on these models
            query = """
            SELECT file, line, query_type
            FROM orm_queries
            WHERE query_type LIKE '%.findMany%'
               OR query_type LIKE '%.findFirst%'
               OR query_type LIKE '%.findUnique%'
            """
            
            self.cursor.execute(query)
            for row in self.cursor.fetchall():
                file, line, query_type = row
                model = query_type.split('.')[0] if '.' in query_type else None
                
                if model in poorly_indexed_models:
                    findings.append(StandardFinding(
                        file=file,
                        line=line,
                        pattern="prisma_missing_index",
                        message=f"Query on {model} with limited indexes - verify performance",
                        confidence=0.65,
                        severity="MEDIUM",
                        category="orm_performance",
                        snippet=f"prisma.{query_type}() on poorly indexed model"
                    ))
        
        return findings
    
    def _detect_connection_pool_issues(self) -> List[StandardFinding]:
        """Detect connection pool configuration issues."""
        findings = []
        
        # Look for schema.prisma files
        query = """
        SELECT path FROM files 
        WHERE path LIKE '%schema.prisma%'
        LIMIT 1
        """
        
        self.cursor.execute(query)
        schema_file = self.cursor.fetchone()
        
        if schema_file:
            # Check for connection pool configuration in environment variables or config
            config_query = """
            SELECT file, line, target_var, source_expr
            FROM assignments
            WHERE (target_var LIKE '%DATABASE_URL%' OR target_var LIKE '%connectionLimit%')
              AND source_expr NOT LIKE '%connection_limit%'
            """
            
            self.cursor.execute(config_query)
            for row in self.cursor.fetchall():
                file, line, var, expr = row
                findings.append(StandardFinding(
                    file=file,
                    line=line,
                    pattern="prisma_no_connection_limit",
                    message="Database URL without connection_limit parameter",
                    confidence=0.70,
                    severity="MEDIUM",
                    category="orm_configuration",
                    snippet="Missing ?connection_limit=N in DATABASE_URL"
                ))
        
        return findings


def analyze(context: StandardRuleContext) -> List[Dict[str, Any]]:
    """Entry point for the analyzer."""
    analyzer = PrismaAnalyzer(context)
    findings = analyzer.analyze()
    return [f.to_dict() for f in findings]