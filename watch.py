import sys
import os
import types
import re
import pygame

# --- CONFIGURATION ---
WARRIOR_1 = "human_warriors/dwarf.red"
WARRIOR_2 = "human_warriors/antidwarf2.red"
SCALE = 2           # <--- 2x ZOOM (Perfect for laptops)
FPS = 60            
SIDEBAR_WIDTH = 260 # Room for the code inspector

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

    print("Initializing...")
    try:
        # 1. Load Modules
        patch_and_load('core', os.path.join(src_dir, 'core.py'))
        patch_and_load('redcode', os.path.join(src_dir, 'redcode.py'))
        patch_and_load('mars', os.path.join(src_dir, 'mars.py'))
        
        # 2. Patch Image Loader
        original_load = pygame.image.load
        def smart_load(path):
            if 'pixels' in path or 'instructions' in path:
                # Look in both potential locations
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

    # --- 3. GRAPHICS SCALING FIX (CRITICAL STEP) ---
    # A. Ensure constants are at DEFAULT (9x9) so loading works
    viz.INSTRUCTION_SIZE_X = 9
    viz.INSTRUCTION_SIZE_Y = 9
    viz.I_SIZE = (9, 9)
    
    # B. Load the original small graphics
    try:
        viz.OPCODE_SURFACES = viz.load_opcode_surfaces()
    except Exception as e:
        print(f"\nGraphics Error: {e}\nCould not cut sprites from sheet.")
        sys.exit(1)

    # C. Scale them up in memory
    print(f"Scaling graphics {SCALE}x...")
    final_size = (9 * SCALE, 9 * SCALE)
    for op in viz.OPCODE_SURFACES:
        viz.OPCODE_SURFACES[op] = pygame.transform.scale(viz.OPCODE_SURFACES[op], final_size)

    # D. Now update constants so the simulator draws big blocks
    viz.INSTRUCTION_SIZE_X = 9 * SCALE
    viz.INSTRUCTION_SIZE_Y = 9 * SCALE
    viz.I_SIZE = final_size
    viz.I_AREA = ((0,0), final_size)

    # --- SIMULATION ---
    print(f"Loading warriors...")
    env = {'CORESIZE': 8000, 'CYCLES': 80000, 'MAXPROCESSES': 8000, 
           'MAXLENGTH': 100, 'MINDISTANCE': 100, 'ROUNDS': 1}
           
    def load_w(path):
        with open(path, 'r', errors='replace') as f:
            return sys.modules['redcode'].parse(f.readlines(), env)

    w1 = load_w(WARRIOR_1)
    w2 = load_w(WARRIOR_2)
    
    w1.color = viz.WARRIOR_COLORS[0] # Blue
    w2.color = viz.WARRIOR_COLORS[3] # Red
    for w in [w1, w2]: w.wins = w.ties = w.losses = 0

    sim = viz.PygameMARS(minimum_separation=100, max_processes=8000)
    sim.warriors = [w1, w2]
    sim.reset()

    # --- WINDOW SETUP ---
    grid_w = viz.INSTRUCTIONS_PER_LINE * viz.INSTRUCTION_SIZE_X
    grid_h = (len(sim) // viz.INSTRUCTIONS_PER_LINE) * viz.INSTRUCTION_SIZE_Y
    
    screen = pygame.display.set_mode((grid_w + SIDEBAR_WIDTH, grid_h))
    pygame.display.set_caption(f"Core War: {w1.name} vs {w2.name}")
    font = pygame.font.SysFont("monospace", 14)
    
    clock = pygame.time.Clock()
    running = True
    paused = False
    cycle = 0

    print("Controls: [SPACE] Pause, [S] Step, [ESC] Quit")

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: running = False
                if event.key == pygame.K_SPACE: paused = not paused
                if event.key == pygame.K_s:
                    paused = True
                    sim.step()
                    cycle += 1

        if not paused and cycle < 80000:
            sim.step()
            cycle += 1
            alive = [w for w in sim.warriors if w.task_queue]
            if len(alive) < 2:
                print(f"Match End at cycle {cycle}.")
                paused = True

        # --- RENDER ---
        # 1. Grid
        sim.blit_into(screen, (0,0))
        
        # 2. Sidebar
        pygame.draw.rect(screen, (20, 20, 20), (grid_w, 0, SIDEBAR_WIDTH, grid_h))
        
        # Inspector Logic
        mx, my = pygame.mouse.get_pos()
        if 0 <= mx < grid_w and 0 <= my < grid_h:
            col = mx // viz.INSTRUCTION_SIZE_X
            row = my // viz.INSTRUCTION_SIZE_Y
            c_addr = (row * viz.INSTRUCTIONS_PER_LINE) + col
            
            # Show +/- 15 lines of code
            text_y = 10
            for i in range(-15, 15):
                addr = (c_addr + i) % 8000
                instr = sim.core[addr]
                color = (255, 255, 255) if i == 0 else (120, 120, 120)
                
                # Highlight if owned by a warrior
                # (We check color to guess ownership since MARS doesn't track it cleanly per cell)
                if hasattr(instr, 'fg_color') and instr.fg_color != (60,60,60): # Default gray
                     if i != 0: color = instr.fg_color

                line = f"{addr:04d} {instr}"
                screen.blit(font.render(line, True, color), (grid_w + 10, text_y))
                text_y += 20

        # Stats
        stats_y = grid_h - 80
        screen.blit(font.render(f"Cycle: {cycle}", True, (0, 255, 0)), (grid_w + 10, stats_y))
        screen.blit(font.render(f"{w1.name}: {len(w1.task_queue)}", True, w1.color[1]), (grid_w + 10, stats_y + 20))
        screen.blit(font.render(f"{w2.name}: {len(w2.task_queue)}", True, w2.color[1]), (grid_w + 10, stats_y + 40))

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()

if __name__ == "__main__":
    main()