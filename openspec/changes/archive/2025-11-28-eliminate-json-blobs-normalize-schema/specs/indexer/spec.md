## ADDED Requirements

### Requirement: Package Dependencies Junction Table

The Node schema SHALL include a `package_dependencies` junction table to store individual dependency entries extracted from package.json files.

The table SHALL contain columns for: file_path (FK to package_configs.file_path), name, version_spec, is_dev, is_peer.

#### Scenario: package.json dependencies stored as junction records
- **WHEN** a package.json with dependencies `{ "lodash": "^4.17.0", "express": "^4.18.0" }` is extracted
- **THEN** two records are inserted into `package_dependencies`
- **AND** each record contains the file_path (FK to package_configs), dependency name, and version specifier
- **AND** is_dev and is_peer flags are set to 0

#### Scenario: devDependencies stored with is_dev flag
- **WHEN** a package.json with devDependencies `{ "jest": "^29.0.0" }` is extracted
- **THEN** one record is inserted into `package_dependencies` with is_dev=1

#### Scenario: peerDependencies stored with is_peer flag
- **WHEN** a package.json with peerDependencies `{ "react": "^18.0.0" }` is extracted
- **THEN** one record is inserted into `package_dependencies` with is_peer=1

### Requirement: Package Scripts Junction Table

The Node schema SHALL include a `package_scripts` junction table to store individual script entries from package.json files.

The table SHALL contain columns for: file_path (FK to package_configs.file_path), script_name, script_command.

#### Scenario: package.json scripts stored as junction records
- **WHEN** a package.json with scripts `{ "test": "jest", "build": "tsc" }` is extracted
- **THEN** two records are inserted into `package_scripts`
- **AND** each record contains the file_path, script name, and command

### Requirement: Package Engines Junction Table

The Node schema SHALL include a `package_engines` junction table to store engine requirements from package.json files.

The table SHALL contain columns for: file_path (FK to package_configs.file_path), engine_name, version_spec.

#### Scenario: package.json engines stored as junction records
- **WHEN** a package.json with engines `{ "node": ">=18.0.0", "npm": ">=9.0.0" }` is extracted
- **THEN** two records are inserted into `package_engines`
- **AND** each record contains the file_path, engine name, and version requirement

### Requirement: Package Workspaces Junction Table

The Node schema SHALL include a `package_workspaces` junction table to store workspace paths from package.json files.

The table SHALL contain columns for: file_path (FK to package_configs.file_path), workspace_path.

#### Scenario: package.json workspaces stored as junction records
- **WHEN** a package.json with workspaces `["packages/*", "apps/*"]` is extracted
- **THEN** two records are inserted into `package_workspaces`
- **AND** each record contains the file_path and workspace path pattern

### Requirement: Dockerfile Ports Junction Table

The infrastructure schema SHALL include a `dockerfile_ports` junction table to store EXPOSE directives from Dockerfiles.

The table SHALL contain columns for: file_path (FK to docker_images.file_path), port, protocol.

#### Scenario: Dockerfile EXPOSE stored as junction records
- **WHEN** a Dockerfile with `EXPOSE 80 443` is extracted
- **THEN** two records are inserted into `dockerfile_ports`
- **AND** each record contains the file_path, port number, and protocol (default tcp)

### Requirement: Dockerfile Env Vars Junction Table

The infrastructure schema SHALL include a `dockerfile_env_vars` junction table to store ENV and ARG directives from Dockerfiles.

The table SHALL contain columns for: file_path (FK to docker_images.file_path), var_name, var_value, is_build_arg.

#### Scenario: Dockerfile ENV stored as junction records
- **WHEN** a Dockerfile with `ENV NODE_ENV=production` is extracted
- **THEN** one record is inserted into `dockerfile_env_vars` with is_build_arg=0

#### Scenario: Dockerfile ARG stored as junction records
- **WHEN** a Dockerfile with `ARG VERSION=1.0` is extracted
- **THEN** one record is inserted into `dockerfile_env_vars` with is_build_arg=1

### Requirement: Compose Service Ports Junction Table

The infrastructure schema SHALL include a `compose_service_ports` junction table to store port mappings from docker-compose files.

The table SHALL contain columns for: file_path, service_name (composite FK to compose_services), host_port, container_port, protocol.

#### Scenario: docker-compose ports stored as junction records
- **WHEN** a docker-compose service with ports `["8080:80", "443:443"]` is extracted
- **THEN** two records are inserted into `compose_service_ports`
- **AND** each record contains host_port and container_port split from the mapping

### Requirement: Compose Service Volumes Junction Table

The infrastructure schema SHALL include a `compose_service_volumes` junction table to store volume mappings from docker-compose files.

The table SHALL contain columns for: file_path, service_name (composite FK to compose_services), host_path, container_path, mode.

#### Scenario: docker-compose volumes stored as junction records
- **WHEN** a docker-compose service with volumes `["./data:/app/data:rw", "./logs:/app/logs:ro"]` is extracted
- **THEN** two records are inserted into `compose_service_volumes`
- **AND** each record contains host_path, container_path, and mode

