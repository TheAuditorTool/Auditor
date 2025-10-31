# Python Coverage Gaps - Ecosystem Parity Analysis

**Goal:** Achieve Node.js-level ecosystem coverage for Python (validation, frameworks, patterns)

---

## TIER 1: CRITICAL SECURITY GAPS (Highest Priority)

### 1. Django Class-Based Views (CBVs)
**Node Equivalent:** Express middleware, route handlers
**Missing:**
- ListView, DetailView, CreateView, UpdateView, DeleteView
- get_queryset() overrides (SQL injection risk)
- Missing auth decorators (@login_required on dispatch)
- Form handling in views

**Tables Needed:**
```python
python_django_views:
  - file, line, view_class_name
  - view_type (ListView, DetailView, etc)
  - model_name (if queryset/model defined)
  - template_name
  - has_permission_check (boolean)
  - http_method_names (JSON list: ['get', 'post'])
```

**Security Impact:** HIGH - Missing auth checks on views = direct access control bypass

---

### 2. Django Forms
**Node Equivalent:** Zod/Joi/Yup validators + React forms
**Missing:**
- Form field definitions (CharField, IntegerField, etc)
- Custom validators (clean_<field>, clean())
- CSRF token handling
- ModelForm associations

**Tables Needed:**
```python
python_django_forms:
  - file, line, form_class_name
  - is_model_form (boolean)
  - model_name (if ModelForm)
  - field_count

python_django_form_fields:
  - file, line, form_class_name, field_name
  - field_type (CharField, EmailField, etc)
  - required (boolean)
  - validators (JSON list)
```

**Security Impact:** HIGH - Input validation = sanitization for taint analysis

---

### 3. Marshmallow Schemas (Validation Framework)
**Node Equivalent:** Zod, Joi, Yup, class-validator
**Missing:**
- Schema definitions (like Pydantic but for Marshmallow)
- Field validators
- Nested schemas
- Deserialization patterns

**Tables Needed:**
```python
python_marshmallow_schemas:
  - file, line, schema_class_name
  - field_count
  - is_nested (boolean)

python_marshmallow_fields:
  - file, line, schema_class_name, field_name
  - field_type (String, Integer, Nested, etc)
  - required, allow_none
  - validators (JSON list)
```

**Security Impact:** HIGH - Validation = sanitizer detection

---

### 4. Celery Tasks (Background Jobs)
**Node Equivalent:** Bull queues, background workers
**Missing:**
- @app.task decorators
- Task names and signatures
- Task chains/groups (workflow)
- Rate limits, retries

**Tables Needed:**
```python
python_celery_tasks:
  - file, line, task_name
  - is_bound (boolean)
  - retry_policy (JSON)
  - rate_limit
  - queue_name
```

**Security Impact:** MEDIUM - Async execution = taint flow tracking, injection risks

---

### 5. Django REST Framework (DRF) Serializers
**Node Equivalent:** Express JSON validation, FastAPI Pydantic models
**Missing:**
- Serializer classes (like Pydantic but DRF-specific)
- Nested serializers
- Read-only/write-only fields
- Validation methods

**Tables Needed:**
```python
python_drf_serializers:
  - file, line, serializer_class_name
  - is_model_serializer (boolean)
  - model_name
  - read_only_fields (JSON list)
  - write_only_fields (JSON list)

python_drf_serializer_fields:
  - file, line, serializer_class_name, field_name
  - field_type
  - required, allow_null
  - source (if different from field_name)
```

**Security Impact:** HIGH - API input validation

---

## TIER 2: FRAMEWORK AWARENESS GAPS (Medium Priority)

### 6. Django Middleware
**Node Equivalent:** Express middleware stack
**Missing:**
- Custom middleware classes
- Middleware order/priority
- process_request/process_response hooks

**Tables Needed:**
```python
python_django_middleware:
  - file, line, middleware_class_name
  - has_process_request, has_process_response
  - has_process_exception
```

---

### 7. Django Admin Customization
**Node Equivalent:** Admin panel patterns
**Missing:**
- ModelAdmin classes
- Custom actions
- Inlines
- list_display, list_filter, search_fields

**Tables Needed:**
```python
python_django_admin:
  - file, line, admin_class_name
  - model_name
  - list_display (JSON list)
  - readonly_fields (JSON list)
  - has_custom_actions (boolean)
```

---

### 8. Flask Extensions (More Patterns)
**Node Equivalent:** Express plugins/middleware
**Missing:**
- @app.errorhandler decorators
- @app.before_request / @app.after_request
- Flask-Login (@login_required locations)
- Flask-WTF form handling

**Tables Needed:**
```python
python_flask_hooks:
  - file, line, hook_type (before_request, after_request, errorhandler)
  - status_code (for errorhandler)
  - function_name

python_flask_login:
  - file, line, decorator_type (login_required, fresh_login_required)
  - view_function_name
```

---

