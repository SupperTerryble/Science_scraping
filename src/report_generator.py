import sqlite3
import json
import os
from typing import List, Dict, Any

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'synthesis.db')
REPORT_FILE = "final_report.json"

def generate_report():
    """Reads from DB and generates a JSON report."""
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all papers
    cursor.execute("SELECT id, title, text_content FROM papers")
    papers = cursor.fetchall()
    
    report_data = []
    
    for paper in papers:
        p_id, title, content = paper
        
        # Get Synthesis
        cursor.execute("SELECT id, target_material, method_type, description FROM syntheses WHERE paper_id=?", (p_id,))
        synthesis = cursor.fetchone()
        
        synth_data = {}
        if synthesis:
            s_id, target, method, desc = synthesis
            synth_data = {
                "target_material": target,
                "method_type": method,
                "description": desc,
                "precursors": [],
                "conditions": []
            }
            
            # Get Precursors
            cursor.execute("SELECT name, amount, unit FROM precursors WHERE synthesis_id=?", (s_id,))
            for prec in cursor.fetchall():
                synth_data["precursors"].append({
                    "name": prec[0],
                    "amount": prec[1],
                    "unit": prec[2]
                })
                
            # Get Conditions
            cursor.execute("SELECT parameter, value, unit FROM conditions WHERE synthesis_id=?", (s_id,))
            for cond in cursor.fetchall():
                synth_data["conditions"].append({
                    "parameter": cond[0],
                    "value": cond[1],
                    "unit": cond[2]
                })
        
        # Note: Scores are not currently stored in DB in the main schema!
        # We only logged them. 
        # To fix this for the report, we should have added a score column or table.
        # For now, we will report what is in the DB.
        
        report_data.append({
            "title": title,
            "synthesis": synth_data
        })
        
    conn.close()
    
    with open(REPORT_FILE, 'w') as f:
        json.dump(report_data, f, indent=2)
        
    print(f"Report generated: {REPORT_FILE} ({len(report_data)} papers)")

if __name__ == "__main__":
    generate_report()
