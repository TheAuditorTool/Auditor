// ESLint v9 Flat Config Format
const globals = require('globals');
const js = require('@eslint/js');
const typescript = require('@typescript-eslint/eslint-plugin');
const typescriptParser = require('@typescript-eslint/parser');
const react = require('eslint-plugin-react');
const reactHooks = require('eslint-plugin-react-hooks');

module.exports = [
  // Base configuration
  js.configs.recommended,
  
  // Global ignores
  {
    ignores: ['**/node_modules/**', '**/dist/**', '**/build/**', '**/.auditor_venv/**']
  },
  
  // Configuration for CommonJS files (configs, scripts, migrations)
  {
    files: [
      '**/*.config.js',
      '**/*.config.ts', 
      '**/scripts/**/*.js',
      '**/migrations/**/*.js',
      '**/seeders/**/*.js',
      '**/database-cli.js'
    ],
    languageOptions: {
      sourceType: 'commonjs',
      ecmaVersion: 2020,
      globals: {
        ...globals.node, // Adds Node.js globals like 'module', 'require', '__dirname'
      }
    },
    rules: {
      '@typescript-eslint/no-var-requires': 'off', // Allow require() in CJS files
      'no-undef': 'error'
    }
  },
  
  // Configuration for FRONTEND (browser) source code
  {
    files: ['**/frontend/src/**/*.js', '**/frontend/src/**/*.jsx', '**/frontend/src/**/*.ts', '**/frontend/src/**/*.tsx'],
    languageOptions: {
      parser: typescriptParser,
      parserOptions: {
        ecmaVersion: 2020,
        sourceType: 'module',
        ecmaFeatures: {
          jsx: true
        }
      },
      globals: {
        ...globals.browser, // Browser globals
      }
    },
    plugins: {
      '@typescript-eslint': typescript,
      'react': react,
      'react-hooks': reactHooks
    },
    rules: {
      // TypeScript rules
      '@typescript-eslint/no-explicit-any': 'error',
      '@typescript-eslint/explicit-function-return-type': 'warn',
      '@typescript-eslint/no-unused-vars': 'error',
      
      // General rules
      'no-console': 'warn',
      'no-debugger': 'error',
      'no-eval': 'error',
      'no-implied-eval': 'error',
      'no-var': 'error',
      'prefer-const': 'error',
      
      // React rules
      'react/prop-types': 'off',
      'react/react-in-jsx-scope': 'off',
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn'
    },
    settings: {
      react: {
        version: 'detect'
      }
    }
  },
  
  // Configuration for BACKEND (Node.js) source code
  {
    files: ['**/backend/src/**/*.js', '**/backend/src/**/*.ts'],
    ignores: ['**/backend/src/config/**', '**/backend/src/scripts/**', '**/backend/src/migrations/**', '**/backend/src/seeders/**'],
    languageOptions: {
      parser: typescriptParser,
      parserOptions: {
        ecmaVersion: 2020,
        sourceType: 'module'
      },
      globals: {
        ...globals.node, // Node.js globals (process, __dirname, etc.)
      }
    },
    plugins: {
      '@typescript-eslint': typescript
    },
    rules: {
      // TypeScript rules
      '@typescript-eslint/no-explicit-any': 'error',
      '@typescript-eslint/explicit-function-return-type': 'warn',
      '@typescript-eslint/no-unused-vars': 'error',
      
      // General rules
      'no-console': 'warn',
      'no-debugger': 'error',
      'no-var': 'error',
      'prefer-const': 'error'
    }
  }
];