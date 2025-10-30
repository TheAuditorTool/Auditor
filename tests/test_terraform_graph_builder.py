"""Integration tests for Terraform graph builder.

Tests the TerraformGraphBuilder against an in-memory database populated with
the terraform fixture data. Validates nodes and edges are correctly built.
Follows the test plan from Phase 2B in terraaform_test.txt.
"""

import pytest
import sqlite3
import tempfile
from pathlib import Path
from theauditor.terraform.graph import TerraformGraphBuilder
from theauditor.indexer.extractors.terraform import TerraformExtractor
from theauditor.utils.ast_parser import ASTParser
from theauditor.database.manager import DatabaseManager


# Path to the fixture directory
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "terraform"


@pytest.fixture
def in_memory_db():
    """Create an in-memory SQLite database for testing."""
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    return conn


@pytest.fixture
def populated_db(in_memory_db):
    """Populate the in-memory database with terraform fixture data.

    This simulates what the indexer would do:
    1. Parse all .tf files in the fixture
    2. Extract data using TerraformExtractor
    3. Insert into database tables
    """
    conn = in_memory_db
    cursor = conn.cursor()

    # Create terraform_* tables
    # Note: Using simplified schema for testing - full schema should match DatabaseManager
    cursor.execute("""
        CREATE TABLE terraform_variables (
            variable_id TEXT PRIMARY KEY,
            file_path TEXT NOT NULL,
            variable_name TEXT NOT NULL,
            variable_type TEXT,
            default_json TEXT,
            is_sensitive INTEGER DEFAULT 0,
            description TEXT,
            line INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE terraform_resources (
            resource_id TEXT PRIMARY KEY,
            file_path TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            resource_name TEXT NOT NULL,
            properties_json TEXT,
            depends_on_json TEXT,
            sensitive_flags_json TEXT,
            has_public_exposure INTEGER DEFAULT 0,
            line INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE terraform_outputs (
            output_id TEXT PRIMARY KEY,
            file_path TEXT NOT NULL,
            output_name TEXT NOT NULL,
            value_json TEXT,
            is_sensitive INTEGER DEFAULT 0,
            description TEXT,
            line INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE terraform_files (
            file_path TEXT PRIMARY KEY,
            module_name TEXT,
            stack_name TEXT,
            backend_type TEXT,
            providers_json TEXT,
            is_module INTEGER DEFAULT 0,
            module_source TEXT
        )
    """)

    conn.commit()

    # TODO: Parse fixture files and populate database
    # For now, manually insert test data representing the fixture
    _insert_fixture_data(conn)

    return conn


