import sys
import os
import random
import time
import types
import re
import pygame

WARRIOR_DIR = "human_warriors"
WARRIORS_PER_ROUND = 6
SCALE = 2
FPS = 60
SIDEBAR_WIDTH = 260

def patch_and_load(module_name, file_path):
    with open(file_path, 'r') as f: code = f.read()
    code = re.sub(r'from \.(\w+) import', r'from \1 import', code)
    code = re.sub(r'from \. import (\w+)', r'import \1', code)
    module = types.ModuleType(module_name)
    module.__file__ = os.path.abspath(file_path) # <--- THE FIX
    sys.modules[module_name] = module
    exec(code, module.__dict__)
    return module

def main():
    root = os.getcwd()
    src_dir = os.path.join(root, 'corewar', 'corewar')
    sys.path.insert(0, src_dir)

    print("Initializing Royale...")
    try:
        patch_and_load('core', os.path.join(src_dir, 'core.py'))
        patch_and_load('redcode', os.path.join(src_dir, 'redcode.py'))
        patch_and_load('mars', os.path.join(src_dir, 'mars.py'))
        viz = patch_and_load('viz', os.path.join(src_dir, 'viz.py'))
    except Exception as e:
        print(f"Setup Error: {e}")
        return

    pygame.init()
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

    # --- LOAD WARRIORS ---
    print(f"Scanning '{WARRIOR_DIR}'...")
    env = {'CORESIZE': 8000, 'CYCLES': 80000, 'MAXPROCESSES': 8000, 
           'MAXLENGTH': 100, 'MINDISTANCE': 100, 'ROUNDS': 1}
    
    all_warriors = []
    files = [f for f in os.listdir(WARRIOR_DIR) if f.endswith('.red')]
    if not files: print("No warriors found!"); sys.exit(1)

    parser = sys.modules['redcode'] # Use loaded module
    for f in files:
        try:
            with open(os.path.join(WARRIOR_DIR, f), 'r', errors='replace') as file:
                w = parser.parse(file.readlines(), env)
                w.filename = f
                all_warriors.append(w)
        except: pass

    print(f"Loaded {len(all_warriors)} warriors.")

    sim = viz.PygameMARS(minimum_separation=100, max_processes=8000)
    grid_w = viz.INSTRUCTIONS_PER_LINE * viz.INSTRUCTION_SIZE_X
    grid_h = (len(sim) // viz.INSTRUCTIONS_PER_LINE) * viz.INSTRUCTION_SIZE_Y
    screen = pygame.display.set_mode((grid_w + SIDEBAR_WIDTH, grid_h))
    pygame.display.set_caption("Core War: Battle Royale")
    font = pygame.font.SysFont("monospace", 14)
    clock = pygame.time.Clock()
    running = True

    while running:
        combatants = random.sample(all_warriors, min(len(all_warriors), WARRIORS_PER_ROUND))
        for i, w in enumerate(combatants):
            w.color = viz.WARRIOR_COLORS[i % len(viz.WARRIOR_COLORS)]
            w.wins = w.ties = w.losses = 0
            w.task_queue = []
        
        sim.warriors = combatants
        sim.reset()
        cycle = 0; paused = False; round_over = False
        print(f"\n--- ROUND: {[w.name for w in combatants]} ---")

        while not round_over and running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT: running = False; round_over = True
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE: running = False; round_over = True
                    if event.key == pygame.K_SPACE: paused = not paused
                    if event.key == pygame.K_n: round_over = True

            if not paused:
                sim.step(); cycle += 1
                alive = [w for w in sim.warriors if w.task_queue]
                if len(alive) <= 1 or cycle >= 80000:
                    print(f"Winner: {alive[0].name if alive else 'Draw'}")
                    round_over = True
                    time.sleep(1.5)

            sim.blit_into(screen, (0,0))
            pygame.draw.rect(screen, (20, 20, 20), (grid_w, 0, SIDEBAR_WIDTH, grid_h))
            y = 10
            for w in sorted(combatants, key=lambda x: len(x.task_queue), reverse=True):
                cnt = len(w.task_queue)
                color = w.color[1] if cnt > 0 else (80,80,80)
                screen.blit(font.render(f"{w.name[:15]}: {cnt}", True, color), (grid_w+10, y))
                y += 25
            
            # Draw Inspector (Simplified)
            mx, my = pygame.mouse.get_pos()
            if 0 <= mx < grid_w and 0 <= my < grid_h:
                col = mx // viz.INSTRUCTION_SIZE_X; row = my // viz.INSTRUCTION_SIZE_Y
                c_addr = (row * viz.INSTRUCTIONS_PER_LINE) + col
                y += 20
                for i in range(-5, 6):
                    addr = (c_addr + i) % 8000
                    instr = sim.core[addr]
                    color = (255,255,255) if i == 0 else (120,120,120)
                    if hasattr(instr, 'fg_color') and instr.fg_color != (60,60,60):
                         if i != 0: color = instr.fg_color
                    screen.blit(font.render(f"{addr:04d} {instr}", True, color), (grid_w + 10, y))
                    y += 18
            
            pygame.display.flip()
            clock.tick(FPS)
    pygame.quit()

if __name__ == "__main__":
    main()