"""JavaScript/TypeScript project initialization."""

import json
from pathlib import Path


def deep_merge(base: dict, overlay: dict) -> dict:
    """
    Deep merge overlay into base, only adding missing keys.

    Existing values in base are never overwritten.
    """
    result = base.copy()

    for key, value in overlay.items():
        if key not in result:
            result[key] = value
        elif isinstance(value, dict) and isinstance(result[key], dict):
            # Recursively merge nested dicts
            result[key] = deep_merge(result[key], value)

    return result


def ensure_package_json(path: str) -> dict[str, str]:
    """
    Create or merge minimal package.json for lint/typecheck.

    Returns:
        {"status": "created"} if new file created
        {"status": "merged"} if existing file updated
        {"status": "unchanged"} if no changes needed
    """
    package_path = Path(path)

    # Template with PIN_ME placeholders
    template = {
        "private": True,
        "devDependencies": {
            "eslint": "<PIN_ME>",
            "@typescript-eslint/parser": "<PIN_ME>",
            "@typescript-eslint/eslint-plugin": "<PIN_ME>",
            "typescript": "<PIN_ME>",
            "prettier": "<PIN_ME>",
        },
        "scripts": {
            "lint": "eslint .",
            "typecheck": "tsc --noEmit",
            "format": "prettier -c .",
        },
    }

    if package_path.exists():
        # Load existing
        with open(package_path) as f:
            existing = json.load(f)

        # Deep merge
        merged = deep_merge(existing, template)

        if merged == existing:
            return {"status": "unchanged"}

        # Write merged version
        with open(package_path, "w") as f:
            json.dump(merged, f, indent=2)

        return {"status": "merged"}
    else:
        # Create new file
        with open(package_path, "w") as f:
            json.dump(template, f, indent=2)

        return {"status": "created"}


def add_auditor_hooks(path: str) -> dict[str, str]:
    """
    Add TheAuditor hooks to package.json scripts non-destructively.
    
    Adds the following hooks:
    - pretest: aud lint --workset
    - prebuild: aud ast-verify  
    - prepush: aud taint-analyze
    
    If hooks already exist, prepends Auditor commands with &&.
    
    Args:
        path: Path to package.json file
        
    Returns:
        {"status": "hooks_added", "details": <list of changes>} if hooks were added
        {"status": "unchanged"} if all hooks already present
        {"status": "error", "message": <error>} if error occurred
    """
    package_path = Path(path)
    
    # Check if file exists
    if not package_path.exists():
        return {"status": "error", "message": f"File not found: {path}"}
    
    try:
        # Read existing package.json
        with open(package_path, 'r') as f:
            package_data = json.load(f)
        
        # Ensure scripts object exists
        if "scripts" not in package_data:
            package_data["scripts"] = {}
        
        scripts = package_data["scripts"]
        
        # Define desired Auditor hooks
        auditor_hooks = {
            "pretest": "aud lint --workset",
            "prebuild": "aud ast-verify",
            "prepush": "aud taint-analyze"
        }
        
        changes = []
        
        for hook_name, auditor_cmd in auditor_hooks.items():
            if hook_name not in scripts:
                # Hook doesn't exist, add it
                scripts[hook_name] = auditor_cmd
                changes.append(f"Added {hook_name}: {auditor_cmd}")
            else:
                existing_cmd = scripts[hook_name]
                
                # Check if Auditor command is already present
                if auditor_cmd in existing_cmd:
                    # Already has the command, skip
                    continue
                
                # Prepend Auditor command with &&
                new_cmd = f"{auditor_cmd} && {existing_cmd}"
                scripts[hook_name] = new_cmd
                changes.append(f"Modified {hook_name}: prepended {auditor_cmd}")
        
        if not changes:
            return {"status": "unchanged"}
        
        # Write modified package.json with 2-space indent
        with open(package_path, 'w') as f:
            json.dump(package_data, f, indent=2)
            # Add trailing newline for consistency with npm
            f.write('\n')
        
        return {"status": "hooks_added", "details": changes}
        
    except json.JSONDecodeError as e:
        return {"status": "error", "message": f"Invalid JSON in {path}: {e}"}
    except Exception as e:
        return {"status": "error", "message": f"Error processing {path}: {e}"}
