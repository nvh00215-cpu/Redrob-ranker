import gradio as gr
import subprocess
import os

# Limit file size to 5MB (plenty for 100 candidates, prevents OOM crashes)
MAX_FILE_SIZE_MB = 5.0

def run_ranker(file):
    if file is None:
        return None, "❌ Please upload a file first."
    
    # 1. Check file size to prevent Out-Of-Memory crashes on HuggingFace Spaces
    file_size_mb = os.path.getsize(file) / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        return None, f"❌ File too large ({file_size_mb:.2f} MB). As per hackathon rules, this sandbox is optimized for small samples (≤100 candidates). Please upload a file under {MAX_FILE_SIZE_MB}MB."

    output_path = "submission.csv"
    
    # Clean up previous output if it exists
    if os.path.exists(output_path):
        os.remove(output_path)
        
    # 2. Run the ranker script using subprocess
    try:
        result = subprocess.run(
            ["python", "rank.py", file, output_path],
            capture_output=True, text=True, check=True
        )
    except subprocess.CalledProcessError as e:
        return None, f"❌ Ranking failed:\n{e.stderr}"
        
    if os.path.exists(output_path):
        return output_path, f"✅ Success! Processed {file_size_mb:.2f} MB. Your ranked CSV is ready for download."
    else:
        return None, "❌ CSV file was not generated."

with gr.Blocks() as demo:
    gr.Markdown("# 🧭 Redrob Intelligent Ranker Sandbox")
    gr.Markdown(f"Upload a small candidate sample (≤100 candidates, <{MAX_FILE_SIZE_MB}MB) to test the ranking logic.")
    
    with gr.Row():
        file_input = gr.File(label="📁 Upload Candidate File", file_types=[".json", ".jsonl"])
        file_output = gr.File(label="📄 Download Ranked CSV")
    
    status_text = gr.Textbox(label="📊 Status", interactive=False, lines=5)
    
    btn = gr.Button("🚀 Run Ranker", variant="primary", size="lg")
    btn.click(fn=run_ranker, inputs=file_input, outputs=[file_output, status_text])

if __name__ == "__main__":
    demo.launch()
