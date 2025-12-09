import os
import logging
import sys
from pypdf import PdfReader
from src import extractor
from src.agents.chemistry_agent import ChemistryAgent

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

PDF_PATH = "data/downloads/Highly_luminescent_silverbased_MOFs_Scalable_ecofriendly_synthesis_paving_the_way_for_photonics_sensors_and_electroluminescent_devices.pdf"

def test_pipeline():
    print(f"Processing {PDF_PATH}...")
    
    # 1. Extract Text
    text_content = ""
    try:
        reader = PdfReader(PDF_PATH)
        # Read first 5 pages
        for page in reader.pages[:5]:
            text_content += page.extract_text() + "\n"
    except Exception as e:
        print(f"Error reading PDF: {e}")
        return

    print("Text extracted. Running LLM Extraction (Text Mode)...")
    
    # 2. Extract Data (Text Mode)
    data = extractor.extract_synthesis_data(text_content, mode='text')
    print(f"Extracted Data: {data}")
    
    # 3. Run Chemistry Agent
    print("Running Chemistry Agent...")
    chem_agent = ChemistryAgent()
    result = chem_agent.analyze(data)
    
    print("\n--- Analysis Result ---")
    print(f"Physics Check: {result.get('physics_check_passed')}")
    print(f"Chemistry Valid: {result.get('chemistry_valid')}")
    print(f"Chemistry Reason: {result.get('chemistry_reason')}")
    print(f"Warnings: {result.get('warnings')}")
    
    if 'precursors' in result:
        print("\nPrecursors Verified:")
        for p in result['precursors']:
            print(f" - {p.get('name')}: Verified={p.get('verified')} (Formula: {p.get('formula')})")

if __name__ == "__main__":
    test_pipeline()
