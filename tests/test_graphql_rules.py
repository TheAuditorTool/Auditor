"""Tests for GraphQL security rules.

Tests cover:
1. mutation_auth - Detects mutations without authentication
2. query_depth - Detects nested query DoS risks
3. input_validation - Detects missing input validation
4. sensitive_fields - Detects exposed sensitive data
"""
import pytest
import sqlite3
import tempfile
import json
from pathlib import Path
from theauditor.indexer.database import DatabaseManager
from theauditor.rules.base import StandardRuleContext
from theauditor.rules.graphql.mutation_auth import check_mutation_auth
from theauditor.rules.graphql.query_depth import check_query_depth
from theauditor.rules.graphql.input_validation import check_input_validation
from theauditor.rules.graphql.sensitive_fields import check_sensitive_fields


class TestMutationAuthRule:
    """Test mutation authentication rule."""

    @pytest.fixture
    def db_with_mutations(self):
        """Create database with sample mutations."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        manager = DatabaseManager(db_path)
        manager.create_tables()

        # Add Mutation type
        mutation_type_id = manager.add_graphql_type(
            schema_path='schema.graphql',
            type_name='Mutation',
            kind='object',
            implements=None,
            description=None,
            line=10
        )

        # Add unprotected mutation
        unprotected_field_id = manager.add_graphql_field(
            type_id=mutation_type_id,
            field_name='deleteUser',
            return_type='Boolean',
            is_list=False,
            is_nullable=False,
            directives_json=None,  # NO @auth directive
            description=None,
            line=15
        )

        # Add protected mutation
        protected_field_id = manager.add_graphql_field(
            type_id=mutation_type_id,
            field_name='updateProfile',
            return_type='User',
            is_list=False,
            is_nullable=False,
            directives_json=json.dumps([{"name": "@auth", "args": {}}]),  # HAS @auth
            description=None,
            line=20
        )

        manager.commit()
        manager.close()

        yield db_path

        Path(db_path).unlink(missing_ok=True)

    def test_detects_unprotected_mutation(self, db_with_mutations):
        """Test detection of mutation without auth."""
        context = StandardRuleContext(
            file_path=Path('schema.graphql'),
            db_path=db_with_mutations
        )

        findings = check_mutation_auth(context)

        # Should find deleteUser as unprotected
        assert len(findings) > 0
        assert any('deleteUser' in f.message for f in findings)

    def test_ignores_protected_mutation(self, db_with_mutations):
        """Test that protected mutations are not flagged."""
        context = StandardRuleContext(
            file_path=Path('schema.graphql'),
            db_path=db_with_mutations
        )

        findings = check_mutation_auth(context)

        # Should NOT flag updateProfile (has @auth)
        assert not any('updateProfile' in f.message for f in findings)

    def test_finding_severity(self, db_with_mutations):
        """Test that findings have correct severity."""
        context = StandardRuleContext(
            file_path=Path('schema.graphql'),
            db_path=db_with_mutations
        )

        findings = check_mutation_auth(context)

        if findings:
            assert findings[0].severity.value == 'high'
            assert findings[0].cwe_id == 'CWE-306'


class TestQueryDepthRule:
    """Test query depth rule."""

    @pytest.fixture
    def db_with_nested_queries(self):
        """Create database with nested query potential."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        manager = DatabaseManager(db_path)
        manager.create_tables()

        # Add User type with list field
        user_type_id = manager.add_graphql_type(
            schema_path='schema.graphql',
            type_name='User',
            kind='object',
            implements=None,
            description=None,
            line=10
        )

        # Add posts field (list of Post)
        posts_field_id = manager.add_graphql_field(
            type_id=user_type_id,
            field_name='posts',
            return_type='[Post!]!',
            is_list=True,
            is_nullable=False,
            directives_json=None,
            description=None,
            line=15
        )

        # Add Post type with list field
        post_type_id = manager.add_graphql_type(
            schema_path='schema.graphql',
            type_name='Post',
            kind='object',
            implements=None,
            description=None,
            line=20
        )

        # Add comments field (list of Comment) - double nesting!
        comments_field_id = manager.add_graphql_field(
            type_id=post_type_id,
            field_name='comments',
            return_type='[Comment!]!',
            is_list=True,
            is_nullable=False,
            directives_json=None,
            description=None,
            line=25
        )

        manager.commit()
        manager.close()

        yield db_path

        Path(db_path).unlink(missing_ok=True)

    def test_detects_nested_list_queries(self, db_with_nested_queries):
        """Test detection of nested list queries (DoS risk)."""
        context = StandardRuleContext(
            file_path=Path('schema.graphql'),
            db_path=db_with_nested_queries
        )

        findings = check_query_depth(context)

        # Should detect User.posts (returns Post with nested list)
        assert len(findings) > 0
        assert any('posts' in f.message for f in findings)


