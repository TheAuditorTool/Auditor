"""
NODE EXTRACTOR OUTPUT AUDIT - TRUTH SERUM

This script runs the JavaScript/TypeScript extractor against a comprehensive sample
and reports the ACTUAL dictionary keys it returns.

NO GUESSING. NO HALLUCINATING. JUST FACTS.

Usage:
    python scripts/audit_node_extractors.py
    python scripts/audit_node_extractors.py > node_extractor_truth.txt
"""

import os
import sys
import tempfile
from pathlib import Path


sys.path.insert(0, os.getcwd())


KITCHEN_SINK_CODE = """
// ============================================================
// IMPORTS - Various styles
// ============================================================
import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { Router, Request, Response, NextFunction } from 'express';
import { Component, NgModule, Injectable, OnInit, OnDestroy } from '@angular/core';
import { defineComponent, ref, computed, watch, watchEffect, onMounted, onUnmounted, provide, inject } from 'vue';
import { Model, DataTypes, Sequelize, Op } from 'sequelize';
import { Queue, Worker, Job } from 'bullmq';
import axios from 'axios';
import * as fs from 'fs';
import { z } from 'zod';

// ============================================================
// REACT COMPONENTS & HOOKS
// ============================================================
interface UserProps {
    userId: number;
    showDetails?: boolean;
}

const UserProfile: React.FC<UserProps> = ({ userId, showDetails = false }) => {
    const [user, setUser] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const mountedRef = useRef(true);

    // useEffect with dependency array
    useEffect(() => {
        async function fetchUser() {
            try {
                // TAINT: userId flows to API call
                const response = await axios.get(`/api/users/${userId}`);
                if (mountedRef.current) {
                    setUser(response.data);
                }
            } catch (err: any) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        }
        fetchUser();

        // Cleanup function
        return () => {
            mountedRef.current = false;
        };
    }, [userId]);

    // useCallback hook
    const handleUpdate = useCallback(async () => {
        await axios.put(`/api/users/${userId}`, { lastSeen: new Date() });
    }, [userId]);

    // useMemo hook
    const fullName = useMemo(() => {
        if (!user) return '';
        return `${user.firstName} ${user.lastName}`;
    }, [user]);

    if (loading) return <div>Loading...</div>;
    if (error) return <div>Error: {error}</div>;

    return (
        <div className="user-profile">
            <h2>{fullName}</h2>
            {showDetails && <UserDetails userId={userId} />}
            <button onClick={handleUpdate}>Update</button>
        </div>
    );
};

// Class component for completeness
class UserDashboard extends React.Component<{}, { count: number }> {
    state = { count: 0 };

    componentDidMount() {
        console.log('Dashboard mounted');
    }

    componentWillUnmount() {
        console.log('Dashboard unmounting');
    }

    render() {
        return <div>Count: {this.state.count}</div>;
    }
}

// ============================================================
// VUE COMPONENTS (Options API and Composition API)
// ============================================================

// Options API style
const VueUserCard = {
    name: 'UserCard',
    props: {
        userId: {
            type: Number,
            required: true
        },
        showAvatar: {
            type: Boolean,
            default: true
        },
        userName: String  // Simple format
    },
    emits: ['update', 'delete', 'select'],
    data() {
        return {
            loading: false,
            userData: null
        };
    },
    computed: {
        displayName() {
            return this.userData?.name || 'Unknown';
        }
    },
    methods: {
        async fetchData() {
            this.loading = true;
            const response = await axios.get(`/api/users/${this.userId}`);
            this.userData = response.data;
            this.loading = false;
        },
        handleUpdate() {
            this.$emit('update', this.userData);
        }
    },
    mounted() {
        this.fetchData();
    }
};

// Composition API style
const VueProductList = defineComponent({
    name: 'ProductList',
    props: {
        categoryId: {
            type: Number,
            required: true
        },
        filters: Object
    },
    emits: {
        'product-selected': (product: any) => true,
        'filters-changed': null
    },
    setup(props, { emit }) {
        const products = ref<any[]>([]);
        const loading = ref(false);
        const searchQuery = ref('');

        const filteredProducts = computed(() => {
            return products.value.filter(p =>
                p.name.toLowerCase().includes(searchQuery.value.toLowerCase())
            );
        });

        watch(() => props.categoryId, async (newId) => {
            loading.value = true;
            const response = await axios.get(`/api/categories/${newId}/products`);
            products.value = response.data;
            loading.value = false;
        }, { immediate: true });

        watchEffect(() => {
            console.log('Products count:', products.value.length);
        });

        const selectProduct = (product: any) => {
            emit('product-selected', product);
        };

        // Provide/Inject
        provide('productContext', { products, loading });

        onMounted(() => {
            console.log('ProductList mounted');
        });

        onUnmounted(() => {
            console.log('ProductList unmounted');
        });

        return {
            products,
            loading,
            searchQuery,
            filteredProducts,
            selectProduct
        };
    }
});

// ============================================================
// ANGULAR COMPONENTS, SERVICES, MODULES
// ============================================================

@Injectable({
    providedIn: 'root'
})
class AuthService {
    private token: string | null = null;

    login(username: string, password: string): Promise<boolean> {
        // TAINT: credentials flow to API
        return axios.post('/api/auth/login', { username, password })
            .then(res => {
                this.token = res.data.token;
                return true;
            });
    }

    logout(): void {
        this.token = null;
    }

    isAuthenticated(): boolean {
        return this.token !== null;
    }
}

@Injectable()
class UserService {
    constructor(private authService: AuthService) {}

    async getUser(id: number): Promise<any> {
        // TAINT: id flows to API call
        const response = await axios.get(`/api/users/${id}`);
        return response.data;
    }
}

@Component({
    selector: 'app-user-list',
    templateUrl: './user-list.component.html',
    styleUrls: ['./user-list.component.scss', './user-list.theme.scss']
})
class UserListComponent implements OnInit, OnDestroy {
    users: any[] = [];
    loading = false;

    constructor(
        private userService: UserService,
        private authService: AuthService
    ) {}

    ngOnInit(): void {
        this.loadUsers();
    }

    ngOnDestroy(): void {
        console.log('UserListComponent destroyed');
    }

    async loadUsers(): Promise<void> {
        this.loading = true;
        this.users = await this.userService.getUser(1);
        this.loading = false;
    }
}

@Component({
    selector: 'app-dashboard',
    template: '<div>Dashboard</div>'
})
class DashboardComponent {}

@NgModule({
    declarations: [
        UserListComponent,
        DashboardComponent
    ],
    imports: [
        CommonModule,
        FormsModule,
        RouterModule
    ],
    providers: [
        UserService,
        { provide: AuthService, useClass: AuthService }
    ],
    exports: [
        UserListComponent
    ]
})
class UserModule {}

// Angular Guard
@Injectable({
    providedIn: 'root'
})
class AuthGuard {
    constructor(private authService: AuthService) {}

    canActivate(): boolean {
        return this.authService.isAuthenticated();
    }
}

// ============================================================
// EXPRESS ROUTES & MIDDLEWARE
// ============================================================
const router = Router();

// Middleware
const authMiddleware = (req: Request, res: Response, next: NextFunction) => {
    const token = req.headers.authorization;
    if (!token) {
        return res.status(401).json({ error: 'Unauthorized' });
    }
    next();
};

const loggerMiddleware = (req: Request, res: Response, next: NextFunction) => {
    console.log(`${req.method} ${req.path}`);
    next();
};

// Routes with middleware chains
router.get('/api/users', authMiddleware, async (req: Request, res: Response) => {
    // TAINT: query params flow to database
    const { page, limit, search } = req.query;
    const users = await db.query(`SELECT * FROM users WHERE name LIKE '%${search}%' LIMIT ${limit}`);
    res.json(users);
});

router.get('/api/users/:id', authMiddleware, async (req: Request, res: Response) => {
    // TAINT: id from URL flows to database
    const { id } = req.params;
    const user = await db.query(`SELECT * FROM users WHERE id = ${id}`);
    res.json(user);
});

router.post('/api/users', authMiddleware, async (req: Request, res: Response) => {
    // TAINT: body flows to database
    const { name, email } = req.body;
    await db.query(`INSERT INTO users (name, email) VALUES ('${name}', '${email}')`);
    res.status(201).json({ success: true });
});

router.put('/api/users/:id', [authMiddleware, loggerMiddleware], async (req: Request, res: Response) => {
    const { id } = req.params;
    const { name } = req.body;
    await db.query(`UPDATE users SET name = '${name}' WHERE id = ${id}`);
    res.json({ success: true });
});

router.delete('/api/users/:id', authMiddleware, async (req: Request, res: Response) => {
    const { id } = req.params;
    await db.query(`DELETE FROM users WHERE id = ${id}`);
    res.status(204).send();
});

// ============================================================
// SEQUELIZE ORM
// ============================================================
class User extends Model {
    declare id: number;
    declare name: string;
    declare email: string;
}

User.init({
    id: {
        type: DataTypes.INTEGER,
        primaryKey: true,
        autoIncrement: true
    },
    name: {
        type: DataTypes.STRING,
        allowNull: false
    },
    email: {
        type: DataTypes.STRING,
        unique: true
    }
}, {
    sequelize,
    tableName: 'users',
    modelName: 'User'
});

class Post extends Model {}
Post.init({
    title: DataTypes.STRING,
    content: DataTypes.TEXT
}, { sequelize, modelName: 'Post' });

// Associations
User.hasMany(Post, { foreignKey: 'authorId' });
Post.belongsTo(User, { foreignKey: 'authorId' });

// ============================================================
// BULLMQ JOB QUEUES
// ============================================================
const emailQueue = new Queue('email-notifications', {
    connection: { host: 'localhost', port: 6379 }
});

const processQueue = new Queue('data-processing');

const emailWorker = new Worker('email-notifications', async (job: Job) => {
    const { to, subject, body } = job.data;
    await sendEmail(to, subject, body);
    return { sent: true };
}, {
    connection: { host: 'localhost', port: 6379 }
});

const processWorker = new Worker('data-processing', './workers/process.js');

// ============================================================
// SQL QUERIES (Vulnerable patterns for taint analysis)
// ============================================================
async function vulnerableQueries(userInput: string) {
    // SQL Injection vulnerabilities
    const query1 = `SELECT * FROM users WHERE name = '${userInput}'`;
    const query2 = "SELECT * FROM products WHERE id = " + userInput;

    await db.query(query1);
    await db.execute(`DELETE FROM logs WHERE user = '${userInput}'`);

    // Parameterized (safe)
    await db.query('SELECT * FROM users WHERE id = ?', [userInput]);
}

// ============================================================
// FRONTEND API CALLS (Cross-boundary taint tracking)
// ============================================================
async function fetchUserData(userId: string) {
    // fetch() calls
    const response1 = await fetch(`/api/users/${userId}`);
    const response2 = await fetch('/api/products', {
        method: 'POST',
        body: JSON.stringify({ userId })
    });

    // axios calls
    const axiosGet = await axios.get(`/api/orders/${userId}`);
    const axiosPost = await axios.post('/api/checkout', { userId, items: [] });
    const axiosPut = await axios.put(`/api/users/${userId}`, { name: 'Updated' });
    const axiosDelete = await axios.delete(`/api/users/${userId}`);
}

// ============================================================
// TYPE ANNOTATIONS (TypeScript)
// ============================================================
interface Product {
    id: number;
    name: string;
    price: number;
}

type Status = 'pending' | 'active' | 'completed';

class TypedClass {
    private id: number;
    public name: string;
    protected status: Status;
    readonly createdAt: Date;

    constructor(id: number, name: string) {
        this.id = id;
        this.name = name;
        this.status = 'pending';
        this.createdAt = new Date();
    }

    async process(): Promise<boolean> {
        return true;
    }
}

// Generic function
function identity<T>(arg: T): T {
    return arg;
}

// ============================================================
// ZOD VALIDATION (Sanitizer detection)
// ============================================================
const userSchema = z.object({
    name: z.string().min(1).max(100),
    email: z.string().email(),
    age: z.number().int().positive()
});

function validateUser(input: unknown) {
    return userSchema.parse(input);
}

// ============================================================
// EXPORTS
// ============================================================
export { UserProfile, VueUserCard, VueProductList, UserModule, router };
export default UserProfile;
"""


