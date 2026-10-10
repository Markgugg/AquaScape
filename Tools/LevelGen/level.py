"""
level.py - the hand-designed AquaScape level, written as a few shapes and
hand-placed objects, then saved as a readable ASCII map that the Unity
builder (AquaScape > Build Level) turns into tilemaps and prefabs.

World is 120 x 34 cells. x grows east, y grows north (row 0 = south edge).
Areas: Blue Lagoon x 0-39, Glass City x 40-79, Moonpool x 80-119.

Terrain:  .  water        #  plaza (white ceramic)    g  grass on ground
          =  glass walkway   1-4  bridge cells (water until the bridge forms)
Objects (sit on whatever terrain surrounds them):
  P player start   o bubble    C bubble clam   Y bridge pylon   S prism shard
  B beacon         X glass cube O pressure pad  G glass gate    L moon lantern
  J jellyfish      M moonpool exit
  T palm  t bush  f flowers  e fern  r rock  l lamp  k glass spire  A arch  n night flower
"""
import math
import os

W, H = 120, 34
grid = [['.'] * W for _ in range(H)]


def put(x, y, ch):
    if 0 <= x < W and 0 <= y < H:
        grid[y][x] = ch


def get(x, y):
    return grid[y][x] if 0 <= x < W and 0 <= y < H else '.'


def ellipse(cx, cy, rx, ry, ch, only=None):
    for y in range(H):
        for x in range(W):
            if ((x + 0.5 - cx) / rx) ** 2 + ((y + 0.5 - cy) / ry) ** 2 <= 1.0:
                if only is None or get(x, y) in only:
                    put(x, y, ch)


def rect(x0, y0, x1, y1, ch, only=None):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if only is None or get(x, y) in only:
                put(x, y, ch)


def objects(*items):
    for x, y, ch in items:
        put(x, y, ch)


LAND = '#g'

# =============================================================================
# 1. BLUE LAGOON  (x 0-39)  - grassy islands, learn to move, collect and pulse
# =============================================================================
# glass walkways first so islands paint over their ends
rect(10, 15, 13, 16, '=')               # start island -> main island
rect(6, 8, 7, 12, '=')                  # start island -> south-west cove
rect(18, 21, 19, 24, '=')               # main island -> north grove

ellipse(6.5, 16.5, 4.6, 4.2, 'g')       # start island
rect(9, 15, 10, 16, '#', LAND)          # little landing plaza
ellipse(20.5, 16.5, 7.8, 6.2, 'g')      # main island
ellipse(20.5, 17.3, 2.6, 1.9, '#', LAND)  # beacon plaza
rect(14, 16, 18, 16, '#', LAND)         # plaza path west
rect(20, 12, 20, 15, '#', LAND)         # plaza path south
ellipse(17.5, 27.0, 6.2, 3.6, 'g')      # north grove
ellipse(8.0, 5.5, 4.2, 3.2, 'g')        # south-west cove
ellipse(30.0, 4.5, 4.3, 2.9, 'g')       # shard islet (reached by bridge 1)
ellipse(30.0, 4.6, 1.8, 1.2, '#', LAND)
ellipse(9.5, 28.5, 2.6, 2.0, 'g')       # decorative islets
ellipse(34.5, 11.5, 1.8, 1.5, 'g')

rect(26, 6, 27, 12, '1', '.')           # bridge 1 (pylon) main -> shard islet
rect(28, 16, 41, 17, '2', '.')          # bridge 2 (beacon 1) lagoon -> city

