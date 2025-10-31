# Framework Extraction Specification

## ADDED Requirements

### Requirement: Sequelize ORM Model Extraction

TheAuditor SHALL extract Sequelize ORM model definitions from JavaScript/TypeScript codebases, including model classes, table mappings, and field definitions.

#### Scenario: Basic Sequelize model detection

- **WHEN** a class extends `Model` from Sequelize
- **THEN** the system SHALL extract:
  - Model name (class name)
  - Table name (from Model.init() or inferred)
  - File path and line number
  - Whether the class explicitly extends Model

#### Scenario: Sequelize model with Model.init()

- **WHEN** a Sequelize model defines fields using `Model.init({ ... }, { sequelize, tableName: 'users' })`
- **THEN** the system SHALL extract:
  - Model name
  - Table name from options
  - Field definitions with types
  - File path and line number

### Requirement: Sequelize Association Extraction

TheAuditor SHALL extract Sequelize model associations (relationships) including hasMany, belongsTo, hasOne, and belongsToMany patterns.

#### Scenario: hasMany relationship

- **WHEN** a model defines `User.hasMany(Post, { foreignKey: 'userId' })`
- **THEN** the system SHALL extract:
  - Source model: User
  - Association type: hasMany
  - Target model: Post
  - Foreign key: userId
  - File path and line number

#### Scenario: belongsToMany through table

- **WHEN** a model defines `User.belongsToMany(Role, { through: 'UserRoles' })`
- **THEN** the system SHALL extract:
  - Source model: User
  - Association type: belongsToMany
  - Target model: Role
  - Through table: UserRoles
  - File path and line number

### Requirement: BullMQ Queue Extraction

TheAuditor SHALL extract BullMQ queue definitions and worker registrations from Node.js codebases.

#### Scenario: Queue instantiation

- **WHEN** code instantiates `new Queue('emailQueue', { connection: redisConfig })`
- **THEN** the system SHALL extract:
  - Queue name: emailQueue
  - Redis configuration (stringified)
  - File path and line number

#### Scenario: Worker registration

- **WHEN** code instantiates `new Worker('emailQueue', async (job) => { ... })`
- **THEN** the system SHALL extract:
  - Queue name: emailQueue
  - Worker function (function body or reference)
  - Processor path (if imported)
  - File path and line number

### Requirement: BullMQ Job Producer Tracking

TheAuditor SHALL track job producers that add jobs to BullMQ queues.

#### Scenario: Job added to queue

- **WHEN** code calls `queue.add('sendEmail', { to, subject, body })`
- **THEN** the system SHALL extract:
  - Queue name (from queue variable)
  - Job type: sendEmail
  - Job data (argument expression)
  - File path and line number

### Requirement: Angular Component Extraction

TheAuditor SHALL extract Angular components from TypeScript codebases, detecting @Component decorators and component metadata.

#### Scenario: Component with decorator

- **WHEN** a class has `@Component({ selector: 'app-user', templateUrl: './user.component.html' })`
- **THEN** the system SHALL extract:
  - Component name (class name)
  - Selector: app-user
  - Template path: ./user.component.html
  - Style paths (if present)
  - File path and line number

#### Scenario: Component with lifecycle hooks

- **WHEN** a component implements OnInit, OnDestroy, or other lifecycle interfaces
- **THEN** the system SHALL extract:
  - Component name
  - Lifecycle hooks implemented (ngOnInit, ngOnDestroy, etc.)
  - File path and line number

### Requirement: Angular Service Extraction

TheAuditor SHALL extract Angular services from TypeScript codebases, detecting @Injectable decorators and service configuration.

#### Scenario: Injectable service

- **WHEN** a class has `@Injectable({ providedIn: 'root' })`
- **THEN** the system SHALL extract:
  - Service name (class name)
  - Is injectable: true
  - Provided in: root
  - File path and line number

### Requirement: Angular Dependency Injection Tracking

TheAuditor SHALL track dependency injection patterns in Angular components, services, and guards.

#### Scenario: Constructor injection

- **WHEN** a component constructor has `constructor(private userService: UserService, private http: HttpClient)`
- **THEN** the system SHALL extract:
  - Target class: component name
  - Injected service: UserService
  - Injection type: constructor
  - File path and line number

AND SHALL extract:
  - Target class: component name
  - Injected service: HttpClient
  - Injection type: constructor
  - File path and line number

### Requirement: Marshmallow Schema Extraction

TheAuditor SHALL extract Marshmallow schema definitions from Python codebases, detecting schema classes and field definitions.

#### Scenario: Basic schema class

- **WHEN** a class extends `Schema` from marshmallow
- **THEN** the system SHALL extract:
  - Schema name (class name)
  - Has Meta class: true/false
  - Meta fields (if present)
  - File path and line number

#### Scenario: Schema with fields

