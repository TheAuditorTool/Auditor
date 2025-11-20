"""
Django Advanced Pattern Extractors (Phase 3.4)

This module contains extractors for advanced Django patterns:
- Django signals (signal definitions and connections)
- Django receivers (@receiver decorators)
- Django custom managers (BaseManager/Manager subclasses)
- Django QuerySet methods (custom querysets)

These extractors identify Django-specific patterns for:
- Event-driven architecture analysis
- Signal/receiver dependency tracking
- Custom ORM manager/queryset usage
- Django application flow analysis

All extractors follow architectural contract: NO file_path in results.
"""
from theauditor.ast_extractors.python.utils.context import FileContext


from typing import Dict, List, Any


def extract_django_signals(context: FileContext) -> list[dict[str, Any]]:
    """
    Extract Django signal definitions and connections.

    Detects:
    - django.dispatch.Signal() definitions
    - signal.connect() calls
    - Signal subclass definitions
    - providing_args parameter

    Security relevance:
    - Signals can trigger privileged operations
    - Signal receivers may bypass authentication
    - Signal chains can create TOCTOU vulnerabilities

    Returns:
        List of dicts with keys:
        - line: int
        - signal_name: str
        - signal_type: str (definition, connection, custom)
        - providing_args: str (JSON array of argument names)
        - sender: str (optional - for connections)
        - receiver_function: str (optional - for connections)
    """
    results = []

    # Signal() instantiation: my_signal = Signal()
    for assign in tree.get('assignments', []):
        if 'Signal(' in assign.get('value', ''):
            signal_name = assign.get('target', 'unknown')
            value = assign.get('value', '')

            # Extract providing_args if present
            providing_args = '[]'
            if 'providing_args=' in value:
                # Simple extraction - could be improved with AST parsing
                start = value.find('providing_args=')
                if start != -1:
                    # Extract the list
                    rest = value[start + len('providing_args='):]
                    if rest.startswith('['):
                        end = rest.find(']')
                        if end != -1:
                            providing_args = rest[:end + 1]

            results.append({
                'line': assign.get('line', 0),
                'signal_name': signal_name,
                'signal_type': 'definition',
                'providing_args': providing_args,
                'sender': None,
                'receiver_function': None
            })

    # signal.connect() calls
    for call in tree.get('function_calls', []):
        if '.connect(' in call.get('function', ''):
            # Extract signal name from "my_signal.connect"
            func_name = call.get('function', '')
            if '.' in func_name:
                signal_name = func_name.split('.connect')[0]
            else:
                signal_name = 'unknown'

            # Try to extract receiver function from arguments
            receiver_function = None
            args = call.get('arguments', [])
            if args and len(args) > 0:
                receiver_function = args[0].get('value', 'unknown')

            # Try to extract sender from keyword arguments
            sender = None
            for arg in args:
                if arg.get('name') == 'sender':
                    sender = arg.get('value', 'unknown')

            results.append({
                'line': call.get('line', 0),
                'signal_name': signal_name,
                'signal_type': 'connection',
                'providing_args': '[]',
                'sender': sender,
                'receiver_function': receiver_function
            })

    # Custom Signal subclasses
    for cls in tree.get('classes', []):
        bases = cls.get('bases', [])
        if any('Signal' in base for base in bases):
            results.append({
                'line': cls.get('line', 0),
                'signal_name': cls.get('name', 'unknown'),
                'signal_type': 'custom',
                'providing_args': '[]',
                'sender': None,
                'receiver_function': None
            })

    return results


def extract_django_receivers(context: FileContext) -> list[dict[str, Any]]:
    """
    Extract Django @receiver decorators.

    Detects:
    - @receiver(signal_name) decorators
    - Multiple signals in one decorator
    - sender parameter

    Security relevance:
    - Receivers can bypass normal authentication flow
    - Receivers may have elevated privileges
    - Race conditions in signal handlers
    - TOCTOU between signal and receiver

    Returns:
        List of dicts with keys:
        - line: int
        - function_name: str
        - signals: str (JSON array of signal names)
        - sender: str (optional)
        - is_weak: bool (weak=True/False parameter)
    """
    results = []

    # Find all functions with @receiver decorator
    for func in tree.get('functions', []):
        decorators = func.get('decorators', [])

        for decorator in decorators:
            if 'receiver' in decorator.get('name', ''):
                # Extract signal names from decorator arguments
                signals = []
                sender = None
                is_weak = False

                # Parse decorator string to extract signals
                # Format: @receiver(post_save, sender=MyModel)
                decorator_str = decorator.get('name', '')

                # Simple extraction - get first argument as signal
                if '(' in decorator_str:
                    args_str = decorator_str[decorator_str.find('(') + 1:decorator_str.rfind(')')]
                    parts = args_str.split(',')

                    for part in parts:
                        part = part.strip()
                        if '=' in part:
                            # Keyword argument
                            key, val = part.split('=', 1)
                            key = key.strip()
                            val = val.strip()

                            if key == 'sender':
                                sender = val
                            elif key == 'weak':
                                is_weak = val.lower() == 'true'
                        else:
                            # Positional argument - signal name
                            if part and part not in ['receiver', '']:
                                signals.append(part)

                import json
                results.append({
                    'line': func.get('line', 0),
                    'function_name': func.get('name', 'unknown'),
                    'signals': json.dumps(signals),
                    'sender': sender,
                    'is_weak': is_weak
                })

    return results


