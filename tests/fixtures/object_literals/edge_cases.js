// Test 8: ES6 method definitions
const methods = {
    async fetch() { return data; },
    generator() { return 1; },
    getValue() { return this._value; },
    setValue(v) { this._value = v; }
};

// Test 9: Spread operators
const base = { x: 1, y: 2 };
const extended = {
    ...base,
    z: 3,
    handler: handleExtended
};

// Test 10: Computed property names
const key = 'dynamicKey';
const computed = {
    [key]: value,
    ['literal']: literalValue,
    normalKey: normalValue
};

// Test 11: String literals with commas (edge case test)
const strings = {
    message: "Hello, world!",
    list: "a, b, c",
    handler: processString
};

// Test 12: Empty object
const empty = {};

// Test 13: Assignment expression (not declaration)
let mutableHandlers;
mutableHandlers = {
    add: addHandler,
    remove: removeHandler
};
