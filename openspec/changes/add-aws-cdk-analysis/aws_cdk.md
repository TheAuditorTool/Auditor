Okay, let's map out the pre-implementation plan for adding the AWS CDK (Python) scanning capability, leveraging your existing AST infrastructure. This follows your suggested file structure (`aws_cdk_impl.py`, `extractors/aws_cdk.py`) and adheres to your architectural principles.

-----

## 1\. Schema Definition (`schema.py`)

Define new tables specifically for storing extracted CDK facts. These will mirror the `terraform_*` tables where logical.

  * **`cdk_constructs` Table:** Stores information about each CDK construct instantiation found.

      * `construct_id` (TEXT, PK): Unique ID, e.g., `"file/path.py::L15::s3.Bucket::myBucket"`.
      * `file_path` (TEXT, FK -\> files.path): File containing the construct.
      * `line` (INTEGER): Line number where the instantiation occurs (e.g., `s3.Bucket(...)`).
      * `cdk_class` (TEXT): The fully qualified CDK class name (e.g., `aws_cdk.aws_s3.Bucket`, `aws_cdk.aws_ec2.SecurityGroup`).
      * `construct_name` (TEXT): The logical ID given in the CDK code (e.g., `"myBucket"`, `"webSg"`).
      * `properties_json` (TEXT): **(Optional/Low Priority)** A JSON blob of *all* properties for debugging/future use. Focus first on the `cdk_construct_properties` table.

  * **`cdk_construct_properties` Table:** Stores individual properties passed during construct instantiation. This is critical for rule analysis.

      * `id` (INTEGER, PK): Auto-incrementing ID.
      * `construct_id` (TEXT, FK -\> cdk\_constructs.construct\_id): Links back to the construct instance.
      * `property_name` (TEXT): The keyword argument name (e.g., `"public_read_access"`, `"storage_encrypted"`, `"peer"`).
      * `property_value_expr` (TEXT): The string representation of the value expression (e.g., `"True"`, `"False"`, `"ec2.Peer.ipv4('0.0.0.0/0')"`). Use `ast.unparse()` for this.
      * `line` (INTEGER): Line number of the specific keyword argument.

  * **`cdk_findings` Table:** Stores findings specific to CDK analysis (mirrors `terraform_findings`).

      * `finding_id` (TEXT, PK): Unique finding ID.
      * `file_path` (TEXT, FK -\> files.path).
      * `construct_id` (TEXT, FK -\> cdk\_constructs.construct\_id): Links finding to the specific construct instance.
      * `category` (TEXT): e.g., "public\_exposure", "missing\_encryption".
      * `severity` (TEXT): "critical", "high", "medium", "low".
      * `title` (TEXT).
      * `description` (TEXT).
      * `remediation` (TEXT).
      * `line` (INTEGER): Line number for the finding (usually the construct instantiation line or property line).

**Action:** Add these `TableSchema` definitions to `schema.py` and register them in the main `TABLES` dictionary.

-----

## 2\. Database Manager Updates (`database.py`)

Add new `add_cdk_*` methods to handle batch insertion for the new tables.

  * **`add_cdk_construct(...)` method:**

      * Signature: `def add_cdk_construct(self, file_path: str, line: int, cdk_class: str, construct_name: str, construct_id: str)`
      * Implementation: Appends a tuple `(construct_id, file_path, line, cdk_class, construct_name)` to `self.generic_batches['cdk_constructs']`.

  * **`add_cdk_construct_property(...)` method:**

      * Signature: `def add_cdk_construct_property(self, construct_id: str, property_name: str, property_value_expr: str, line: int)`
      * Implementation: Appends a tuple `(construct_id, property_name, property_value_expr, line)` to `self.generic_batches['cdk_construct_properties']`.

  * **`add_cdk_finding(...)` method:** (Mirror `add_terraform_finding`)

      * Signature: `def add_cdk_finding(self, finding_id: str, file_path: str, construct_id: Optional[str], category: str, severity: str, title: str, description: str, remediation: str, line: Optional[int])`
      * Implementation: Appends a tuple `(finding_id, file_path, construct_id, category, severity, title, description, remediation, line)` to `self.generic_batches['cdk_findings']`.

  * **`flush_batch()` Update:** Add the new table names (`cdk_constructs`, `cdk_construct_properties`, `cdk_findings`) to the `flush_order` list, ensuring `cdk_constructs` is flushed before `cdk_construct_properties`. Use `'INSERT'` mode.

**Action:** Implement these methods in `database.py`.

-----

## 3\. AST Implementation Enhancements (`python_impl.py`)