### 9. FastAPI Advanced Patterns
**Node Equivalent:** NestJS dependency injection
**Missing:**
- Background tasks (@app.on_event, BackgroundTasks)
- WebSocket routes
- More comprehensive dependency injection
- Response model validation

**Tables Needed:**
```python
python_fastapi_background_tasks:
  - file, line, task_function_name
  - trigger_route

python_fastapi_websockets:
  - file, line, pattern, handler_function
```

---

### 10. Template Injection Points
**Node Equivalent:** JSX/Vue template analysis
**Missing:**
- Jinja2 template variables ({{ user_input }})
- Django template tags ({{ request.GET.foo }})
- Template inheritance tracking
- Custom filters/tags

**Tables Needed:**
```python
python_template_variables:
  - template_file, line, variable_expr
  - is_user_controlled (heuristic)
  - has_safe_filter (boolean)

python_template_tags:
  - template_file, line, tag_name
  - is_custom (boolean)
```

**Security Impact:** HIGH - Template injection (XSS/SSTI)

---

## TIER 3: COVERAGE PARITY (Lower Priority)

### 11. Click CLI Commands
**Node Equivalent:** Commander.js
**Missing:**
- @click.command decorators
- @click.option / @click.argument
- Command groups

**Tables Needed:**
```python
python_click_commands:
  - file, line, command_name
  - options (JSON list)
  - arguments (JSON list)
```

---

### 12. Attrs/Dataclasses Validators
**Node Equivalent:** Class-validator decorators
**Missing:**
- @dataclass field validators
- attrs validators

---

### 13. Other Validation Frameworks
**Missing:**
- Cerberus schemas
- Voluptuous schemas
- WTForms (overlap with Django forms)

---

### 14. Other Web Frameworks
**Missing:**
- Tornado handlers
- Sanic routes
- Quart (async Flask)
- Starlette middleware

---

## RECOMMENDED IMPLEMENTATION ORDER

**Phase 2.3A: Django Deep Dive (2-3 sessions)**
1. Django CBVs (python_django_views)
2. Django Forms (python_django_forms, python_django_form_fields)
3. Django Admin (python_django_admin)
Priority: These are EVERYWHERE in Django codebases

**Phase 2.3B: Validation Frameworks (2 sessions)**
1. Marshmallow schemas (python_marshmallow_schemas, python_marshmallow_fields)
2. DRF serializers (python_drf_serializers, python_drf_serializer_fields)
Priority: Direct sanitizer detection for taint analysis

**Phase 2.3C: Background Tasks & Async (1 session)**
1. Celery tasks (python_celery_tasks)
2. FastAPI background tasks (python_fastapi_background_tasks)
Priority: Async taint flow tracking

**Phase 2.3D: Template Engines (2 sessions)**
1. Jinja2 template analysis (python_template_variables)
2. Django template analysis
Priority: XSS/SSTI detection

**Phase 2.3E: Middleware & Hooks (1 session)**
1. Django middleware (python_django_middleware)
2. Flask hooks (python_flask_hooks, python_flask_login)
Priority: Auth bypass detection

---

## METRICS (After Full Coverage)

**Current Python Tables:** 19 (5 original + 14 Phase 2.2)
**Target Python Tables:** ~40-45 (matching Node.js breadth)

**Estimated Work:**
- Phase 2.3A-E: ~10-12 sessions
- ~15-20 new tables
- ~8,000-10,000 lines of extraction code
- ~5,000-8,000 lines of test fixtures

**Parity Goal:**
- JavaScript: 28 specialized functions, 4,649 lines
- Python: Currently 32 functions, ~5,600 lines
- Target: ~50-60 functions, ~10,000-12,000 lines (50-60% parity with broader ecosystem coverage)

---

## PRIORITY MATRIX (Security Impact × Usage Frequency)

```
HIGH IMPACT + HIGH FREQUENCY:
  1. Django Forms (input validation)
  2. Django CBVs (auth checks)
  3. DRF Serializers (API validation)
  4. Marshmallow schemas (validation)

HIGH IMPACT + MEDIUM FREQUENCY:
  5. Template variables (XSS/SSTI)
  6. Celery tasks (async injection)
  7. Django middleware (auth bypass)

MEDIUM IMPACT + HIGH FREQUENCY:
  8. Django Admin (mass assignment)
  9. Flask hooks (request lifecycle)
  10. FastAPI background tasks

LOW IMPACT + ANY FREQUENCY:
  - Click commands (mostly internal tools)
  - Attrs validators (less common)
  - Other web frameworks (niche)
```

---

## NEXT STEPS

Recommendation: Start with **Phase 2.3A: Django Deep Dive**
- Django is used in ~40% of Python web projects
- CBVs + Forms = massive security surface area
- Missing auth decorators on CBVs = critical vulnerability class
- Forms = immediate sanitizer detection for taint analysis

This mirrors how Node.js coverage prioritized Express/React/Vue (most common frameworks) over niche frameworks.
