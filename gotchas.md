What You Missed (The "Gotchas")

    The checker Dependency in Extraction:

        In EXTRACTION.md, you plan to fix Sink Aliasing (const run = exec). This requires TypeScript's TypeChecker.

        Risk: If main.ts creates the Program with transpileOnly: true or similar speed optimizations, the TypeChecker might be weak or unavailable.

        Fix: Add a check in main.ts to ensure program.getTypeChecker() is fully instantiated before passing it to extractors.

    The "Ghost Node" Problem in Graph:

        In GRAPH.md, you enforce "Strict Resolution" (no more fuzzy matching).

        Risk: Real-world code is messy. If routes.ts imports UserController from a path you failed to resolve (e.g., a weird webpack alias), strict resolution returns null. The edge is dead.

        Fix: Implement "Ghost Nodes." If strict resolution fails, create a node of type="ghost" with the import path. This keeps the graph connected even if the file is missing.


Did You Miss Anything? (Gap Analysis)

Your plans are 98% complete. Here are the 2% edge cases to add:

    In EXTRACTION.md: You mentioned fixing path mismatches, but be explicit about Windows vs. POSIX paths.

        Add: Ensure main.ts normalizes all paths to forward slashes (/) before sending them to Python. The "Split-Brain" often happens because TS sends C:\Users\... and Python expects src/....

    In GRAPH.md: You listed "Ghost Nodes" for Express.

        Add: "Ghost Nodes" for Imports. If javascript_resolvers.py fails to find a file, it currently drops the edge. It should instead create an unresolved_module node so you can see which imports are breaking.

1. Assessment: Are these plans good?

Yes. They are technically accurate and address the root causes rather than just the symptoms.

    system.md (The Enabler): Correctly identifies that you cannot fix the logic if the engine runs out of RAM. Switching from "Batch" to "Streaming" is the only way to scale to 50k+ files.

    EXTRACTION.md (The Source): correctly flags the ast: null "Headless Bug" as the primary data loss vector. Fixing this enables the Python layer to actually see the code.

    STORAGE.md (The Vault): The "Negative ID" bug finding is a critical catch. This explains why your Control Flow Graphs (CFG) were detached—blocks were being saved with ID -1.

    GRAPH.md (The Connector): Moving to create_bidirectional_edges is the exact fix needed for the IFDS Analyzer to walk backward.

    TAINT.md (The Brain): The success metrics (zero "unknown" types, <5% max depth hits) are perfect for validating the fix.

2. Did you miss anything?

You covered 95% of the issues. Here are the 3 missing details you should add to ensure success:

    The "Schema Lock" (Crucial for Parallelization):

        Gap: EXTRACTION.md changes what main.ts outputs, and STORAGE.md changes how node_storage.py saves it. If these two drift apart during development, you will have a schema mismatch.

        Fix: Define the JSON contract between main.ts and node_storage.py before starting work.

    The "Ghost" Cleanup:

        Gap: EXTRACTION.md mentions typescript_impl.py is "dead weight". You need an explicit task to delete this file and remove the fallback logic from javascript.py. If you leave it, it might silently activate in the future and re-corrupt your data.

    The "Virtual File" Mapping:

        Gap: While EXTRACTION.md mentions "Path Hell", ensure you explicitly map Vue "virtual" paths (e.g., /virtual_vue/123.ts) back to their source files (Component.vue) in the final output JSON. If you don't, the graph will show files that don't exist on disk.