def format_value(value: any, max_len: int = 80) -> str:
    """Format a value for display, truncating if needed."""
    if value is None:
        return "None"
    s = str(value)
    if len(s) > max_len:
        return s[: max_len - 3] + "..."
    return s


def audit():
    """Run the Node extractor audit."""
    print("=" * 80)
    print("NODE EXTRACTOR OUTPUT AUDIT - TRUTH SERUM")
    print("=" * 80)
    print()
    print("This audit runs the JavaScriptExtractor against a comprehensive sample")
    print("and reports the ACTUAL dictionary keys and value samples it returns.")
    print()

    try:
        from theauditor.indexer.extractors.javascript import JavaScriptExtractor
        from theauditor.js_semantic_parser import JSSemanticParser
    except ImportError as e:
        print(f"[ERROR] Failed to import required modules: {e}")
        print("Make sure you're running from the project root.")
        sys.exit(1)

    temp_dir = Path(tempfile.gettempdir()) / "theauditor_audit"
    temp_dir.mkdir(exist_ok=True)
    temp_file = temp_dir / "kitchen_sink.tsx"

    print(f"[INFO] Writing sample code to: {temp_file}")
    temp_file.write_text(KITCHEN_SINK_CODE, encoding="utf-8")

    print("[INFO] Initializing JSSemanticParser...")
    try:
        parser = JSSemanticParser(project_root=str(temp_dir))
    except Exception as e:
        print(f"[ERROR] Failed to initialize parser: {e}")
        print("[INFO] This may be expected if Node.js runtime is not configured.")
        print("[INFO] Falling back to showing expected schema structure...")
        show_expected_schema()
        return

    print("[INFO] Initializing JavaScriptExtractor...")
    extractor = JavaScriptExtractor(root_path=str(temp_dir))
    extractor.ast_parser = parser

    print("[INFO] Parsing sample code...")
    try:
        tree = parser.get_semantic_ast(str(temp_file))
    except Exception as e:
        print(f"[ERROR] Failed to parse: {e}")
        print("[INFO] Falling back to showing expected schema structure...")
        show_expected_schema()
        return

    if not tree:
        print("[ERROR] Parser returned empty tree")
        show_expected_schema()
        return

    print(
        "[DEBUG] Parser returned tree with keys:",
        list(tree.keys()) if isinstance(tree, dict) else type(tree),
    )
    if isinstance(tree, dict):
        if "extracted_data" in tree:
            ed = tree["extracted_data"]
            print(
                "[DEBUG] extracted_data keys:",
                list(ed.keys()) if isinstance(ed, dict) else type(ed),
            )
            if isinstance(ed, dict):
                for k, v in ed.items():
                    if isinstance(v, list) and len(v) > 0:
                        print(f"[DEBUG]   {k}: {len(v)} items")
        elif "tree" in tree:
            inner = tree["tree"]
            if isinstance(inner, dict) and "extracted_data" in inner:
                ed = inner["extracted_data"]
                print(
                    "[DEBUG] tree.extracted_data keys:",
                    list(ed.keys()) if isinstance(ed, dict) else type(ed),
                )
        if "error" in tree:
            print(f"[DEBUG] Parser error: {tree['error']}")
            print("[INFO] TypeScript compiler not available - showing expected schema instead.")
            show_expected_schema()
            return

    print("[INFO] Running extraction...")
    file_info = {"path": str(temp_file), "extension": ".tsx", "size": len(KITCHEN_SINK_CODE)}

    try:
        result = extractor.extract(file_info, KITCHEN_SINK_CODE, tree)
    except Exception as e:
        print(f"[ERROR] Extraction failed: {e}")
        import traceback

        traceback.print_exc()
        show_expected_schema()
        return

    print()
    print("=" * 80)
    print("EXTRACTION RESULTS")
    print("=" * 80)

    keys_with_data = []
    keys_without_data = []

    for key in sorted(result.keys()):
        value = result[key]
        if isinstance(value, list) and len(value) > 0 or isinstance(value, dict) and len(value) > 0:
            keys_with_data.append(key)
        else:
            keys_without_data.append(key)

    print()
    print("-" * 60)
    print("KEYS WITH DATA (Extraction Working)")
    print("-" * 60)

    for key in keys_with_data:
        value = result[key]
        print(f"\n{key}:")

        if isinstance(value, list):
            print(f"  COUNT: {len(value)}")

            if len(value) > 0 and isinstance(value[0], dict):
                item_keys = sorted(value[0].keys())
                print(f"  ITEM KEYS: {item_keys}")

                discriminator_keys = [
                    k
                    for k in item_keys
                    if k
                    in (
                        "type",
                        "kind",
                        "method",
                        "hook_name",
                        "directive_name",
                        "component_type",
                        "import_style",
                        "operation_type",
                        "guard_type",
                        "association_type",
                        "injection_type",
                        "style",
                    )
                ]

                if discriminator_keys:
                    print("  VALUE SAMPLES (discriminators):")
                    for dk in discriminator_keys:
                        values = sorted({str(item.get(dk, "")) for item in value if item.get(dk)})[
                            :8
                        ]
                        if values:
                            print(f"    {dk}: {values}")

                print(f"  SAMPLE ITEM: {format_value(value[0], 200)}")
            else:
                print(f"  SAMPLE: {format_value(value[:3], 200)}")

        elif isinstance(value, dict):
            print(f"  COUNT: {len(value)} keys")
            print(f"  KEYS: {sorted(list(value.keys())[:10])}")

    print()
    print("-" * 60)
    print("KEYS WITHOUT DATA (May need different sample code)")
    print("-" * 60)
    print(f"  {', '.join(keys_without_data)}")

    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total extraction keys: {len(result)}")
    print(f"Keys with data: {len(keys_with_data)}")
    print(f"Keys without data: {len(keys_without_data)}")

    print()
    print("-" * 60)
    print("SCHEMA ALIGNMENT CHECK (Junction Tables)")
    print("-" * 60)

    junction_relevant_keys = [
        "vue_components",
        "angular_components",
        "angular_modules",
        "react_components",
        "react_hooks",
    ]

    for key in junction_relevant_keys:
        if key in result and result[key]:
            items = result[key]
            if isinstance(items, list) and len(items) > 0 and isinstance(items[0], dict):
                item_keys = set(items[0].keys())
                print(f"\n{key}:")
                print(f"  Fields: {sorted(item_keys)}")

                json_fields = [
                    k
                    for k in item_keys
                    if k
                    in (
                        "props_definition",
                        "emits_definition",
                        "setup_return",
                        "style_paths",
                        "declarations",
                        "imports",
                        "providers",
                        "exports",
                        "hooks_used",
                        "dependency_vars",
                    )
                ]
                if json_fields:
                    print(f"  [WARNING] Contains JSON fields: {json_fields}")
                    print("            These should be in junction tables!")

    try:
        temp_file.unlink()
    except Exception:
        pass

    print()
    print("=" * 80)
    print("AUDIT COMPLETE")
    print("=" * 80)


