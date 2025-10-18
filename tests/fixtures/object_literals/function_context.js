// Test 14: Global scope
const globalHandlers = { create: createGlobal };

// Test 15: Inside function
function setupRoutes() {
    const localHandlers = {
        create: createLocal,
        update: updateLocal
    };
    return localHandlers;
}

// Test 16: Inside arrow function
const init = () => {
    const arrowHandlers = { delete: deleteArrow };
    return arrowHandlers;
};

// Test 17: Inside class method
class Controller {
    setupActions() {
        const methodHandlers = {
            submit: submitAction,
            cancel: cancelAction
        };
        return methodHandlers;
    }
}
