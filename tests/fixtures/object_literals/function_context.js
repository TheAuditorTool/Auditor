const globalHandlers = { create: createGlobal };

function setupRoutes() {
  const localHandlers = {
    create: createLocal,
    update: updateLocal,
  };
  return localHandlers;
}

const init = () => {
  const arrowHandlers = { delete: deleteArrow };
  return arrowHandlers;
};

class Controller {
  setupActions() {
    const methodHandlers = {
      submit: submitAction,
      cancel: cancelAction,
    };
    return methodHandlers;
  }
}