objects(
    (5, 16, 'P'),
    # start island: a trail of bubbles toward the walkway
    (7, 18, 'o'), (9, 18, 'o'), (11, 16, 'o'), (12, 15, 'o'), (4, 14, 'o'),
    (3, 18, 'T'), (5, 20, 'T'), (8, 13, 'T'), (2, 15, 't'), (6, 19, 'f'), (9, 14, 'e'), (4, 13, 'r'),
    # south-west cove: first clam
    (8, 5, 'C'), (6, 6, 'o'), (10, 6, 'o'), (6, 10, 'o'),
    (5, 4, 'T'), (11, 4, 't'), (9, 7, 'f'), (7, 3, 'r'),
    # main island
    (20, 18, 'B'),
    (24, 12, 'Y'),
    (15, 19, 'o'), (16, 13, 'o'), (24, 19, 'o'), (26, 15, 'o'), (17, 16, 'o'), (23, 14, 'o'),
    (14, 20, 'T'), (26, 19, 'T'), (16, 12, 'T'), (13, 14, 't'), (27, 14, 't'), (22, 21, 'f'),
    (18, 11, 'f'), (25, 17, 'e'), (15, 15, 'r'), (23, 12, 'l'), (17, 20, 'l'),
    # north grove: two clams and lots of plants
    (14, 27, 'C'), (21, 28, 'C'), (17, 26, 'o'), (19, 29, 'o'), (12, 26, 'o'), (23, 26, 'o'),
    (13, 29, 'T'), (22, 25, 'T'), (16, 30, 'T'), (18, 28, 't'), (20, 26, 'f'), (11, 27, 'e'), (24, 28, 'f'),
    # shard islet
    (30, 5, 'S'), (28, 4, 'o'), (32, 4, 'o'), (27, 3, 'T'), (33, 3, 't'), (31, 6, 'f'),
    # decor islets
    (9, 29, 'T'), (34, 11, 'T'),
)

# =============================================================================
# 2. GLASS CITY  (x 40-79)  - white plazas, glass walkways, sliding-cube puzzle
# =============================================================================
rect(47, 15, 48, 17, '=')               # entry plaza -> puzzle plaza
rect(54, 24, 56, 26, '=')               # puzzle plaza -> shard terrace (gated)
rect(63, 15, 66, 17, '=')               # puzzle plaza -> beacon plaza
rect(44, 8, 45, 12, '=')                # entry plaza -> south garden

rect(41, 12, 46, 21, '#')               # entry plaza
rect(42, 18, 44, 20, 'g', LAND)
rect(49, 9, 62, 23, '#')                # puzzle plaza
rect(49, 22, 51, 23, 'g', LAND)         # corner planters (walkable)
rect(60, 22, 62, 23, 'g', LAND)
rect(52, 27, 58, 30, '#')               # shard terrace
rect(53, 29, 57, 30, 'g', LAND)
rect(54, 15, 56, 17, 'g', LAND)         # central planter (off the cube lanes)
rect(67, 11, 74, 21, '#')               # beacon plaza
ellipse(70.5, 16.5, 2.4, 2.4, 'g', LAND)
rect(41, 3, 47, 7, 'g')                 # south garden
rect(43, 4, 45, 6, '#', LAND)
rect(75, 16, 81, 17, '3', '.')          # bridge 3 (beacon 2) city -> moonpool

