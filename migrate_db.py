#!/usr/bin/env python3
"""Database migration script for Digital Being.

Adds new columns to existing vector_memory database:
- access_count (for LRU tracking)
- last_access (for LRU tracking)
- Index for efficient cleanup

Usage:
    python migrate_db.py
"""

import sqlite3
import sys
from pathlib import Path


def migrate_vector_memory(db_path: Path) -> bool:
    """Migrate vector memory database to new schema."""
    print(f"Migrating database: {db_path}")
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check current schema
        cursor.execute("PRAGMA table_info(vectors)")
        columns = {row[1] for row in cursor.fetchall()}
        
        print(f"Current columns: {sorted(columns)}")
        
        changes_made = False
        
        # Add access_count if missing
        if "access_count" not in columns:
            print("➕ Adding access_count column...")
            cursor.execute(
                "ALTER TABLE vectors ADD COLUMN access_count INTEGER DEFAULT 0"
            )
            changes_made = True
        else:
            print("✅ access_count already exists")
        
        # Add last_access if missing
        if "last_access" not in columns:
            print("➕ Adding last_access column...")
            cursor.execute(
                "ALTER TABLE vectors ADD COLUMN last_access REAL"
            )
            changes_made = True
        else:
            print("✅ last_access already exists")
        
        # Create index if not exists
        print("📊 Creating/verifying index...")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_vectors_access "
            "ON vectors(access_count DESC, last_access DESC)"
        )
        
        conn.commit()
        conn.close()
        
        if changes_made:
            print("✅ Migration completed successfully!")
        else:
            print("✅ Database already up to date!")
        
        return True
        
    except sqlite3.Error as e:
        print(f"❌ Migration failed: {e}")
        return False


def main():
    """Run all migrations."""
    print("="*60)
    print("Digital Being - Database Migration")
    print("="*60)
    print()
    
    # Find database files
    memory_dir = Path("memory")
    
    if not memory_dir.exists():
        print("❌ memory/ directory not found")
        print("   Run Digital Being first to create databases")
        return 1
    
    # Migrate vector memory
    vector_db = memory_dir / "vectors.db"
    
    if vector_db.exists():
        if not migrate_vector_memory(vector_db):
            return 1
    else:
        print(f"ℹ️  No vector database found at {vector_db}")
        print("   Will be created on first run")
    
    print()
    print("="*60)
    print("✅ ALL MIGRATIONS COMPLETE!")
    print("="*60)
    print()
    print("You can now run Digital Being:")
    print("  python main.py")
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
