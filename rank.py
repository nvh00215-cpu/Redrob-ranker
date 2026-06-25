import json
import pandas as pd
import re
import sys
import os
from datetime import datetime

# ==============================================================================
# 1. CONFIGURATION & LEXICONS
# ==============================================================================
CURRENT_DATE = datetime(2026, 6, 1) # Contextual date based on dataset signals

# Company Classifications
CONSULTING_BLACKLIST = {"tcs", "wipro", "infosys", "cognizant", "accenture", 
                        "capgemini", "tech mahindra", "hcl", "mindtree"}
PRODUCT_COMPANIES = {"swiggy", "zomato", "uber", "flipkart", "razorpay", "cred", 
                     "ola", "meesho", "phonepe", "paytm", "mad street den"}
TARGET_CITIES = {"pune", "noida", "hyderabad", "mumbai", "delhi", "gurgaon", "bangalore"}

# Skill Tiers based on JD requirements
TIER1_SKILLS = {"embeddings", "faiss", "pinecone", "weaviate", "qdrant", "milvus", 
                "opensearch", "elasticsearch", "information retrieval", "ranking", 
                "ndcg", "mrr", "map", "sentence-transformers", "bm25", "vector search"}
TIER2_SKILLS = {"python", "xgboost", "lightgbm", "scikit-learn", "pytorch", "tensorflow", 
                "machine learning", "nlp", "recommendation systems", "feature engineering"}
TIER3_SKILLS = {"langchain", "openai", "prompt engineering", "rag", "llm"} # Framework fluff
TIER4_SKILLS = {"opencv", "yolo", "image classification", "speech recognition", "robotics", 
                "cnn", "gans", "object detection"} # Wrong domain

# "Nice-to-Haves" (Bonus points, not disqualifiers)
BONUS_SKILLS = {"lora", "qlora", "peft", "learning to rank", "distributed systems", 
                "inference optimization", "model optimization"}
TARGET_DOMAINS = {"recruiting", "hr-tech", "hr tech", "marketplace", "staffing", 
                  "human resources", "talent intelligence"}

# Regex for Shipper vs Researcher mentality in career descriptions
SHIPPER_RE = re.compile(r'\b(production|deploy|shipped|latency|scale|a/b test|ab test|monitor|ci/cd|mlops|api|sla)\b', re.IGNORECASE)
RESEARCHER_RE = re.compile(r'\b(published|paper|arxiv|theoretical|novel|state-of-the-art|simulation|benchmark|proof of concept|thesis)\b', re.IGNORECASE)

TRAP_TITLES = {"marketing", "hr", "accountant", "graphic", "sales", "content writer", 
               "customer support", "civil", "mechanical", "operations"}

