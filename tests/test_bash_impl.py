"""
Bash Implementation Unit Tests - Test bash_impl.py extraction functions.

These tests verify that tree-sitter based Bash extraction works correctly
by parsing actual Bash code and checking the extracted data.

Created as part of: add-bash-support OpenSpec proposal
Task: 4.2.1 Unit tests for function extraction
Task: 4.2.2 Unit tests for variable extraction
Task: 4.2.3 Unit tests for quoting analysis
Task: 4.2.6 Test case for wrapper unwrapping
Task: 4.2.7 Test case for nested expansion recursion
Task: 4.2.8 Test case for heredoc variable expansion
Task: 4.2.9 Test case for IFS manipulation detection
Task: 4.2.10 Test case for BashPipeStrategy edge creation
"""

import pytest
from tree_sitter_language_pack import get_parser

from theauditor.ast_extractors import bash_impl


@pytest.fixture
def bash_parser():
    """Create a Bash tree-sitter parser."""
    parser = get_parser("bash")
    return parser


def parse_bash(parser, code: str):
    """Helper to parse Bash code and return extraction result."""
    tree = parser.parse(code.encode("utf-8"))
    return bash_impl.extract_all_bash_data(tree, code, "test.sh")


# =============================================================================
# TASK 4.2.1: FUNCTION EXTRACTION TESTS
# =============================================================================
class TestBashFunctionExtraction:
    """Tests for Bash function extraction."""

    def test_extract_posix_function(self, bash_parser):
        """Test POSIX-style function extraction: name() { ... }"""
        code = '''my_func() {
    echo "hello"
}'''
        result = parse_bash(bash_parser, code)

        funcs = result["bash_functions"]
        assert len(funcs) == 1
        assert funcs[0]["name"] == "my_func"
        assert funcs[0]["style"] == "posix"
        assert funcs[0]["line"] == 1
        assert funcs[0]["end_line"] == 3

    def test_extract_bash_function(self, bash_parser):
        """Test Bash-style function extraction: function name() { ... }"""
        code = '''function my_func() {
    echo "hello"
}'''
        result = parse_bash(bash_parser, code)

        funcs = result["bash_functions"]
        assert len(funcs) == 1
        assert funcs[0]["name"] == "my_func"
        assert funcs[0]["style"] == "bash"
        assert funcs[0]["line"] == 1

    def test_extract_function_no_parens(self, bash_parser):
        """Test function keyword without parentheses: function name { ... }"""
        code = '''function my_func {
    echo "hello"
}'''
        result = parse_bash(bash_parser, code)

        funcs = result["bash_functions"]
        assert len(funcs) == 1
        assert funcs[0]["name"] == "my_func"
        # Style should be "bash" for function keyword variant
        assert funcs[0]["style"] == "bash"

    def test_extract_multiple_functions(self, bash_parser):
        """Test extraction of multiple functions."""
        code = '''func_one() {
    echo "one"
}

func_two() {
    echo "two"
}

function func_three {
    echo "three"
}'''
        result = parse_bash(bash_parser, code)

        funcs = result["bash_functions"]
        assert len(funcs) == 3
        names = {f["name"] for f in funcs}
        assert names == {"func_one", "func_two", "func_three"}

    def test_function_body_lines(self, bash_parser):
        """Test that function body line numbers are correctly captured."""
        code = '''my_func() {
    line1
    line2
    line3
}'''
        result = parse_bash(bash_parser, code)

        funcs = result["bash_functions"]
        assert len(funcs) == 1
        assert funcs[0]["body_start_line"] == 1
        assert funcs[0]["body_end_line"] == 5

    def test_nested_function_scope(self, bash_parser):
        """Test that variables inside functions track containing_function."""
        code = '''outer_func() {
    local inner_var="value"
    echo "$inner_var"
}'''
        result = parse_bash(bash_parser, code)

        variables = result["bash_variables"]
        # Find the inner_var variable
        inner_vars = [v for v in variables if v["name"] == "inner_var"]
        assert len(inner_vars) == 1
        assert inner_vars[0]["containing_function"] == "outer_func"
        assert inner_vars[0]["scope"] == "local"


