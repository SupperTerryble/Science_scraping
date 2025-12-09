import requests
import json
import re
import logging
from typing import Dict, Any, List, Optional

class ChemistryAgent:
    """
    Agent responsible for normalizing data, verifying physical consistency,
    and validating chemical logic using PubChem and LLM.
    """
    
    def __init__(self, ollama_url: str = "http://localhost:11434/api/generate", model_name: str = "qwen3:8b"):
        self.ollama_url = ollama_url
        self.model_name = model_name
        self.unit_map = {
            # Temperature -> Kelvin
            'c': 'celsius', 'celsius': 'celsius', '°c': 'celsius',
            'k': 'kelvin', 'kelvin': 'kelvin',
            'f': 'fahrenheit', 'fahrenheit': 'fahrenheit',
            # Time -> Minutes
            'h': 'hours', 'hr': 'hours', 'hours': 'hours',
            'min': 'minutes', 'm': 'minutes', 'minutes': 'minutes',
            's': 'seconds', 'sec': 'seconds', 'seconds': 'seconds',
            'd': 'days', 'days': 'days'
        }

    def analyze(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point: Normalize data and perform chemical validation.
        """
        # 1. Normalize Units (Physics)
        normalized = self._normalize_data(raw_data)
        
        # 2. Validate Chemicals (PubChem)
        normalized = self._validate_chemicals(normalized)
        
        # 3. Validate Reaction Logic (LLM)
        normalized = self._validate_reaction_logic(normalized)
        
        return normalized

    def _normalize_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize units and basic formatting."""
        normalized = raw_data.copy()
        normalized['physics_check_passed'] = True
        normalized['warnings'] = []
        
        # Normalize Conditions
        if 'conditions' in normalized:
            new_conditions = []
            for cond in normalized['conditions']:
                norm_cond = self._normalize_condition(cond)
                if norm_cond:
                    new_conditions.append(norm_cond)
                    # Sanity Check
                    check_ok, warning = self._check_physical_validity(norm_cond)
                    if not check_ok:
                        normalized['physics_check_passed'] = False
                        normalized['warnings'].append(warning)
            normalized['conditions'] = new_conditions

        # Normalize Precursors (Basic name cleanup)
        if 'precursors' in normalized:
            for prec in normalized['precursors']:
                prec['name'] = self._clean_chemical_name(prec.get('name', ''))
                
        return normalized

    def _validate_chemicals(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Check precursors against PubChem."""
        if 'precursors' not in data:
            return data
            
        for prec in data['precursors']:
            name = prec.get('name')
            if name:
                pubchem_data = self._search_pubchem(name)
                if pubchem_data:
                    prec['pubchem_cid'] = pubchem_data.get('cid')
                    prec['formula'] = pubchem_data.get('formula')
                    prec['mw'] = pubchem_data.get('molecular_weight')
                    prec['verified'] = True
                else:
                    prec['verified'] = False
                    data['warnings'].append(f"Chemical not found in PubChem: {name}")
        return data

    def _validate_reaction_logic(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Ask LLM if the reaction makes sense."""
        target = data.get('target_material', 'Unknown')
        precursors = [p.get('name') for p in data.get('precursors', [])]
        method = data.get('method_type', 'Unknown')
        
        if not precursors or target == 'Unknown':
            return data

        prompt = f"""
        You are a chemistry expert. Validate this synthesis reaction.
        
        Target: {target}
        Method: {method}
        Precursors: {', '.join(precursors)}
        
        Questions:
        1. Is it chemically possible to synthesize {target} from these precursors?
        2. Are key elements missing (e.g. trying to make a sulfide without sulfur)?
        
        Return ONLY a JSON object:
        {{
            "valid": true/false,
            "reason": "Short explanation",
            "missing_elements": ["Element1", "Element2"] (or empty list)
        }}
        """
        
        try:
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "format": "json"
            }
            response = requests.post(self.ollama_url, json=payload)
            if response.status_code == 200:
                resp_json = response.json()
                llm_data = json.loads(resp_json.get('response', '{}'))
                
                data['chemistry_valid'] = llm_data.get('valid', False)
                data['chemistry_reason'] = llm_data.get('reason', 'Unknown')
                
                if not llm_data.get('valid'):
                    data['warnings'].append(f"Chemical Logic Error: {llm_data.get('reason')}")
                if llm_data.get('missing_elements'):
                    data['warnings'].append(f"Missing Elements: {llm_data.get('missing_elements')}")
                    
        except Exception as e:
            logging.error(f"LLM Validation failed: {e}")
            
        return data

    def _search_pubchem(self, name: str) -> Optional[Dict[str, Any]]:
        """Query PubChem PUG REST API."""
        try:
            url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{name}/property/MolecularFormula,MolecularWeight/JSON"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                props = resp.json()['PropertyTable']['Properties'][0]
                return {
                    'cid': props.get('CID'),
                    'formula': props.get('MolecularFormula'),
                    'molecular_weight': props.get('MolecularWeight')
                }
        except Exception as e:
            logging.debug(f"PubChem lookup failed for {name}: {e}")
        return None

    # --- Legacy Physics Methods (Refactored) ---
    def _normalize_condition(self, condition: Dict[str, str]) -> Dict[str, Any]:
        """Normalize a single condition dictionary."""
        param = condition.get('parameter', '').lower()
        val_str = str(condition.get('value', ''))
        unit_str = condition.get('unit', '').lower().strip()
        
        try:
            value = self._parse_value(val_str)
        except ValueError:
            return condition 

        std_unit = self.unit_map.get(unit_str, unit_str)
        
        if 'temp' in param:
            if std_unit == 'celsius':
                value = value + 273.15
                std_unit = 'K'
            elif std_unit == 'fahrenheit':
                value = (value - 32) * 5/9 + 273.15
                std_unit = 'K'
            elif std_unit == 'kelvin':
                std_unit = 'K'
        elif 'time' in param or 'duration' in param:
            if std_unit == 'hours':
                value = value * 60
                std_unit = 'min'
            elif std_unit == 'seconds':
                value = value / 60
                std_unit = 'min'
            elif std_unit == 'days':
                value = value * 1440
                std_unit = 'min'
            elif std_unit == 'minutes':
                std_unit = 'min'

        return {
            'parameter': param,
            'value': round(value, 2),
            'unit': std_unit,
            'original_value': val_str,
            'original_unit': unit_str
        }

    def _parse_value(self, val_str: str) -> float:
        clean_val = re.sub(r'[^\d\.\-]', '', val_str)
        if '-' in clean_val and not clean_val.startswith('-'):
            parts = clean_val.split('-')
            if len(parts) == 2 and parts[0] and parts[1]:
                return (float(parts[0]) + float(parts[1])) / 2
        return float(clean_val)

    def _check_physical_validity(self, condition: Dict[str, Any]) -> (bool, str):
        param = condition['parameter']
        val = condition['value']
        unit = condition['unit']
        
        if 'temp' in param and unit == 'K':
            if isinstance(val, (int, float)):
                if val < 0: return False, f"Impossible Temperature: {val} K"
                if val > 4000: return False, f"Suspiciously High Temperature: {val} K"
        if ('time' in param or 'duration' in param):
            if isinstance(val, (int, float)) and val < 0:
                return False, f"Impossible Time: {val} {unit}"
        return True, ""

    def _clean_chemical_name(self, name: str) -> str:
        name = name.strip()
        mapping = {
            '2-meim': '2-methylimidazole',
            'h2o': 'water',
            'etoh': 'ethanol',
            'meoh': 'methanol'
        }
        return mapping.get(name.lower(), name)
