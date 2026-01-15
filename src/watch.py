import sys
import os
import pygame

# --- 1. PATH FIXES ---
# Get the current directory (drq/)
current_dir = os.getcwd()

# A. Add the package root so 'import corewar' works
sys.path.append(os.path.join(current_dir, 'corewar'))

# B. Add the source source folder so internal files like viz.py 
# can find 'mars.py' and 'core.py' directly.
sys.path.append(os.path.join(current_dir, 'corewar', 'corewar'))

# Monkey-patch pygame to find the pixels/instructions.png
# (The original code looks for it in the current folder, but it's hidden deep inside)
original_image_load = pygame.image.load
def smart_load(filename):
    # If the file is right here, load it
    if os.path.exists(filename):
        return original_image_load(filename)
    
    # Check the likely nested location: corewar/corewar/pixels/...
    nested_path = os.path.join("corewar", "corewar", filename)
    if os.path.exists(nested_path):
        return original_image_load(nested_path)
    
    # Try one level shallower just in case
    nested_path_2 = os.path.join("corewar", filename)
    if os.path.exists(nested_path_2):
        return original_image_load(nested_path_2)
        
    raise FileNotFoundError(f"Could not find {filename}. Run this from the 'drq' folder.")
pygame.image.load = smart_load

# --- 2. IMPORT SIMULATOR ---
try:
    # We try importing 'viz' directly since we added the inner folder to path
    import viz
    import redcode
    # Extract the classes we need
    PygameMARS = viz.PygameMARS
    load_opcode_surfaces = viz.load_opcode_surfaces
    WARRIOR_COLORS = viz.WARRIOR_COLORS
except ImportError as e:
    print(f"Import Error: {e}")
    print("Debug: paths are", sys.path)
    sys.exit(1)

# --- 3. CONFIGURATION ---
WARRIOR_1_PATH = "human_warriors/dwarf.red"
WARRIOR_2_PATH = "human_warriors/antidwarf2.red"
SCALE = 3          # <--- TRIPLES THE SIZE (1 pixel becomes 3x3)
FPS = 60           # Speed of the simulation

ENV = {
    'CORESIZE': 8000,
    'CYCLES': 80000,
    'MAXPROCESSES': 8000,
    'MAXLENGTH': 100,
    'MINDISTANCE': 100,
    'ROUNDS': 1
}

# --- 4. MAIN LOOP ---
def load_warrior(filename, environment):
    with open(filename, 'r', encoding='utf-8', errors='replace') as f:
        return redcode.parse(f.readlines(), environment)

def main():
    pygame.init()
    
    # Initialize graphics resources
    viz.OPCODE_SURFACES = load_opcode_surfaces()

    # 1. Prepare Warriors
    print(f"Loading {WARRIOR_1_PATH} vs {WARRIOR_2_PATH}...")
    w1 = load_warrior(WARRIOR_1_PATH, ENV)
    w2 = load_warrior(WARRIOR_2_PATH, ENV)
    
    w1.color = WARRIOR_COLORS[0] # Blueish
    w2.color = WARRIOR_COLORS[3] # Reddish
    
    for w in [w1, w2]:
        w.wins = w.ties = w.losses = 0

    # 2. Initialize Simulator
    sim = PygameMARS(minimum_separation=ENV['MINDISTANCE'], max_processes=ENV['MAXPROCESSES'])
    sim.warriors = [w1, w2]
    sim.reset()

    # 3. Setup Screen
    base_w, base_h = sim.size 
    screen = pygame.display.set_mode((base_w * SCALE, base_h * SCALE))
    pygame.display.set_caption(f"Core War (3x Zoom) - [SPACE] Pause [S] Step")
    
    virtual_screen = pygame.Surface(sim.size)
    clock = pygame.time.Clock()
    running = True
    paused = False
    cycle = 0

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    paused = not paused
                elif event.key == pygame.K_s:
                    paused = True
                    # Step once manually
                    sim.step()
                    cycle += 1

        if not paused and cycle < ENV['CYCLES']:
            sim.step()
            cycle += 1
            
            alive = [w for w in sim.warriors if w.task_queue]
            if len(alive) < 2:
                print(f"Battle ended at cycle {cycle}.")
                paused = True 

        # Render
        virtual_screen.fill((0,0,0)) 
        sim.blit_into(virtual_screen, (0,0))
        
        # Scale Up
        scaled_view = pygame.transform.scale(virtual_screen, (base_w * SCALE, base_h * SCALE))
        screen.blit(scaled_view, (0,0))
        
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()

if __name__ == "__main__":
    main()