# =============================================================================
# TASK 4.2.2: VARIABLE EXTRACTION TESTS
# =============================================================================
class TestBashVariableExtraction:
    """Tests for Bash variable extraction."""

    def test_extract_simple_assignment(self, bash_parser):
        """Test simple variable assignment."""
        code = '''MY_VAR="hello world"'''
        result = parse_bash(bash_parser, code)

        variables = result["bash_variables"]
        assert len(variables) == 1
        assert variables[0]["name"] == "MY_VAR"
        assert variables[0]["scope"] == "global"
        assert variables[0]["readonly"] is False
        assert '"hello world"' in variables[0]["value_expr"]

    def test_extract_export_variable(self, bash_parser):
        """Test export variable extraction."""
        code = '''export PATH="/usr/bin:$PATH"'''
        result = parse_bash(bash_parser, code)

        variables = result["bash_variables"]
        assert len(variables) == 1
        assert variables[0]["name"] == "PATH"
        assert variables[0]["scope"] == "exported"

    def test_extract_local_variable(self, bash_parser):
        """Test local variable extraction inside function."""
        code = '''my_func() {
    local my_local="value"
}'''
        result = parse_bash(bash_parser, code)

        variables = result["bash_variables"]
        local_vars = [v for v in variables if v["name"] == "my_local"]
        assert len(local_vars) == 1
        assert local_vars[0]["scope"] == "local"
        assert local_vars[0]["containing_function"] == "my_func"

    def test_extract_readonly_variable(self, bash_parser):
        """Test readonly variable extraction."""
        code = '''readonly MY_CONST="immutable"'''
        result = parse_bash(bash_parser, code)

        variables = result["bash_variables"]
        assert len(variables) == 1
        assert variables[0]["name"] == "MY_CONST"
        assert variables[0]["readonly"] is True

    def test_extract_declare_variable(self, bash_parser):
        """Test declare variable extraction."""
        code = '''declare -a MY_ARRAY=(1 2 3)'''
        result = parse_bash(bash_parser, code)

        variables = result["bash_variables"]
        assert len(variables) >= 1
        array_vars = [v for v in variables if v["name"] == "MY_ARRAY"]
        assert len(array_vars) == 1

    def test_extract_command_substitution_capture(self, bash_parser):
        """Test variable capturing command substitution output."""
        code = '''RESULT=$(whoami)'''
        result = parse_bash(bash_parser, code)

        variables = result["bash_variables"]
        subshells = result["bash_subshells"]

        # Variable should exist
        result_vars = [v for v in variables if v["name"] == "RESULT"]
        assert len(result_vars) == 1

        # Subshell should have capture_target
        assert len(subshells) >= 1
        captures = [s for s in subshells if s["capture_target"] == "RESULT"]
        assert len(captures) >= 1

    def test_variable_containing_function_tracking(self, bash_parser):
        """Test that global vs local scope is correctly tracked."""
        code = '''GLOBAL_VAR="outside"

my_func() {
    local FUNC_VAR="inside"
}'''
        result = parse_bash(bash_parser, code)

        variables = result["bash_variables"]
        global_vars = [v for v in variables if v["name"] == "GLOBAL_VAR"]
        func_vars = [v for v in variables if v["name"] == "FUNC_VAR"]

        assert len(global_vars) == 1
        assert global_vars[0]["containing_function"] is None

        assert len(func_vars) == 1
        assert func_vars[0]["containing_function"] == "my_func"