def show_expected_schema():
    """Show the expected schema structure when parsing fails."""
    print()
    print("=" * 80)
    print("EXPECTED SCHEMA STRUCTURE (from node_schema.py)")
    print("=" * 80)
    print()
    print("This is the Ground Truth for what the database layer expects.")
    print("The schema was normalized in node-schema-normalization to replace")
    print("JSON blob columns with proper junction tables.")
    print()

    from theauditor.indexer.schemas.node_schema import NODE_TABLES

    junction_tables = [
        "vue_component_props",
        "vue_component_emits",
        "vue_component_setup_returns",
        "angular_component_styles",
        "angular_module_declarations",
        "angular_module_imports",
        "angular_module_providers",
        "angular_module_exports",
    ]

    react_tables = [
        "react_components",
        "react_component_hooks",
        "react_hooks",
        "react_hook_dependencies",
    ]
    vue_tables = ["vue_components", "vue_hooks", "vue_directives", "vue_provide_inject"]
    angular_tables = [
        "angular_components",
        "angular_services",
        "angular_modules",
        "angular_guards",
        "di_injections",
    ]
    sequelize_tables = ["sequelize_models", "sequelize_associations"]
    bullmq_tables = ["bullmq_queues", "bullmq_workers"]
    express_tables = ["express_middleware_chains", "frontend_api_calls"]

    print("=" * 80)
    print("1. NEW JUNCTION TABLES (node-schema-normalization)")
    print("=" * 80)
    print()
    print("These tables replace JSON blob columns with normalized relational data.")
    print("Each row represents one item from what was previously a JSON array.")

    for table_name in junction_tables:
        if table_name in NODE_TABLES:
            table = NODE_TABLES[table_name]
            cols = [
                (col.name, col.type, "NOT NULL" if not col.nullable else "NULL")
                for col in table.columns
            ]
            print(f"\n{table_name}:")
            for col_name, col_type, nullable in cols:
                print(f"    {col_name}: {col_type} {nullable}")

    print()
    print("=" * 80)
    print("2. PARENT TABLES (JSON columns REMOVED)")
    print("=" * 80)
    print()
    print("These tables had JSON blob columns that are now in junction tables:")
    print("  - vue_components: props_definition, emits_definition, setup_return REMOVED")
    print("  - angular_components: style_paths REMOVED")
    print("  - angular_modules: declarations, imports, providers, exports REMOVED")

    parent_tables = ["vue_components", "angular_components", "angular_modules"]
    for table_name in parent_tables:
        if table_name in NODE_TABLES:
            table = NODE_TABLES[table_name]
            cols = [(col.name, col.type) for col in table.columns]
            print(f"\n{table_name}: ({len(cols)} columns)")
            for col_name, col_type in cols:
                print(f"    {col_name}: {col_type}")

    print()
    print("=" * 80)
    print("3. REACT TABLES")
    print("=" * 80)

    for table_name in react_tables:
        if table_name in NODE_TABLES:
            table = NODE_TABLES[table_name]
            cols = [col.name for col in table.columns]
            print(f"\n{table_name}: {cols}")

    print()
    print("=" * 80)
    print("4. VUE TABLES (including junction)")
    print("=" * 80)

    for table_name in vue_tables + [t for t in junction_tables if t.startswith("vue_")]:
        if table_name in NODE_TABLES:
            table = NODE_TABLES[table_name]
            cols = [col.name for col in table.columns]
            is_junction = table_name in junction_tables
            marker = " [JUNCTION]" if is_junction else ""
            print(f"\n{table_name}{marker}: {cols}")

    print()
    print("=" * 80)
    print("5. ANGULAR TABLES (including junction)")
    print("=" * 80)

    for table_name in angular_tables + [t for t in junction_tables if t.startswith("angular_")]:
        if table_name in NODE_TABLES:
            table = NODE_TABLES[table_name]
            cols = [col.name for col in table.columns]
            is_junction = table_name in junction_tables
            marker = " [JUNCTION]" if is_junction else ""
            print(f"\n{table_name}{marker}: {cols}")

    print()
    print("=" * 80)
    print("6. OTHER NODE TABLES")
    print("=" * 80)

    other_tables = sequelize_tables + bullmq_tables + express_tables
    for table_name in other_tables:
        if table_name in NODE_TABLES:
            table = NODE_TABLES[table_name]
            cols = [col.name for col in table.columns]
            print(f"\n{table_name}: {cols}")

    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total NODE_TABLES: {len(NODE_TABLES)}")
    print(f"Junction tables: {len(junction_tables)}")
    print(f"React tables: {len(react_tables)}")
    print(f"Vue tables: {len(vue_tables)}")
    print(f"Angular tables: {len(angular_tables)}")
    print()
    print("ARCHITECTURE NOTE:")
    print("  - Extractors produce dictionaries with these key names")
    print("  - Storage handlers (node_storage.py) dispatch to add_*() methods")
    print("  - Database mixin (node_database.py) batches records to generic_batches")
    print("  - Schema (node_schema.py) defines table structures")
    print()
    print("For live extraction testing, ensure TypeScript compiler is available:")
    print("  aud setup-ai --sync")
    print()


if __name__ == "__main__":
    audit()