class TestInputValidationRule:
    """Test input validation rule."""

    @pytest.fixture
    def db_with_mutations(self):
        """Create database with mutation arguments."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        manager = DatabaseManager(db_path)
        manager.create_tables()

        # Add Mutation type
        mutation_type_id = manager.add_graphql_type(
            schema_path='schema.graphql',
            type_name='Mutation',
            kind='object',
            implements=None,
            description=None,
            line=10
        )

        # Add searchPosts mutation
        search_field_id = manager.add_graphql_field(
            type_id=mutation_type_id,
            field_name='searchPosts',
            return_type='[Post!]!',
            is_list=True,
            is_nullable=False,
            directives_json=None,
            description=None,
            line=15
        )

        # Add keyword argument WITHOUT validation
        manager.add_graphql_field_arg(
            field_id=search_field_id,
            arg_name='keyword',
            arg_type='String',
            is_nullable=True,  # Nullable and no validation!
            default_value=None,
            directives_json=None  # NO @constraint/@validate
        )

        manager.commit()
        manager.close()

        yield db_path

        Path(db_path).unlink(missing_ok=True)

    def test_detects_missing_validation(self, db_with_mutations):
        """Test detection of arguments without validation."""
        context = StandardRuleContext(
            file_path=Path('schema.graphql'),
            db_path=db_with_mutations
        )

        findings = check_input_validation(context)

        # Should detect keyword argument missing validation
        assert len(findings) > 0
        assert any('keyword' in f.message for f in findings)


class TestSensitiveFieldsRule:
    """Test sensitive fields detection rule."""

    @pytest.fixture
    def db_with_sensitive_fields(self):
        """Create database with sensitive field names."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        manager = DatabaseManager(db_path)
        manager.create_tables()

        # Add User type
        user_type_id = manager.add_graphql_type(
            schema_path='schema.graphql',
            type_name='User',
            kind='object',
            implements=None,
            description=None,
            line=10
        )

        # Add password field (SENSITIVE, no protection)
        password_field_id = manager.add_graphql_field(
            type_id=user_type_id,
            field_name='password',
            return_type='String!',
            is_list=False,
            is_nullable=False,
            directives_json=None,  # NO @private directive
            description=None,
            line=15
        )

        # Add apiKey field (SENSITIVE, no protection)
        apikey_field_id = manager.add_graphql_field(
            type_id=user_type_id,
            field_name='apiKey',
            return_type='String!',
            is_list=False,
            is_nullable=False,
            directives_json=None,  # NO @private directive
            description=None,
            line=16
        )

        # Add username field (NOT sensitive, should be ignored)
        username_field_id = manager.add_graphql_field(
            type_id=user_type_id,
            field_name='username',
            return_type='String!',
            is_list=False,
            is_nullable=False,
            directives_json=None,
            description=None,
            line=17
        )

        manager.commit()
        manager.close()

        yield db_path

        Path(db_path).unlink(missing_ok=True)

    def test_detects_password_field(self, db_with_sensitive_fields):
        """Test detection of exposed password field."""
        context = StandardRuleContext(
            file_path=Path('schema.graphql'),
            db_path=db_with_sensitive_fields
        )

        findings = check_sensitive_fields(context)

        # Should detect password field
        assert len(findings) > 0
        assert any('password' in f.message.lower() for f in findings)

    def test_detects_api_key_field(self, db_with_sensitive_fields):
        """Test detection of exposed API key field."""
        context = StandardRuleContext(
            file_path=Path('schema.graphql'),
            db_path=db_with_sensitive_fields
        )

        findings = check_sensitive_fields(context)

        # Should detect apiKey field
        assert any('apikey' in f.message.lower() or 'api_key' in f.message.lower() for f in findings)

    def test_ignores_non_sensitive_fields(self, db_with_sensitive_fields):
        """Test that non-sensitive fields are not flagged."""
        context = StandardRuleContext(
            file_path=Path('schema.graphql'),
            db_path=db_with_sensitive_fields
        )

        findings = check_sensitive_fields(context)

        # Should NOT flag username
        assert not any('username' in f.message.lower() and 'password' not in f.message.lower() for f in findings)

    def test_finding_has_cwe(self, db_with_sensitive_fields):
        """Test that findings have correct CWE classification."""
        context = StandardRuleContext(
            file_path=Path('schema.graphql'),
            db_path=db_with_sensitive_fields
        )

        findings = check_sensitive_fields(context)

        if findings:
            assert findings[0].cwe_id == 'CWE-200'
            assert findings[0].severity.value == 'high'


class TestGraphQLRulesIntegration:
    """Integration tests for GraphQL rules."""

    def test_all_rules_have_metadata(self):
        """Verify all rules define METADATA."""
        from theauditor.rules.graphql import mutation_auth, query_depth, input_validation, sensitive_fields

        assert hasattr(mutation_auth, 'METADATA')
        assert hasattr(query_depth, 'METADATA')
        assert hasattr(input_validation, 'METADATA')
        assert hasattr(sensitive_fields, 'METADATA')

    def test_all_rules_have_check_function(self):
        """Verify all rules have callable check functions."""
        assert callable(check_mutation_auth)
        assert callable(check_query_depth)
        assert callable(check_input_validation)
        assert callable(check_sensitive_fields)

    def test_rules_use_database_scope(self):
        """Verify all rules use database execution scope."""
        from theauditor.rules.graphql import mutation_auth, query_depth, input_validation, sensitive_fields

        assert mutation_auth.METADATA.execution_scope == 'database'
        assert query_depth.METADATA.execution_scope == 'database'
        assert input_validation.METADATA.execution_scope == 'database'
        assert sensitive_fields.METADATA.execution_scope == 'database'
