# Phase 2.3 Plan - Iterative Focused Work Blocks

**Strategy:** Do 3-4 focused sessions on one area, mark complete, then cycle to another area. Avoid jumping between unrelated tasks.

---

## BLOCK 1: Django Framework Deep Dive (3-4 Sessions)

**Why First:**
- Highest security impact (auth bypass, input validation)
- Most common framework in Python web apps (~40% market share)
- Direct parity with Express/React coverage in Node.js

### Session 12: Django Class-Based Views (CBVs)
**Extractors to Build:**
1. `extract_django_cbvs()` in framework_extractors.py
   - Detect ListView, DetailView, CreateView, UpdateView, DeleteView
   - Extract get_queryset() overrides (SQL injection surface)
   - Check for permission_required decorators on dispatch()
   - Extract http_method_names restrictions

**Database Schema:**
```python
PYTHON_DJANGO_VIEWS = TableSchema(
    name="python_django_views",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("view_class_name", "TEXT", nullable=False),
        Column("view_type", "TEXT", nullable=False),  # ListView, DetailView, etc
        Column("model_name", "TEXT"),
        Column("template_name", "TEXT"),
        Column("has_permission_check", "BOOLEAN", default="0"),
        Column("http_method_names", "TEXT"),  # JSON list
        Column("has_get_queryset_override", "BOOLEAN", default="0"),
    ],
)
```

**Test Fixture:**
- Create `realworld_project/views/article_views.py` with 8-10 CBV examples
- Cover all view types, permission checks, queryset overrides

**Verification:**
- Extract >= 8 CBV records
- Verify model_name resolution
- Verify permission check detection

**Estimated:** 1 session

---

### Session 13: Django Forms & Validation
**Extractors to Build:**
1. `extract_django_forms()` in framework_extractors.py
   - Form class detection
   - ModelForm association
   - Field count
2. `extract_django_form_fields()` in framework_extractors.py
   - Field definitions (CharField, EmailField, etc)
   - required/optional detection
   - Custom validators (clean_<field>, clean())

**Database Schema:**
```python
PYTHON_DJANGO_FORMS = TableSchema(
    name="python_django_forms",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("form_class_name", "TEXT", nullable=False),
        Column("is_model_form", "BOOLEAN", default="0"),
        Column("model_name", "TEXT"),
        Column("field_count", "INTEGER", default="0"),
        Column("has_custom_clean", "BOOLEAN", default="0"),
    ],
)

PYTHON_DJANGO_FORM_FIELDS = TableSchema(
    name="python_django_form_fields",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("form_class_name", "TEXT", nullable=False),
        Column("field_name", "TEXT", nullable=False),
        Column("field_type", "TEXT", nullable=False),  # CharField, EmailField, etc
        Column("required", "BOOLEAN", default="1"),
        Column("max_length", "INTEGER"),
        Column("has_custom_validator", "BOOLEAN", default="0"),
    ],
)
```

**Test Fixture:**
- Create `realworld_project/forms/article_forms.py`
- 5-6 Form classes (both Form and ModelForm)
- 20-30 field definitions with validators

**Verification:**
- Extract >= 5 form classes
- Extract >= 20 form fields
- Verify ModelForm model_name resolution
- Verify custom validator detection

**Estimated:** 1 session

---

### Session 14: Django Admin Customization
**Extractors to Build:**
1. `extract_django_admin()` in framework_extractors.py
   - ModelAdmin class detection
   - list_display, list_filter, search_fields
   - readonly_fields detection
   - Custom actions

**Database Schema:**
```python
PYTHON_DJANGO_ADMIN = TableSchema(
    name="python_django_admin",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("admin_class_name", "TEXT", nullable=False),
        Column("model_name", "TEXT", nullable=False),
        Column("list_display", "TEXT"),  # JSON list
        Column("list_filter", "TEXT"),  # JSON list
        Column("search_fields", "TEXT"),  # JSON list
        Column("readonly_fields", "TEXT"),  # JSON list
        Column("has_custom_actions", "BOOLEAN", default="0"),
    ],
)
```