def _insert_fixture_data(conn):
    """Insert minimal fixture data for testing graph builder.

    This is a simplified version - full implementation would parse all fixture files.
    """
    cursor = conn.cursor()

    # Insert variables from variables.tf
    cursor.execute("""
        INSERT INTO terraform_variables
        (variable_id, file_path, variable_name, variable_type, is_sensitive, line)
        VALUES
        (?, ?, ?, ?, ?, ?)
    """, (
        f"{FIXTURE_PATH}/variables.tf::db_password",
        str(FIXTURE_PATH / "variables.tf"),
        "db_password",
        "string",
        1,  # is_sensitive = true
        13
    ))

    cursor.execute("""
        INSERT INTO terraform_variables
        (variable_id, file_path, variable_name, variable_type, is_sensitive, line)
        VALUES
        (?, ?, ?, ?, ?, ?)
    """, (
        f"{FIXTURE_PATH}/variables.tf::app_name",
        str(FIXTURE_PATH / "variables.tf"),
        "app_name",
        "string",
        0,  # is_sensitive = false
        1
    ))

    # Insert resource from modules/rds_db/main.tf that uses db_password
    import json
    cursor.execute("""
        INSERT INTO terraform_resources
        (resource_id, file_path, resource_type, resource_name, properties_json, line)
        VALUES
        (?, ?, ?, ?, ?, ?)
    """, (
        f"{FIXTURE_PATH}/modules/rds_db/main.tf::aws_db_instance.default",
        str(FIXTURE_PATH / "modules" / "rds_db" / "main.tf"),
        "aws_db_instance",
        "default",
        json.dumps({"password": "var.db_password", "engine": "mysql"}),
        1
    ))

    # Insert resource from main.tf (aws_instance.web)
    cursor.execute("""
        INSERT INTO terraform_resources
        (resource_id, file_path, resource_type, resource_name, properties_json, depends_on_json, line)
        VALUES
        (?, ?, ?, ?, ?, ?, ?)
    """, (
        f"{FIXTURE_PATH}/main.tf::aws_instance.web",
        str(FIXTURE_PATH / "main.tf"),
        "aws_instance",
        "web",
        json.dumps({"ami": "data.aws_ami.amazon_linux.id", "instance_type": "t2.micro"}),
        json.dumps([]),
        27
    ))

    # Insert resource with explicit depends_on
    cursor.execute("""
        INSERT INTO terraform_resources
        (resource_id, file_path, resource_type, resource_name, properties_json, depends_on_json, line)
        VALUES
        (?, ?, ?, ?, ?, ?, ?)
    """, (
        f"{FIXTURE_PATH}/main.tf::null_resource.app_provisioner",
        str(FIXTURE_PATH / "main.tf"),
        "null_resource",
        "app_provisioner",
        json.dumps({}),
        json.dumps(["aws_instance.web"]),
        42
    ))

    # Insert aws_s3_bucket.public_read (security violation)
    cursor.execute("""
        INSERT INTO terraform_resources
        (resource_id, file_path, resource_type, resource_name, properties_json, has_public_exposure, line)
        VALUES
        (?, ?, ?, ?, ?, ?, ?)
    """, (
        f"{FIXTURE_PATH}/security_violations/public_s3.tf::aws_s3_bucket.public_read",
        str(FIXTURE_PATH / "security_violations" / "public_s3.tf"),
        "aws_s3_bucket",
        "public_read",
        json.dumps({"acl": "public-read"}),
        1,  # has_public_exposure = true
        1
    ))

    # Insert outputs
    cursor.execute("""
        INSERT INTO terraform_outputs
        (output_id, file_path, output_name, value_json, is_sensitive, line)
        VALUES
        (?, ?, ?, ?, ?, ?)
    """, (
        f"{FIXTURE_PATH}/outputs.tf::web_instance_id",
        str(FIXTURE_PATH / "outputs.tf"),
        "web_instance_id",
        json.dumps("aws_instance.web.id"),
        0,  # is_sensitive = false
        1
    ))

    cursor.execute("""
        INSERT INTO terraform_outputs
        (output_id, file_path, output_name, value_json, is_sensitive, line)
        VALUES
        (?, ?, ?, ?, ?, ?)
    """, (
        f"{FIXTURE_PATH}/outputs.tf::app_name_passthrough",
        str(FIXTURE_PATH / "outputs.tf"),
        "app_name_passthrough",
        json.dumps("var.app_name"),
        0,  # is_sensitive = false
        11
    ))

    # Insert sensitive output violation (exposes db_password without marking sensitive)
    cursor.execute("""
        INSERT INTO terraform_outputs
        (output_id, file_path, output_name, value_json, is_sensitive, line)
        VALUES
        (?, ?, ?, ?, ?, ?)
    """, (
        f"{FIXTURE_PATH}/security_violations/sensitive_output.tf::database_password",
        str(FIXTURE_PATH / "security_violations" / "sensitive_output.tf"),
        "database_password",
        json.dumps("var.db_password"),
        0,  # is_sensitive = false - THIS IS THE VIOLATION!
        4
    ))

    conn.commit()


