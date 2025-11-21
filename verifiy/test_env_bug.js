// Minimal reproduction case for env var duplicate bug
console.log('TEST:', process.env.TEST_VAR ? `Found (${process.env.TEST_VAR.length} chars)` : 'NOT SET');
