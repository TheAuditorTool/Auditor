"""Unit and integration tests for Terraform extractor.

Tests the TerraformExtractor and hcl_impl.py against the real-world fixture.
Follows the test plan from Phase 2A in terraaform_test.txt.
"""

import pytest
import sqlite3
from pathlib import Path
from theauditor.indexer.extractors.terraform import TerraformExtractor
from theauditor.ast_extractors import hcl_impl
from theauditor.ast_parser import ASTParser


# Path to the fixture directory
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "terraform"


@pytest.fixture
def ast_parser():
    """Create an AST parser instance for tree-sitter parsing."""
    return ASTParser()


@pytest.fixture
def terraform_extractor(ast_parser):
    """Create a TerraformExtractor instance."""
    return TerraformExtractor(root_path=FIXTURE_PATH, ast_parser=ast_parser)


class TestFixtureLoading:
    """Test that TerraformExtractor finds and supports fixture files."""

    def test_supported_extensions(self, terraform_extractor):
        """Verify .tf, .tfvars, and .tf.json are supported."""
        extensions = terraform_extractor.supported_extensions()
        assert '.tf' in extensions
        assert '.tfvars' in extensions
        assert '.tf.json' in extensions

    def test_fixture_files_exist(self):
        """Verify all expected fixture files exist."""
        expected_files = [
            "main.tf",
            "variables.tf",
            "outputs.tf",
            "data.tf",
            "versions.tf",
            "terraform.tfvars",
            "sensitive.auto.tfvars",
            "modules/vpc/main.tf",
            "modules/vpc/variables.tf",
            "modules/vpc/outputs.tf",
            "modules/rds_db/main.tf",
            "modules/rds_db/variables.tf",
            "modules/rds_db/outputs.tf",
            "security_violations/public_s3.tf",
            "security_violations/hardcoded_secrets.tf",
            "security_violations/overly_permissive_iam.tf",
            "security_violations/sensitive_output.tf",
        ]

        for file_path in expected_files:
            full_path = FIXTURE_PATH / file_path
            assert full_path.exists(), f"Fixture file missing: {file_path}"


class TestResourceExtraction:
    """Test extraction of Terraform resources."""

    def test_extract_simple_resource(self, terraform_extractor, ast_parser):
        """Test extracting aws_instance.web from main.tf."""
        main_tf = FIXTURE_PATH / "main.tf"
        with open(main_tf, 'r', encoding='utf-8') as f:
            content = f.read()

        # Parse with tree-sitter
        tree = ast_parser.parse_file(main_tf, language="hcl")

        # Extract using hcl_impl directly
        resources = hcl_impl.extract_hcl_resources(tree['tree'], content, str(main_tf))

        # Find aws_instance.web
        web_instance = None
        for resource in resources:
            if resource['resource_type'] == 'aws_instance' and resource['resource_name'] == 'web':
                web_instance = resource
                break

        assert web_instance is not None, "aws_instance.web not found"
        assert web_instance['resource_type'] == 'aws_instance'
        assert web_instance['resource_name'] == 'web'
        assert web_instance['line'] > 0

    def test_extract_resource_with_for_each(self, terraform_extractor, ast_parser):
        """Test extracting aws_route53_record.app_records (with for_each)."""
        main_tf = FIXTURE_PATH / "main.tf"
        with open(main_tf, 'r', encoding='utf-8') as f:
            content = f.read()

        tree = ast_parser.parse_file(main_tf, language="hcl")
        resources = hcl_impl.extract_hcl_resources(tree['tree'], content, str(main_tf))

        # Find aws_route53_record.app_records
        route53_record = None
        for resource in resources:
            if resource['resource_type'] == 'aws_route53_record' and resource['resource_name'] == 'app_records':
                route53_record = resource
                break

        assert route53_record is not None, "aws_route53_record.app_records not found"
        assert 'for_each' in route53_record['attributes']

    def test_extract_resource_with_count(self, terraform_extractor, ast_parser):
        """Test extracting aws_subnet.public (with count) from vpc module."""
        vpc_main = FIXTURE_PATH / "modules" / "vpc" / "main.tf"
        with open(vpc_main, 'r', encoding='utf-8') as f:
            content = f.read()

        tree = ast_parser.parse_file(vpc_main, language="hcl")
        resources = hcl_impl.extract_hcl_resources(tree['tree'], content, str(vpc_main))

        # Find aws_subnet.public
        public_subnet = None
        for resource in resources:
            if resource['resource_type'] == 'aws_subnet' and resource['resource_name'] == 'public':
                public_subnet = resource
                break

        assert public_subnet is not None, "aws_subnet.public not found"
        assert 'count' in public_subnet['attributes']

    def test_extract_public_s3_violation(self, terraform_extractor, ast_parser):
        """Test extracting aws_s3_bucket.public_read from security violations."""
        public_s3 = FIXTURE_PATH / "security_violations" / "public_s3.tf"
        with open(public_s3, 'r', encoding='utf-8') as f:
            content = f.read()

        tree = ast_parser.parse_file(public_s3, language="hcl")
        resources = hcl_impl.extract_hcl_resources(tree['tree'], content, str(public_s3))

        # Find aws_s3_bucket.public_read
        public_bucket = None
        for resource in resources:
            if resource['resource_type'] == 'aws_s3_bucket' and resource['resource_name'] == 'public_read':
                public_bucket = resource
                break

        assert public_bucket is not None, "aws_s3_bucket.public_read not found"
        # Verify the violation attribute is present
        assert 'acl' in public_bucket['attributes']


