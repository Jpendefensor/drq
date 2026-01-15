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
MODEL_NAME = "deepseek-coder-v2:latest"
OUTPUT_DIR = "generated_warriors"
MAX_RETRIES = 5

FEW_SHOT_PROMPT = """
### Redcode Specification (ICWS'94)
You are an expert Core War programmer. Write high-performance Redcode.

### Syntax Protocol:
1. Instruction Format: <OPCODE>.<MODIFIER> <OPERAND_A>, <OPERAND_B>
2. Opcodes: MOV, ADD, SUB, JMP, JMZ, JMN, DJN, SPL, DAT, SLT, SEQ, SNE.
3. Addressing: # (Immediate), $ (Direct), @ (Indirect), < (Pre-dec), > (Post-inc).
4. No Markdown headers inside the code block.
5. All warriors must be self-sustaining (looping).

### Strategy Definition: "The Stone"
A 'Stone' is a fast, aggressive bomber. It uses a small, tight loop to throw DAT bombs at regular intervals across the core.

### Objective:
Write a 'Stone' warrior.
- Line 1: Increment a pointer.
- Line 2: Move a DAT bomb to the pointer's location.
- Line 3: Jump back to Line 1.
- Line 4: The DAT bomb itself.
"""

COMPILE_ENV = {'CORESIZE': 8000, 'MAXLENGTH': 100, 'MINDISTANCE': 100}

def query_ollama(prompt, history=[]):
    # Simplified prompt to avoid confusing the model
    full_text = f"{FEW_SHOT_PROMPT}\n"
    for item in history:
        full_text += f"\n{item}"
    full_text += f"\nUSER REQUEST: {prompt}\n\nAssistant: Here is the Redcode:\n```redcode\n"

    payload = {
        "model": MODEL_NAME,
        "prompt": full_text,
        "stream": False,
        "options": {
            "temperature": 0.1,  # Keep it very predictable
            "stop": ["```"]      # Tell the model to stop exactly when the block ends
        }
    }
    
    try:
        response = requests.post(OLLAMA_URL, json=payload)
        response.raise_for_status()
        return response.json()['response']
    except Exception as e:
        print(f"LLM Error: {e}")
        return None

def extract_redcode(text):
    # 1. FIND THE CODE BLOCK: DeepSeek loves ```redcode ... ```
    # This regex looks for the first code block and takes its content.
    match = re.search(r"```(?:[a-zA-Z]+)?\n(.*?)\n```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    
    # 2. FALLBACK: If no backticks, take lines that look like opcodes
    valid_ops = ["MOV", "ADD", "SUB", "MUL", "DIV", "MOD", "JMP", "JMZ", 
                 "JMN", "DJN", "SPL", "SLT", "CMP", "SEQ", "SNE", "NOP", "DAT"]
    
    lines = []
    for line in text.split('\n'):
        # Just check if any valid opcode is in the line
        if any(op in line.upper() for op in valid_ops):
            lines.append(line.strip())
    
    return "\n".join(lines)

def validate_code(code_str):
    if not code_str.strip():
        return False, "No valid Redcode instructions found."
    try:
        lines = code_str.split('\n')
        redcode.parse(lines, COMPILE_ENV)
        
        # Basic survival check
        has_loop = any(op in code_str.upper() for op in ["JMP", "DJN", "SPL", "MOV 0, 1"])
        if not has_loop:
            return False, "Warrior will die instantly (no loop)."
            
        return True, None
    except Exception as e:
        return False, str(e)

def generate_warrior(prompt_text, filename):
    print(f"\nTarget: {filename}")
    history = []
    
    for attempt in range(MAX_RETRIES):
        print(f" > Attempt {attempt+1}/{MAX_RETRIES}...", end=" ")
        
        response = query_ollama(prompt_text, history)
        if not response: 
            print("No response from Ollama.")
            continue
        
        code = extract_redcode(response)
        is_valid, error_msg = validate_code(code)
        
        if is_valid:
            print("SUCCESS.")
            if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
            path = os.path.join(OUTPUT_DIR, f"{filename}.red")
            with open(path, "w") as f: f.write(code)
            return path
        else:
            print(f"FAILED. ({error_msg})")
            history.append(f"ERROR in previous code: {error_msg}")
            history.append("Ensure your labels are followed by a space and a valid opcode.")

    return None

if __name__ == "__main__":
    # Switching to DeepSeek's logical strength
    generate_warrior(
        "Generate a 'Stone' variant with a bombing step of 127. "
        "Use relative addressing. Ensure the labels 'loop' and 'bomb' are distinct.", 
        "deepseek_stone_v1"
    )