Modify the existing Python AST extraction logic to specifically identify CDK construct calls and extract their keyword arguments.

  * **New Function: `extract_python_cdk_constructs(tree: Dict, parser_self)`:**
      * Purpose: Find all `ast.Call` nodes that instantiate CDK constructs.
      * Logic:
          * Walk the `actual_tree` (the `ast.Module` object).
          * Identify `ast.Call` nodes.
          * For each `ast.Call`, analyze `node.func`. Use `get_node_name` or similar logic to resolve the called function/class name (e.g., `s3.Bucket`, `ec2.SecurityGroup`).
          * **Filter:** Keep only calls where the resolved name matches known CDK patterns (e.g., starts with `aws_cdk.`, `s3.`, `ec2.`, `rds.`, `iam.`). Import statements (`python_imports` table) might help resolve aliases here if needed later, but start simple.
          * For each matching CDK call:
              * Extract the `construct_name` (usually the second positional argument, `node.args[1]`, if it's a string literal).
              * Extract `line = node.lineno`.
              * Extract `cdk_class = resolved_name`.
              * **Extract Properties:** Iterate through `node.keywords` (the keyword arguments).
                  * For each `ast.keyword`:
                      * `property_name = keyword.arg`.
                      * `property_value_expr = ast.unparse(keyword.value)`.
                      * `property_line = keyword.lineno` (or `node.lineno` if keyword has no line).
                      * Store these as a list of property dictionaries.
              * Yield/return a dictionary containing: `{'line': ..., 'cdk_class': ..., 'construct_name': ..., 'properties': [{'name': ..., 'value_expr': ..., 'line': ...}, ...]}`.

**Action:** Implement `extract_python_cdk_constructs` in `python_impl.py`.

-----

## 4\. New Extractor (`indexer/extractors/aws_cdk.py`)

Create a dedicated extractor that uses the enhanced Python AST implementation to gather CDK facts.

  * **File Structure:** Create `theauditor/indexer/extractors/aws_cdk.py`.
  * **Class Definition:**
    ```python
    from . import BaseExtractor
    # Potentially import from python_impl if needed, or rely on ast_parser

    class AWSCdkExtractor(BaseExtractor):
        def supported_extensions(self) -> List[str]:
            return ['.py']

        def should_extract(self, file_path: str) -> bool:
            # OPTIONAL: Add faster check, e.g., if content contains 'import aws_cdk'
            # For now, rely on PythonExtractor running first and then checking imports
            return True # Let extract() handle the import check

        def extract(self, file_info: Dict[str, Any], content: str,
                    tree: Optional[Any] = None) -> Dict[str, Any]:
            if not tree or tree.get("type") != "python_ast":
                return {} # Only operate on Python AST

            # Check if this file imports aws_cdk
            # Use data already extracted by the standard PythonExtractor run
            # This avoids re-parsing imports
            imports = self.ast_parser.extract_imports(tree) # Assumes ast_parser has general extract methods
            if not any('aws_cdk' in imp[1] for imp in imports if len(imp) > 1):
                 return {} # Not a CDK file

            extracted_constructs = []
            extracted_properties = []

            # Call the NEW function from python_impl via ast_parser
            cdk_calls = self.ast_parser.extract_cdk_constructs(tree) # Need to add this method to ASTParser facade

            for call in cdk_calls:
                # Generate construct_id
                file_path_str = file_info['path']
                construct_id = f"{file_path_str}::L{call['line']}::{call['cdk_class']}::{call['construct_name']}"

                extracted_constructs.append({
                    'construct_id': construct_id,
                    'file_path': file_path_str, # Extractor adds file_path for DB manager
                    'line': call['line'],
                    'cdk_class': call['cdk_class'],
                    'construct_name': call['construct_name']
                })

                for prop in call['properties']:
                    extracted_properties.append({
                        'construct_id': construct_id,
                        'property_name': prop['name'],
                        'property_value_expr': prop['value_expr'],
                        'line': prop['line']
                    })

            return {
                'cdk_constructs': extracted_constructs,
                'cdk_construct_properties': extracted_properties,
                # Include other standard Python extractions if needed, or let PythonExtractor handle them
                'imports': imports # Pass along imports if PythonExtractor isn't run separately
            }

    ```
  * **AST Parser Facade (`ast_parser.py`):** Add a method `extract_cdk_constructs(self, tree)` that simply calls the `extract_python_cdk_constructs` from `python_impl.py` if the tree type is `python_ast`.

**Action:** Implement `AWSCdkExtractor` and update `ASTParser`.

-----

## 5\. Indexer Orchestrator Integration (`indexer/__init__.py`)

Register the new extractor and ensure its data is stored.

  * **Extractor Registration:** In `ExtractorRegistry`, register `AWSCdkExtractor`. Ensure the standard `PythonExtractor` still runs for *all* `.py` files to get basic symbols, imports, calls, etc. The `AWSCdkExtractor` should run *after* the `PythonExtractor` or rely on the `PythonExtractor` having already populated basic AST data if run independently. *Decision:* Simplest is to have `AWSCdkExtractor` run, check for CDK imports, and then perform its specific extraction.
  * **`_store_extracted_data` Update:**
      * Add `if 'cdk_constructs' in extracted:` block.
      * Inside, loop through `extracted['cdk_constructs']` and call `self.db_manager.add_cdk_construct(...)`, passing the necessary fields. Remember the extractor provides `file_path`. Increment `self.counts['cdk_constructs']`.
      * Add `if 'cdk_construct_properties' in extracted:` block.
      * Inside, loop through `extracted['cdk_construct_properties']` and call `self.db_manager.add_cdk_construct_property(...)`. Increment `self.counts['cdk_properties']`.

**Action:** Update `ExtractorRegistry` and `_store_extracted_data` in `indexer/__init__.py`.

-----

## 6\. New Analyzer (`analyzers/aws_cdk_analyzer.py`)

Create the analyzer module responsible for finding security issues in the stored CDK data.

  * **File Structure:** Create `theauditor/analyzers/aws_cdk_analyzer.py`.
  * **Class Definition:** Create `AWSCdkAnalyzer` class, similar to `TerraformAnalyzer`.
      * `__init__(self, db_path: str)`: Store db path.
      * `analyze(self) -> List[FindingDataclass]`: Main entry point. Connects to DB, calls individual check methods, aggregates findings, calls `_write_findings`.
  * **Check Methods (`_check_public_s3_buckets`, `_check_unencrypted_storage`, etc.):**
      * Each method queries the `cdk_constructs` and `cdk_construct_properties` tables using `build_query`.
      * **Example (`_check_public_s3_buckets`):**
        ```python
        # Find s3.Bucket constructs
        bucket_constructs_query = build_query(
            'cdk_constructs',
            columns=['construct_id', 'file_path', 'line', 'construct_name'],
            where="cdk_class LIKE '%.Bucket'" # Adjust based on actual class names
        )
        # For each bucket, query its properties
        for bucket in cursor.execute(bucket_constructs_query):
            props_query = build_query(
                'cdk_construct_properties',
                columns=['property_name', 'property_value_expr', 'line'],
                where=f"construct_id = '{bucket['construct_id']}'"
            )
            properties = {row['property_name']: row for row in cursor.execute(props_query)}

            # Check for public_read_access = True
            if 'public_read_access' in properties and properties['public_read_access']['property_value_expr'] == 'True':
                 findings.append(FindingDataclass(..., title=f"S3 Bucket '{bucket['construct_name']}' has public_read_access=True", ...))

            # Check for block_public_access settings (more complex logic needed)
            # ...
        ```
      * Implement similar logic for other rules (unencrypted RDS/EBS, open security groups, IAM wildcards) by querying the relevant `cdk_class` and `property_name`/`property_value_expr`.
  * **`_write_findings` Method:**
      * Connects to DB.
      * Deletes existing findings from `cdk_findings` and `findings_consolidated WHERE tool = 'cdk'`.
      * Iterates through findings list.
      * Calls `db_manager.add_cdk_finding(...)` for the specific table.
      * Calls `db_manager.write_findings_batch(...)` (or similar) to write to `findings_consolidated`, mapping fields appropriately and setting `tool='cdk'`.
      * Commits transaction.

**Action:** Implement the `AWSCdkAnalyzer` module.

-----

## 7\. Pipeline/CLI Integration

Wire the new analyzer into the main execution flow.

  * **CLI:** Add a new command group/command (e.g., `aud cdk analyze`) that instantiates `AWSCdkAnalyzer` and calls its `analyze` method.
  * **Pipeline (`pipelines.py`):** Add the new `cdk analyze` command to the appropriate stage (e.g., Stage 3 - Analysis, alongside Terraform).

**Action:** Update CLI definitions and `pipelines.py`.

-----

## 8\. Testing

  * **Unit Tests:**
      * Test `extract_python_cdk_constructs` with various CDK code snippets (different constructs, args, kwargs).
      * Test `AWSCdkExtractor` correctly filters files and formats data for the DB manager.
      * Test individual `AWSCdkAnalyzer` check methods with mock DB data representing vulnerable and non-vulnerable constructs.
  * **Integration Tests:**
      * Create small sample Python CDK projects (one vulnerable, one secure).
      * Run the full `aud index` and `aud cdk analyze` pipeline.
      * Verify the database contains the expected construct/property data.
      * Verify the analyzer produces the correct findings (and no false positives).
      * Verify findings appear in `findings_consolidated`.

**Action:** Create test files and implement tests.

-----

This plan leverages your existing Python AST parsing, minimizing redundant work and focusing on the CDK-specific identification, extraction, and analysis logic within your established architecture.