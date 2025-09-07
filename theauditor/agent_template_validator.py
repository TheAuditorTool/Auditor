"""Agent template validator - ensures templates comply with SOP permissions."""

import json
import re
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
import yaml


class TemplateValidator:
    """Validates agent templates for SOP compliance and structure."""
    
    # Tools that allow code modification
    WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
    
    # Agents allowed to modify code
    ALLOWED_EDITOR_AGENTS = {"coder", "documentation-manager", "implementation-specialist"}
    
    # Required frontmatter fields
    REQUIRED_FIELDS = {"name", "description", "tools", "model"}
    
    def __init__(self, template_dir: str = None):
        """Initialize validator with template directory."""
        if template_dir:
            self.template_dir = Path(template_dir)
        else:
            # Default to agent_templates relative to module
            self.template_dir = Path(__file__).parent.parent / "agent_templates"
        
        self.violations = []
        self.warnings = []
    
    def _extract_frontmatter(self, content: str) -> Optional[Dict[str, Any]]:
        """Extract YAML frontmatter from markdown file.
        
        Args:
            content: File content
            
        Returns:
            Parsed frontmatter dict or None if not found
        """
        # Match frontmatter between --- markers
        pattern = r'^---\s*\n(.*?)\n---\s*\n'
        match = re.match(pattern, content, re.DOTALL)
        
        if not match:
            return None
        
        try:
            frontmatter_text = match.group(1)
            return yaml.safe_load(frontmatter_text)
        except yaml.YAMLError as e:
            self.violations.append(f"Invalid YAML frontmatter: {e}")
            return None
    
    def _parse_tools(self, tools_value: Any) -> List[str]:
        """Parse tools from frontmatter value.
        
        Args:
            tools_value: Tools field from frontmatter
            
        Returns:
            List of tool names
        """
        if isinstance(tools_value, str):
            # Comma-separated string
            return [t.strip() for t in tools_value.split(',')]
        elif isinstance(tools_value, list):
            return tools_value
        else:
            return []
    
    def _check_sop_permissions(
        self,
        template_name: str,
        frontmatter: Dict[str, Any]
    ) -> List[str]:
        """Check SOP permission rules.
        
        Args:
            template_name: Name of template file
            frontmatter: Parsed frontmatter
            
        Returns:
            List of violations found
        """
        violations = []
        
        # Get name and description, ensuring they're strings
        agent_name = frontmatter.get("name", "")
        if not isinstance(agent_name, str):
            agent_name = str(agent_name) if agent_name else ""
        # Skip validation for templates with placeholders
        if "{" in agent_name or "}" in agent_name:
            # This is a template with placeholders, not a real agent
            return []
        agent_name = agent_name.lower()
        
        description = frontmatter.get("description", "")
        if not isinstance(description, str):
            description = str(description) if description else ""
        description = description.lower()
        
        tools = self._parse_tools(frontmatter.get("tools", ""))
        
        # Check if agent has write tools
        has_write_tools = any(tool in self.WRITE_TOOLS for tool in tools)
        
        # Check compliance/legal agents first (they have stricter rules)
        is_compliance_agent = (
            "compliance" in agent_name or 
            "compliance" in description or
            "legal" in agent_name or
            "legal" in description
        )
        
        if is_compliance_agent and has_write_tools:
            violations.append(
                f"Compliance/legal agent '{agent_name}' must not have write tools, "
                f"found: {self.WRITE_TOOLS & set(tools)}"
            )
        elif has_write_tools:
            # For non-compliance agents, check if they're allowed to have write tools
            is_allowed_editor = any(
                allowed in agent_name 
                for allowed in self.ALLOWED_EDITOR_AGENTS
            )
            
            if not is_allowed_editor:
                violations.append(
                    f"Agent '{agent_name}' has write tools ({self.WRITE_TOOLS & set(tools)}) "
                    f"but is not in allowed editor list: {self.ALLOWED_EDITOR_AGENTS}"
                )
        
        return violations
    
    def _check_internal_links(
        self,
        content: str,
        template_path: Path
    ) -> List[str]:
        """Check internal repository links are valid.
        
        Args:
            content: Template content
            template_path: Path to template file
            
        Returns:
            List of broken links
        """
        broken_links = []
        
        # Find markdown links and references to repo paths
        link_patterns = [
            r'\[.*?\]\((\/[^)]+)\)',  # Markdown links with absolute paths
            r'`(\/[^`]+)`',  # Code blocks with paths
            r'"(\/[^"]+)"',  # Quoted paths
            r"'(\/[^']+)'",  # Single-quoted paths
        ]
        
        for pattern in link_patterns:
            for match in re.finditer(pattern, content):
                path_str = match.group(1)
                
                # Skip URLs and anchors
                if path_str.startswith('http') or path_str.startswith('#'):
                    continue
                
                # Check if path exists relative to repo root
                repo_root = template_path.parent.parent
                full_path = repo_root / path_str.lstrip('/')
                
                if not full_path.exists():
                    broken_links.append(f"Broken internal link: {path_str}")
        
        return broken_links
    
    def validate_template(self, template_path: Path) -> Dict[str, Any]:
        """Validate a single template file.
        
        Args:
            template_path: Path to template markdown file
            
        Returns:
            Validation result dict
        """
        result = {
            "path": str(template_path),
            "valid": True,
            "violations": [],
            "warnings": []
        }
        
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except IOError as e:
            result["valid"] = False
            result["violations"].append(f"Cannot read file: {e}")
            return result
        
        # Extract frontmatter
        frontmatter = self._extract_frontmatter(content)
        
        if frontmatter is None:
            result["valid"] = False
            result["violations"].append("No valid frontmatter found")
            return result
        
        # Check required fields
        missing_fields = self.REQUIRED_FIELDS - set(frontmatter.keys())
        if missing_fields:
            result["valid"] = False
            result["violations"].append(
                f"Missing required frontmatter fields: {missing_fields}"
            )
        
        # Check SOP permissions
        sop_violations = self._check_sop_permissions(
            template_path.name,
            frontmatter
        )
        if sop_violations:
            result["valid"] = False
            result["violations"].extend(sop_violations)
        
        # Check internal links
        broken_links = self._check_internal_links(content, template_path)
        if broken_links:
            result["warnings"].extend(broken_links)
        
        # Check for tool typos/inconsistencies
        tools = self._parse_tools(frontmatter.get("tools", ""))
        known_tools = {
            "Bash", "Glob", "Grep", "LS", "Read", "Edit", "Write",
            "MultiEdit", "NotebookEdit", "WebFetch", "TodoWrite",
            "WebSearch", "BashOutput", "KillBash", "Task", "ExitPlanMode"
        }
        
        unknown_tools = set(tools) - known_tools
        if unknown_tools:
            result["warnings"].append(
                f"Unknown tools found: {unknown_tools}"
            )
        
        return result
    
    def validate_all(self, source_dir: Optional[str] = None) -> Dict[str, Any]:
        """Validate all templates in directory.
        
        Args:
            source_dir: Directory containing templates (default: self.template_dir)
            
        Returns:
            Validation summary
        """
        if source_dir:
            template_dir = Path(source_dir)
        else:
            template_dir = self.template_dir
        
        if not template_dir.exists():
            return {
                "valid": False,
                "error": f"Template directory not found: {template_dir}",
                "templates": []
            }
        
        results = []
        all_valid = True
        total_violations = 0
        total_warnings = 0
        
        # Find all .md files
        for template_path in template_dir.glob("*.md"):
            result = self.validate_template(template_path)
            results.append(result)
            
            if not result["valid"]:
                all_valid = False
            
            total_violations += len(result["violations"])
            total_warnings += len(result["warnings"])
        
        return {
            "valid": all_valid,
            "templates_checked": len(results),
            "total_violations": total_violations,
            "total_warnings": total_warnings,
            "templates": results
        }
    
    def generate_report(
        self,
        validation_results: Dict[str, Any],
        format: str = "json"
    ) -> str:
        """Generate validation report.
        
        Args:
            validation_results: Results from validate_all()
            format: Output format ('json' or 'text')
            
        Returns:
            Formatted report string
        """
        if format == "json":
            return json.dumps(validation_results, indent=2, sort_keys=True)
        
        # Text format
        lines = []
        lines.append("=== Agent Template Validation Report ===\n")
        lines.append(f"Templates checked: {validation_results['templates_checked']}")
        lines.append(f"Total violations: {validation_results['total_violations']}")
        lines.append(f"Total warnings: {validation_results['total_warnings']}")
        lines.append(f"Overall status: {'PASS' if validation_results['valid'] else 'FAIL'}\n")
        
        for template in validation_results.get("templates", []):
            lines.append(f"\n{template['path']}:")
            lines.append(f"  Status: {'✓' if template['valid'] else '✗'}")
            
            if template["violations"]:
                lines.append("  Violations:")
                for v in template["violations"]:
                    lines.append(f"    - {v}")
            
            if template["warnings"]:
                lines.append("  Warnings:")
                for w in template["warnings"]:
                    lines.append(f"    - {w}")
        
        return "\n".join(lines)


# Module-level convenience function
def validate_templates(source_dir: str) -> Tuple[bool, Dict[str, Any]]:
    """Validate all templates in directory.
    
    Args:
        source_dir: Directory containing agent templates
        
    Returns:
        Tuple of (all_valid, validation_results)
    """
    validator = TemplateValidator()
    results = validator.validate_all(source_dir)
    return results["valid"], results