def extract_django_managers(context: FileContext) -> list[dict[str, Any]]:
    """
    Extract Django custom manager definitions.

    Detects:
    - models.Manager subclasses
    - Custom manager methods
    - .objects assignments in models
    - Multiple managers per model

    Security relevance:
    - Custom managers can bypass row-level security
    - Manager methods may not respect permissions
    - Queryset filtering can be security boundary

    Returns:
        List of dicts with keys:
        - line: int
        - manager_name: str
        - base_class: str (Manager, BaseManager, etc.)
        - custom_methods: str (JSON array of method names)
        - model_assignment: str (Model.objects = ManagerName())
    """
    results = []

    # Find Manager subclasses
    for cls in tree.get('classes', []):
        bases = cls.get('bases', [])

        # Check if inherits from Manager or BaseManager
        manager_base = None
        for base in bases:
            if 'Manager' in base:
                manager_base = base
                break

        if manager_base:
            # Extract custom methods
            methods = cls.get('methods', [])
            custom_methods = []

            for method in methods:
                method_name = method.get('name', '')
                # Exclude special methods and get_queryset
                if not method_name.startswith('_') and method_name not in ['get_queryset']:
                    custom_methods.append(method_name)

            import json
            results.append({
                'line': cls.get('line', 0),
                'manager_name': cls.get('name', 'unknown'),
                'base_class': manager_base,
                'custom_methods': json.dumps(custom_methods),
                'model_assignment': None
            })

    # Find manager assignments in models
    # Pattern: objects = MyManager()
    for cls in tree.get('classes', []):
        # Check if this is a Model class
        bases = cls.get('bases', [])
        is_model = any('Model' in base for base in bases)

        if is_model:
            # Look for .objects assignments in class body
            for assign in tree.get('assignments', []):
                if assign.get('target', '').endswith('.objects'):
                    # Extract model name and manager
                    target = assign.get('target', '')
                    model_name = target.split('.')[0] if '.' in target else 'unknown'
                    manager_value = assign.get('value', '')

                    results.append({
                        'line': assign.get('line', 0),
                        'manager_name': manager_value.replace('()', '').replace('=', '').strip(),
                        'base_class': 'Manager',
                        'custom_methods': '[]',
                        'model_assignment': f'{model_name}.objects'
                    })

    return results


def extract_django_querysets(context: FileContext) -> list[dict[str, Any]]:
    """
    Extract Django QuerySet method definitions and chains.

    Detects:
    - QuerySet subclasses
    - Custom queryset methods
    - Queryset method chains (.filter().exclude().order_by())
    - as_manager() pattern

    Security relevance:
    - QuerySets define data access boundaries
    - Custom filters may have security implications
    - Method chaining can bypass security checks
    - as_manager() exposes queryset methods on model

    Returns:
        List of dicts with keys:
        - line: int
        - queryset_name: str
        - base_class: str (QuerySet)
        - custom_methods: str (JSON array of method names)
        - has_as_manager: bool
        - method_chain: str (optional - for queryset chains)
    """
    results = []

    # Find QuerySet subclasses
    for cls in tree.get('classes', []):
        bases = cls.get('bases', [])

        # Check if inherits from QuerySet
        queryset_base = None
        for base in bases:
            if 'QuerySet' in base:
                queryset_base = base
                break

        if queryset_base:
            # Extract custom methods
            methods = cls.get('methods', [])
            custom_methods = []
            has_as_manager = False

            for method in methods:
                method_name = method.get('name', '')
                # Exclude special methods
                if not method_name.startswith('_'):
                    custom_methods.append(method_name)

            # Check for as_manager assignment
            # Pattern: MyModel.objects = MyQuerySet.as_manager()
            for assign in tree.get('assignments', []):
                if cls.get('name', '') in assign.get('value', '') and 'as_manager()' in assign.get('value', ''):
                    has_as_manager = True

            import json
            results.append({
                'line': cls.get('line', 0),
                'queryset_name': cls.get('name', 'unknown'),
                'base_class': queryset_base,
                'custom_methods': json.dumps(custom_methods),
                'has_as_manager': has_as_manager,
                'method_chain': None
            })

    # Find queryset method chains
    # Pattern: Model.objects.filter().exclude().order_by()
    for call in tree.get('function_calls', []):
        func_name = call.get('function', '')

        # Check for queryset method chains
        queryset_methods = ['filter', 'exclude', 'order_by', 'select_related', 'prefetch_related',
                           'annotate', 'aggregate', 'values', 'values_list', 'distinct']

        if any(f'.{method}(' in func_name for method in queryset_methods):
            # Extract the full chain
            method_chain = func_name

            results.append({
                'line': call.get('line', 0),
                'queryset_name': 'chain',
                'base_class': 'QuerySet',
                'custom_methods': '[]',
                'has_as_manager': False,
                'method_chain': method_chain
            })

    return results
