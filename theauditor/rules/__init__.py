"""TheAuditor AST-based rule definitions.

Rules are discovered by the orchestrator via METADATA in individual files.
This __init__.py provides the package structure only.

Rule categories:
- auth/: Authentication rules (JWT, OAuth, password, session)
- bash/: Shell script security (injection, quoting, dangerous patterns)
- dependency/: Dependency analysis (ghost deps, typosquatting, etc.)
- deployment/: Infrastructure (AWS CDK, Docker, nginx, compose)
- frameworks/: Framework-specific (Express, FastAPI, Flask, Next.js, React, Vue)
- github_actions/: CI/CD security (script injection, permissions, etc.)
- go/: Go-specific (concurrency, crypto, error handling, injection)
- graphql/: GraphQL security (injection, auth, query depth)
- logic/: General logic analysis
- node/: Node.js runtime issues
- orm/: ORM security (Prisma, Sequelize, TypeORM)
- performance/: Performance analysis
- python/: Python-specific (crypto, deserialization, injection)
- quality/: Code quality (dead code)
- react/: React-specific (hooks, state, render)
- rust/: Rust safety (panic paths, unsafe, memory, FFI)
- secrets/: Hardcoded secrets detection
- security/: General security (CORS, crypto, input validation, etc.)
- sql/: SQL security (injection, multi-tenant, safety)
- terraform/: IaC security
- typescript/: TypeScript type safety
- vue/: Vue-specific (reactivity, lifecycle, state)
- xss/: XSS detection (DOM, template, framework-specific)
"""
