# TheAuditor Project Roadmap

TheAuditor's mission is to provide an incorruptible source of ground truth for AI-assisted development. This roadmap outlines our vision for evolving the platform while maintaining our commitment to verifiable, uninterpreted data that both developers and AI assistants can trust.

## Guiding Principles

All future development must adhere to these architectural rules:

* **Never Interpret Truth**: TheAuditor preserves raw, verifiable data from industry-standard tools. We orchestrate and structure, but never summarize or interpret the core evidence.
* **AI-First Output**: All new reports and findings must be structured for LLM consumption, with outputs chunked to fit context windows and formatted for machine parsing.
* **Industry-Standard Tooling**: We prioritize integrating battle-tested, widely-adopted tools over building custom analyzers. The community trusts ESLint, Ruff, and similar tools—we leverage that trust.
* **Offline-First Operation**: All analysis must run without network access, ensuring data privacy and reproducible results.
* **Sandboxed Execution**: Analysis tools remain isolated from project dependencies to prevent cross-contamination and ensure consistent results.

## Development Priorities

### Tier 1: Core Engine Enhancements (Maintained by TheAuditorTool)

These are our primary focus areas where we will lead development:

* **Improve & Expand Existing Components**: Enhance current extractors (Python, JavaScript/TypeScript), expand pattern coverage beyond basic regex, add more AST-based rules for deeper semantic analysis, and improve parser accuracy for configuration files
* **Performance Improvements**: Optimize analysis speed for large codebases, improve parallel processing, and reduce memory footprint during graph analysis
* **Deeper Taint Analysis**: Enhance data-flow tracking to detect more complex injection patterns, improve inter-procedural analysis, and add support for asynchronous code flows
* **Advanced Pattern Detection**: Expand YAML-based rule engine capabilities, add support for semantic patterns beyond regex, and improve cross-file correlation
* **Improved AI Output Formatting**: Optimize chunk generation for newer LLM context windows, add structured output formats (JSON-LD), and enhance evidence presentation
* ** Overall optimize FCE (Factual correlation engine) to dare venture into bit more "actionable grouping intelligence behaviour". Its a tricky one without falling into endless error mapping, guessing or interpretation...

### Tier 2: Expanding Coverage (Community Contributions Welcome)

We actively seek community expertise to expand TheAuditor's capabilities in these areas:

* **GraphQL Support**: Add comprehensive GraphQL schema analysis, query complexity detection, and authorization pattern verification

* **Framework-Specific Rules** (Currently Limited to Basic Regex Patterns):
  
  **Note**: We currently have very basic framework detection(Outside python/node ecosystem) and minimal framework-specific patterns. Most are simple regex patterns in `/patterns` with no real AST-based rules in `/rules`. The architecture supports expansion, but substantial work is needed:

  * Django: Enhanced ORM analysis, middleware security patterns, template injection detection
  * Ruby on Rails: ActiveRecord anti-patterns, authentication bypass detection, mass assignment vulnerabilities
  * Angular: Dependency injection issues, template security, change detection problems
  * Laravel: Eloquent ORM patterns, blade template security, middleware analysis
  * Spring Boot: Bean configuration issues, security annotations, JPA query analysis
  * Next.js: Server-side rendering security, API route protection, data fetching patterns
  * FastAPI: Pydantic validation gaps, dependency injection security, async patterns
  * Express.js: Middleware ordering issues, CORS misconfigurations, session handling

* **Language Support Expansion** (Top 10 Languages Outside Python/Node Ecosystem):

  **Current State**: Full support for Python and JavaScript/TypeScript only. The modular architecture supports adding new languages via extractors, but each requires significant implementation effort:

  1. **Java**: JVM bytecode analysis, Spring/Spring Boot integration, Maven/Gradle dependency scanning, Android-specific patterns
  2. **C#**: .NET CLR analysis, ASP.NET Core patterns, Entity Framework queries, NuGet vulnerability scanning
  3. **Go**: Goroutine leak detection, error handling patterns, module security analysis, interface compliance
  4. **Rust**: Unsafe block analysis, lifetime/borrow checker integration, cargo dependency scanning, memory safety patterns
  5. **PHP**: Composer dependency analysis, Laravel/Symfony patterns, SQL injection detection, legacy code patterns
  6. **Ruby**: Gem vulnerability scanning, Rails-specific patterns, metaprogramming analysis, DSL parsing
  7. **Swift**: iOS security patterns, memory management issues, Objective-C interop, CocoaPods scanning
  8. **Kotlin**: Coroutine analysis, null safety violations, Android-specific patterns, Gradle integration
  9. **C/C++**: Memory safety issues, buffer overflow detection, undefined behavior patterns, CMake/Make analysis
  10. **Scala**: Akka actor patterns, implicit resolution issues, SBT dependency analysis, functional pattern detection

### Tier 3: Docs sync ###

Its a nightmare keeping track of everything and "AI compilations" never reflect the actual code, its surface level guessing, at best :(

## Conclusion

TheAuditor's strength lies in its unwavering commitment to ground truth. Whether you're interested in performance optimization, security analysis, or framework support, we welcome contributions that align with our core principles.

Join the discussion on [GitHub Issues](https://github.com/TheAuditorTool/Auditor/issues) to share ideas, report bugs, or propose enhancements. Ready to contribute? See our [CONTRIBUTING.md](CONTRIBUTING.md) for detailed setup instructions and development guidelines.

