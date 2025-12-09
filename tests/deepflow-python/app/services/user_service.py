"""User service - HOP 3: Business logic layer.

Receives tainted data from routes and passes to processors.
"""

from app.processors.data_transformer import DataTransformer


class UserService:
    """User business logic service.

    HOP 3: Receives tainted query from routes, passes to processors.
    No sanitization occurs at this layer.
    """

    def __init__(self):
        self.transformer = DataTransformer()

    async def search(self, query: str) -> dict:
        """Search for users by query string.

        HOP 3: Service layer passes tainted query to processor.

        Args:
            query: TAINTED user input from request.query_params

        Returns:
            Search results from database
        """
        # Pass tainted query to transformer (HOP 4)
        transformed = self.transformer.prepare_search(query)
        return transformed

    async def get_by_id(self, user_id: str) -> dict:
        """Get user by ID.

        Args:
            user_id: TAINTED user input from path parameter
        """
        return self.transformer.prepare_lookup(user_id)