# =============================================================================
# TASK 4.2.3: QUOTING ANALYSIS TESTS
# =============================================================================
class TestBashQuotingAnalysis:
    """Tests for Bash quoting analysis in command arguments."""

    def test_unquoted_variable_expansion(self, bash_parser):
        """Test detection of unquoted variable expansion (security risk)."""
        code = '''rm $file'''
        result = parse_bash(bash_parser, code)

        commands = result["bash_commands"]
        assert len(commands) == 1

        args = commands[0]["args"]
        assert len(args) == 1
        assert args[0]["is_quoted"] is False
        assert args[0]["has_expansion"] is True
        assert "file" in args[0]["expansion_vars"]

    def test_double_quoted_variable(self, bash_parser):
        """Test double-quoted variable (safe)."""
        code = '''rm "$file"'''
        result = parse_bash(bash_parser, code)

        commands = result["bash_commands"]
        assert len(commands) == 1

        args = commands[0]["args"]
        assert len(args) == 1
        assert args[0]["is_quoted"] is True
        assert args[0]["quote_type"] == "double"
        assert args[0]["has_expansion"] is True

    def test_single_quoted_literal(self, bash_parser):
        """Test single-quoted literal (no expansion)."""
        code = """echo '$VAR is literal'"""
        result = parse_bash(bash_parser, code)

        commands = result["bash_commands"]
        echo_cmds = [c for c in commands if c["command_name"] == "echo"]
        assert len(echo_cmds) == 1

        args = echo_cmds[0]["args"]
        assert len(args) == 1
        assert args[0]["is_quoted"] is True
        assert args[0]["quote_type"] == "single"
        assert args[0]["has_expansion"] is False

    def test_mixed_quoting(self, bash_parser):
        """Test command with mixed quoting."""
        code = """cmd "quoted $var" unquoted '$literal'"""
        result = parse_bash(bash_parser, code)

        commands = result["bash_commands"]
        cmd_list = [c for c in commands if c["command_name"] == "cmd"]
        assert len(cmd_list) == 1

        args = cmd_list[0]["args"]
        assert len(args) == 3

        # First arg: double-quoted with expansion
        assert args[0]["quote_type"] == "double"
        assert args[0]["has_expansion"] is True

        # Second arg: unquoted
        assert args[1]["is_quoted"] is False

        # Third arg: single-quoted, no expansion
        assert args[2]["quote_type"] == "single"
        assert args[2]["has_expansion"] is False


# =============================================================================
# COMMAND EXTRACTION TESTS
# =============================================================================
class TestBashCommandExtraction:
    """Tests for Bash command extraction."""

    def test_simple_command(self, bash_parser):
        """Test simple command extraction."""
        code = '''ls -la /tmp'''
        result = parse_bash(bash_parser, code)

        commands = result["bash_commands"]
        assert len(commands) == 1
        assert commands[0]["command_name"] == "ls"
        assert len(commands[0]["args"]) == 2

    def test_command_containing_function(self, bash_parser):
        """Test command tracking of containing function."""
        code = '''my_func() {
    ls -la
}'''
        result = parse_bash(bash_parser, code)

        commands = result["bash_commands"]
        ls_cmds = [c for c in commands if c["command_name"] == "ls"]
        assert len(ls_cmds) == 1
        assert ls_cmds[0]["containing_function"] == "my_func"


# =============================================================================
# TASK 4.2.6: WRAPPER UNWRAPPING TESTS (DRAGON)
# =============================================================================
class TestBashWrapperUnwrapping:
    """Tests for wrapper command unwrapping (sudo, time, xargs, etc.)."""

    def test_sudo_unwrapping(self, bash_parser):
        """Test that sudo wrapper extracts the wrapped command."""
        code = '''sudo rm -rf /tmp/test'''
        result = parse_bash(bash_parser, code)

        commands = result["bash_commands"]
        sudo_cmds = [c for c in commands if c["command_name"] == "sudo"]
        assert len(sudo_cmds) == 1
        assert sudo_cmds[0]["wrapped_command"] == "rm"

    def test_sudo_with_user_flag(self, bash_parser):
        """Test sudo with -u flag unwrapping."""
        code = '''sudo -u nobody cat /etc/passwd'''
        result = parse_bash(bash_parser, code)

        commands = result["bash_commands"]
        sudo_cmds = [c for c in commands if c["command_name"] == "sudo"]
        assert len(sudo_cmds) == 1
        assert sudo_cmds[0]["wrapped_command"] == "cat"

    def test_time_unwrapping(self, bash_parser):
        """Test that time wrapper extracts the wrapped command."""
        code = '''time curl https://example.com'''
        result = parse_bash(bash_parser, code)

        commands = result["bash_commands"]
        time_cmds = [c for c in commands if c["command_name"] == "time"]
        assert len(time_cmds) == 1
        assert time_cmds[0]["wrapped_command"] == "curl"

    def test_nohup_unwrapping(self, bash_parser):
        """Test that nohup wrapper extracts the wrapped command."""
        code = '''nohup ./long_process.sh &'''
        result = parse_bash(bash_parser, code)

        commands = result["bash_commands"]
        nohup_cmds = [c for c in commands if c["command_name"] == "nohup"]
        assert len(nohup_cmds) == 1
        assert nohup_cmds[0]["wrapped_command"] == "./long_process.sh"

    def test_env_unwrapping(self, bash_parser):
        """Test that env wrapper skips VAR=val and finds command."""
        code = '''env PATH=/bin VAR=value ls -la'''
        result = parse_bash(bash_parser, code)

        commands = result["bash_commands"]
        env_cmds = [c for c in commands if c["command_name"] == "env"]
        assert len(env_cmds) == 1
        assert env_cmds[0]["wrapped_command"] == "ls"

    def test_non_wrapper_command(self, bash_parser):
        """Test that non-wrapper commands have no wrapped_command."""
        code = '''ls -la'''
        result = parse_bash(bash_parser, code)

        commands = result["bash_commands"]
        assert len(commands) == 1
        assert commands[0]["wrapped_command"] is None