- **WHEN** a schema defines `username = fields.String(required=True, validate=Length(max=80))`
- **THEN** the system SHALL extract:
  - Schema name
  - Field name: username
  - Field type: String
  - Is required: true
  - Validators: Length(max=80)
  - File path and line number

### Requirement: WTForms Form Extraction

TheAuditor SHALL extract WTForms form definitions from Python codebases, detecting form classes and field definitions.

#### Scenario: Basic form class

- **WHEN** a class extends `Form` from wtforms
- **THEN** the system SHALL extract:
  - Form name (class name)
  - Has CSRF protection: true/false
  - Submit method (if defined)
  - File path and line number

#### Scenario: Form with fields

- **WHEN** a form defines `email = StringField('Email', validators=[DataRequired(), Email()])`
- **THEN** the system SHALL extract:
  - Form name
  - Field name: email
  - Field type: StringField
  - Validators: [DataRequired, Email]
  - Default value (if present)
  - File path and line number

### Requirement: Celery Task Extraction

TheAuditor SHALL extract Celery task definitions from Python codebases, detecting @task decorators and task configuration.

#### Scenario: Basic task definition

- **WHEN** a function has `@app.task` decorator
- **THEN** the system SHALL extract:
  - Task name (function name)
  - Bind: false (default)
  - Max retries: null (default)
  - Rate limit: null (default)
  - File path and line number

#### Scenario: Task with options

- **WHEN** a function has `@app.task(bind=True, max_retries=3, rate_limit='10/m')`
- **THEN** the system SHALL extract:
  - Task name (function name)
  - Bind: true
  - Max retries: 3
  - Rate limit: 10/m
  - File path and line number

### Requirement: Celery Task Invocation Tracking

TheAuditor SHALL track Celery task invocations using .delay() and .apply_async() methods.

#### Scenario: Task invocation with .delay()

- **WHEN** code calls `send_email.delay(to='user@example.com', subject='Hello')`
- **THEN** the system SHALL extract:
  - Task name: send_email
  - Call type: delay
  - Arguments: to='user@example.com', subject='Hello'
  - File path and line number

#### Scenario: Task invocation with .apply_async()

- **WHEN** code calls `send_email.apply_async((to, subject), countdown=60)`
- **THEN** the system SHALL extract:
  - Task name: send_email
  - Call type: apply_async
  - Arguments: (to, subject), countdown=60
  - File path and line number

### Requirement: Celery Beat Schedule Extraction

TheAuditor SHALL extract Celery Beat periodic task schedules from configuration.

#### Scenario: Crontab schedule

- **WHEN** beat_schedule defines `'send-daily-report': { 'task': 'tasks.send_report', 'schedule': crontab(hour=9, minute=0) }`
- **THEN** the system SHALL extract:
  - Schedule name: send-daily-report
  - Task name: tasks.send_report
  - Crontab: hour=9, minute=0
  - Interval: null
  - File path and line number

#### Scenario: Interval schedule

- **WHEN** beat_schedule defines `'cleanup-cache': { 'task': 'tasks.cleanup', 'schedule': 3600.0 }`
- **THEN** the system SHALL extract:
  - Schedule name: cleanup-cache
  - Task name: tasks.cleanup
  - Crontab: null
  - Interval: 3600.0
  - File path and line number

### Requirement: Pytest Fixture Extraction

TheAuditor SHALL extract pytest fixture definitions from Python test files.

#### Scenario: Basic fixture

- **WHEN** a function has `@pytest.fixture` decorator
- **THEN** the system SHALL extract:
  - Fixture name (function name)
  - Scope: function (default)
  - Autouse: false (default)
  - File path and line number

#### Scenario: Fixture with scope

- **WHEN** a function has `@pytest.fixture(scope='session', autouse=True)`
- **THEN** the system SHALL extract:
  - Fixture name (function name)
  - Scope: session
  - Autouse: true
  - File path and line number

### Requirement: Pytest Parametrize Extraction

TheAuditor SHALL extract pytest parametrize decorators from test functions.

#### Scenario: Parametrized test

- **WHEN** a test has `@pytest.mark.parametrize('input,expected', [(1, 2), (2, 3), (3, 4)])`
- **THEN** the system SHALL extract:
  - Test function name
  - Parameter names: input,expected
  - Parameter values: [(1, 2), (2, 3), (3, 4)] (stringified)
  - File path and line number

### Requirement: Pytest Marker Extraction

TheAuditor SHALL extract custom pytest markers from test functions.

#### Scenario: Custom marker

- **WHEN** a test has `@pytest.mark.slow` decorator
- **THEN** the system SHALL extract:
  - Test function name
  - Marker name: slow
  - Marker args: null
  - File path and line number

#### Scenario: Marker with arguments