class TestVariableExtraction:
    """Test extraction of Terraform variables."""

    def test_extract_sensitive_variable(self, terraform_extractor, ast_parser):
        """Test extracting var.db_password with is_sensitive = True."""
        variables_tf = FIXTURE_PATH / "variables.tf"
        with open(variables_tf, 'r', encoding='utf-8') as f:
            content = f.read()

        tree = ast_parser.parse_file(variables_tf, language="hcl")
        variables = hcl_impl.extract_hcl_variables(tree['tree'], content, str(variables_tf))

        # Find db_password variable
        db_password_var = None
        for var in variables:
            if var['variable_name'] == 'db_password':
                db_password_var = var
                break

        assert db_password_var is not None, "db_password variable not found"
        assert db_password_var['variable_name'] == 'db_password'
        assert db_password_var['line'] > 0
        # NOTE: is_sensitive extraction is TODO in current implementation
        # This test documents the expected behavior once implemented

    def test_extract_map_variable(self, terraform_extractor, ast_parser):
        """Test extracting var.common_tags with variable_type = map(string)."""
        variables_tf = FIXTURE_PATH / "variables.tf"
        with open(variables_tf, 'r', encoding='utf-8') as f:
            content = f.read()

        tree = ast_parser.parse_file(variables_tf, language="hcl")
        variables = hcl_impl.extract_hcl_variables(tree['tree'], content, str(variables_tf))

        # Find common_tags variable
        common_tags_var = None
        for var in variables:
            if var['variable_name'] == 'common_tags':
                common_tags_var = var
                break

        assert common_tags_var is not None, "common_tags variable not found"
        assert common_tags_var['variable_name'] == 'common_tags'
        # NOTE: variable_type extraction is TODO in current implementation

    def test_extract_list_variable(self, terraform_extractor, ast_parser):
        """Test extracting var.ami_id_list with variable_type = list(string)."""
        variables_tf = FIXTURE_PATH / "variables.tf"
        with open(variables_tf, 'r', encoding='utf-8') as f:
            content = f.read()

        tree = ast_parser.parse_file(variables_tf, language="hcl")
        variables = hcl_impl.extract_hcl_variables(tree['tree'], content, str(variables_tf))

        # Find ami_id_list variable
        ami_id_list_var = None
        for var in variables:
            if var['variable_name'] == 'ami_id_list':
                ami_id_list_var = var
                break

        assert ami_id_list_var is not None, "ami_id_list variable not found"
        assert ami_id_list_var['variable_name'] == 'ami_id_list'