# =============================================================================
# FLAG NORMALIZATION TESTS
# =============================================================================
class TestBashFlagNormalization:
    """Tests for combined flag normalization (-la -> -l, -a)."""

    def test_combined_short_flags(self, bash_parser):
        """Test that combined short flags are normalized."""
        code = '''ls -la'''
        result = parse_bash(bash_parser, code)

        commands = result["bash_commands"]
        assert len(commands) == 1

        args = commands[0]["args"]
        la_args = [a for a in args if a["value"] == "-la"]
        assert len(la_args) == 1
        assert la_args[0]["normalized_flags"] == ["-l", "-a"]

    def test_single_short_flag(self, bash_parser):
        """Test that single short flags are not normalized."""
        code = '''ls -l'''
        result = parse_bash(bash_parser, code)

        commands = result["bash_commands"]
        args = commands[0]["args"]
        l_args = [a for a in args if a["value"] == "-l"]
        assert len(l_args) == 1
        assert l_args[0]["normalized_flags"] is None

    def test_long_flag(self, bash_parser):
        """Test that long flags are not normalized."""
        code = '''ls --all'''
        result = parse_bash(bash_parser, code)

        commands = result["bash_commands"]
        args = commands[0]["args"]
        all_args = [a for a in args if a["value"] == "--all"]
        assert len(all_args) == 1
        assert all_args[0]["normalized_flags"] is None


# =============================================================================
# SOURCE STATEMENT EXTRACTION TESTS
# =============================================================================
class TestBashSourceExtraction:
    """Tests for source/dot statement extraction."""

    def test_source_command(self, bash_parser):
        """Test source command extraction."""
        code = '''source /etc/profile'''
        result = parse_bash(bash_parser, code)

        sources = result["bash_sources"]
        assert len(sources) == 1
        assert sources[0]["sourced_path"] == "/etc/profile"
        assert sources[0]["syntax"] == "source"
        assert sources[0]["has_variable_expansion"] is False

    def test_dot_command(self, bash_parser):
        """Test dot (.) command extraction."""
        code = '''. ./lib/utils.sh'''
        result = parse_bash(bash_parser, code)

        sources = result["bash_sources"]
        assert len(sources) == 1
        assert sources[0]["sourced_path"] == "./lib/utils.sh"
        assert sources[0]["syntax"] == "dot"

    def test_source_with_variable(self, bash_parser):
        """Test source with variable expansion (security concern)."""
        code = '''source "$CONFIG_DIR/settings.sh"'''
        result = parse_bash(bash_parser, code)

        sources = result["bash_sources"]
        assert len(sources) == 1
        assert sources[0]["has_variable_expansion"] is True


