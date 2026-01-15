import requests
import json
import re
import os
import sys

# --- SETUP PATHS ---
current_dir = os.getcwd()
src_dir = os.path.join(current_dir, 'corewar', 'corewar')
sys.path.insert(0, src_dir)

try:
    import redcode
except ImportError:
    print("Error: Could not find 'redcode' library.")
    sys.exit(1)

# --- CONFIGURATION ---
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3.1:8b" # This fits perfectly in 15GB RAM
OUTPUT_DIR = "generated_warriors"
MAX_RETRIES = 5

# Optimized for Llama 3.1 logic
FEW_SHOT_PROMPT = """You are a Core War expert. Write ICWS'94 Redcode. 
Output ONLY the code block. Do not explain the code.

Example Stone Strategy:
step  DAT #4, #4
start ADD step, target
      MOV step, @target
      JMP start
target DAT #0, #0

TASK: Write the warrior requested by the user. 
Use labels and ensure there is a JMP loop.
"""

COMPILE_ENV = {'CORESIZE': 8000, 'MAXLENGTH': 100, 'MINDISTANCE': 100}

def query_ollama(prompt, history=[]):
    # Llama 3.1 responds best to a clear distinction between instructions and task
    full_prompt = f"{FEW_SHOT_PROMPT}\n\n"
    for item in history:
        full_prompt += f"{item}\n"
    full_prompt += f"USER REQUEST: {prompt}\nASSISTANT: Here is the code:\n```redcode\n"

    payload = {
        "model": MODEL_NAME,
        "prompt": full_prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_ctx": 2048
        }
    }
    
    try:
        # Reduced timeout to 30s because Llama 8b should be fast
        response = requests.post(OLLAMA_URL, json=payload, timeout=30)
        response.raise_for_status()
        return response.json().get('response', '')
    except Exception as e:
        print(f"\n[LLM ERROR]: {e}")
        return None

def extract_redcode(text):
    # 1. Grab everything inside the first code block
    match = re.search(r"```(?:\w+)?\n(.*?)```", text, re.DOTALL)
    code = match.group(1) if match else text
    
    valid_ops = ["MOV", "ADD", "SUB", "MUL", "DIV", "MOD", "JMP", "JMZ", 
                 "JMN", "DJN", "SPL", "SLT", "CMP", "SEQ", "SNE", "NOP", "DAT"]
    
    clean_lines = []
    for line in code.split('\n'):
        # 2. Strict line cleaning
        line = line.split(';')[0].strip() # Remove comments
        if not line: continue
        
        # 3. Final sanity check: Does this line actually have an opcode?
        # This prevents "This code does X" from entering the compiler
        upper_line = line.upper()
        if any(f" {op}" in f" {upper_line}" or f"{op}." in upper_line or upper_line.startswith(op) for op in valid_ops):
            clean_lines.append(line)
                
    return "\n".join(clean_lines)

def validate_code(code_str):
    if not code_str.strip():
        return False, "No code instructions found."
    try:
        lines = code_str.split('\n')
        redcode.parse(lines, COMPILE_ENV)
        
        # Survival check
        has_loop = any(op in code_str.upper() for op in ["JMP", "DJN", "SPL", "MOV 0, 1"])
        if not has_loop:
            return False, "The code has no execution loop (JMP/SPL) and will die instantly."
            
        return True, None
    except Exception as e:
        return False, str(e)

def generate_warrior(prompt_text, filename):
    print(f"\nGenerating: {filename} with {MODEL_NAME}...")
    history = []
    
    for attempt in range(MAX_RETRIES):
        print(f" > Attempt {attempt+1}/{MAX_RETRIES}...", end=" ", flush=True)
        
        raw_response = query_ollama(prompt_text, history)
        if not raw_response:
            continue
            
        code = extract_redcode(raw_response)
        is_valid, error_msg = validate_code(code)
        
        if is_valid:
            print("SUCCESS.")
            if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
            path = os.path.join(OUTPUT_DIR, f"{filename}.red")
            with open(path, "w") as f: f.write(code)
            return path
        else:
            print(f"RETRYING... ({error_msg[:40]}...)")
            history.append(f"USER: Fix the syntax error: {error_msg}")

    print("!!! Failed after 5 attempts.")
    return None

if __name__ == "__main__":
    generate_warrior(
        "Design a 'Vampire' warrior. \n"
        "1. Create a 'trap' (pit) using a DAT instruction that kills any process. \n"
        "2. Create a 'fang' (a JMP instruction) that points back to your trap. \n"
        "3. Use a loop to copy your 'fang' to a new random or incrementing location in memory. \n"
        "Goal: Ensnare the enemy process and force them to execute your trap.", 
        "vampire_v1"
    )