# ==============================================================================
# 2. DATA LOADING & TRAP BYPASS
# ==============================================================================
def clean_data(obj):
    """
    CRITICAL FIX: The dataset contains a trap where every JSON key and string 
    value has a trailing space (e.g., "candidate_id " instead of "candidate_id").
    This function recursively strips whitespace to prevent KeyErrors and 
    ensure candidate IDs pass the strict regex validator.
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

    # Check if it's a JSON array (like sample_candidates.json)
    if content.startswith('['):
        try:
            data = json.loads(content)
            raw_candidates = data if isinstance(data, list) else [data]
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON array: {e}")
            return []
    else:
        # Assume it's JSONL (like candidates.jsonl)
        raw_candidates = []
        for line in content.splitlines():
            line = line.strip()
            if line:
                try:
                    raw_candidates.append(json.loads(line))
                except json.JSONDecodeError:
                    pass # Skip malformed lines

    # CRITICAL: Clean the data to remove the dataset's trailing space trap
    for c in raw_candidates:
        candidates.append(clean_data(c))
                    
    return candidates

def is_honeypot(c):
    """Catches impossible profiles (e.g., 8 years exp at a 3-year-old company)."""
    yoe = c['profile']['years_of_experience']
    total_months = sum(job['duration_months'] for job in c.get('career_history', []))
    
    # Trap 1: Total career duration exceeds total years of experience
    if total_months > (yoe * 12) + 6:
        return True
    
    # Trap 2: Time travel (start date after end date)
    for job in c.get('career_history', []):
        if job['start_date'] and job['end_date']:
            if job['start_date'] > job['end_date']:
                return True
                
    # Trap 3: Skill duration exceeds total experience
    for skill in c.get('skills', []):
        if skill.get('duration_months', 0) > (yoe * 12) + 6:
            return True
    return False

# ==============================================================================
# 3. FEATURE EXTRACTION
# ==============================================================================
def extract_features(c):
    profile = c['profile']
    signals = c['redrob_signals']
    career = c.get('career_history', [])
    skills = c.get('skills', [])
    
    # 1. Title Check
    title = profile['current_title'].lower()
    is_trap_title = any(t in title for t in TRAP_TITLES)
    
    # 2. Skills Analysis
    skill_names = {s['name'].lower() for s in skills}
    t1_count = len(skill_names.intersection(TIER1_SKILLS))
    t2_count = len(skill_names.intersection(TIER2_SKILLS))
    t3_count = len(skill_names.intersection(TIER3_SKILLS))
    t4_count = len(skill_names.intersection(TIER4_SKILLS))
    bonus_skill_count = len(skill_names.intersection(BONUS_SKILLS))
    
    # 3. Company History (Product vs Consulting)
    companies = [job['company'].lower() for job in career]
    is_consulting_only = all(comp in CONSULTING_BLACKLIST for comp in companies) if companies else False
    has_product_exp = any(comp in PRODUCT_COMPANIES for comp in companies)
    
    # 4. Domain Check (HR-Tech, Marketplace)
    all_industries = [profile['current_industry'].lower()] + [job['industry'].lower() for job in career]
    has_target_domain = any(domain in " ".join(all_industries) for domain in TARGET_DOMAINS)
    
    # 5. Shipper vs Researcher Lexicon
    shipper_score = 0
    researcher_score = 0
    for job in career:
        desc = job.get('description', '')
        shipper_score += len(SHIPPER_RE.findall(desc))
        researcher_score += len(RESEARCHER_RE.findall(desc))
        
    # 6. Stability / Job Hopper Math
    tenures = [job['duration_months'] for job in career if not job['is_current']]
    avg_tenure = sum(tenures) / len(tenures) if tenures else 999
    is_job_hopper = avg_tenure < 18
    
    # 7. Behavioral Signals
    last_active = datetime.strptime(signals['last_active_date'], '%Y-%m-%d')
    days_inactive = (CURRENT_DATE - last_active).days
    response_rate = signals['recruiter_response_rate']
    github_score = signals['github_activity_score']
    notice_period = signals['notice_period_days']
    location = profile['location'].lower()
    willing_relocate = signals['willing_to_relocate']
    
    return {
        'candidate_id': c['candidate_id'],
        'is_trap_title': is_trap_title,
        't1_count': t1_count, 't2_count': t2_count, 
        't3_count': t3_count, 't4_count': t4_count,
        'bonus_skill_count': bonus_skill_count,
        'is_consulting_only': is_consulting_only,
        'has_product_exp': has_product_exp,
        'has_target_domain': has_target_domain,
        'shipper_score': shipper_score, 'researcher_score': researcher_score,
        'avg_tenure': avg_tenure, 'is_job_hopper': is_job_hopper,
        'days_inactive': days_inactive, 'response_rate': response_rate,
        'github_score': github_score, 'notice_period': notice_period,
        'is_target_city': any(city in location for city in TARGET_CITIES),
        'willing_relocate': willing_relocate,
        'yoe': profile['years_of_experience'],
        'current_title': profile['current_title'],
        'current_company': profile['current_company']
    }

# ==============================================================================
# 4. SCORING ENGINE
# ==============================================================================
def calculate_score(feat):
    # --- HARD DISQUALIFICATIONS ---
    if feat['is_consulting_only']:
        return 0.0, "Disqualified: 100% consulting/service company background."
    if feat['days_inactive'] > 180 and feat['response_rate'] < 0.15:
        return 0.0, f"Disqualified: Ghost profile (inactive {feat['days_inactive']}d, response {feat['response_rate']})."
    if feat['is_trap_title'] and feat['t1_count'] == 0 and feat['shipper_score'] == 0:
        return 0.0, f"Disqualified: Trap title ({feat['current_title']}) with no core IR/ML evidence."
    if feat['researcher_score'] > feat['shipper_score'] and feat['researcher_score'] >= 3 and feat['t1_count'] == 0:
        return 0.0, "Disqualified: Pure research background with no production deployment."
    if feat['t4_count'] > 2 and feat['t1_count'] == 0:
        return 0.0, "Disqualified: Pure CV/Speech background, no NLP/IR exposure."

    score = 0.0
    reasons = []

    # 1. Core IR/Retrieval Depth (Max 30 pts)
    score += min(feat['t1_count'] * 6, 24)
    score += min(feat['t2_count'] * 2, 6)
    if feat['t3_count'] > 0 and feat['t1_count'] == 0:
        score -= 15
        reasons.append("Framework enthusiast without core IR depth")
    if feat['t4_count'] > 0 and feat['t1_count'] == 0:
        score -= 10
        reasons.append("Wrong domain (CV/Speech)")
    if feat['t1_count'] > 0:
        reasons.append(f"{feat['t1_count']} core IR/Retrieval skills")

    # 2. Product & Shipper Pedigree (Max 25 pts)
    if feat['has_product_exp']:
        score += 15
        reasons.append("Product company exp")
    if feat['shipper_score'] >= 3:
        score += 10
        reasons.append("Strong shipper mentality (production/A/B tests)")
    elif feat['shipper_score'] >= 1:
        score += 5
    if feat['researcher_score'] > feat['shipper_score'] and feat['researcher_score'] >= 2:
        score -= 10
        reasons.append("Research-heavy background")

    # 3. Stability & Culture Fit (Max 20 pts)
    if feat['avg_tenure'] >= 36:
        score += 15
        reasons.append(f"Stable ({feat['avg_tenure']:.0f}mo avg tenure)")
    elif feat['avg_tenure'] >= 24:
        score += 5
    if feat['is_job_hopper']:
        score -= 15
        reasons.append("Job hopper (<18mo avg tenure)")

    # 4. Behavioral & Logistics (Max 25 pts)
    if feat['days_inactive'] < 30:
        score += 10
    elif feat['days_inactive'] < 90:
        score += 5
        
    if feat['response_rate'] > 0.6:
        score += 8
    elif feat['response_rate'] > 0.3:
        score += 4
        
    if feat['github_score'] > 30:
        score += 4
        reasons.append("Active GitHub")
        
    if feat['notice_period'] <= 30:
        score += 3
        
    if feat['is_target_city'] or feat['willing_relocate']:
        score += 5
        reasons.append("Target city/willing to relocate")

    # 5. Bonus / "Nice-to-Haves" (Max 15 pts)
    if feat['bonus_skill_count'] > 0:
        bonus_pts = min(feat['bonus_skill_count'] * 4, 12)
        score += bonus_pts
        reasons.append(f"Bonus skills (LoRA/PEFT/Distributed)")
        
    if feat['has_target_domain']:
        score += 5
        reasons.append("HR-tech/Marketplace domain exposure")

    # Trap title penalty (if not disqualified but still a mismatch)
    if feat['is_trap_title'] and feat['t1_count'] > 0:
        score -= 10
        reasons.append(f"Title mismatch ({feat['current_title']}) but has IR skills")

    return score, "; ".join(reasons) if reasons else "Standard profile"

# ==============================================================================
# 5. REASONING GENERATOR (Stage 4 Manual Review Optimization)
# ==============================================================================
def generate_reasoning(feat, rank):
    title = feat['current_title']
    company = feat['current_company']
    yoe = feat['yoe']
    t1 = feat['t1_count']
    shipper = feat['shipper_score']
    
    if rank <= 20:
        strengths = []
        if t1 > 0: strengths.append(f"{t1} core IR/retrieval skills")
        if shipper >= 3: strengths.append("proven production/shipper experience")
        if feat['has_product_exp']: strengths.append(f"product background ({company})")
        if feat['bonus_skill_count'] > 0: strengths.append("bonus skills (LoRA/PEFT/LTR)")
        
        concerns = []
        if feat['notice_period'] > 60: concerns.append(f"notice period {feat['notice_period']}d")
        if feat['days_inactive'] > 30: concerns.append(f"last active {feat['days_inactive']}d ago")
        if feat['is_trap_title']: concerns.append(f"title '{title}' is non-standard for ML")
        
        reason = f"{title} at {company} ({yoe} YOE); {', '.join(strengths) if strengths else 'strong applied ML background'}."
        if concerns:
            reason += f" Note: {'; '.join(concerns)}."
        return reason
        
    elif rank <= 60:
        strengths = []
        if t1 > 0: strengths.append(f"{t1} IR skills")
        if feat['has_product_exp']: strengths.append("product exp")
        if feat['response_rate'] > 0.5: strengths.append("high response rate")
        
        gaps = []
        if t1 == 0: gaps.append("lacks explicit vector search/IR experience")
        if feat['is_job_hopper']: gaps.append("short tenures")
        if shipper == 0: gaps.append("limited production evidence")
        
        reason = f"{title} with {yoe} YOE; {', '.join(strengths) if strengths else 'adjacent backend/data skills'}."
        if gaps:
            reason += f" Concern: {', '.join(gaps)}."
        return reason
        
    else:
        reason = f"{title} ({yoe} YOE); "
        if t1 > 0:
            reason += f"has {t1} IR skills but "
        reason += "limited direct ranking/retrieval production experience. Included as final filler given platform engagement."
        return reason

# ==============================================================================
# 6. MAIN EXECUTION
# ==============================================================================
def main():
    # Strictly defaults to the uncompressed 100k file
    input_file = sys.argv[1] if len(sys.argv) > 1 else 'candidates.jsonl'
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'submission.csv'
    
    print(f"Loading candidates from {input_file}...")
    candidates = load_candidates(input_file)
    print(f"Loaded {len(candidates)} candidates.")
    
    print("Filtering honeypots and extracting features...")
    valid_features = []
    for c in candidates:
        if is_honeypot(c):
            continue
        feat = extract_features(c)
        score, _ = calculate_score(feat)
        if score > 0:
            valid_features.append((feat, score))
            
    print(f"Scored {len(valid_features)} valid candidates.")
    
    # Sort by score descending, then candidate_id ascending for strict tie-breaking
    valid_features.sort(key=lambda x: (-x[1], x[0]['candidate_id']))
    
    # Take top 100
    top_100 = valid_features[:100]
    
    if len(top_100) < 100:
        print(f"WARNING: Only found {len(top_100)} valid candidates. The validator requires exactly 100.")
    
    print("Generating submission...")
    rows = []
    for i, (feat, score) in enumerate(top_100):
        rank = i + 1
        reasoning = generate_reasoning(feat, rank)
        rows.append({
            'candidate_id': feat['candidate_id'],
            'rank': rank,
            'score': round(score, 4),
            'reasoning': reasoning
        })
        
    df = pd.DataFrame(rows)
    df.to_csv(output_file, index=False)
    print(f"Submission saved to {output_file}")
    print("Validation: Exactly 100 rows generated." if len(df) == 100 else f"Validation: {len(df)} rows generated.")

if __name__ == "__main__":
    main()
