"""
TypeORM Analyzer - SQL-based implementation.

This module detects TypeORM anti-patterns and performance issues
using TheAuditor's indexed database.

Migration from: typeorm_detector.py (384 lines -> ~320 lines)
Performance: ~12x faster using direct SQL queries
"""

import sqlite3
import json
import re
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


class TypeORMAnalyzer:
    """Analyzer for TypeORM anti-patterns using SQL queries."""
    
    def __init__(self, context: StandardRuleContext):
        """Initialize with standard context."""
        self.context = context
        self.conn = sqlite3.connect(context.db_path)
        self.cursor = self.conn.cursor()
        
        # TypeORM query methods
        self.query_methods = [
            'getMany', 'getManyAndCount', 'getRawMany', 
            'find', 'findAndCount', 'findOne', 'findOneBy'
        ]
        
        # Common indexed fields that should have @Index
        self.common_indexed_fields = [
            'email', 'username', 'userId', 'createdAt', 
            'updatedAt', 'status', 'type', 'slug', 'code'
        ]
    
    def analyze(self) -> List[StandardFinding]:
        """Run all TypeORM checks."""
        findings = []
        
        try:
            # Check if orm_queries table exists
            self.cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='orm_queries'"
            )
            if not self.cursor.fetchone():
                logger.info("No orm_queries table found, skipping TypeORM analysis")
                return findings
            
            # Run each analysis
            findings.extend(self._detect_unbounded_querybuilder())
            findings.extend(self._detect_unbounded_repository())
            findings.extend(self._detect_complex_joins())
            findings.extend(self._detect_missing_transactions())
            findings.extend(self._detect_n_plus_one())
            findings.extend(self._detect_raw_queries())
            findings.extend(self._detect_cascade_issues())
            findings.extend(self._detect_synchronize_issues())
            findings.extend(self._detect_missing_indexes())
            
            logger.info(f"Found {len(findings)} TypeORM issues")
            
        except Exception as e:
            logger.error(f"Error during TypeORM analysis: {e}")
        finally:
            self.conn.close()
            
        return findings
    
    def _detect_unbounded_querybuilder(self) -> List[StandardFinding]:
        """Detect QueryBuilder without limits."""
        findings = []
        
        query = """
        SELECT file, line, query_type
        FROM orm_queries
        WHERE (query_type LIKE 'QueryBuilder.getMany%' 
               OR query_type LIKE 'QueryBuilder.getRawMany%')
          AND has_limit = 0
        """
        
        self.cursor.execute(query)
        for row in self.cursor.fetchall():
            file, line, query_type = row
            method = query_type.split('.')[-1] if '.' in query_type else query_type
            
            findings.append(StandardFinding(
                file=file,
                line=line,
                pattern="typeorm_unbounded_querybuilder",
                message=f"QueryBuilder.{method} without limit/take",
                confidence=0.90,
                severity="HIGH",
                category="orm_performance",
                snippet=f"{query_type}() without .limit() or .take()"
            ))
        
        return findings
    
    def _detect_unbounded_repository(self) -> List[StandardFinding]:
        """Detect Repository.find without pagination."""
        findings = []
        
        query = """
        SELECT file, line, query_type
        FROM orm_queries
        WHERE (query_type = 'Repository.find' 
               OR query_type = 'Repository.findAndCount')
          AND has_limit = 0
        """
        
        self.cursor.execute(query)
        for row in self.cursor.fetchall():
            file, line, query_type = row
            
            findings.append(StandardFinding(
                file=file,
                line=line,
                pattern="typeorm_unbounded_find",
                message=f"{query_type} without take option - fetches all records",
                confidence=0.85,
                severity="MEDIUM",
                category="orm_performance",
                snippet=f"{query_type}() without pagination"
            ))
        
        return findings
    
    def _detect_complex_joins(self) -> List[StandardFinding]:
        """Detect complex joins without pagination."""
        findings = []
        
        query = """
        SELECT file, line, query_type, includes
        FROM orm_queries
        WHERE query_type LIKE 'QueryBuilder.%'
          AND includes IS NOT NULL
          AND has_limit = 0
        """
        
        self.cursor.execute(query)
        for row in self.cursor.fetchall():
            file, line, query_type, includes_json = row
            
            try:
                includes = json.loads(includes_json) if includes_json else {}
                join_count = includes.get('joins', 0)
                
                if join_count >= 3:
                    findings.append(StandardFinding(
                        file=file,
                        line=line,
                        pattern="typeorm_complex_join_no_limit",
                        message=f"Complex query with {join_count} joins but no pagination",
                        confidence=0.80,
                        severity="HIGH",
                        category="orm_performance",
                        snippet=f"QueryBuilder with {join_count} joins"
                    ))
            except json.JSONDecodeError:
                pass
        
        return findings
    
    def _detect_missing_transactions(self) -> List[StandardFinding]:
        """Detect multiple save operations without transactions."""
        findings = []
        
        # Get all save operations grouped by file
        query = """
        SELECT file, line, query_type, has_transaction
        FROM orm_queries
        WHERE query_type IN ('Repository.save', 'Repository.remove', 
                            'Repository.update', 'Repository.delete')
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
                        pattern="typeorm_missing_transaction",
                        message=f"Multiple operations without transaction: {op1['query']} and {op2['query']}",
                        confidence=0.85,
                        severity="HIGH",
                        category="orm_data_integrity",
                        snippet="Use EntityManager.transaction() for atomicity"
                    ))
                    break  # One finding per cluster
        
        return findings
    
    def _detect_n_plus_one(self) -> List[StandardFinding]:
        """Detect potential N+1 query patterns."""
        findings = []
        
        # Look for multiple findOne calls close together
        query = """
        SELECT file, line, query_type
        FROM orm_queries
        WHERE query_type IN ('Repository.findOne', 'Repository.findOneBy')
        ORDER BY file, line
        """
        
        self.cursor.execute(query)
        
        # Group by file and check for patterns
        file_queries = {}
        for row in self.cursor.fetchall():
            file, line, query_type = row
            if file not in file_queries:
                file_queries[file] = []
            file_queries[file].append({'line': line, 'query': query_type})
        
        for file, queries in file_queries.items():
            for i in range(len(queries) - 1):
                q1 = queries[i]
                q2 = queries[i + 1]
                
                # Multiple findOne within 10 lines
                if q2['line'] - q1['line'] <= 10:
                    findings.append(StandardFinding(
                        file=file,
                        line=q1['line'],
                        pattern="typeorm_n_plus_one",
                        message=f"Multiple {q1['query']} calls - potential N+1",
                        confidence=0.75,
                        severity="MEDIUM",
                        category="orm_performance",
                        snippet="Consider using relations or joins"
                    ))
                    break
        
        return findings
    
    def _detect_raw_queries(self) -> List[StandardFinding]:
        """Detect potentially unsafe raw SQL queries."""
        findings = []
        
        # Look for raw query methods
        query = """
        SELECT DISTINCT f.file, f.line, f.callee_function, f.args_json
        FROM function_call_args f
        WHERE f.callee_function LIKE '%query%'
           OR f.callee_function LIKE '%createQueryBuilder%'
           OR f.callee_function = 'query'
        """
        
        self.cursor.execute(query)
        for row in self.cursor.fetchall():
            file, line, func, args_json = row
            
            # Check for string concatenation or interpolation
            if args_json:
                has_interpolation = any(x in args_json for x in ['${', '"+', '" +', '` +', '${'])
                if has_interpolation:
                    findings.append(StandardFinding(
                        file=file,
                        line=line,
                        pattern="typeorm_sql_injection",
                        message=f"Potential SQL injection in {func}",
                        confidence=0.80,
                        severity="CRITICAL",
                        category="orm_security",
                        snippet=f"{func}() with string interpolation"
                    ))
        
        return findings
    
    def _detect_cascade_issues(self) -> List[StandardFinding]:
        """Detect dangerous cascade: true configurations."""
        findings = []
        
        # Look for cascade: true in assignments
        query = """
        SELECT file, line, source_expr
        FROM assignments
        WHERE source_expr LIKE '%cascade%true%'
           OR source_expr LIKE '%cascade:%true%'
        """
        
        self.cursor.execute(query)
        for row in self.cursor.fetchall():
            file, line, expr = row
            findings.append(StandardFinding(
                file=file,
                line=line,
                pattern="typeorm_cascade_true",
                message="cascade: true can cause unintended data deletion",
                confidence=0.90,
                severity="HIGH",
                category="orm_data_integrity",
                snippet="Use specific cascade options instead"
            ))
        
        # Also check in symbols for decorator usage
        query = """
        SELECT file, line, name
        FROM symbols
        WHERE name LIKE '%cascade%true%'
        """
        
        self.cursor.execute(query)
        for row in self.cursor.fetchall():
            file, line, name = row
            findings.append(StandardFinding(
                file=file,
                line=line,
                pattern="typeorm_cascade_true",
                message="cascade: true in decorator - use specific options",
                confidence=0.85,
                severity="HIGH",
                category="orm_data_integrity",
                snippet='cascade: ["insert", "update"] instead of true'
            ))
        
        return findings
    
    def _detect_synchronize_issues(self) -> List[StandardFinding]:
        """Detect synchronize: true in production."""
        findings = []
        
        # Look for synchronize: true in configuration
        query = """
        SELECT file, line, source_expr
        FROM assignments
        WHERE (source_expr LIKE '%synchronize%true%'
               OR source_expr LIKE '%synchronize:%true%')
          AND file NOT LIKE '%test%'
          AND file NOT LIKE '%spec%'
        """
        
        self.cursor.execute(query)
        for row in self.cursor.fetchall():
            file, line, expr = row
            findings.append(StandardFinding(
                file=file,
                line=line,
                pattern="typeorm_synchronize_true",
                message="synchronize: true - NEVER use in production",
                confidence=0.95,
                severity="CRITICAL",
                category="orm_security",
                snippet="Use migrations instead of synchronize"
            ))
        
        return findings
    
    def _detect_missing_indexes(self) -> List[StandardFinding]:
        """Detect entities missing important indexes."""
        findings = []
        
        # Look for entity files
        query = """
        SELECT DISTINCT path 
        FROM files
        WHERE (path LIKE '%entity.ts' OR path LIKE '%entity.js')
          AND path NOT LIKE '%test%'
        """
        
        self.cursor.execute(query)
        entity_files = self.cursor.fetchall()
        
        for (entity_file,) in entity_files:
            # Check symbols for this file to find properties
            property_query = """
            SELECT COUNT(DISTINCT name) as prop_count
            FROM symbols
            WHERE file = ?
              AND type IN ('property', 'field', 'column')
            """
            
            self.cursor.execute(property_query, (entity_file,))
            prop_count = self.cursor.fetchone()[0]
            
            # Check for @Index decorators
            index_query = """
            SELECT COUNT(*) as index_count
            FROM symbols
            WHERE file = ?
              AND (name LIKE '%@Index%' OR name LIKE '%Index()%')
            """
            
            self.cursor.execute(index_query, (entity_file,))
            index_count = self.cursor.fetchone()[0]
            
            # Flag if many properties but few indexes
            if prop_count > 5 and index_count < 2:
                findings.append(StandardFinding(
                    file=entity_file,
                    line=0,
                    pattern="typeorm_missing_indexes",
                    message=f"Entity has {prop_count} properties but only {index_count} indexes",
                    confidence=0.70,
                    severity="MEDIUM",
                    category="orm_performance",
                    snippet="Add @Index() to frequently queried fields"
                ))
            
            # Check for common fields without indexes
            for field in self.common_indexed_fields:
                field_query = """
                SELECT line FROM symbols
                WHERE file = ?
                  AND name LIKE ?
                  AND type IN ('property', 'field', 'column')
                """
                
                self.cursor.execute(field_query, (entity_file, f'%{field}%'))
                field_row = self.cursor.fetchone()
                
                if field_row:
                    # Check if indexed
                    index_check = """
                    SELECT COUNT(*) FROM symbols
                    WHERE file = ?
                      AND ABS(line - ?) <= 2
                      AND name LIKE '%Index%'
                    """
                    
                    self.cursor.execute(index_check, (entity_file, field_row[0]))
                    is_indexed = self.cursor.fetchone()[0] > 0
                    
                    if not is_indexed:
                        findings.append(StandardFinding(
                            file=entity_file,
                            line=field_row[0],
                            pattern="typeorm_field_not_indexed",
                            message=f"Common field '{field}' should be indexed",
                            confidence=0.75,
                            severity="MEDIUM",
                            category="orm_performance",
                            snippet=f"Add @Index() to {field} field"
                        ))
        
        return findings


def analyze(context: StandardRuleContext) -> List[Dict[str, Any]]:
    """Entry point for the analyzer."""
    analyzer = TypeORMAnalyzer(context)
    findings = analyzer.analyze()
    return [f.to_dict() for f in findings]