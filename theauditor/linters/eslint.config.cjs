const globals = require("globals");
const js = require("@eslint/js");
const typescript = require("@typescript-eslint/eslint-plugin");
const typescriptParser = require("@typescript-eslint/parser");
const react = require("eslint-plugin-react");
const reactHooks = require("eslint-plugin-react-hooks");

module.exports = [
  js.configs.recommended,

  {
    ignores: [
      "**/node_modules/**",
      "**/dist/**",
      "**/build/**",
      "**/.auditor_venv/**",
    ],
  },

  {
    files: [
      "**/*.config.js",
      "**/*.config.ts",
      "**/scripts/**/*.js",
      "**/migrations/**/*.js",
      "**/seeders/**/*.js",
      "**/database-cli.js",
    ],

    languageOptions: {
      sourceType: "commonjs",
      ecmaVersion: 2020,
      globals: {
        ...globals.node,
      },
    },

    rules: {
      "@typescript-eslint/no-var-requires": "off",
      "no-undef": "error",
    },
  },

  {
    files: [
      "**/frontend/src/**/*.js",
      "**/frontend/src/**/*.jsx",
      "**/frontend/src/**/*.ts",
      "**/frontend/src/**/*.tsx",
    ],

    languageOptions: {
      parser: typescriptParser,
      parserOptions: {
        ecmaVersion: 2020,
        sourceType: "module",
        ecmaFeatures: {
          jsx: true,
        },
      },
      globals: {
        ...globals.browser,
      },
    },

    plugins: {
      "@typescript-eslint": typescript,
      react: react,
      "react-hooks": reactHooks,
    },

    rules: {
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/explicit-function-return-type": "warn",
      "@typescript-eslint/no-unused-vars": "error",

      "no-console": "warn",
      "no-debugger": "error",
      "no-eval": "error",
      "no-implied-eval": "error",
      "no-var": "error",
      "prefer-const": "error",

      "react/prop-types": "off",
      "react/react-in-jsx-scope": "off",
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
    },

    settings: {
      react: {
        version: "detect",
      },
    },
  },

  {
    files: ["**/backend/src/**/*.js", "**/backend/src/**/*.ts"],
    ignores: [
      "**/backend/src/config/**",
      "**/backend/src/scripts/**",
      "**/backend/src/migrations/**",
      "**/backend/src/seeders/**",
    ],

    languageOptions: {
      parser: typescriptParser,
      parserOptions: {
        ecmaVersion: 2020,
        sourceType: "module",
      },
      globals: {
        ...globals.node,
      },
    },

    plugins: {
      "@typescript-eslint": typescript,
    },

    rules: {
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/explicit-function-return-type": "warn",
      "@typescript-eslint/no-unused-vars": "error",

      "no-console": "warn",
      "no-debugger": "error",
      "no-var": "error",
      "prefer-const": "error",
    },
  },
];
