const methods = {
  async fetch() {
    return data;
  },
  generator() {
    return 1;
  },
  getValue() {
    return this._value;
  },
  setValue(v) {
    this._value = v;
  },
};

const base = { x: 1, y: 2 };
const extended = {
  ...base,
  z: 3,
  handler: handleExtended,
};

const key = "dynamicKey";
const computed = {
  [key]: value,
  ["literal"]: literalValue,
  normalKey: normalValue,
};

const strings = {
  message: "Hello, world!",
  list: "a, b, c",
  handler: processString,
};

const empty = {};

let mutableHandlers;
mutableHandlers = {
  add: addHandler,
  remove: removeHandler,
};
