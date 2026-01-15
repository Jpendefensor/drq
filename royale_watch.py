import sys
import os
import types
import re
import random
import time
import pygame

# --- CONFIGURATION ---
WARRIOR_DIR = "human_warriors" # Folder to scan for fighters
WARRIORS_PER_ROUND = 6         # How many bots fight at once (6 is standard)
SCALE = 2                      # 2x Zoom
FPS = 60                       
SIDEBAR_WIDTH = 260

# --- THE MEMORY PATCHER ---
def patch_and_load(module_name, file_path):
    with open(file_path, 'r') as f:
        code = f.read()
    code = re.sub(r'from \.(\w+) import', r'from \1 import', code)
    code = re.sub(r'from \. import (\w+)', r'import \1', code)
    module = types.ModuleType(module_name)
    sys.modules[module_name] = module
    exec(code, module.__dict__)
    return module

def main():
    root = os.getcwd()
    src_dir = os.path.join(root, 'corewar', 'corewar')
    sys.path.insert(0, src_dir)

    print("Initializing Battle Royale Engine...")
    try:
        # 1. Load Modules
        patch_and_load('core', os.path.join(src_dir, 'core.py'))
        patch_and_load('redcode', os.path.join(src_dir, 'redcode.py'))
        patch_and_load('mars', os.path.join(src_dir, 'mars.py'))
        
        # 2. Patch Image Loader
        original_load = pygame.image.load
        def smart_load(path):
            if 'pixels' in path or 'instructions' in path:
                locs = [
                    os.path.join(src_dir, 'pixels', 'instructions.png'),
                    os.path.join(root, 'corewar', 'pixels', 'instructions.png')
                ]
                for p in locs:
                    if os.path.exists(p): return original_load(p)
            return original_load(path)
        pygame.image.load = smart_load
        
        viz = patch_and_load('viz', os.path.join(src_dir, 'viz.py'))
        
    except Exception as e:
        print(f"Setup Error: {e}")
        return

    pygame.init()

    # --- 3. GRAPHICS SCALING ---
    viz.INSTRUCTION_SIZE_X = 9
    viz.INSTRUCTION_SIZE_Y = 9
    viz.I_SIZE = (9, 9)
    
    try:
        viz.OPCODE_SURFACES = viz.load_opcode_surfaces()
        final_size = (9 * SCALE, 9 * SCALE)
        for op in viz.OPCODE_SURFACES:
            viz.OPCODE_SURFACES[op] = pygame.transform.scale(viz.OPCODE_SURFACES[op], final_size)
    except Exception as e:
        print(f"Graphics Error: {e}")
        sys.exit(1)

    viz.INSTRUCTION_SIZE_X = 9 * SCALE
    viz.INSTRUCTION_SIZE_Y = 9 * SCALE
    viz.I_SIZE = final_size
    viz.I_AREA = ((0,0), final_size)

    # --- 4. LOAD ALL WARRIORS ---
    print(f"Scanning '{WARRIOR_DIR}' for warriors...")
    env = {'CORESIZE': 8000, 'CYCLES': 80000, 'MAXPROCESSES': 8000, 
           'MAXLENGTH': 100, 'MINDISTANCE': 100, 'ROUNDS': 1}
    
    all_warriors = []
    parser = sys.modules['redcode']
    
    files = [f for f in os.listdir(WARRIOR_DIR) if f.endswith('.red')]
    if not files:
        print(f"Error: No .red files found in {WARRIOR_DIR}")
        sys.exit(1)

    for f in files:
        try:
            path = os.path.join(WARRIOR_DIR, f)
            with open(path, 'r', errors='replace') as file:
                w = parser.parse(file.readlines(), env)
                w.filename = f # Store filename for display
                all_warriors.append(w)
        except Exception as e:
            print(f"Skipping {f}: {e}")

    print(f"Loaded {len(all_warriors)} warriors. Starting tournament!")

    # --- WINDOW SETUP ---
    sim = viz.PygameMARS(minimum_separation=100, max_processes=8000)
    grid_w = viz.INSTRUCTIONS_PER_LINE * viz.INSTRUCTION_SIZE_X
    grid_h = (len(sim) // viz.INSTRUCTIONS_PER_LINE) * viz.INSTRUCTION_SIZE_Y
    
    screen = pygame.display.set_mode((grid_w + SIDEBAR_WIDTH, grid_h))
    pygame.display.set_caption("Core War: Battle Royale")
    font = pygame.font.SysFont("monospace", 14)
    big_font = pygame.font.SysFont("monospace", 24)
    
    clock = pygame.time.Clock()
    running = True
    
    # --- BATTLE LOOP ---
    while running:
        # A. Pick Random Combatants
        combatants = random.sample(all_warriors, min(len(all_warriors), WARRIORS_PER_ROUND))
        
        # B. Assign Colors (Cycle through the 10 available colors)
        for i, w in enumerate(combatants):
            w.color = viz.WARRIOR_COLORS[i % len(viz.WARRIOR_COLORS)]
            w.wins = w.ties = w.losses = 0
            w.task_queue = [] # Ensure clean state
        
        sim.warriors = combatants
        sim.reset()
        
        cycle = 0
        paused = False
        round_over = False
        
        print(f"\n--- NEW ROUND ---")
        for w in combatants: print(f" > {w.name} ({w.filename})")

        # C. Round Loop
        while not round_over and running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT: 
                    running = False
                    round_over = True
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE: 
                        running = False
                        round_over = True
                    if event.key == pygame.K_SPACE: paused = not paused
                    if event.key == pygame.K_n: round_over = True # Force next round

            if not paused:
                sim.step()
                cycle += 1
                alive = [w for w in sim.warriors if w.task_queue]
                
                # End condition: 1 or 0 warriors left
                if len(alive) <= 1 or cycle >= 80000:
                    winner = alive[0].name if len(alive) == 1 else "None"
                    print(f"Round Over. Winner: {winner}")
                    round_over = True
                    # Pause briefly to show winner
                    time.sleep(2.0)

            # --- RENDER ---
            sim.blit_into(screen, (0,0))
            pygame.draw.rect(screen, (20, 20, 20), (grid_w, 0, SIDEBAR_WIDTH, grid_h))
            
            # Sidebar Stats
            y = 10
            screen.blit(big_font.render("COMBATANTS", True, (255,255,255)), (grid_w + 10, y))
            y += 40
            
            # Sort by processes (who is winning right now?)
            sorted_w = sorted(combatants, key=lambda w: len(w.task_queue), reverse=True)
            
            for w in sorted_w:
                alive_count = len(w.task_queue)
                color = w.color[1] if alive_count > 0 else (80, 80, 80)
                name_txt = f"{w.name[:15]}"
                proc_txt = f"{alive_count}"
                
                screen.blit(font.render(name_txt, True, color), (grid_w + 10, y))
                screen.blit(font.render(proc_txt, True, (200,200,200)), (grid_w + 200, y))
                y += 25

            # Instructions Inspector
            mx, my = pygame.mouse.get_pos()
            if 0 <= mx < grid_w and 0 <= my < grid_h:
                col = mx // viz.INSTRUCTION_SIZE_X
                row = my // viz.INSTRUCTION_SIZE_Y
                c_addr = (row * viz.INSTRUCTIONS_PER_LINE) + col
                
                y += 20
                pygame.draw.line(screen, (100,100,100), (grid_w+10, y), (grid_w+240, y))
                y += 10
                
                for i in range(-5, 6): # Show +/- 5 lines
                    addr = (c_addr + i) % 8000
                    instr = sim.core[addr]
                    color = (255, 255, 255) if i == 0 else (120, 120, 120)
                    if hasattr(instr, 'fg_color') and instr.fg_color != (60,60,60):
                         if i != 0: color = instr.fg_color
                    
                    line = f"{addr:04d} {instr}"
                    screen.blit(font.render(line, True, color), (grid_w + 10, y))
                    y += 18

            pygame.display.flip()
            clock.tick(FPS)

    pygame.quit()

if __name__ == "__main__":
    main()