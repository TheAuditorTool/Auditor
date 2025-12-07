// The "Poisoned Reference" Challenge
function infect(objRef) {
    // 3. Mutating the object via a reference passed as an argument
    // Most engines lose track here because they don't map 'objRef' back to 'A' in the caller's heap scope.
    objRef.data = process.env.MALICIOUS_INPUT;
}

function sink(data) {
    // Dangerous sink - SQL injection, command injection, etc.
    console.log("Executing with: " + data);
}

function main() {
    // 1. Create a clean object
    let A = { data: "safe" };

    // 2. Create an alias (B points to A)
    let B = A;

    // 4. Pass the ALIAS (B) to the infector
    infect(B);

    // 5. The Sink uses the ORIGINAL reference (A)
    // A naive engine sees: A was defined as "safe", never reassigned. It misses the side-effect on the heap.
    sink(A.data);
}

main();
