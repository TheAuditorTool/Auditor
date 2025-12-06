import os
import sqlite3

hist_dir = "C:/Users/santa/Desktop/PlantFlow/.pf/history/full/20251125_002047"
print("Files in historical backup:")
for f in os.listdir(hist_dir):
    path = os.path.join(hist_dir, f)
    size = os.path.getsize(path) / 1024 / 1024
    print(f"  {f}: {size:.2f} MB")

hist_db = os.path.join(hist_dir, "repo_index.db")
curr_db = "C:/Users/santa/Desktop/PlantFlow/.pf/repo_index.db"

print()
print("=== COMPARISON: CURRENT vs 20251125_002047 ===")

hist_conn = sqlite3.connect(hist_db)
curr_conn = sqlite3.connect(curr_db)
hist_c = hist_conn.cursor()
curr_c = curr_conn.cursor()

hist_c.execute("SELECT name FROM sqlite_master WHERE type='table'")
hist_tables = {r[0] for r in hist_c.fetchall()}

curr_c.execute("SELECT name FROM sqlite_master WHERE type='table'")
curr_tables = {r[0] for r in curr_c.fetchall()}

diffs = []
for t in hist_tables | curr_tables:
    hist_count = 0
    curr_count = 0
    if t in hist_tables:
        hist_c.execute(f"SELECT COUNT(*) FROM [{t}]")
        hist_count = hist_c.fetchone()[0]
    if t in curr_tables:
        curr_c.execute(f"SELECT COUNT(*) FROM [{t}]")
        curr_count = curr_c.fetchone()[0]
    diff = curr_count - hist_count
    if diff != 0:
        diffs.append((t, curr_count, hist_count, diff))

diffs.sort(key=lambda x: abs(x[3]), reverse=True)

print("Tables with differences (top 30):")
for t, curr, hist, diff in diffs[:30]:
    sign = "+" if diff > 0 else ""
    print(f"  {t}: {curr:,} vs {hist:,} ({sign}{diff:,})")

hist_total = sum(hist_c.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0] for t in hist_tables)
curr_total = sum(curr_c.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0] for t in curr_tables)

print()
print(f"HISTORICAL: {hist_total:,} rows, {os.path.getsize(hist_db) / 1024 / 1024:.1f} MB")
print(f"CURRENT: {curr_total:,} rows, {os.path.getsize(curr_db) / 1024 / 1024:.1f} MB")
print(f"DELTA: {curr_total - hist_total:,} rows")

hist_conn.close()
curr_conn.close()
