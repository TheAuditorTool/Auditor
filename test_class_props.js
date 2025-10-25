const ts = require('C:/Users/santa/Desktop/TheAuditor/.auditor_venv/.theauditor_tools/node_modules/typescript/lib/typescript.js');

const code = `
class User {
  declare username: string;
  declare email: string | null;
  private password_hash: string;
}
`;

const sourceFile = ts.createSourceFile('test.ts', code, ts.ScriptTarget.Latest, true);

// Inline extractClassProperties for testing
function extractClassProperties(sourceFile, ts) {
    const properties = [];
    let currentClass = null;

    function traverse(node) {
        if (!node) return;
        const kind = ts.SyntaxKind[node.kind];

        if (kind === 'ClassDeclaration' || kind === 'ClassExpression') {
            const previousClass = currentClass;
            currentClass = node.name ? (node.name.text || node.name.escapedText || 'UnknownClass') : 'UnknownClass';
            ts.forEachChild(node, traverse);
            currentClass = previousClass;
            return;
        }

        if (kind === 'PropertyDeclaration' && currentClass) {
            const { line } = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile));
            const propertyName = node.name ? (node.name.text || node.name.escapedText || '') : '';

            if (!propertyName) {
                ts.forEachChild(node, traverse);
                return;
            }

            const property = {
                line: line + 1,
                class_name: currentClass,
                property_name: propertyName
            };

            properties.push(property);
        }

        ts.forEachChild(node, traverse);
    }

    traverse(sourceFile);
    return properties;
}

const props = extractClassProperties(sourceFile, ts);
console.log('Extracted ' + props.length + ' properties');
props.forEach(p => console.log('  ' + p.class_name + '.' + p.property_name + ' at line ' + p.line));
