import sqlite3
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

class EpisodicMemoryDB:
    def __init__(self, db_path: str = "episodic_memory.db"):
        """Initialize database connection and create tables if they don't exist."""
        self.db_path = Path(db_path)
        self._init_db()
    
    def _init_db(self):
        """Create the database tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS episodic_memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    analyst_id TEXT NOT NULL,
                    analyst_name TEXT NOT NULL,
                    property_address TEXT NOT NULL,
                    report_id TEXT NOT NULL,
                    partners_data TEXT NOT NULL,
                    memory_data TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            
            # Create index for faster queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp ON episodic_memories(timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_event_type ON episodic_memories(event_type)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_analyst_id ON episodic_memories(analyst_id)
            """)
    
    def save_memory(self, memory_data: Dict[str, Any]) -> str:
        """Save a new episodic memory to the database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO episodic_memories 
                (event_type, timestamp, analyst_id, analyst_name, property_address, 
                 report_id, partners_data, memory_data, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                memory_data['event_type'],
                memory_data['timestamp'],
                memory_data['analyst']['id'],
                memory_data['analyst']['name'],
                memory_data['property_address'],
                memory_data['report_id'],
                json.dumps(memory_data['selected_partners']),
                json.dumps(memory_data),
                datetime.utcnow().isoformat()
            ))
            
            memory_id = cursor.lastrowid
            conn.commit()
            return str(memory_id)
    
    def get_memories(self, limit: Optional[int] = None, offset: int = 0, 
                    event_type: Optional[str] = None, analyst_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve episodic memories with optional filtering."""
        query = """
            SELECT id, memory_data, created_at 
            FROM episodic_memories 
            WHERE 1=1
        """
        params = []
        
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        
        if analyst_id:
            query += " AND analyst_id = ?"
            params.append(analyst_id)
        
        query += " ORDER BY timestamp DESC"
        
        if limit:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            memories = []
            for row in rows:
                memory_id, memory_data_json, created_at = row
                memory_data = json.loads(memory_data_json)
                memory_data['db_id'] = memory_id
                memory_data['db_created_at'] = created_at
                memories.append(memory_data)
            
            return memories
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get statistics about stored memories."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Total count
            cursor.execute("SELECT COUNT(*) FROM episodic_memories")
            total_count = cursor.fetchone()[0]
            
            # Count by event type
            cursor.execute("""
                SELECT event_type, COUNT(*) 
                FROM episodic_memories 
                GROUP BY event_type
            """)
            by_event_type = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Count by analyst
            cursor.execute("""
                SELECT analyst_name, COUNT(*) 
                FROM episodic_memories 
                GROUP BY analyst_id, analyst_name
            """)
            by_analyst = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Recent activity (last 24 hours)
            cursor.execute("""
                SELECT COUNT(*) 
                FROM episodic_memories 
                WHERE datetime(created_at) >= datetime('now', '-1 day')
            """)
            recent_count = cursor.fetchone()[0]
            
            return {
                'total_memories': total_count,
                'by_event_type': by_event_type,
                'by_analyst': by_analyst,
                'recent_24h': recent_count
            }

# Global database instance
episodic_db = EpisodicMemoryDB()