/**
 * GOLDEN MASTER INPUT FILE
 *
 * This file contains EVERY syntax feature the JavaScript/TypeScript extractor supports.
 * Hand-verified extraction output is saved as golden_master.json.
 *
 * If extraction results differ from the master, either:
 * 1. You broke the extractor (regression) - FIX IT
 * 2. You improved the extractor - UPDATE THE MASTER
 *
 * DO NOT modify this file casually. Changes require re-verification.
 */

// =============================================================================
// IMPORTS (various styles)
// =============================================================================
import defaultExport from 'module-a';
import * as namespaceImport from 'module-b';
import { namedImport, renamedImport as aliased } from 'module-c';
import type { TypeImport } from 'module-d';
const dynamicImport = () => import('module-e');
const require1 = require('module-f');

// =============================================================================
// EXPORTS (various styles)
// =============================================================================
export const exportedConst = 'value';
export function exportedFunction() { return 1; }
export class ExportedClass {}
export default class DefaultExportedClass {}
export { namedImport as reExported };
export * from 'module-g';

// =============================================================================
// FUNCTIONS (all declaration styles)
// =============================================================================

// Regular function declaration
function regularFunction(a: string, b: number): boolean {
    return a.length > b;
}

// Async function
async function asyncFunction(): Promise<void> {
    await Promise.resolve();
}

// Generator function
function* generatorFunction(): Generator<number> {
    yield 1;
    yield 2;
}

// Arrow function (const)
const arrowFunction = (x: number): number => x * 2;

// Arrow function (implicit return)
const implicitArrow = (x: number) => x * 2;

// Arrow function (block body)
const blockArrow = (x: number): number => {
    const doubled = x * 2;
    return doubled;
};

// IIFE
(function immediatelyInvoked() {
    console.log('IIFE');
})();

// Function with rest parameters
function restParams(...args: string[]): number {
    return args.length;
}

// Function with default parameters
function defaultParams(a: string = 'default', b: number = 42): string {
    return `${a}-${b}`;
}

// Function with destructuring parameters
function destructuringParams({ name, value }: { name: string; value: number }): void {
    console.log(name, value);
}

// =============================================================================
// CLASSES (comprehensive)
// =============================================================================

// Abstract class
abstract class AbstractBase {
    abstract abstractMethod(): void;

    concreteMethod(): string {
        return 'concrete';
    }
}

// Class with everything
class CompleteClass extends AbstractBase implements SomeInterface {
    // Static members
    static staticProperty: string = 'static';
    static staticMethod(): void {}

    // Instance members with visibility
    public publicProperty: string;
    protected protectedProperty: number;
    private privateProperty: boolean;
    readonly readonlyProperty: string = 'readonly';

    // Private field (ES2022)
    #truePrivateField: string = 'truly private';

    // Constructor
    constructor(
        public constructorPublic: string,
        private constructorPrivate: number
    ) {
        super();
        this.publicProperty = 'value';
        this.protectedProperty = 42;
        this.privateProperty = true;
    }

    // Methods with various modifiers
    public publicMethod(): void {}
    protected protectedMethod(): void {}
    private privateMethod(): void {}

    // Getters and setters
    get computedValue(): string {
        return this.publicProperty;
    }

    set computedValue(val: string) {
        this.publicProperty = val;
    }

    // Async method
    async asyncMethod(): Promise<string> {
        return 'async';
    }

    // Implementation of abstract
    abstractMethod(): void {
        console.log('implemented');
    }
}

// Generic class
class GenericClass<T, U extends string> {
    constructor(public value: T, public label: U) {}

    getValue(): T {
        return this.value;
    }
}

// =============================================================================
// INTERFACES AND TYPES
// =============================================================================

interface SomeInterface {
    requiredProp: string;
    optionalProp?: number;
    methodSignature(arg: string): boolean;
}

interface ExtendedInterface extends SomeInterface {
    additionalProp: boolean;
}

// Generic interface
interface GenericInterface<T> {
    data: T;
    process(input: T): T;
}

// Type aliases
type StringOrNumber = string | number;
type ObjectType = { x: number; y: number };
type FunctionType = (a: string) => boolean;
type ConditionalType<T> = T extends string ? 'string' : 'other';
type MappedType = { [K in 'a' | 'b']: number };

// =============================================================================
// ENUMS
// =============================================================================

enum NumericEnum {
    First,
    Second,
    Third
}

enum StringEnum {
    Red = 'RED',
    Green = 'GREEN',
    Blue = 'BLUE'
}

const enum ConstEnum {
    A = 1,
    B = 2
}

// =============================================================================
// VARIABLES (various declaration styles)
// =============================================================================

const constVariable: string = 'const';
let letVariable: number = 42;
var varVariable: boolean = true;

// Destructuring declarations
const { destructuredA, destructuredB: renamedB } = { destructuredA: 1, destructuredB: 2 };
const [arrayDestructured1, arrayDestructured2] = [1, 2];

