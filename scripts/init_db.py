#!/usr/bin/env python3
"""Initialize database schema."""

from database.models import init_db, engine
from sqlalchemy import text

def main():
    print("Initializing database...")
    
    # Create tables
    init_db()
    print("✓ Tables created")
    
    # Create indexes for performance
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_workflow_id 
            ON workflow_checkpoints(workflow_id);
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_task_execution_workflow 
            ON task_executions(workflow_id);
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_task_execution_status 
            ON task_executions(status);
        """))
        conn.commit()
    
    print("✓ Indexes created")
    print("\nDatabase initialization complete!")

if __name__ == '__main__':
    main()