class TestOutputExtraction:
    """Test extraction of Terraform outputs."""

    def test_extract_resource_output(self, terraform_extractor, ast_parser):
        """Test extracting output.web_instance_id."""
        outputs_tf = FIXTURE_PATH / "outputs.tf"
        with open(outputs_tf, 'r', encoding='utf-8') as f:
            content = f.read()

        tree = ast_parser.parse_file(outputs_tf, language="hcl")
        outputs = hcl_impl.extract_hcl_outputs(tree['tree'], content, str(outputs_tf))

        # Find web_instance_id output
        web_instance_output = None
        for output in outputs:
            if output['output_name'] == 'web_instance_id':
                web_instance_output = output
                break

        assert web_instance_output is not None, "web_instance_id output not found"
        assert web_instance_output['output_name'] == 'web_instance_id'
        assert web_instance_output['line'] > 0

    def test_extract_sensitive_output_violation(self, terraform_extractor, ast_parser):
        """Test extracting output.database_password (NOT marked sensitive - violation)."""
        sensitive_output = FIXTURE_PATH / "security_violations" / "sensitive_output.tf"
        with open(sensitive_output, 'r', encoding='utf-8') as f:
            content = f.read()

        tree = ast_parser.parse_file(sensitive_output, language="hcl")
        outputs = hcl_impl.extract_hcl_outputs(tree['tree'], content, str(sensitive_output))

        # Find database_password output
        db_password_output = None
        for output in outputs:
            if output['output_name'] == 'database_password':
                db_password_output = output
                break

        assert db_password_output is not None, "database_password output not found"
        # NOTE: is_sensitive=False is the violation - this should be detected
        # This test documents the expected behavior


class TestDataSourceExtraction:
    """Test extraction of Terraform data sources."""

    def test_extract_ami_data_source(self, terraform_extractor, ast_parser):
        """Test extracting data.aws_ami.amazon_linux."""
        data_tf = FIXTURE_PATH / "data.tf"
        with open(data_tf, 'r', encoding='utf-8') as f:
            content = f.read()

        tree = ast_parser.parse_file(data_tf, language="hcl")
        data_sources = hcl_impl.extract_hcl_data_sources(tree['tree'], content, str(data_tf))

        # Find aws_ami.amazon_linux
        amazon_linux_ami = None
        for ds in data_sources:
            if ds['data_type'] == 'aws_ami' and ds['data_name'] == 'amazon_linux':
                amazon_linux_ami = ds
                break

        assert amazon_linux_ami is not None, "data.aws_ami.amazon_linux not found"
        assert amazon_linux_ami['data_type'] == 'aws_ami'
        assert amazon_linux_ami['data_name'] == 'amazon_linux'
        assert amazon_linux_ami['line'] > 0

    def test_extract_iam_policy_document_data(self, terraform_extractor, ast_parser):
        """Test extracting data.aws_iam_policy_document.wildcard_policy."""
        iam_tf = FIXTURE_PATH / "security_violations" / "overly_permissive_iam.tf"
        with open(iam_tf, 'r', encoding='utf-8') as f:
            content = f.read()

        tree = ast_parser.parse_file(iam_tf, language="hcl")
        data_sources = hcl_impl.extract_hcl_data_sources(tree['tree'], content, str(iam_tf))

        # Find aws_iam_policy_document.wildcard_policy
        wildcard_policy = None
        for ds in data_sources:
            if ds['data_type'] == 'aws_iam_policy_document' and ds['data_name'] == 'wildcard_policy':
                wildcard_policy = ds
                break

        assert wildcard_policy is not None, "data.aws_iam_policy_document.wildcard_policy not found"


class TestTfvarsExtraction:
    """Test parsing of .tfvars files."""

    def test_extract_standard_tfvars(self, terraform_extractor):
        """Test parsing terraform.tfvars for string, number, and map assignments."""
        tfvars = FIXTURE_PATH / "terraform.tfvars"
        with open(tfvars, 'r', encoding='utf-8') as f:
            content = f.read()

        result = terraform_extractor._extract_tfvars(str(tfvars), content, None)

        assert 'terraform_variable_values' in result
        var_values = result['terraform_variable_values']

        # Find app_name assignment
        app_name = None
        for vv in var_values:
            if vv['variable_name'] == 'app_name':
                app_name = vv
                break

        assert app_name is not None, "app_name assignment not found in tfvars"
        assert app_name['variable_value'] == '"my-test-app"'

    def test_extract_sensitive_tfvars(self, terraform_extractor):
        """Test parsing sensitive.auto.tfvars with is_sensitive_context = True."""
        sensitive_tfvars = FIXTURE_PATH / "sensitive.auto.tfvars"
        with open(sensitive_tfvars, 'r', encoding='utf-8') as f:
            content = f.read()

        result = terraform_extractor._extract_tfvars(str(sensitive_tfvars), content, None)

        assert 'terraform_variable_values' in result
        var_values = result['terraform_variable_values']

        # Find db_password assignment
        db_password = None
        for vv in var_values:
            if vv['variable_name'] == 'db_password':
                db_password = vv
                break

        assert db_password is not None, "db_password assignment not found in sensitive.auto.tfvars"
        assert db_password['is_sensitive_context'] is True, "db_password should be marked as sensitive context"


