import sqlite3
import os
from typing import List, Dict, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'synthesis.db')

def init_db(db_path: str = DB_PATH):
    """Initialize the database with the required schema."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Papers table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS papers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        doi TEXT UNIQUE,
        text_content TEXT,
        ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Syntheses table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS syntheses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        paper_id INTEGER,
        target_material TEXT,
        method_type TEXT,
        description TEXT,
        FOREIGN KEY(paper_id) REFERENCES papers(id) ON DELETE CASCADE
    )
    ''')
    
    # Precursors table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS precursors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        synthesis_id INTEGER,
        name TEXT,
        amount TEXT,
        unit TEXT,
        FOREIGN KEY(synthesis_id) REFERENCES syntheses(id) ON DELETE CASCADE
    )
    ''')
    
    # Conditions table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS conditions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        synthesis_id INTEGER,
        parameter TEXT, -- e.g., "temperature", "time", "pressure"
        value TEXT,
        unit TEXT,
        FOREIGN KEY(synthesis_id) REFERENCES syntheses(id) ON DELETE CASCADE
    )
    ''')
    
    conn.commit()
    conn.close()
    print(f"Database initialized at {db_path}")

def insert_paper(title: str, doi: str, text_content: str) -> int:
    """Insert a paper and return its ID."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO papers (title, doi, text_content) VALUES (?, ?, ?)', (title, doi, text_content))
        paper_id = cursor.lastrowid
        conn.commit()
        return paper_id
    except sqlite3.IntegrityError:
        # Paper likely already exists, return existing ID
        cursor.execute('SELECT id FROM papers WHERE doi = ?', (doi,))
        result = cursor.fetchone()
        conn.close()
        if result:
            return result[0]
        raise
    finally:
        conn.close()

def insert_synthesis(paper_id: int, target_material: str, method_type: str, description: str) -> int:
    """Insert a synthesis procedure and return its ID."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO syntheses (paper_id, target_material, method_type, description) 
        VALUES (?, ?, ?, ?)
    ''', (paper_id, target_material, method_type, description))
    synthesis_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return synthesis_id

def insert_precursor(synthesis_id: int, name: str, amount: str, unit: str):
    """Insert a precursor."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO precursors (synthesis_id, name, amount, unit) 
        VALUES (?, ?, ?, ?)
    ''', (synthesis_id, name, amount, unit))
    conn.commit()
    conn.close()

def insert_condition(synthesis_id: int, parameter: str, value: str, unit: str):
    """Insert a synthesis condition."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO conditions (synthesis_id, parameter, value, unit) 
        VALUES (?, ?, ?, ?)
    ''', (synthesis_id, parameter, value, unit))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