**Test Fixture:**
- Create `realworld_project/admin.py`
- 3-4 ModelAdmin classes with various customizations

**Verification:**
- Extract >= 3 admin classes
- Verify list_display/list_filter extraction
- Verify model_name resolution

**Estimated:** 1 session

---

### Session 15: Django Middleware (Optional - if time)
**Extractors to Build:**
1. `extract_django_middleware()` in framework_extractors.py
   - Middleware class detection
   - process_request/process_response hooks
   - process_exception detection

**Database Schema:**
```python
PYTHON_DJANGO_MIDDLEWARE = TableSchema(
    name="python_django_middleware",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("middleware_class_name", "TEXT", nullable=False),
        Column("has_process_request", "BOOLEAN", default="0"),
        Column("has_process_response", "BOOLEAN", default="0"),
        Column("has_process_exception", "BOOLEAN", default="0"),
        Column("has_process_view", "BOOLEAN", default="0"),
    ],
)
```

**Test Fixture:**
- Create `realworld_project/middleware/auth_middleware.py`
- 2-3 middleware classes

**Verification:**
- Extract >= 2 middleware classes

**Estimated:** 1 session (optional)

---

## BLOCK 1 DELIVERABLES:

**New Tables:** 3-4 (django_views, django_forms, django_form_fields, django_admin, +middleware)
**New Extractors:** 4-5 functions
**Code Added:** ~1,500-2,000 lines (extractors + schema + integration)
**Test Fixtures:** ~800-1,200 lines
**Records Extracted:** Estimate 50-100+ records from realworld_project

**Mark Complete in OpenSpec:** Update proposal.md + tasks.md when Block 1 done

---

## BLOCK 2: Validation Frameworks (2-3 Sessions) - AFTER BLOCK 1

**Focus:** Marshmallow, DRF Serializers
- Marshmallow schema extraction
- DRF serializer extraction (high priority for REST APIs)
- Field-level validation rules

**Deliverables:** 4 new tables, 3-4 extractors

---

## BLOCK 3: Background Tasks & Templates (2-3 Sessions) - AFTER BLOCK 2

**Focus:** Celery, Jinja2/Django templates
- Celery task extraction
- Template variable extraction (XSS/SSTI detection)

**Deliverables:** 3-4 new tables, 3-4 extractors

---

## BLOCK 4: Flask Extensions (1-2 Sessions) - AFTER BLOCK 3

**Focus:** Flask-Login, Flask-WTF, error handlers
- @login_required decorator tracking
- @app.before_request/@app.after_request
- @app.errorhandler

**Deliverables:** 2-3 new tables, 2-3 extractors

---

## ITERATION CYCLE:

1. **Do Block 1** (Django) - 3-4 focused sessions → Mark complete
2. **Do Block 2** (Validation) - 2-3 focused sessions → Mark complete
3. **Do Block 3** (Background/Templates) - 2-3 focused sessions → Mark complete
4. **Do Block 4** (Flask) - 1-2 focused sessions → Mark complete
5. **Review & Iterate** - Go back, add missing patterns, enhance existing extractors

**Total Estimated:** 10-15 sessions to complete all 4 blocks

---

## GUIDING PRINCIPLES:

✅ **DO:** Work in focused 3-4 session blocks on ONE framework/area
✅ **DO:** Complete extraction, schema, integration, testing for that block
✅ **DO:** Mark tasks complete in OpenSpec before moving to next block
✅ **DO:** Build comprehensive test fixtures as you go

❌ **DON'T:** Jump between unrelated tasks (5 min validation, 5 min framework)
❌ **DON'T:** Leave work half-done before switching areas
❌ **DON'T:** Build extractors without test fixtures + verification

---

## NEXT ACTION:

Start **Block 1, Session 12: Django CBVs** - build extract_django_cbvs(), schema, test fixture, verify extraction.