class TestGraphBuilderInitialization:
    """Test TerraformGraphBuilder initialization."""

    def test_init_with_missing_db(self):
        """Test that init fails with clear error if database doesn't exist."""
        with pytest.raises(FileNotFoundError, match="Database not found"):
            TerraformGraphBuilder(db_path="/nonexistent/path.db")


class TestNodeValidation:
    """Test that nodes are correctly loaded from database."""

    def test_variable_nodes_created(self, populated_db):
        """Test that variable nodes are created with correct attributes."""
        # Create temporary DB file for graph builder
        with tempfile.NamedTemporaryFile(mode='w', suffix='.db', delete=False) as f:
            temp_db_path = f.name

        try:
            # Copy in-memory db to temp file
            backup_conn = sqlite3.connect(temp_db_path)
            populated_db.backup(backup_conn)
            backup_conn.close()

            # Also create graphs.db in same directory
            graphs_db_path = str(Path(temp_db_path).parent / "graphs.db")

            # Build graph
            builder = TerraformGraphBuilder(db_path=temp_db_path)
            graph = builder.build_provisioning_flow_graph()

            # Verify nodes
            nodes = graph['nodes']
            node_ids = {node['id'] for node in nodes}

            # Should have db_password variable node
            db_password_node_id = f"{FIXTURE_PATH}/variables.tf::db_password"
            assert db_password_node_id in node_ids, "db_password variable node not found"

            # Find the node and check is_sensitive
            db_password_node = None
            for node in nodes:
                if node['id'] == db_password_node_id:
                    db_password_node = node
                    break

            assert db_password_node is not None
            assert db_password_node['is_sensitive'] is True, "db_password should be marked sensitive"
            assert db_password_node['node_type'] == 'variable'

        finally:
            # Cleanup
            import os
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)
            if os.path.exists(graphs_db_path):
                os.remove(graphs_db_path)

    def test_resource_nodes_created(self, populated_db):
        """Test that resource nodes are created with correct attributes."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.db', delete=False) as f:
            temp_db_path = f.name

        try:
            backup_conn = sqlite3.connect(temp_db_path)
            populated_db.backup(backup_conn)
            backup_conn.close()

            graphs_db_path = str(Path(temp_db_path).parent / "graphs.db")

            builder = TerraformGraphBuilder(db_path=temp_db_path)
            graph = builder.build_provisioning_flow_graph()

            nodes = graph['nodes']
            node_ids = {node['id'] for node in nodes}

            # Should have aws_instance.web resource node
            web_instance_node_id = f"{FIXTURE_PATH}/main.tf::aws_instance.web"
            assert web_instance_node_id in node_ids, "aws_instance.web node not found"

        finally:
            import os
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)
            if os.path.exists(graphs_db_path):
                os.remove(graphs_db_path)

    def test_public_exposure_flag(self, populated_db):
        """Test that has_public_exposure is correctly set on resource nodes."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.db', delete=False) as f:
            temp_db_path = f.name

        try:
            backup_conn = sqlite3.connect(temp_db_path)
            populated_db.backup(backup_conn)
            backup_conn.close()

            graphs_db_path = str(Path(temp_db_path).parent / "graphs.db")

            builder = TerraformGraphBuilder(db_path=temp_db_path)
            graph = builder.build_provisioning_flow_graph()

            nodes = graph['nodes']

            # Find public S3 bucket node
            public_s3_node_id = f"{FIXTURE_PATH}/security_violations/public_s3.tf::aws_s3_bucket.public_read"
            public_s3_node = None
            for node in nodes:
                if node['id'] == public_s3_node_id:
                    public_s3_node = node
                    break

            assert public_s3_node is not None, "Public S3 bucket node not found"
            assert public_s3_node['has_public_exposure'] is True, "Public S3 bucket should have has_public_exposure=True"

        finally:
            import os
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)
            if os.path.exists(graphs_db_path):
                os.remove(graphs_db_path)


