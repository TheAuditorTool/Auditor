"""Cross-file taint flow test fixture for Python.

This fixture demonstrates multi-hop taint propagation:
  User Input (controller) → Business Logic (service) → Database Sink (database)

Expected Taint Path:
  1. controller.py: user_input = request.args.get('query')
  2. service.py: search_service.search(user_input)
  3. database.py: cursor.execute(query)

This tests:
  - callee_file_path resolution across files
  - Stage 3 interprocedural analysis
  - Path reconstruction through multiple hops
"""