# =============================================================================
# PIPELINE EXTRACTION TESTS
# =============================================================================
class TestBashPipelineExtraction:
    """Tests for pipeline extraction."""

    def test_simple_pipeline(self, bash_parser):
        """Test simple two-command pipeline."""
        code = '''cat file.txt | grep pattern'''
        result = parse_bash(bash_parser, code)

        pipes = result["bash_pipes"]
        assert len(pipes) == 2

        # Check positions
        positions = sorted([p["position"] for p in pipes])
        assert positions == [0, 1]

        # Both should have same pipeline_id
        pipeline_ids = set(p["pipeline_id"] for p in pipes)
        assert len(pipeline_ids) == 1

    def test_three_stage_pipeline(self, bash_parser):
        """Test three-stage pipeline."""
        code = '''cat file.txt | grep pattern | wc -l'''
        result = parse_bash(bash_parser, code)

        pipes = result["bash_pipes"]
        assert len(pipes) == 3

    def test_pipeline_command_text(self, bash_parser):
        """Test that pipeline captures command text."""
        code = '''echo hello | tr a-z A-Z'''
        result = parse_bash(bash_parser, code)

        pipes = result["bash_pipes"]
        cmd_texts = [p["command_text"] for p in pipes]
        assert any("echo" in ct for ct in cmd_texts)
        assert any("tr" in ct for ct in cmd_texts)


# =============================================================================
# TASK 4.2.7: NESTED EXPANSION RECURSION TESTS (DRAGON)
# =============================================================================
class TestBashNestedExpansion:
    """Tests for nested command substitution inside parameter expansion."""

    def test_nested_default_value_expansion(self, bash_parser):
        """Test ${VAR:-$(cmd)} pattern extracts inner subshell."""
        code = '''RESULT="${VAR:-$(cat /etc/hostname)}"'''
        result = parse_bash(bash_parser, code)

        subshells = result["bash_subshells"]
        # The nested $(cat /etc/hostname) should be extracted
        assert len(subshells) >= 1
        cat_subshells = [s for s in subshells if "cat" in s["command_text"]]
        assert len(cat_subshells) >= 1

    def test_deeply_nested_expansion(self, bash_parser):
        """Test deeply nested expansion ${A:-${B:-$(cmd)}}."""
        code = '''VALUE="${OUTER:-${INNER:-$(whoami)}}"'''
        result = parse_bash(bash_parser, code)

        subshells = result["bash_subshells"]
        whoami_subs = [s for s in subshells if "whoami" in s["command_text"]]
        assert len(whoami_subs) >= 1


# =============================================================================
# SUBSHELL EXTRACTION TESTS
# =============================================================================
class TestBashSubshellExtraction:
    """Tests for command substitution extraction."""

    def test_dollar_paren_syntax(self, bash_parser):
        """Test $() command substitution extraction."""
        code = '''result=$(ls -la)'''
        result = parse_bash(bash_parser, code)

        subshells = result["bash_subshells"]
        assert len(subshells) >= 1
        dollar_paren = [s for s in subshells if s["syntax"] == "dollar_paren"]
        assert len(dollar_paren) >= 1

    def test_backtick_syntax(self, bash_parser):
        """Test backtick command substitution extraction."""
        code = '''result=`date`'''
        result = parse_bash(bash_parser, code)

        subshells = result["bash_subshells"]
        backtick_subs = [s for s in subshells if s["syntax"] == "backtick"]
        assert len(backtick_subs) >= 1

    def test_subshell_capture_target(self, bash_parser):
        """Test that capture_target links to variable."""
        code = '''MY_OUTPUT=$(process_data)'''
        result = parse_bash(bash_parser, code)

        subshells = result["bash_subshells"]
        captured = [s for s in subshells if s["capture_target"] == "MY_OUTPUT"]
        assert len(captured) >= 1

    def test_multiple_subshells_same_line(self, bash_parser):
        """Test multiple subshells on same line (col uniqueness fix)."""
        code = '''echo "$(date) - $(whoami)"'''
        result = parse_bash(bash_parser, code)

        subshells = result["bash_subshells"]
        # Should have at least 2 subshells
        assert len(subshells) >= 2

        # Each should have unique col position
        cols = [s["col"] for s in subshells]
        assert len(cols) == len(set(cols)), "Each subshell should have unique col"