class TestEdgeValidation:
    """Test that edges (data flow relationships) are correctly built."""

    def test_variable_to_resource_edge(self, populated_db):
        """Test edge from var.db_password to resource.aws_db_instance.default."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.db', delete=False) as f:
            temp_db_path = f.name

        try:
            backup_conn = sqlite3.connect(temp_db_path)
            populated_db.backup(backup_conn)
            backup_conn.close()

            graphs_db_path = str(Path(temp_db_path).parent / "graphs.db")

            builder = TerraformGraphBuilder(db_path=temp_db_path)
            graph = builder.build_provisioning_flow_graph()

            edges = graph['edges']

            # Find edge from db_password variable to aws_db_instance resource
            var_id = f"{FIXTURE_PATH}/variables.tf::db_password"
            resource_id = f"{FIXTURE_PATH}/modules/rds_db/main.tf::aws_db_instance.default"

            edge_found = False
            for edge in edges:
                if edge['source'] == var_id and edge['target'] == resource_id:
                    edge_found = True
                    assert edge['edge_type'] == 'variable_reference'
                    assert 'db_password' in edge['expression']
                    break

            assert edge_found, f"Edge from {var_id} to {resource_id} not found"

        finally:
            import os
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)
            if os.path.exists(graphs_db_path):
                os.remove(graphs_db_path)

    def test_resource_to_output_edge(self, populated_db):
        """Test edge from resource.aws_instance.web to output.web_instance_id."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.db', delete=False) as f:
            temp_db_path = f.name

        try:
            backup_conn = sqlite3.connect(temp_db_path)
            populated_db.backup(backup_conn)
            backup_conn.close()

            graphs_db_path = str(Path(temp_db_path).parent / "graphs.db")

            builder = TerraformGraphBuilder(db_path=temp_db_path)
            graph = builder.build_provisioning_flow_graph()

            edges = graph['edges']

            # Find edge from aws_instance.web to output.web_instance_id
            resource_id = f"{FIXTURE_PATH}/main.tf::aws_instance.web"
            output_id = f"{FIXTURE_PATH}/outputs.tf::web_instance_id"

            edge_found = False
            for edge in edges:
                if edge['source'] == resource_id and edge['target'] == output_id:
                    edge_found = True
                    assert edge['edge_type'] == 'output_reference'
                    break

            assert edge_found, f"Edge from {resource_id} to {output_id} not found"

        finally:
            import os
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)
            if os.path.exists(graphs_db_path):
                os.remove(graphs_db_path)

    def test_variable_to_output_edge(self, populated_db):
        """Test edge from var.app_name to output.app_name_passthrough."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.db', delete=False) as f:
            temp_db_path = f.name

        try:
            backup_conn = sqlite3.connect(temp_db_path)
            populated_db.backup(backup_conn)
            backup_conn.close()

            graphs_db_path = str(Path(temp_db_path).parent / "graphs.db")

            builder = TerraformGraphBuilder(db_path=temp_db_path)
            graph = builder.build_provisioning_flow_graph()

            edges = graph['edges']

            # Find edge from var.app_name to output.app_name_passthrough
            var_id = f"{FIXTURE_PATH}/variables.tf::app_name"
            output_id = f"{FIXTURE_PATH}/outputs.tf::app_name_passthrough"

            edge_found = False
            for edge in edges:
                if edge['source'] == var_id and edge['target'] == output_id:
                    edge_found = True
                    assert edge['edge_type'] == 'output_reference'
                    break

            assert edge_found, f"Edge from {var_id} to {output_id} not found"

        finally:
            import os
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)
            if os.path.exists(graphs_db_path):
                os.remove(graphs_db_path)

    def test_explicit_depends_on_edge(self, populated_db):
        """Test edge with explicit depends_on (aws_instance.web -> null_resource.app_provisioner)."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.db', delete=False) as f:
            temp_db_path = f.name

        try:
            backup_conn = sqlite3.connect(temp_db_path)
            populated_db.backup(backup_conn)
            backup_conn.close()

            graphs_db_path = str(Path(temp_db_path).parent / "graphs.db")

            builder = TerraformGraphBuilder(db_path=temp_db_path)
            graph = builder.build_provisioning_flow_graph()

            edges = graph['edges']

            # Find edge from aws_instance.web to null_resource.app_provisioner
            source_id = f"{FIXTURE_PATH}/main.tf::aws_instance.web"
            target_id = f"{FIXTURE_PATH}/main.tf::null_resource.app_provisioner"

            edge_found = False
            for edge in edges:
                if edge['source'] == source_id and edge['target'] == target_id:
                    edge_found = True
                    assert edge['edge_type'] == 'resource_dependency'
                    assert edge['metadata'].get('explicit_depends_on') is True
                    break

            assert edge_found, f"Edge from {source_id} to {target_id} not found"

        finally:
            import os
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)
            if os.path.exists(graphs_db_path):
                os.remove(graphs_db_path)


