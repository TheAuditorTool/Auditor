-- Python Coverage V2 - Week 5: Control Flow Patterns
-- Add these tables to theauditor/indexer/schemas/python_schema.py

-- 1. For loops
CREATE TABLE IF NOT EXISTS python_for_loops (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    loop_type TEXT NOT NULL,  -- 'enumerate' | 'zip' | 'range' | 'items' | 'values' | 'keys' | 'plain'
    has_else BOOLEAN NOT NULL,
    nesting_level INTEGER NOT NULL,
    target_count INTEGER NOT NULL,
    in_function TEXT NOT NULL,
    PRIMARY KEY (file, line)
);

-- 2. While loops
CREATE TABLE IF NOT EXISTS python_while_loops (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    has_else BOOLEAN NOT NULL,
    is_infinite BOOLEAN NOT NULL,
    nesting_level INTEGER NOT NULL,
    in_function TEXT NOT NULL,
    PRIMARY KEY (file, line)
);

-- 3. Async for loops
CREATE TABLE IF NOT EXISTS python_async_for_loops (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    has_else BOOLEAN NOT NULL,
    target_count INTEGER NOT NULL,
    in_function TEXT NOT NULL,
    PRIMARY KEY (file, line)
);

-- 4. If statements
CREATE TABLE IF NOT EXISTS python_if_statements (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    has_elif BOOLEAN NOT NULL,
    has_else BOOLEAN NOT NULL,
    chain_length INTEGER NOT NULL,
    nesting_level INTEGER NOT NULL,
    has_complex_condition BOOLEAN NOT NULL,
    in_function TEXT NOT NULL,
    PRIMARY KEY (file, line)
);

-- 5. Match statements (Python 3.10+)
CREATE TABLE IF NOT EXISTS python_match_statements (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    case_count INTEGER NOT NULL,
    has_wildcard BOOLEAN NOT NULL,
    has_guards BOOLEAN NOT NULL,
    pattern_types TEXT NOT NULL,  -- Comma-separated
    in_function TEXT NOT NULL,
    PRIMARY KEY (file, line)
);

-- 6. Break/continue/pass statements
CREATE TABLE IF NOT EXISTS python_break_continue_pass (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    statement_type TEXT NOT NULL,  -- 'break' | 'continue' | 'pass'
    loop_type TEXT NOT NULL,  -- 'for' | 'while' | 'none'
    in_function TEXT NOT NULL,
    PRIMARY KEY (file, line)
);

-- 7. Assert statements
CREATE TABLE IF NOT EXISTS python_assert_statements (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    has_message BOOLEAN NOT NULL,
    condition_type TEXT NOT NULL,  -- 'comparison' | 'isinstance' | 'callable' | 'simple'
    in_function TEXT NOT NULL,
    PRIMARY KEY (file, line)
);

-- 8. Del statements
CREATE TABLE IF NOT EXISTS python_del_statements (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    target_type TEXT NOT NULL,  -- 'name' | 'subscript' | 'attribute'
    target_count INTEGER NOT NULL,
    in_function TEXT NOT NULL,
    PRIMARY KEY (file, line)
);

-- 9. Import statements (enhanced)
CREATE TABLE IF NOT EXISTS python_import_statements (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    import_type TEXT NOT NULL,  -- 'import' | 'from' | 'relative'
    module TEXT NOT NULL,
    has_alias BOOLEAN NOT NULL,
    is_wildcard BOOLEAN NOT NULL,
    relative_level INTEGER NOT NULL,
    imported_names TEXT NOT NULL,  -- Comma-separated
    in_function TEXT NOT NULL,
    PRIMARY KEY (file, line, module, imported_names)
);

-- 10. With statements
CREATE TABLE IF NOT EXISTS python_with_statements (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    is_async BOOLEAN NOT NULL,
    context_count INTEGER NOT NULL,
    has_alias BOOLEAN NOT NULL,
    in_function TEXT NOT NULL,
    PRIMARY KEY (file, line)
);

