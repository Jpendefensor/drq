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
MODEL_NAME = "mistral:7b"
OUTPUT_DIR = "generated_warriors"
MAX_RETRIES = 4

# --- PROMPT ENGINEERING ---
# We give the LLM examples of "Good Code" so it knows to use loops.
FEW_SHOT_PROMPT = """
You are an expert Redcode programmer. Write a warrior that wins.

Here are examples of valid, working warriors:

Example 1 (The Dwarf - A simple bomber):
; strategy: Bomb memory at regular intervals
start:  ADD #4, bomb     ; Increment the bombing pointer
        MOV bomb, @bomb  ; Throw the bomb to location 'bomb'
        JMP start        ; Loop back to start
bomb:   DAT #0, #0       ; The bomb data

Example 2 (The Imp - A mover):
        MOV 0, 1         ; Copy self to next address

Task: Write a warrior based on the user's request.
CRITICAL: 
1. The code MUST have a loop (JMP, DJN, or SPL).
2. Do not let execution fall into a DAT instruction.
3. Use labels (like 'start:') to organize loops.
"""

# Dummy environment
COMPILE_ENV = {'CORESIZE': 8000, 'MAXLENGTH': 100, 'MINDISTANCE': 100}

def query_ollama(prompt, history=[]):
    # Combine System Prompt + History + User Request
    full_text = FEW_SHOT_PROMPT + "\n"
    for item in history:
        full_text += f"\n{item}"
    full_text += f"\nUSER REQUEST: {prompt}\nRESPONSE (Code Block Only):"

    payload = {
        "model": MODEL_NAME,
        "prompt": full_text,
        "stream": False,
        "options": {"temperature": 0.6} # Lower temp = more logical/structured
    }
    
    try:
        response = requests.post(OLLAMA_URL, json=payload)
        response.raise_for_status()
        return response.json()['response']
    except Exception as e:
        print(f"LLM Error: {e}")
        return None

def extract_redcode(text):
    # Same extraction logic as before
    match = re.search(r"```(?:\w+)?\n(.*?)```", text, re.DOTALL)
    code = match.group(1) if match else text
    
    valid_ops = ["MOV", "ADD", "SUB", "MUL", "DIV", "MOD", "JMP", "JMZ", 
                 "JMN", "DJN", "SPL", "SLT", "CMP", "SEQ", "SNE", "NOP", 
                 "DAT", "ORG", "END"]
    
    clean_lines = []
    for line in code.split('\n'):
        clean = line.split(';')[0].strip().upper() # Remove comments
        if not clean: continue
        
        # Heuristic: Line must contain an opcode
        parts = clean.replace(',', ' ').split()
        is_valid = False
        for p in parts:
            if p.split('.')[0] in valid_ops:
                is_valid = True
                break
        
        if is_valid:
            clean_lines.append(line.strip()) # Keep original casing/spacing for readability
                
    return "\n".join(clean_lines)

def validate_code(code_str):
    try:
        lines = code_str.split('\n')
        redcode.parse(lines, COMPILE_ENV)
        
        # LOGIC CHECK: Does it have a loop?
        # A valid warrior usually needs JMP, DJN, or SPL to survive > 10 cycles.
        has_loop = any(op in code_str.upper() for op in ["JMP", "DJN", "SPL", "MOV 0, 1"])
        if not has_loop:
            return False, "Code executes linearly and dies. You are missing a JMP or SPL instruction to create a loop."
            
        return True, None
    except Exception as e:
        return False, str(e)

def generate_warrior(prompt_text, filename):
    print(f"\nTask: {prompt_text}")
    history = []
    
    for attempt in range(MAX_RETRIES):
        print(f" > Attempt {attempt+1}/{MAX_RETRIES}...")
        
        response = query_ollama(prompt_text, history)
        if not response: return None
        
        code = extract_redcode(response)
        if not code.strip(): continue

        is_valid, error_msg = validate_code(code)
        
        if is_valid:
            print(" > SUCCESS! Valid logic found.")
            if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
            path = os.path.join(OUTPUT_DIR, f"{filename}.red")
            with open(path, "w") as f: f.write(code)
            return path
        else:
            print(f"   Logic/Syntax Error: {error_msg}")
            history.append(f"USER: {prompt_text}")
            history.append(f"LLM RESPONSE:\n{code}")
            history.append(f"SYSTEM ERROR: {error_msg}. Please rewrite the code to fix this.")

    print("Failed to generate valid code.")
    return None

if __name__ == "__main__":
    # Test the new logic
    generate_warrior("Write a warrior that throws 'DAT 0, 0' bombs in a loop.", "better_bomber")