class TestTaintFlowDetection:
    """Test that taint flow can be detected through the graph (sensitive variable -> output)."""

    def test_sensitive_var_to_output_taint_path(self, populated_db):
        """THE CRITICAL TEST: Detect taint path var.db_password -> output.database_password.

        This validates the entire graph and taint flow:
        1. sensitive.auto.tfvars sets var.db_password
        2. variables.tf marks var.db_password as sensitive = true
        3. sensitive_output.tf's output.database_password references var.db_password but is NOT marked sensitive
        4. The graph should show this edge exists, enabling taint tracking rules to flag it
        """
        with tempfile.NamedTemporaryFile(mode='w', suffix='.db', delete=False) as f:
            temp_db_path = f.name

        try:
            backup_conn = sqlite3.connect(temp_db_path)
            populated_db.backup(backup_conn)
            backup_conn.close()

            graphs_db_path = str(Path(temp_db_path).parent / "graphs.db")

            builder = TerraformGraphBuilder(db_path=temp_db_path)
            graph = builder.build_provisioning_flow_graph()

            edges = graph['edges']
            nodes = graph['nodes']

            # Find the sensitive variable node
            var_id = f"{FIXTURE_PATH}/variables.tf::db_password"
            var_node = None
            for node in nodes:
                if node['id'] == var_id:
                    var_node = node
                    break

            assert var_node is not None, "db_password variable not found"
            assert var_node['is_sensitive'] is True, "db_password should be marked sensitive"

            # Find the output node
            output_id = f"{FIXTURE_PATH}/security_violations/sensitive_output.tf::database_password"
            output_node = None
            for node in nodes:
                if node['id'] == output_id:
                    output_node = node
                    break

            assert output_node is not None, "database_password output not found"
            assert output_node['is_sensitive'] is False, "database_password output should NOT be marked sensitive (this is the violation)"

            # Find edge from sensitive var to unsecured output
            edge_found = False
            for edge in edges:
                if edge['source'] == var_id and edge['target'] == output_id:
                    edge_found = True
                    # This edge represents the taint flow that rules should detect
                    assert edge['edge_type'] == 'output_reference'
                    break

            assert edge_found, f"Taint edge from {var_id} to {output_id} not found - this is the critical security finding!"

        finally:
            import os
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)
            if os.path.exists(graphs_db_path):
                os.remove(graphs_db_path)


class TestModuleEdges:
    """Test module-related edges (currently FAILING - module support not implemented)."""

    @pytest.mark.skip(reason="Module edge detection not yet implemented")
    def test_module_output_to_resource_edge(self):
        """FAILING TEST: Detect edge module.networking -> resource.aws_instance.web.

        Due to module.networking.public_subnets[0] reference in aws_instance.web.
        """
        pass

    @pytest.mark.skip(reason="Module edge detection not yet implemented")
    def test_module_to_module_edge(self):
        """FAILING TEST: Detect edge module.networking -> module.database.

        Due to module.networking.private_subnets reference in module.database input.
        """
        pass
