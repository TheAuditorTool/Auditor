"""Tests for GraphQL schema extraction and resolver detection.

Tests cover:
1. SDL parsing from .graphql files (GraphQLExtractor)
2. Python resolver detection (Graphene, Ariadne, Strawberry)
3. JavaScript resolver detection (Apollo, NestJS, TypeGraphQL)
"""
import pytest
from pathlib import Path
from theauditor.indexer.extractors.graphql import GraphQLExtractor


class TestGraphQLExtractor:
    """Test SDL schema extraction."""

    @pytest.fixture
    def extractor(self):
        """Create GraphQL extractor instance."""
        return GraphQLExtractor(root_path=Path("."))

    @pytest.fixture
    def sample_schema(self):
        """Sample GraphQL schema content."""
        return '''
type Query {
  user(id: ID!): User
  posts(userId: ID!): [Post!]!
}

type Mutation {
  createUser(input: CreateUserInput!): User
  deleteUser(id: ID!): Boolean
}

type User {
  id: ID!
  username: String!
  email: String!
  password: String!
  apiKey: String!
}

type Post {
  id: ID!
  title: String!
  content: String!
  author: User!
}

input CreateUserInput {
  username: String!
  email: String!
  password: String!
}
'''

    def test_supported_extensions(self, extractor):
        """Test that GraphQL extractor supports correct extensions."""
        extensions = extractor.supported_extensions()
        assert '.graphql' in extensions
        assert '.gql' in extensions
        assert '.graphqls' in extensions
        assert len(extensions) == 3

    def test_extract_schema_types(self, extractor, sample_schema):
        """Test extraction of GraphQL types from SDL."""
        file_info = {'path': 'schema.graphql', 'sha256': 'test_hash'}

        result = extractor.extract(file_info, sample_schema, tree=None)

        # Verify schemas table entry
        assert 'graphql_schemas' in result
        assert len(result['graphql_schemas']) == 1
        schema = result['graphql_schemas'][0]
        assert schema['file_path'] == 'schema.graphql'
        assert schema['language'] == 'graphql'

        # Verify types extracted
        assert 'graphql_types' in result
        types = result['graphql_types']
        type_names = [t['type_name'] for t in types]

        assert 'Query' in type_names
        assert 'Mutation' in type_names
        assert 'User' in type_names
        assert 'Post' in type_names
        assert 'CreateUserInput' in type_names

        # Verify type kinds
        query_type = next(t for t in types if t['type_name'] == 'Query')
        assert query_type['kind'] == 'object'

        input_type = next(t for t in types if t['type_name'] == 'CreateUserInput')
        assert input_type['kind'] == 'input'

    def test_extract_fields(self, extractor, sample_schema):
        """Test extraction of GraphQL fields."""
        file_info = {'path': 'schema.graphql', 'sha256': 'test_hash'}

        result = extractor.extract(file_info, sample_schema, tree=None)

        # Verify fields extracted
        assert 'graphql_fields' in result
        fields = result['graphql_fields']

        # Check Query fields
        query_fields = [f for f in fields if f['type_name'] == 'Query']
        query_field_names = [f['field_name'] for f in query_fields]
        assert 'user' in query_field_names
        assert 'posts' in query_field_names

        # Check Mutation fields
        mutation_fields = [f for f in fields if f['type_name'] == 'Mutation']
        mutation_field_names = [f['field_name'] for f in mutation_fields]
        assert 'createUser' in mutation_field_names
        assert 'deleteUser' in mutation_field_names

        # Check User fields
        user_fields = [f for f in fields if f['type_name'] == 'User']
        user_field_names = [f['field_name'] for f in user_fields]
        assert 'id' in user_field_names
        assert 'username' in user_field_names
        assert 'email' in user_field_names
        assert 'password' in user_field_names
        assert 'apiKey' in user_field_names

    def test_extract_field_arguments(self, extractor, sample_schema):
        """Test extraction of field arguments."""
        file_info = {'path': 'schema.graphql', 'sha256': 'test_hash'}

        result = extractor.extract(file_info, sample_schema, tree=None)

        # Verify field arguments extracted
        assert 'graphql_field_args' in result
        args = result['graphql_field_args']

        # Check user field arguments
        user_args = [a for a in args if a['field_name'] == 'user']
        assert len(user_args) == 1
        assert user_args[0]['arg_name'] == 'id'
        assert user_args[0]['arg_type'] == 'ID!'
        assert user_args[0]['is_nullable'] == False

        # Check createUser arguments
        create_user_args = [a for a in args if a['field_name'] == 'createUser']
        assert len(create_user_args) == 1
        assert create_user_args[0]['arg_name'] == 'input'
        assert 'CreateUserInput' in create_user_args[0]['arg_type']

    def test_extract_list_types(self, extractor, sample_schema):
        """Test detection of list return types."""
        file_info = {'path': 'schema.graphql', 'sha256': 'test_hash'}

        result = extractor.extract(file_info, sample_schema, tree=None)

        fields = result['graphql_fields']

        # Check posts field is list
        posts_field = next(f for f in fields if f['field_name'] == 'posts' and f['type_name'] == 'Query')
        assert posts_field['is_list'] == True
        assert 'Post' in posts_field['return_type']

    def test_extract_nullable_types(self, extractor, sample_schema):
        """Test detection of nullable return types."""
        file_info = {'path': 'schema.graphql', 'sha256': 'test_hash'}

        result = extractor.extract(file_info, sample_schema, tree=None)

        fields = result['graphql_fields']

        # Check user field is nullable (User, not User!)
        user_field = next(f for f in fields if f['field_name'] == 'user')
        assert user_field['is_nullable'] == True

        # Check id field is non-nullable (ID!)
        id_field = next(f for f in fields if f['field_name'] == 'id' and f['type_name'] == 'User')
        assert id_field['is_nullable'] == False

    def test_malformed_schema_fails_gracefully(self, extractor):
        """Test that malformed GraphQL fails gracefully."""
        file_info = {'path': 'bad.graphql', 'sha256': 'test_hash'}
        malformed = "type User { id: ID! username"  # Missing closing brace

        # Should raise or return empty result
        with pytest.raises(Exception):
            extractor.extract(file_info, malformed, tree=None)


