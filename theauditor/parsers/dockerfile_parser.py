"""Parser for Dockerfile files.

This module provides parsing of Dockerfiles to extract
instructions for security analysis.
"""

from pathlib import Path
from typing import Dict, List, Any

try:
    from dockerfile_parse import DockerfileParser as DFParser
except ImportError:
    DFParser = None


class DockerfileParser:
    """Parser for Dockerfile files."""
    
    def __init__(self):
        """Initialize the Dockerfile parser."""
        pass
    
    def parse_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Parse a Dockerfile and extract all instructions.
        
        Args:
            file_path: Path to the Dockerfile
            
        Returns:
            Dictionary with parsed Dockerfile instructions:
            {
                'instructions': [
                    {
                        'instruction': 'FROM',
                        'value': 'python:3.11-slim',
                        'line': 1
                    },
                    ...
                ]
            }
        """
        try:
            # Check if dockerfile-parse is available
            if DFParser is None:
                return {
                    'instructions': [],
                    'error': 'dockerfile-parse library not installed'
                }
            
            # Read the file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse using dockerfile-parse library
            parser = DFParser(content=content)
            
            # Extract instructions with line numbers
            instructions = []
            lines = content.split('\n')
            current_line = 1
            
            for instruction_dict in parser.structure:
                # Extract instruction and value from the parser output
                instruction = instruction_dict.get('instruction', '').upper()
                value = instruction_dict.get('value', '')
                
                # Find the line number by searching for the instruction in the content
                # This is a simple approach - more sophisticated line tracking could be added
                for i, line in enumerate(lines[current_line-1:], start=current_line):
                    if line.strip().upper().startswith(instruction):
                        current_line = i
                        break
                
                if instruction:  # Only add non-empty instructions
                    instructions.append({
                        'instruction': instruction,
                        'value': value,
                        'line': current_line
                    })
                
                current_line += 1  # Move to next line for next instruction
            
            return {'instructions': instructions}
            
        except FileNotFoundError:
            return {
                'instructions': [],
                'error': f'File not found: {file_path}'
            }
        except PermissionError:
            return {
                'instructions': [],
                'error': f'Permission denied: {file_path}'
            }
        except Exception as e:
            # Handle any parsing exceptions from the library
            return {
                'instructions': [],
                'error': f'Parsing error: {str(e)}'
            }
    
    def parse_content(self, content: str, file_path: str = 'unknown') -> Dict[str, Any]:
        """
        Parse Dockerfile content string.
        
        Args:
            content: Dockerfile content as string
            file_path: Optional file path for reference
            
        Returns:
            Dictionary with parsed Dockerfile instructions
        """
        try:
            # Check if dockerfile-parse is available
            if DFParser is None:
                return {
                    'instructions': [],
                    'error': 'dockerfile-parse library not installed'
                }
            
            # Parse using dockerfile-parse library
            parser = DFParser(content=content)
            
            # Extract instructions with line numbers
            instructions = []
            lines = content.split('\n')
            current_line = 1
            
            for instruction_dict in parser.structure:
                # Extract instruction and value from the parser output
                instruction = instruction_dict.get('instruction', '').upper()
                value = instruction_dict.get('value', '')
                
                # Find the line number
                for i, line in enumerate(lines[current_line-1:], start=current_line):
                    if line.strip().upper().startswith(instruction):
                        current_line = i
                        break
                
                if instruction:  # Only add non-empty instructions
                    instructions.append({
                        'instruction': instruction,
                        'value': value,
                        'line': current_line
                    })
                
                current_line += 1
            
            return {'instructions': instructions}
            
        except Exception as e:
            return {
                'instructions': [],
                'error': f'Parsing error: {str(e)}'
            }