-- Python Coverage V2 - Week 6: Protocol Patterns

-- 11. Iterator protocol
CREATE TABLE IF NOT EXISTS python_iterator_protocol (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    class_name TEXT NOT NULL,
    has_iter BOOLEAN NOT NULL,
    has_next BOOLEAN NOT NULL,
    raises_stopiteration BOOLEAN NOT NULL,
    is_generator BOOLEAN NOT NULL,
    PRIMARY KEY (file, line, class_name)
);

-- 12. Container protocol
CREATE TABLE IF NOT EXISTS python_container_protocol (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    class_name TEXT NOT NULL,
    has_len BOOLEAN NOT NULL,
    has_getitem BOOLEAN NOT NULL,
    has_setitem BOOLEAN NOT NULL,
    has_delitem BOOLEAN NOT NULL,
    has_contains BOOLEAN NOT NULL,
    is_sequence BOOLEAN NOT NULL,
    is_mapping BOOLEAN NOT NULL,
    PRIMARY KEY (file, line, class_name)
);

-- 13. Callable protocol
CREATE TABLE IF NOT EXISTS python_callable_protocol (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    class_name TEXT NOT NULL,
    param_count INTEGER NOT NULL,
    has_args BOOLEAN NOT NULL,
    has_kwargs BOOLEAN NOT NULL,
    PRIMARY KEY (file, line, class_name)
);

-- 14. Comparison protocol
CREATE TABLE IF NOT EXISTS python_comparison_protocol (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    class_name TEXT NOT NULL,
    methods TEXT NOT NULL,  -- Comma-separated
    is_total_ordering BOOLEAN NOT NULL,
    has_all_rich BOOLEAN NOT NULL,
    PRIMARY KEY (file, line, class_name)
);

-- 15. Arithmetic protocol
CREATE TABLE IF NOT EXISTS python_arithmetic_protocol (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    class_name TEXT NOT NULL,
    methods TEXT NOT NULL,  -- Comma-separated
    has_reflected BOOLEAN NOT NULL,
    has_inplace BOOLEAN NOT NULL,
    PRIMARY KEY (file, line, class_name)
);

-- 16. Pickle protocol
CREATE TABLE IF NOT EXISTS python_pickle_protocol (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    class_name TEXT NOT NULL,
    has_getstate BOOLEAN NOT NULL,
    has_setstate BOOLEAN NOT NULL,
    has_reduce BOOLEAN NOT NULL,
    has_reduce_ex BOOLEAN NOT NULL,
    PRIMARY KEY (file, line, class_name)
);

-- 17. Weakref usage
CREATE TABLE IF NOT EXISTS python_weakref_usage (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    usage_type TEXT NOT NULL,  -- 'ref' | 'proxy' | 'WeakValueDictionary' | 'WeakKeyDictionary'
    in_function TEXT NOT NULL,
    PRIMARY KEY (file, line)
);

-- 18. Context variables usage
CREATE TABLE IF NOT EXISTS python_contextvar_usage (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    operation TEXT NOT NULL,  -- 'ContextVar' | 'get' | 'set' | 'Token'
    in_function TEXT NOT NULL,
    PRIMARY KEY (file, line)
);

-- 19. Module attributes
CREATE TABLE IF NOT EXISTS python_module_attributes (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    attribute TEXT NOT NULL,  -- '__name__' | '__file__' | '__doc__' | '__all__'
    usage_type TEXT NOT NULL,  -- 'read' | 'write' | 'check'
    in_function TEXT NOT NULL,
    PRIMARY KEY (file, line, attribute)
);

-- 20. Class decorators
CREATE TABLE IF NOT EXISTS python_class_decorators (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    class_name TEXT NOT NULL,
    decorator TEXT NOT NULL,
    decorator_type TEXT NOT NULL,  -- 'dataclass' | 'total_ordering' | 'custom'
    has_arguments BOOLEAN NOT NULL,
    PRIMARY KEY (file, line, class_name, decorator)
);
