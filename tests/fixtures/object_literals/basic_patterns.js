// Test 1: Simple function references
const handlers = {
    create: handleCreate,
    update: handleUpdate,
    delete: handleDelete
};

// Test 2: Shorthand properties
const actions = {
    handleClick,
    handleSubmit,
    handleCancel
};

// Test 3: Mixed literals and references
const config = {
    timeout: 5000,
    retry: true,
    maxRetries: 3,
    handler: processRequest,
    fallback: null
};

// Test 4: Arrow functions
const processors = {
    validate: (data) => data.length > 0,
    transform: (x) => x * 2,
    cleanup: () => {}
};

// Test 5: Function expressions
const legacy = {
    process: function(data) { return data; },
    validate: function() {}
};