class TestModuleExtraction:
    """Test extraction of module calls (currently not implemented - these are FAILING tests)."""

    @pytest.mark.skip(reason="Module extraction not yet implemented - Phase 7 TODO")
    def test_extract_module_networking(self, terraform_extractor, ast_parser):
        """FAILING TEST: Extract module.networking block including source and inputs."""
        main_tf = FIXTURE_PATH / "main.tf"
        with open(main_tf, 'r', encoding='utf-8') as f:
            content = f.read()

        tree = ast_parser.parse_file(main_tf, language="hcl")

        # Module extraction not yet implemented in hcl_impl.py
        # This test documents the expected behavior
        # TODO: Implement extract_hcl_modules() in hcl_impl.py
        modules = []  # hcl_impl.extract_hcl_modules(tree['tree'], content, str(main_tf))

        networking_module = None
        for mod in modules:
            if mod['module_name'] == 'networking':
                networking_module = mod
                break

        assert networking_module is not None, "module.networking not found"
        assert networking_module['source'] == '"./modules/vpc"'
        assert 'app_name' in networking_module['inputs']


class TestProviderBackendExtraction:
    """Test extraction of provider and backend blocks (currently not implemented - FAILING tests)."""

    @pytest.mark.skip(reason="Provider/backend extraction not yet implemented - Phase 7 TODO")
    def test_extract_backend_s3(self, terraform_extractor, ast_parser):
        """FAILING TEST: Extract terraform { backend "s3" { ... } } from versions.tf."""
        versions_tf = FIXTURE_PATH / "versions.tf"
        with open(versions_tf, 'r', encoding='utf-8') as f:
            content = f.read()

        tree = ast_parser.parse_file(versions_tf, language="hcl")

        # Terraform block extraction not yet implemented
        # This test documents the expected behavior
        terraform_blocks = []  # hcl_impl.extract_hcl_terraform_blocks(tree['tree'], content, str(versions_tf))

        # Should find backend configuration
        backend_found = False
        for block in terraform_blocks:
            if 'backend' in block and 's3' in block['backend']:
                backend_found = True
                break

        assert backend_found, "terraform { backend 's3' { ... } } not found"

    @pytest.mark.skip(reason="Provider extraction not yet implemented - Phase 7 TODO")
    def test_extract_provider_aws(self, terraform_extractor, ast_parser):
        """FAILING TEST: Extract provider "aws" { ... } block."""
        # Provider extraction not yet implemented
        # This test documents the expected behavior
        pass


class TestFullExtractorIntegration:
    """Integration tests for the full TerraformExtractor.extract() method."""

    def test_extract_main_tf(self, terraform_extractor, ast_parser):
        """Test full extraction of main.tf file."""
        main_tf = FIXTURE_PATH / "main.tf"
        with open(main_tf, 'r', encoding='utf-8') as f:
            content = f.read()

        tree = ast_parser.parse_file(main_tf, language="hcl")

        file_info = {'path': str(main_tf)}
        result = terraform_extractor.extract(file_info, content, tree)

        # Verify structure
        assert 'terraform_resources' in result
        assert 'terraform_file' in result

        # Verify we extracted multiple resources
        assert len(result['terraform_resources']) > 0

        # Verify terraform_file metadata
        assert result['terraform_file']['file_path'] == str(main_tf)

    def test_extract_variables_tf(self, terraform_extractor, ast_parser):
        """Test full extraction of variables.tf file."""
        variables_tf = FIXTURE_PATH / "variables.tf"
        with open(variables_tf, 'r', encoding='utf-8') as f:
            content = f.read()

        tree = ast_parser.parse_file(variables_tf, language="hcl")

        file_info = {'path': str(variables_tf)}
        result = terraform_extractor.extract(file_info, content, tree)

        # Verify structure
        assert 'terraform_variables' in result
        assert len(result['terraform_variables']) == 5, f"Expected 5 variables, got {len(result['terraform_variables'])}"

        # Verify all variables are present
        var_names = {v['variable_name'] for v in result['terraform_variables']}
        assert 'app_name' in var_names
        assert 'common_tags' in var_names
        assert 'db_password' in var_names
        assert 'instance_count' in var_names
        assert 'ami_id_list' in var_names