objects(
    # entry plaza
    (42, 13, 'k'), (46, 21, 'k'), (41, 21, 'l'), (46, 12, 'l'), (43, 19, 't'), (44, 15, 'o'), (42, 16, 'o'),
    (45, 18, 'o'), (41, 17, 'f'),
    # south garden: clam
    (44, 5, 'C'), (42, 4, 'T'), (46, 6, 'T'), (41, 6, 'f'), (47, 4, 't'), (42, 7, 'o'), (46, 3, 'o'),
    # puzzle plaza ------------------------------------------------------------
    # cube A: push east (stops at spire), then south onto pad A
    (51, 20, 'X'), (59, 20, 'k'), (58, 12, 'O'),
    # cube B: push west (stops at spire), then north onto pad B
    (60, 11, 'X'), (51, 11, 'k'), (52, 14, 'O'),
    (54, 25, 'G'), (55, 25, 'G'), (56, 25, 'G'),
    (49, 9, 'l'), (62, 9, 'l'), (49, 15, 'k'), (62, 18, 'k'),
    (50, 22, 't'), (61, 23, 't'), (55, 16, 't'), (54, 17, 'f'), (56, 15, 'f'),
    (62, 14, 'l'), (49, 18, 'l'), (55, 22, 'f'), (60, 17, 'f'), (56, 22, 'o'), (55, 17, 'o'), (60, 15, 'o'), (53, 18, 'o'), (50, 13, 'o'),
    # shard terrace
    (55, 28, 'S'), (52, 30, 'k'), (58, 30, 'k'), (53, 27, 'o'), (57, 27, 'o'), (54, 30, 'f'), (56, 29, 't'),
    # beacon plaza
    (70, 17, 'B'), (67, 21, 'k'), (74, 21, 'k'), (67, 11, 'k'), (74, 11, 'k'),
    (69, 19, 'A'), (72, 13, 'l'), (68, 13, 'o'), (73, 15, 'o'), (71, 20, 'o'), (68, 16, 'f'), (73, 18, 't'),
)

# =============================================================================
# 3. MOONPOOL  (x 80-119) - night, lanterns, drifting jellyfish, the exit
# =============================================================================
rect(87, 15, 90, 17, '=')               # landing -> moon island
rect(104, 6, 105, 11, '=')              # moon island -> exit islet

ellipse(84.5, 16.5, 4.0, 4.2, 'g')      # landing island
ellipse(97.5, 16.5, 9.0, 7.2, 'g')      # moon island
ellipse(97.5, 17.3, 2.6, 1.9, '#', LAND)
rect(90, 16, 94, 16, '#', LAND)
ellipse(114.5, 17.0, 3.8, 3.8, 'g')     # shard island (bridge 4)
ellipse(108.5, 6.0, 4.5, 3.2, 'g')      # exit islet
ellipse(108.5, 6.0, 2.4, 1.7, '#', LAND)
ellipse(88.0, 28.0, 3.0, 2.2, 'g')      # decor islets
ellipse(117.0, 28.0, 2.5, 2.0, 'g')
rect(107, 16, 110, 17, '4', '.')        # bridge 4 (lanterns) -> shard island

objects(
    (83, 18, 'T'), (86, 14, 'n'), (82, 15, 'r'), (85, 19, 'o'), (84, 13, 'o'),
    # moon island
    (97, 18, 'B'),
    (92, 21, 'L'), (103, 21, 'L'), (97, 11, 'L'),
    (93, 18, 'J'), (101, 14, 'J'), (98, 21, 'J'),
    (90, 19, 'n'), (104, 18, 'n'), (95, 12, 'n'), (100, 21, 'n'), (91, 13, 'T'), (104, 13, 'T'),
    (94, 22, 'T'), (100, 11, 'r'), (89, 17, 'o'), (93, 15, 'o'), (102, 17, 'o'), (99, 22, 'o'),
    (95, 20, 'o'), (100, 13, 'o'), (102, 20, 'C'),
    # shard island
    (114, 17, 'S'), (116, 19, 'n'), (112, 15, 'n'), (116, 15, 'T'), (113, 20, 'o'), (116, 17, 'o'),
    (115, 14, 'J'),
    # exit islet
    (108, 6, 'M'), (105, 5, 'n'), (111, 7, 'n'), (110, 4, 'T'), (106, 8, 'o'),
    (88, 28, 'T'), (117, 28, 'n'),
)

# -----------------------------------------------------------------------------
# write the map (row 0 printed last so north is at the top of the file)
# -----------------------------------------------------------------------------
out = os.path.join(os.path.dirname(__file__), '../../Assets/AquaScape/Level/level.txt')
with open(out, 'w') as f:
    for y in range(H - 1, -1, -1):
        f.write(''.join(grid[y]) + '\n')
print('wrote', out)
