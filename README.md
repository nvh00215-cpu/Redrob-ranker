# 🧭 Redrob Intelligent Candidate Ranker | Team Compass

## Team Information
* **Team Name:** Compass
* **Problem Statement:** Traditional keyword-matching fails to identify true production-ready AI engineers. We need a system that filters out "keyword stuffers" and pure academics to find candidates who actually build and ship retrieval systems.
* **Team Leader Name:** Naveen V Hiremath

---

## Solution Overview
* **Proposed Solution:** A context-aware, deterministic heuristic ranking engine that codifies senior recruiter intuition into executable logic. It ranks the top 100 candidates for the Senior AI Engineer role from a pool of 100,000 profiles.
* **Differentiators:** 
  * **Context over Keywords:** Cross-references job titles against actual career descriptions to catch resume-padders.
  * **Intent Detection:** Uses regex lexicons to identify "Shipper" (production/A/B tests) vs. "Researcher" (papers/theory) mindsets.
  * **Behavioral Reality:** Weights platform engagement (response rates, active dates) to ensure candidates are actually hireable.

## JD Understanding & Candidate Evaluation
* **Key Requirements:** Production experience with embeddings/vector DBs (FAISS, Pinecone), Python, evaluation frameworks (NDCG, MRR), and product company background.
* **Important Signals:** Core IR/Retrieval skills (Tier 1), "Shipper" lexicon matches in work history, product company tenure, and high recruiter response rates.
* **Beyond Keyword Matching:** We don't just read the `skills` array. We scan the `career_history` descriptions to verify the candidate actually *used* the skills in a production environment.

## Ranking Methodology
* **Retrieve, Score, Rank:** Load data → Apply hard filters → Extract multi-dimensional features → Calculate weighted composite score → Sort & take Top 100.
* **Algorithms & Heuristics:** Rule-based weighted scoring, Regex pattern matching for intent, and statistical aggregation (average tenure calculation). No heavy ML models.
* **Combining Signals:** Additive weighted scoring (Core IR + Product/Shipper + Stability + Behavioral + Bonus Skills) with strict hard-disqualifiers applied *before* scoring.

## Explainability & Data Validation
* **Explaining Decisions:** Generates rank-specific, fact-based reasoning (e.g., *"Backend Engineer at Swiggy, 3 core IR skills, strong shipper mentality"*). 
* **Zero Hallucinations:** **Because our system does not use an LLM for ranking or text generation, there are absolutely zero hallucinations.** Every piece of reasoning is deterministically generated from verified JSON fields using strict string templates. We never invent skills, companies, or experiences.
* **Handling Bad Profiles:** 
  * **Honeypot Detection:** Math-based checks for time-travel and impossible career durations.
  * **Data Cleaning:** Recursive whitespace normalization to handle messy JSON keys/values.
  * **Hard Filters:** Instant disqualification for consulting-only backgrounds and inactive "ghost" profiles.

## End-to-End Workflow
1. **Ingestion:** Stream and parse `candidates.jsonl`.
2. **Cleaning:** Normalize data and drop honeypots.
3. **Feature Extraction:** Calculate skill tiers, tenure math, and lexicon scores.
4. **Scoring:** Apply hard filters and calculate the 100-point composite score.
5. **Ranking:** Sort by score (desc), break ties by ID (asc).
6. **Export:** Generate reasoning and output `submission.csv`.

## System Architecture
The pipeline is a single-file, linear architecture designed for maximum reproducibility:
1. **Loader:** Reads data and normalizes whitespace.
2. **Filters:** Honeypot detection and hard disqualifiers (drops bad data early).
3. **Scoring Engine:** Feature extraction and weighted heuristic scoring.
4. **Reasoning Gen:** Template-based text generation and CSV export.

## Results & Performance
* **Ranking Quality:** Successfully filters out keyword-stuffers (e.g., Marketing Managers with AI skills) and elevates "hidden gems" (e.g., Data Engineers who shipped FAISS to production).
* **Compute Constraints:**
  * **Runtime:** ~12 seconds (Limit: 5 minutes).
  * **Memory:** ~500 MB RAM (Limit: 16 GB).
  * **Environment:** 100% CPU-only, fully offline, zero network calls.

## Technologies Used
* **Python 3.11:** Fast execution, excellent standard library.
* **Pandas:** Used strictly for efficient, UTF-8 CSV export and sorting.
* **Standard Lib (`json`, `re`, `gzip`, `datetime`):** Handles all parsing, regex matching, and date math.
* **Why this stack?** It guarantees the system runs in seconds on a basic CPU, completely avoiding the latency, compute costs, and hallucination risks of LLM-based approaches.

