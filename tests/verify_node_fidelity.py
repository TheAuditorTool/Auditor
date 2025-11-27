"""Node.js Fidelity Verification Script.

This script creates a micro-project and runs the indexer on it to verify
the end-to-end flow: Extraction -> Manifest -> Storage -> Receipt -> Fidelity Check.

Created as part of node-fidelity-infrastructure ticket Phase 3.
"""
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from theauditor.indexer.orchestrator import IndexerOrchestrator


def test_node_fidelity():
    print("=== STARTING NODE.JS FIDELITY VERIFICATION ===")

    # 1. Setup Test Environment
    temp_dir = Path(tempfile.mkdtemp(prefix="aud_fidelity_test_"))
    db_path = temp_dir / "test_repo.db"

    try:
        print(f"[1] Created temp environment: {temp_dir}")

        # Create package.json (Identity)
        with open(temp_dir / "package.json", "w") as f:
            f.write('{"name": "test-project", "version": "1.0.0"}')

        # Create Sequelize Model (Target 1)
        # Pattern: sequelize.define('User', ...) -> sequelize_models table
        with open(temp_dir / "models.js", "w") as f:
            f.write("""
const User = sequelize.define('User', {
  firstName: { type: DataTypes.STRING },
  lastName: { type: DataTypes.STRING }
});
""")

        # Create Angular Component (Target 2)
        # Pattern: @Component(...) -> angular_components table
        with open(temp_dir / "app.component.ts", "w") as f:
            f.write("""
@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css']
})
export class AppComponent {
  title = 'fidelity-test';
}
""")

        # 2. Run Indexer
        print("[2] Running IndexerOrchestrator...")
        # Note: This will trigger extraction -> manifest -> storage -> receipt -> fidelity check
        orchestrator = IndexerOrchestrator(temp_dir, str(db_path))

        # Initialize database schema (required before indexing)
        orchestrator.db_manager.create_schema()

        counts, stats = orchestrator.index()

        print(f"[3] Indexing complete. Counts: {counts}")

        # 3. Verify Database Content
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Check Sequelize Models
        cursor.execute("SELECT count(*) FROM sequelize_models")
        seq_count = cursor.fetchone()[0]
        print(f"[CHECK] sequelize_models count: {seq_count}")

        # Check Angular Components
        cursor.execute("SELECT count(*) FROM angular_components")
        ng_count = cursor.fetchone()[0]
        print(f"[CHECK] angular_components count: {ng_count}")

        conn.close()

        # Close orchestrator's DB connection before cleanup
        orchestrator.db_manager.close()

        # 4. Assertions
        if seq_count != 1:
            print(f"[FAILED] Expected 1 sequelize model, got {seq_count}")
            print("[INFO] This may be due to TypeScript parser not being available in test environment")
            sys.exit(1)

        if ng_count != 1:
            print(f"[FAILED] Expected 1 angular component, got {ng_count}")
            print("[INFO] This may be due to TypeScript parser not being available in test environment")
            sys.exit(1)

        print("")
        print("[SUCCESS] Fidelity check passed. Data extracted and stored correctly.")
        print("   - Manifest generation worked (otherwise Orchestrator would rely on empty manifest)")
        print("   - Storage batching worked (otherwise DB would be empty)")
        print("   - Fidelity check passed (otherwise DataFidelityError would crash script)")

    finally:
        # Cleanup - give Windows time to release file handles
        import time
        time.sleep(0.5)
        if temp_dir.exists():
            try:
                shutil.rmtree(temp_dir)
            except PermissionError:
                print(f"[WARN] Could not clean up temp dir: {temp_dir}")


if __name__ == "__main__":
    test_node_fidelity()
