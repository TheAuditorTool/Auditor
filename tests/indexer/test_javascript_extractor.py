from pathlib import Path

from theauditor.indexer.extractors.javascript import JavaScriptExtractor


def make_extractor():
    return JavaScriptExtractor(root_path=Path('.'), ast_parser=None)


def test_react_component_requires_jsx_or_react_import():
    extractor = make_extractor()
    file_info = {'path': 'frontend/components/Dashboard.tsx'}
    extracted = {
        'imports': [('from', 'react')],
        'symbols': [{'name': 'Dashboard', 'type': 'function', 'line': 5}],
        'returns': [{'function_name': 'Dashboard', 'return_expr': '<View />'}],
    }
    components = extractor._detect_react_components(file_info, '<View />', extracted)
    assert components and components[0]['name'] == 'Dashboard'

    backend_info = {'path': 'backend/controllers/AccountController.ts'}
    backend_symbols = {
        'imports': [('from', 'express')],
        'symbols': [{'name': 'AccountController', 'type': 'class', 'line': 10}],
        'returns': [{'function_name': 'AccountController', 'return_expr': ''}],
    }
    backend_components = extractor._detect_react_components(backend_info, '', backend_symbols)
    assert backend_components == []


def test_react_hooks_ignore_non_components_and_methods():
    extractor = make_extractor()
    components = [{'name': 'Dashboard'}]
    function_calls = [
        {'line': 10, 'caller_function': 'Dashboard', 'callee_function': 'useState'},
        {'line': 11, 'caller_function': 'Dashboard', 'callee_function': 'React.useEffect'},
        {'line': 12, 'caller_function': 'Dashboard', 'callee_function': 'users.map'},
        {'line': 13, 'caller_function': 'Dashboard', 'callee_function': 'users.useFetch'},
    ]
    hooks = extractor._detect_react_hooks(components, function_calls)
    hook_names = {hook['name'] for hook in hooks}
    assert hook_names == {'useState', 'useEffect'}


def test_sql_query_detection_filters_noise():
    extractor = make_extractor()
    valid_content = """
    const query = `SELECT id, name FROM users WHERE id = ?`;
    """
    queries = extractor.extract_sql_queries(valid_content)
    assert len(queries) == 1
    assert queries[0]['command'] == 'SELECT'
    assert 'users' in queries[0]['tables']

    noisy_content = "const text = 'export class AccountController {}';"
    assert extractor.extract_sql_queries(noisy_content) == []

    ambiguous_content = "const q = `INSERT INTO logs(message) VALUES($1);`;"
    insert_queries = extractor.extract_sql_queries(ambiguous_content)
    assert len(insert_queries) == 1
    assert insert_queries[0]['command'] == 'INSERT'
    assert 'logs' in insert_queries[0]['tables']
