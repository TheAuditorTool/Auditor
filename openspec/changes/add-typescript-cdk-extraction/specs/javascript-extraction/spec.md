# Spec Delta: JavaScript/TypeScript Extraction

**Capability**: javascript-extraction
**Change**: add-typescript-cdk-extraction
**Type**: Feature Addition (Critical Gap)

## ADDED Requirements

### Requirement: AWS CDK Construct Extraction

The JavaScript/TypeScript extractor SHALL extract AWS CDK infrastructure-as-code constructs to enable security analysis of cloud infrastructure definitions.

**Previous Implementation**: CDK constructs extracted from Python files only (`ast_extractors/python/cdk_extractor.py`). TypeScript/JavaScript CDK code is NOT analyzed.

**New Implementation**: Add `extractCDKConstructs()` function to `ast_extractors/javascript/security_extractors.js` to extract:
- CDK construct instantiations (`new s3.Bucket(...)`, `new rds.DatabaseInstance(...)`)
- Construct properties (encryption, access controls, network rules)
- Import detection for `aws-cdk-lib` modules

**Rationale**: TypeScript is the AWS-recommended language for CDK. Without TypeScript extraction, TheAuditor has a critical blind spot for 80%+ of production CDK infrastructure.

#### Scenario: Extract S3 Bucket with Public Access

- **GIVEN** a TypeScript CDK stack file with a public S3 bucket (`publicReadAccess: true`)
- **WHEN** `aud index` is run on the project
- **THEN** the construct SHALL be written to `cdk_constructs` table with cdk_class='s3.Bucket'
- **AND** the `publicReadAccess` property SHALL be written to `cdk_construct_properties` table
- **AND** the CDK analyzer SHALL detect this as a CRITICAL vulnerability

#### Scenario: Extract Unencrypted RDS Instance

- **GIVEN** a TypeScript CDK stack with an RDS instance (`storageEncrypted: false`)
- **WHEN** `aud index` and `aud cdk analyze` are run
- **THEN** the construct SHALL be extracted with cdk_class='rds.DatabaseInstance'
- **AND** the CDK analyzer SHALL detect this as a CRITICAL vulnerability
- **AND** `aud cdk analyze` SHALL return exit code 2 (critical findings)

#### Scenario: Extract Security Group with Open Ingress

- **GIVEN** a TypeScript CDK stack with a security group (`allowAllOutbound: true`)
- **WHEN** the CDK analyzer queries the database
- **THEN** the security rule SHALL detect the open egress configuration
- **AND** a HIGH severity finding SHALL be created
- **AND** the finding SHALL recommend restricting allowAllOutbound to false

#### Scenario: Handle Multiple Import Styles

- **GIVEN** a TypeScript file with 3 CDK import patterns (namespace, named, direct)
- **WHEN** `extractCDKConstructs()` processes imports and function calls
- **THEN** all 3 constructs SHALL be detected and extracted
- **AND** namespace imports (`import * as s3`) SHALL be mapped correctly
- **AND** named imports (`import { Bucket }`) SHALL be mapped correctly
- **AND** direct class imports SHALL be mapped correctly

#### Scenario: Offline Extraction (No Network Calls)

- **GIVEN** a TypeScript CDK project analyzed with `aud full --offline` flag
- **WHEN** the full analysis pipeline runs
- **THEN** the JavaScript extractor SHALL use only local AST data
- **AND** zero network calls SHALL be made to npm registry or AWS
- **AND** extraction SHALL complete successfully
- **AND** CDK constructs SHALL be written to database

#### Scenario: Parity with Python CDK Extraction

- **GIVEN** two CDK stacks (Python and TypeScript) with identical vulnerabilities (public S3 bucket)
- **WHEN** both files are indexed and analyzed
- **THEN** both SHALL produce identical database records (language-agnostic schema)
- **AND** the CDK analyzer SHALL detect both vulnerabilities with identical rule logic
- **AND** both findings SHALL have the same severity and remediation guidance

## Notes

**Breaking Changes**: NONE - This is a pure addition to JavaScript extraction. Python CDK extraction is unaffected.

**Testing**: New tests created (`test_cdk_extraction.py`, `test_cdk_integration.py`) plus comprehensive test fixtures.

**Teamsop.md Compliance**: ZERO FALLBACK POLICY enforced, DATABASE-FIRST architecture maintained, deterministic extraction guaranteed.

**Future Work**: Rust CDK support deferred to separate proposal (Phase 2).
