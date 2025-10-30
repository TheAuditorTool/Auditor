"""Service layer - business logic that propagates taint."""

from .database import Database


class SearchService:
    """Service that receives tainted data from controller and passes to database.

    This demonstrates multi-hop taint propagation:
      controller.py (source) → service.py (propagation) → database.py (sink)
    """

    def __init__(self):
        self.db = Database()

    def search(self, query: str):
        """
        TAINT PROPAGATION: query parameter is tainted from controller

        Expected flow:
          query (tainted) → self.db.execute_search(query) → [cross-file to database.py]
        """
        # Propagate tainted data to database layer
        results = self.db.execute_search(query)
        return results

    def get_user_by_id(self, user_id: str):
        """
        TAINT PROPAGATION: user_id is tainted from controller

        Expected flow:
          user_id (tainted) → self.db.get_user(user_id) → [cross-file to database.py]
        """
        # Propagate tainted data to database layer
        user = self.db.get_user(user_id)
        return user

    def filter_records(self, filter_expression: str):
        """
        TAINT PROPAGATION: filter_expression is tainted from controller

        Expected flow:
          filter_expression (tainted) → self.db.dynamic_query(filter_expression) → [cross-file to database.py]
        """
        # Propagate tainted data to database layer
        records = self.db.dynamic_query(filter_expression)
        return records

    def process_batch(self, items: list):
        """
        TAINT PROPAGATION: items list contains tainted data

        Expected flow:
          items (tainted) → self.db.batch_insert(items) → [cross-file to database.py]
        """
        # Batch processing that propagates taint
        for item in items:
            self.db.batch_insert(item)