- **WHEN** a test has `@pytest.mark.skipif(sys.version_info < (3, 8), reason='Requires Python 3.8+')`
- **THEN** the system SHALL extract:
  - Test function name
  - Marker name: skipif
  - Marker args: sys.version_info < (3, 8), reason='Requires Python 3.8+'
  - File path and line number

---

## Database Schema Requirements

### Requirement: Framework Extraction Database Tables

TheAuditor SHALL create database tables to store extracted framework data with proper indexing for efficient querying.

#### Scenario: Sequelize tables created

- **WHEN** database schema is initialized
- **THEN** the system SHALL create:
  - sequelize_models table with columns: file, line, model_name, table_name, extends_model
  - sequelize_associations table with columns: file, line, model_name, association_type, target_model, foreign_key, through_table
  - Indexes on: file, model_name, target_model, association_type

#### Scenario: BullMQ tables created

- **WHEN** database schema is initialized
- **THEN** the system SHALL create:
  - bullmq_queues table with columns: file, line, queue_name, redis_config
  - bullmq_workers table with columns: file, line, queue_name, worker_function, processor_path
  - Indexes on: file, queue_name, worker_function

#### Scenario: Angular tables created

- **WHEN** database schema is initialized
- **THEN** the system SHALL create:
  - angular_components table with columns: file, line, component_name, selector, template_path, style_paths, has_lifecycle_hooks
  - angular_services table with columns: file, line, service_name, is_injectable, provided_in
  - angular_modules table with columns: file, line, module_name, declarations, imports, providers, exports
  - angular_guards table with columns: file, line, guard_name, guard_type, implements_interface
  - di_injections table with columns: file, line, target_class, injected_service, injection_type
  - Indexes on: file, component_name, service_name, target_class, injected_service

#### Scenario: Python framework tables populated

- **WHEN** Python files are indexed
- **THEN** the system SHALL populate:
  - python_marshmallow_schemas table (if Marshmallow schemas detected)
  - python_marshmallow_fields table (if Marshmallow fields detected)
  - python_wtforms_forms table (if WTForms forms detected)
  - python_wtforms_fields table (if WTForms fields detected)
  - python_celery_tasks table (if Celery tasks detected)
  - python_celery_task_calls table (if Celery task calls detected)
  - python_celery_beat_schedules table (if Celery Beat schedules detected)
  - python_pytest_fixtures table (if pytest fixtures detected)
  - python_pytest_parametrize table (if pytest parametrize decorators detected)
  - python_pytest_markers table (if pytest markers detected)

---

## Integration Requirements

### Requirement: Extractor-Indexer-Schema Integration

TheAuditor SHALL ensure extracted framework data flows from extractors through indexers to database storage without data loss.

#### Scenario: Node.js extraction pipeline

- **WHEN** JavaScript extractor returns framework data (sequelize_models, bullmq_jobs, angular_*)
- **THEN** the indexer SHALL:
  - Receive the data from batch extraction results
  - Validate data structure
  - Store data to corresponding database tables
  - Log extraction counts

#### Scenario: Python extraction pipeline

- **WHEN** Python extractor calls framework extraction functions
- **THEN** the system SHALL:
  - Execute extraction function (extract_marshmallow_schemas, etc.)
  - Receive extracted data as List[Dict]
  - Validate data structure
  - Store data to corresponding database tables
  - Log extraction counts

#### Scenario: Silent failure prevention

- **WHEN** extractor returns data that indexer doesn't recognize
- **THEN** the system SHALL:
  - Log a WARNING message with unrecognized keys
  - Continue processing other data
  - NOT silently discard data without warning

---

## Testing Requirements

### Requirement: Framework Extraction Test Fixtures

TheAuditor SHALL provide comprehensive test fixtures for each framework extraction capability.

#### Scenario: Sequelize test fixture

- **WHEN** tests run on node-sequelize-orm fixture
- **THEN** the system SHALL:
  - Extract all Sequelize models (minimum 3 models)
  - Extract all associations (minimum 5 associations)
  - Pass all SQL queries in spec.yaml

#### Scenario: Python framework test fixtures

- **WHEN** tests run on Python framework fixtures
- **THEN** the system SHALL:
  - Extract Marshmallow schemas from python-marshmallow-schemas fixture
  - Extract WTForms forms from python-wtforms-forms fixture
  - Extract Celery tasks from python-celery-tasks fixture
  - Extract pytest fixtures from python-pytest-fixtures fixture
  - Pass all SQL queries in respective spec.yaml files

#### Scenario: No regressions in existing extraction

- **WHEN** new framework extraction is added
- **THEN** the system SHALL:
  - Continue extracting React components correctly
  - Continue extracting Vue components correctly
  - Continue extracting TypeScript type annotations correctly
  - Continue extracting Python ORM models correctly
  - NOT reduce extraction counts in any existing category
