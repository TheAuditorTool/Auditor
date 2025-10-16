This will be a new openspec proposal. Read graph.md in root. I have drafted a quick start for you to investigate independently yourself. We are not reinventing the wheel, we are adding a feature/addition/enhancement. We still avoid regex/string/heuristics like the cancer it is. Openspec proposals are always light and incomplete to me so please read teamsop.md and combine the two methods specially the prime directives and verifications and all the rules, never guess, never assume, always read the code, the answer and truth is always in the code... And also add your own additions and enhancements to the plan below. Be persistent and professional, there is no timer on you or rush to get it done. Get it right...Always look how we already do things, we consistent, keep to the modular architecture.

Assistant, your new task is to fully implement the graph analysis feature using the `networkx` library. The documentation currently promises this functionality, but the code is missing the implementation. Your job is to make the tool's capabilities match its documentation.

### **Objective** 🎯

Integrate the `networkx` library into the graph analyzer to build the project's dependency graph. You will implement robust cycle detection and hotspot identification, replacing any placeholder or non-functional code.

### **Why it Matters**

  * **Correctness**: This fixes a major discrepancy between our documentation and the tool's actual features, ensuring we deliver what we promise.
  * **Efficiency**: We will leverage a powerful, highly-optimized library instead of attempting to write complex graph algorithms from scratch.
  * **Capability**: This will unlock the architectural analysis capabilities described in `ARCHITECTURE.md`, allowing us to find critical design flaws like circular dependencies.

-----

### **Step-by-Step Guidance**

#### **Step 1: Add the Dependency**

First, declare `networkx` as an optional dependency.

1.  Navigate to the project's dependency file (this is likely `pyproject.toml` or `setup.py`).
2.  Find the section for `[project.optional-dependencies]` or `extras_require`.
3.  Add `networkx` to the `all` group. This will ensure that when a user runs `pip install -e ".[all]"`, the library is installed correctly.

-----

#### **Step 2: Refactor the Graph Analyzer**

Now, you will modify the core analysis module to use NetworkX.

1.  Open the graph analyzer module, located at `theauditor/graph/analyzer.py`.

2.  Add the necessary import at the top of the file:

    ```python
    import networkx as nx
    import sqlite3
    ```

3.  Implement the primary analysis function. It should connect to the database, build the graph, run the analyses, and return the structured results.

    ```python
    def analyze_graph(db_path: str) -> dict:
        """
        Builds a dependency graph from the database and analyzes it for
        architectural issues like cycles and hotspots.

        Args:
            db_path: Path to the repo_index.db SQLite database.

        Returns:
            A dictionary containing lists of cycles and hotspots.
        """
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 1. Build the Graph from the 'refs' table.
        # A DiGraph (Directed Graph) is essential for finding import direction.
        graph = nx.DiGraph()
        cursor.execute("SELECT src, value FROM refs")
        for importer, imported_item in cursor.fetchall():
            graph.add_edge(importer, imported_item)
        
        conn.close()

        # 2. Implement Cycle Detection.
        # nx.simple_cycles() is a powerful generator that does all the work.
        try:
            cycles = list(nx.simple_cycles(graph))
        except Exception:
            # Handle potential errors if the graph has issues.
            cycles = []

        # 3. Implement Hotspot Identification.
        # Degree centrality measures how connected a node is.
        # A high degree indicates a "hotspot" or a potential "god object".
        if graph.nodes:
            centrality = nx.degree_centrality(graph)
            # Sort by centrality score, descending, to find the top 10.
            sorted_hotspots = sorted(centrality.items(), key=lambda item: item[1], reverse=True)
            hotspots = sorted_hotspots[:10]
        else:
            hotspots = []

        # 4. Return the structured findings.
        return {
            "cycles": cycles,
            "hotspots": hotspots
        }
    ```


4. Modify Project Dependencies: Locate your pyproject.toml or setup.py file. In the section defining optional dependencies (extras), add networkx to the [all] group. This will ensure pip install -e ".[all]" installs the required package. 
5.  Ensure that the `aud graph analyze` command calls this new `analyze_graph` function and correctly processes its output to generate the final report.

----

You're likely right. Given your tool's sophisticated architecture, it's very possible you already have a custom algorithm in place that detects circular dependencies. Many linters that TheAuditor orchestrates can also flag this issue.

The recommendation to use `networkx` isn't just about adding cycle detection; it's about **upgrading and centralizing** your entire graph analysis capability into a single, powerful, and extensible engine.

---
### ## The Strategic Advantage of NetworkX

Think of it as replacing a custom-built component with an industry-standard, high-performance engine.

* **Performance at Scale** 🚀: While a custom cycle detector works, `networkx` algorithms are highly optimized and often implemented in C. As you analyze larger repositories, `networkx` will be significantly faster and more memory-efficient.
* **A Foundation for Deeper Insights**: The real power is what you can do *after* you find cycles. Once your dependency map exists as a `networkx` graph object, you unlock a massive library of advanced graph theory algorithms with one-line function calls, including:
    * **Advanced Hotspot Analysis**: Go beyond simple connection counts to find architecturally critical files using metrics like "betweenness centrality."
    * **Shortest Path Analysis**: Power your `impact` command by finding the shortest dependency chain between two modules.
    * **Community Detection**: Automatically identify clusters of tightly-coupled modules that could be candidates for refactoring into separate services.

Adopting `networkx` isn't a redundant step. It's a strategic upgrade that makes your existing feature more robust and provides a solid foundation for making your architectural analysis capabilities best-in-class.