### Requirement: Compose Service Env Junction Table

The infrastructure schema SHALL include a `compose_service_env` junction table to store environment variables from docker-compose files.

The table SHALL contain columns for: file_path, service_name (composite FK to compose_services), var_name, var_value.

#### Scenario: docker-compose environment stored as junction records
- **WHEN** a docker-compose service with environment `{ "NODE_ENV": "production", "PORT": "3000" }` is extracted
- **THEN** two records are inserted into `compose_service_env`
- **AND** each record contains the variable name and value

### Requirement: Compose Service Capabilities Junction Table

The infrastructure schema SHALL include a `compose_service_capabilities` junction table to store cap_add and cap_drop from docker-compose files.

The table SHALL contain columns for: file_path, service_name (composite FK to compose_services), capability, is_add.

#### Scenario: docker-compose cap_add stored as junction records
- **WHEN** a docker-compose service with cap_add `["SYS_ADMIN", "NET_ADMIN"]` is extracted
- **THEN** two records are inserted into `compose_service_capabilities` with is_add=1

#### Scenario: docker-compose cap_drop stored as junction records
- **WHEN** a docker-compose service with cap_drop `["ALL"]` is extracted
- **THEN** one record is inserted into `compose_service_capabilities` with is_add=0

### Requirement: Compose Service Dependencies Junction Table

The infrastructure schema SHALL include a `compose_service_deps` junction table to store depends_on entries from docker-compose files.

The table SHALL contain columns for: file_path, service_name (composite FK to compose_services), depends_on_service, condition.

#### Scenario: docker-compose depends_on stored as junction records
- **WHEN** a docker-compose service with depends_on `["db", "redis"]` is extracted
- **THEN** two records are inserted into `compose_service_deps`
- **AND** condition defaults to "service_started"

### Requirement: Terraform Resource Properties Junction Table

The infrastructure schema SHALL include a `terraform_resource_properties` junction table to store resource properties from Terraform files.

The table SHALL contain columns for: resource_id, property_name, property_value, property_type.

#### Scenario: Terraform resource properties stored as junction records
- **WHEN** a Terraform resource with properties `ami = "ami-12345"` and `instance_type = "t3.micro"` is extracted
- **THEN** two records are inserted into `terraform_resource_properties`
- **AND** each record contains the property name, value, and inferred type

### Requirement: Terraform Resource Dependencies Junction Table

The infrastructure schema SHALL include a `terraform_resource_deps` junction table to store depends_on entries from Terraform resources.

The table SHALL contain columns for: resource_id, depends_on_resource.

#### Scenario: Terraform depends_on stored as junction records
- **WHEN** a Terraform resource with depends_on `[aws_vpc.main, aws_subnet.private]` is extracted
- **THEN** two records are inserted into `terraform_resource_deps`
- **AND** each record contains the dependency reference

### Requirement: GraphQL Field Directives Junction Table

The GraphQL schema SHALL include a `graphql_field_directives` junction table to store directives applied to GraphQL fields.

The table SHALL contain columns for: field_id (FK to graphql_fields.field_id), directive_name, directive_args.

#### Scenario: GraphQL field directives stored as junction records
- **WHEN** a GraphQL field with `@deprecated(reason: "Use newField")` is extracted
- **THEN** one record is inserted into `graphql_field_directives`
- **AND** the record contains directive_name "@deprecated" and args as JSON

### Requirement: GraphQL Arg Directives Junction Table

The GraphQL schema SHALL include a `graphql_arg_directives` junction table to store directives applied to GraphQL field arguments.

The table SHALL contain columns for: field_id, arg_name (composite FK to graphql_field_args), directive_name, directive_args.

**NOTE**: graphql_field_args uses composite PK (field_id, arg_name), NOT an arg_id column.

#### Scenario: GraphQL argument directives stored as junction records
- **WHEN** a GraphQL argument with `@constraint(min: 0, max: 100)` is extracted
- **THEN** one record is inserted into `graphql_arg_directives`
- **AND** the record contains directive_name and args

### Requirement: No JSON Blob Columns for Normalized Data

The schema SHALL NOT use TEXT columns to store JSON-serialized arrays for data that can be normalized into junction tables.

#### Scenario: Package dependencies use junction table
- **WHEN** package.json dependencies are stored
- **THEN** they SHALL be stored in `package_dependencies` junction table
- **AND** NOT as a JSON string in `package_configs.dependencies`

#### Scenario: Docker port mappings use junction table
- **WHEN** Dockerfile EXPOSE directives are stored
- **THEN** they SHALL be stored in `dockerfile_ports` junction table
- **AND** NOT as a JSON string in `docker_images.exposed_ports`

#### Scenario: Schema contract test for no JSON blobs
- **WHEN** schema contract tests run
- **THEN** tests SHALL verify no JSON blob columns remain for normalized data
- **AND** tests SHALL pass if junction tables are used consistently
