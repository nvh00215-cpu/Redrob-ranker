import json
import sys
from datetime import datetime

def clean_data(obj):
    """
    Recursively strips whitespace from all dictionary keys and string values.
    Crucial for bypassing the dataset's trailing space trap in JSON keys.
    """
    if isinstance(obj, dict):
        return {k.strip(): clean_data(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_data(item) for item in obj]
    elif isinstance(obj, str):
        return obj.strip()
    else:
        return obj

def load_candidates(filepath):
    """Reads candidates from .json (array) or .jsonl (line-by-line) files."""
    candidates = []
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read().strip()
        
    if not content:
        return candidates

    if content.startswith('['):
        data = json.loads(content)
        raw_candidates = data if isinstance(data, list) else [data]
    else:
        raw_candidates = [json.loads(line) for line in content.splitlines() if line.strip()]

    for c in raw_candidates:
        candidates.append(clean_data(c))
    return candidates

def main():
    input_file = sys.argv[1] if len(sys.argv) > 1 else 'candidates.jsonl'
    print(f"Loading candidates from {input_file}...")
    candidates = load_candidates(input_file)
    print(f"Successfully loaded and cleaned {len(candidates)} candidates.")

if __name__ == "__main__":
    main()