# =============================================================================
# TASK 4.2.8: HEREDOC VARIABLE EXPANSION TESTS (DRAGON)
# =============================================================================
class TestBashHeredocExtraction:
    """Tests for heredoc extraction with quoting detection."""

    def test_unquoted_heredoc_delimiter(self, bash_parser):
        """Test unquoted heredoc delimiter (variables expand)."""
        code = '''cat <<EOF
Hello $USER
EOF'''
        result = parse_bash(bash_parser, code)

        redirections = result["bash_redirections"]
        heredocs = [r for r in redirections if r["direction"] == "heredoc"]
        assert len(heredocs) == 1
        # Unquoted delimiter means variables expand
        assert heredocs[0].get("heredoc_quoted", False) is False

    def test_quoted_heredoc_delimiter(self, bash_parser):
        """Test quoted heredoc delimiter (variables do not expand)."""
        code = '''cat <<'EOF'
Hello $USER stays literal
EOF'''
        result = parse_bash(bash_parser, code)

        redirections = result["bash_redirections"]
        heredocs = [r for r in redirections if r["direction"] == "heredoc"]
        assert len(heredocs) == 1
        # Quoted delimiter means no variable expansion
        assert heredocs[0].get("heredoc_quoted", False) is True

    def test_heredoc_target_captured(self, bash_parser):
        """Test heredoc captures delimiter as target."""
        code = '''cat <<MYDELIM
content here
MYDELIM'''
        result = parse_bash(bash_parser, code)

        redirections = result["bash_redirections"]
        heredocs = [r for r in redirections if r["direction"] == "heredoc"]
        assert len(heredocs) == 1
        assert heredocs[0]["target"] == "MYDELIM"


# =============================================================================
# REDIRECTION EXTRACTION TESTS
# =============================================================================
class TestBashRedirectionExtraction:
    """Tests for I/O redirection extraction."""

    def test_output_redirect(self, bash_parser):
        """Test output redirection extraction."""
        code = '''echo hello > output.txt'''
        result = parse_bash(bash_parser, code)

        redirections = result["bash_redirections"]
        output_redir = [r for r in redirections if r["direction"] == "output"]
        assert len(output_redir) == 1
        assert output_redir[0]["target"] == "output.txt"

    def test_input_redirect(self, bash_parser):
        """Test input redirection extraction."""
        code = '''cat < input.txt'''
        result = parse_bash(bash_parser, code)

        redirections = result["bash_redirections"]
        input_redir = [r for r in redirections if r["direction"] == "input"]
        assert len(input_redir) == 1


# =============================================================================
# CONTROL FLOW EXTRACTION TESTS
# =============================================================================
class TestBashControlFlowExtraction:
    """Tests for control flow statement extraction."""

    def test_if_statement(self, bash_parser):
        """Test if statement extraction."""
        code = '''if [ -f file.txt ]; then
    echo "exists"
fi'''
        result = parse_bash(bash_parser, code)

        control_flows = result["bash_control_flows"]
        if_stmts = [cf for cf in control_flows if cf["type"] == "if"]
        assert len(if_stmts) == 1

    def test_for_loop(self, bash_parser):
        """Test for loop extraction with loop variable."""
        code = '''for item in a b c; do
    echo "$item"
done'''
        result = parse_bash(bash_parser, code)

        control_flows = result["bash_control_flows"]
        for_loops = [cf for cf in control_flows if cf["type"] == "for"]
        assert len(for_loops) == 1
        assert for_loops[0]["loop_variable"] == "item"

    def test_while_loop(self, bash_parser):
        """Test while loop extraction."""
        code = '''while [ true ]; do
    echo "loop"
done'''
        result = parse_bash(bash_parser, code)

        control_flows = result["bash_control_flows"]
        while_loops = [cf for cf in control_flows if cf["type"] == "while"]
        assert len(while_loops) == 1

    def test_case_statement(self, bash_parser):
        """Test case statement extraction."""
        code = '''case "$1" in
    start) echo "starting" ;;
    stop) echo "stopping" ;;
    *) echo "unknown" ;;
esac'''
        result = parse_bash(bash_parser, code)

        control_flows = result["bash_control_flows"]
        case_stmts = [cf for cf in control_flows if cf["type"] == "case"]
        assert len(case_stmts) == 1


