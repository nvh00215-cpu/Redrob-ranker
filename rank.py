import json
import pandas as pd
import re
import sys
from datetime import datetime

CURRENT_DATE = datetime(2026, 6, 1)
CONSULTING_BLACKLIST = {"tcs", "wipro", "infosys", "cognizant", "accenture", "capgemini", "tech mahindra", "hcl", "mindtree"}
TIER1_SKILLS = {"embeddings", "faiss", "pinecone", "weaviate", "qdrant", "milvus", "opensearch", "elasticsearch", "information retrieval", "ranking", "ndcg", "mrr", "map", "sentence-transformers", "bm25", "vector search"}
TIER2_SKILLS = {"python", "xgboost", "lightgbm", "scikit-learn", "pytorch", "tensorflow", "machine learning", "nlp", "recommendation systems", "feature engineering"}
TIER3_SKILLS = {"langchain", "openai", "prompt engineering", "rag", "llm"}
BONUS_SKILLS = {"lora", "qlora", "peft", "learning to rank", "distributed systems", "inference optimization"}
TRAP_TITLES = {"marketing", "hr", "accountant", "graphic", "sales", "content writer", "customer support", "civil", "mechanical", "operations"}

SHIPPER_RE = re.compile(r'\b(production|deploy|shipped|latency|scale|a/b test|ab test|monitor|ci/cd|mlops|api|sla)\b', re.IGNORECASE)
RESEARCHER_RE = re.compile(r'\b(published|paper|arxiv|theoretical|novel|state-of-the-art|simulation|benchmark|proof of concept|thesis)\b', re.IGNORECASE)

def clean_data(obj):
    if isinstance(obj, dict): return {k.strip(): clean_data(v) for k, v in obj.items()}
    elif isinstance(obj, list): return [clean_data(item) for item in obj]
    elif isinstance(obj, str): return obj.strip()
    else: return obj

def load_candidates(filepath):
    candidates = []
    with open(filepath, 'r', encoding='utf-8') as f: content = f.read().strip()
    if not content: return candidates
    if content.startswith('['):
        data = json.loads(content)
        raw_candidates = data if isinstance(data, list) else [data]
    else:
        raw_candidates = [json.loads(line) for line in content.splitlines() if line.strip()]
    for c in raw_candidates: candidates.append(clean_data(c))
    return candidates

def extract_features(c):
    profile = c['profile']
    signals = c['redrob_signals']
    career = c.get('career_history', [])
    skills = c.get('skills', [])
    title = profile['current_title'].lower()
    is_trap_title = any(t in title for t in TRAP_TITLES)
    skill_names = {s['name'].lower() for s in skills}
    t1_count = len(skill_names.intersection(TIER1_SKILLS))
    t2_count = len(skill_names.intersection(TIER2_SKILLS))
    t3_count = len(skill_names.intersection(TIER3_SKILLS))
    bonus_skill_count = len(skill_names.intersection(BONUS_SKILLS))
    companies = [job['company'].lower() for job in career]
    is_consulting_only = all(comp in CONSULTING_BLACKLIST for comp in companies) if companies else False
    
    shipper_score = sum(len(SHIPPER_RE.findall(job.get('description', ''))) for job in career)
    researcher_score = sum(len(RESEARCHER_RE.findall(job.get('description', ''))) for job in career)
    
    tenures = [job['duration_months'] for job in career if not job['is_current']]
    avg_tenure = sum(tenures) / len(tenures) if tenures else 999
    
    last_active = datetime.strptime(signals['last_active_date'], '%Y-%m-%d')
    days_inactive = (CURRENT_DATE - last_active).days
    
    return {
        'candidate_id': c['candidate_id'], 'is_trap_title': is_trap_title,
        't1_count': t1_count, 't2_count': t2_count, 't3_count': t3_count, 'bonus_skill_count': bonus_skill_count,
        'is_consulting_only': is_consulting_only, 'shipper_score': shipper_score, 'researcher_score': researcher_score,
        'avg_tenure': avg_tenure, 'days_inactive': days_inactive, 'response_rate': signals['recruiter_response_rate'],
        'current_title': profile['current_title'], 'current_company': profile['current_company'], 'yoe': profile['years_of_experience']
    }

def calculate_score(feat):
    if feat['is_consulting_only']: return 0.0, "Disqualified: Consulting-only background."
    if feat['days_inactive'] > 180 and feat['response_rate'] < 0.15: return 0.0, "Disqualified: Ghost profile."
    if feat['is_trap_title'] and feat['t1_count'] == 0 and feat['shipper_score'] == 0: return 0.0, f"Disqualified: Trap title."
    if feat['researcher_score'] > feat['shipper_score'] and feat['researcher_score'] >= 3 and feat['t1_count'] == 0: return 0.0, "Disqualified: Pure researcher."

    score = 0.0
    reasons = []
    score += min(feat['t1_count'] * 6, 24)
    score += min(feat['t2_count'] * 2, 6)
    if feat['t3_count'] > 0 and feat['t1_count'] == 0: score -= 15; reasons.append("Framework enthusiast")
    if feat['t1_count'] > 0: reasons.append(f"{feat['t1_count']} core IR skills")
    
    if feat['shipper_score'] >= 3: score += 10; reasons.append("Strong shipper mentality")
    elif feat['shipper_score'] >= 1: score += 5
    if feat['researcher_score'] > feat['shipper_score'] and feat['researcher_score'] >= 2: score -= 10; reasons.append("Research-heavy")
    
    if feat['avg_tenure'] >= 36: score += 15; reasons.append(f"Stable ({feat['avg_tenure']:.0f}mo tenure)")
    elif feat['avg_tenure'] < 18: score -= 15; reasons.append("Job hopper")
    
    if feat['days_inactive'] < 30: score += 10
    elif feat['days_inactive'] < 90: score += 5
    if feat['response_rate'] > 0.6: score += 8
    elif feat['response_rate'] > 0.3: score += 4
    
    if feat['bonus_skill_count'] > 0: score += min(feat['bonus_skill_count'] * 4, 12); reasons.append("Bonus skills (LoRA/PEFT)")
    return score, "; ".join(reasons) if reasons else "Standard profile"

def main():
    input_file = sys.argv[1] if len(sys.argv) > 1 else 'candidates.jsonl'
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'submission.csv'
    print(f"Loading and scoring candidates from {input_file}...")
    candidates = load_candidates(input_file)
    valid_features = []
    for c in candidates:
        feat = extract_features(c)
        score, _ = calculate_score(feat)
        if score > 0: valid_features.append((feat, score))
    print(f"Scored {len(valid_features)} valid candidates. Generating output...")
    valid_features.sort(key=lambda x: (-x[1], x[0]['candidate_id']))
    top_100 = valid_features[:100]
    rows = [{'candidate_id': f['candidate_id'], 'rank': i+1, 'score': round(s, 4), 'reasoning': 'Advanced scoring'} for i, (f, s) in enumerate(top_100)]
    pd.DataFrame(rows).to_csv(output_file, index=False)
    print(f"Saved {len(rows)} rows to {output_file}")

if __name__ == "__main__":
    main()