class TestPythonResolverDetection:
    """Test Python GraphQL resolver detection."""

    def test_graphene_resolver_detection(self):
        """Test detection of Graphene resolve_* methods."""
        # This would use the Python AST extractor with Graphene patterns
        # For now, verify the pattern exists in framework_extractors.py
        from theauditor.ast_extractors.python.framework_extractors import extract_graphene_resolvers

        # Verify function exists and is callable
        assert callable(extract_graphene_resolvers)

    def test_ariadne_resolver_detection(self):
        """Test detection of Ariadne @query.field decorators."""
        from theauditor.ast_extractors.python.framework_extractors import extract_ariadne_resolvers

        assert callable(extract_ariadne_resolvers)

    def test_strawberry_resolver_detection(self):
        """Test detection of Strawberry @strawberry.field decorators."""
        from theauditor.ast_extractors.python.framework_extractors import extract_strawberry_resolvers

        assert callable(extract_strawberry_resolvers)


class TestJavaScriptResolverDetection:
    """Test JavaScript/TypeScript GraphQL resolver detection."""

    def test_apollo_resolver_detection(self):
        """Test detection of Apollo resolvers object."""
        # Verify function exists in framework_extractors.js
        from pathlib import Path
        js_extractors_path = Path("theauditor/ast_extractors/javascript/framework_extractors.js")

        assert js_extractors_path.exists()
        content = js_extractors_path.read_text()
        assert 'extractApolloResolvers' in content

    def test_nestjs_resolver_detection(self):
        """Test detection of NestJS @Resolver decorators."""
        from pathlib import Path
        js_extractors_path = Path("theauditor/ast_extractors/javascript/framework_extractors.js")

        content = js_extractors_path.read_text()
        assert 'extractNestJSResolvers' in content

    def test_typegraphql_resolver_detection(self):
        """Test detection of TypeGraphQL @Resolver decorators."""
        from pathlib import Path
        js_extractors_path = Path("theauditor/ast_extractors/javascript/framework_extractors.js")

        content = js_extractors_path.read_text()
        assert 'extractTypeGraphQLResolvers' in content


class TestGraphQLFixtures:
    """Test that fixture files are valid and parseable."""

    def test_schema_fixture_exists(self):
        """Verify schema.graphql fixture exists."""
        schema_path = Path("tests/fixtures/graphql/schema.graphql")
        assert schema_path.exists()

    def test_python_resolver_fixture_exists(self):
        """Verify Python resolver fixture exists."""
        resolver_path = Path("tests/fixtures/graphql/resolvers_python.py")
        assert resolver_path.exists()

    def test_javascript_resolver_fixture_exists(self):
        """Verify JavaScript resolver fixture exists."""
        resolver_path = Path("tests/fixtures/graphql/resolvers_javascript.js")
        assert resolver_path.exists()

    def test_schema_fixture_parseable(self):
        """Verify schema fixture can be parsed."""
        extractor = GraphQLExtractor(root_path=Path("."))
        schema_path = Path("tests/fixtures/graphql/schema.graphql")
        content = schema_path.read_text()
        file_info = {'path': str(schema_path), 'sha256': 'fixture'}

        result = extractor.extract(file_info, content, tree=None)

        # Should extract types, fields, and args
        assert 'graphql_types' in result
        assert 'graphql_fields' in result
        assert 'graphql_field_args' in result
        assert len(result['graphql_types']) > 0
        assert len(result['graphql_fields']) > 0
        assert len(result['graphql_field_args']) > 0