# =============================================================================
# TASK 4.2.9: SET COMMAND / SAFETY FLAGS TESTS
# =============================================================================
class TestBashSetCommandTracking:
    """Tests for set command and safety flag detection."""

    def test_set_e_flag(self, bash_parser):
        """Test detection of set -e (errexit)."""
        code = '''set -e
echo "safe script"'''
        result = parse_bash(bash_parser, code)

        metadata = result.get("_bash_metadata", {})
        assert metadata.get("has_errexit") is True

    def test_set_u_flag(self, bash_parser):
        """Test detection of set -u (nounset)."""
        code = '''set -u
echo "$UNDEFINED"'''
        result = parse_bash(bash_parser, code)

        metadata = result.get("_bash_metadata", {})
        assert metadata.get("has_nounset") is True

    def test_set_o_pipefail(self, bash_parser):
        """Test detection of set -o pipefail."""
        code = '''set -o pipefail
cat file | grep pattern'''
        result = parse_bash(bash_parser, code)

        metadata = result.get("_bash_metadata", {})
        assert metadata.get("has_pipefail") is True

    def test_combined_set_flags(self, bash_parser):
        """Test detection of combined flags like set -euo pipefail."""
        code = '''set -euo pipefail
echo "strict mode"'''
        result = parse_bash(bash_parser, code)

        metadata = result.get("_bash_metadata", {})
        assert metadata.get("has_errexit") is True
        assert metadata.get("has_nounset") is True
        assert metadata.get("has_pipefail") is True

    def test_no_safety_flags(self, bash_parser):
        """Test script without safety flags."""
        code = '''echo "unsafe script"'''
        result = parse_bash(bash_parser, code)

        metadata = result.get("_bash_metadata", {})
        assert metadata.get("has_errexit") is False
        assert metadata.get("has_nounset") is False
        assert metadata.get("has_pipefail") is False


# =============================================================================
# COMPLEX REAL-WORLD SCRIPT TESTS
# =============================================================================
class TestBashRealWorldScripts:
    """Integration tests with realistic script patterns."""

    def test_devops_script_pattern(self, bash_parser):
        """Test extraction from DevOps-style deployment script."""
        code = '''#!/bin/bash
set -euo pipefail

DEPLOY_DIR="/opt/myapp"
LOG_FILE="/var/log/deploy.log"

log() {
    local level="$1"
    local message="$2"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $message" | tee -a "$LOG_FILE"
}

deploy() {
    log "INFO" "Starting deployment"
    cd "$DEPLOY_DIR" || exit 1
    git pull origin main
    ./restart.sh
    log "INFO" "Deployment complete"
}

deploy "$@"
'''
        result = parse_bash(bash_parser, code)

        # Should extract functions
        funcs = result["bash_functions"]
        func_names = {f["name"] for f in funcs}
        assert "log" in func_names
        assert "deploy" in func_names

        # Should extract variables
        variables = result["bash_variables"]
        var_names = {v["name"] for v in variables}
        assert "DEPLOY_DIR" in var_names
        assert "LOG_FILE" in var_names

        # Should detect safety flags
        metadata = result.get("_bash_metadata", {})
        assert metadata.get("has_errexit") is True
        assert metadata.get("has_pipefail") is True

    def test_ci_pipeline_pattern(self, bash_parser):
        """Test extraction from CI/CD pipeline script pattern."""
        code = '''#!/bin/bash

build() {
    docker build -t "$IMAGE_NAME:$TAG" .
}

test() {
    docker run --rm "$IMAGE_NAME:$TAG" npm test
}

push() {
    docker push "$IMAGE_NAME:$TAG"
}

case "$1" in
    build) build ;;
    test) test ;;
    push) push ;;
    *) echo "Usage: $0 {build|test|push}" ;;
esac
'''
        result = parse_bash(bash_parser, code)

        # Should extract all functions
        funcs = result["bash_functions"]
        func_names = {f["name"] for f in funcs}
        assert func_names == {"build", "test", "push"}

        # Should extract case statement
        control_flows = result["bash_control_flows"]
        case_stmts = [cf for cf in control_flows if cf["type"] == "case"]
        assert len(case_stmts) == 1