// =============================================================================
// CONTROL FLOW (for CFG extraction)
// =============================================================================

function controlFlowExample(x: number): string {
    // If-else
    if (x > 0) {
        return 'positive';
    } else if (x < 0) {
        return 'negative';
    } else {
        return 'zero';
    }
}

function loopExample(items: string[]): void {
    // For loop
    for (let i = 0; i < items.length; i++) {
        console.log(items[i]);
    }

    // For-of loop
    for (const item of items) {
        console.log(item);
    }

    // For-in loop
    for (const key in items) {
        console.log(key);
    }

    // While loop
    let j = 0;
    while (j < 10) {
        j++;
    }

    // Do-while loop
    do {
        j--;
    } while (j > 0);
}

function switchExample(value: string): number {
    switch (value) {
        case 'a':
            return 1;
        case 'b':
            return 2;
        default:
            return 0;
    }
}

function tryExample(): void {
    try {
        throw new Error('test');
    } catch (e) {
        console.error(e);
    } finally {
        console.log('cleanup');
    }
}

// =============================================================================
// DECORATORS (Angular/NestJS style)
// =============================================================================

function ClassDecorator(target: any) {
    return target;
}

function MethodDecorator(target: any, key: string, descriptor: PropertyDescriptor) {
    return descriptor;
}

function PropertyDecorator(target: any, key: string) {}

@ClassDecorator
class DecoratedClass {
    @PropertyDecorator
    decoratedProperty: string = 'decorated';

    @MethodDecorator
    decoratedMethod(): void {}
}

// =============================================================================
// JSX/TSX (React patterns)
// =============================================================================

interface ComponentProps {
    name: string;
    count?: number;
}

// Function component
function FunctionComponent(props: ComponentProps): JSX.Element {
    return <div className="component">{props.name}</div>;
}

// Arrow function component
const ArrowComponent: React.FC<ComponentProps> = ({ name, count = 0 }) => {
    return (
        <div>
            <span>{name}</span>
            <span>{count}</span>
        </div>
    );
};

// Class component
class ClassComponent extends React.Component<ComponentProps> {
    render() {
        return <div>{this.props.name}</div>;
    }
}

// Hooks usage
function HooksComponent(): JSX.Element {
    const [state, setState] = React.useState(0);
    const ref = React.useRef<HTMLDivElement>(null);

    React.useEffect(() => {
        console.log('effect');
        return () => console.log('cleanup');
    }, [state]);

    const memoized = React.useMemo(() => state * 2, [state]);
    const callback = React.useCallback(() => setState(s => s + 1), []);

    return <div ref={ref}>{memoized}</div>;
}

// =============================================================================
// SECURITY PATTERNS (for security extractors)
// =============================================================================

// Potential XSS sink
function xssSink(userInput: string): void {
    document.innerHTML = userInput; // Dangerous!
    element.insertAdjacentHTML('beforeend', userInput);
}

// SQL-like patterns
const sqlQuery = `SELECT * FROM users WHERE id = ${userId}`;

// Eval usage
const evalResult = eval('1 + 1');

// =============================================================================
// ASYNC PATTERNS
// =============================================================================

// Promise chain
function promiseChain(): Promise<string> {
    return fetch('/api')
        .then(res => res.json())
        .then(data => data.value)
        .catch(err => 'error');
}

// Async/await with error handling
async function asyncAwaitPattern(): Promise<void> {
    try {
        const response = await fetch('/api');
        const data = await response.json();
        console.log(data);
    } catch (error) {
        console.error(error);
    }
}

// Promise.all
async function parallelAsync(): Promise<string[]> {
    const results = await Promise.all([
        fetch('/api/1').then(r => r.text()),
        fetch('/api/2').then(r => r.text()),
    ]);
    return results;
}

// =============================================================================
// MODULE PATTERNS
// =============================================================================

// Namespace (legacy)
namespace LegacyNamespace {
    export const value = 42;
    export function helper(): void {}
}

// Module augmentation
declare module 'some-module' {
    interface ExistingInterface {
        newProperty: string;
    }
}

// Global augmentation
declare global {
    interface Window {
        customProperty: string;
    }
}

// =============================================================================
// EDGE CASES
// =============================================================================

// Unicode identifiers
const 変数 = 'japanese';
const émoji = '🎉';

// Computed property names
const computedKey = 'dynamic';
const objWithComputed = {
    [computedKey]: 'value',
    [`prefix_${computedKey}`]: 'prefixed'
};

// Template literals with expressions
const template = `Value: ${constVariable}, Computed: ${1 + 2}`;

// Tagged template literal
function tag(strings: TemplateStringsArray, ...values: any[]): string {
    return strings.join('');
}
const tagged = tag`Hello ${'world'}`;

// Nullish coalescing and optional chaining
const nullish = null ?? 'default';
const optional = objWithComputed?.nested?.value;

// BigInt
const bigNumber = 9007199254740991n;

// Symbols
const symbolKey = Symbol('description');
const objWithSymbol = { [symbolKey]: 'symbol value' };
