#!/usr/bin/env python3
"""
Jigsaw Sudoku Generator & Solver (single-script, no external dependencies)

Features:
- Generates 9x9 Jigsaw Sudoku regions (irregular contiguous regions)
- Backtracking solver for Jigsaw Sudoku
- Puzzle generator with uniqueness enforcement
- Difficulty selection (1–6) controls number of clues
- Outputs both puzzle and solution SVGs per Sudoku
- Alphanumeric ID embedded in filename and bottom-left of SVG
- Difficulty shown in filename and top of SVG
- argparse CLI: -d/--difficulty, -n/--count

Python 3 only; standard library only.
"""

import argparse
import random
import secrets
import string
import os
import time
from typing import List, Tuple, Optional

# ------------------------------
# Constants and configuration
# ------------------------------
GRID_SIZE = 9
DIGITS = list(range(1, GRID_SIZE + 1))
FOUR_NEIGHBORS = [(1, 0), (-1, 0), (0, 1), (0, -1)]

# Difficulty mapping: target givens per puzzle
DIFFICULTY_GIVENS = {
    1: 45,
    2: 40,
    3: 36,
    4: 32,
    5: 28,
    6: 26,
}

# ------------------------------
# Region generation (irregular contiguous nonominoes)
# ------------------------------


def in_bounds(r: int, c: int) -> bool:
    return 0 <= r < GRID_SIZE and 0 <= c < GRID_SIZE


def generate_regions(max_restarts: int = 300) -> List[List[int]]:
    """Generate 9 irregular contiguous regions (size 9) via randomized multi-source growth.
    Guarantees: contiguous regions, not equal to the standard 3x3 box mapping, and
    at least a few regions crossing 3x3 box boundaries.
    Returns a 9x9 matrix of region indices in [0..8].
    """

    def frontier(
        idx: int, regs: List[List[Tuple[int, int]]], reg_of: List[List[int]]
    ) -> List[Tuple[int, int]]:
        f: List[Tuple[int, int]] = []
        seen = set()
        for r, c in regs[idx]:
            for dr, dc in FOUR_NEIGHBORS:
                nr, nc = r + dr, c + dc
                if in_bounds(nr, nc) and reg_of[nr][nc] == -1:
                    if (nr, nc) not in seen:
                        seen.add((nr, nc))
                        f.append((nr, nc))
        random.shuffle(f)
        return f

    def standard_box_mapping(r: int, c: int) -> int:
        return (r // 3) * 3 + (c // 3)

    def not_standard(mat: List[List[int]]) -> bool:
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                if mat[r][c] != standard_box_mapping(r, c):
                    return True
        return False

    def regions_cross_boxes(mat: List[List[int]], min_cross: int = 4) -> bool:
        # Count how many regions occupy cells in more than one 3x3 box
        boxsets = [set() for _ in range(GRID_SIZE)]
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                ridx = mat[r][c]
                boxsets[ridx].add(standard_box_mapping(r, c))
        cross = sum(1 for s in boxsets if len(s) >= 2)
        return cross >= min_cross

    all_cells = [(r, c) for r in range(GRID_SIZE) for c in range(GRID_SIZE)]

    for _ in range(max_restarts):
        # Random seeds: 9 distinct random cells
        random.shuffle(all_cells)
        seeds = all_cells[:GRID_SIZE]

        regions: List[List[Tuple[int, int]]] = [[] for _ in range(GRID_SIZE)]
        region_of = [[-1 for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]

        for idx, (sr, sc) in enumerate(seeds):
            regions[idx].append((sr, sc))
            region_of[sr][sc] = idx

        # grow regions fairly (smaller regions first) until each has 9 cells
        made_progress = True
        while made_progress:
            made_progress = False
            order = list(range(GRID_SIZE))
            # prefer smaller regions to avoid starving
            random.shuffle(order)
            order = [i for _, i in sorted(((len(regions[i]), i) for i in order))]
            for idx in order:
                if len(regions[idx]) >= GRID_SIZE:
                    continue
                f = frontier(idx, regions, region_of)
                if not f:
                    continue
                # pick candidate with most free neighbors to reduce isolation
                best_cell = None
                best_score = -1
                for nr, nc in f:
                    score = 0
                    for dr, dc in FOUR_NEIGHBORS:
                        rr, cc = nr + dr, nc + dc
                        if in_bounds(rr, cc) and region_of[rr][cc] == -1:
                            score += 1
                    # light randomization
                    score += random.random() * 0.1
                    if score > best_score:
                        best_score = score
                        best_cell = (nr, nc)
                pr, pc = best_cell
                region_of[pr][pc] = idx
                regions[idx].append((pr, pc))
                made_progress = True

            # completion check
            if all(len(regions[i]) == GRID_SIZE for i in range(GRID_SIZE)):
                mat = [[-1 for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
                for ridx in range(GRID_SIZE):
                    for r, c in regions[ridx]:
                        mat[r][c] = ridx
                # validate non-standard and crossing boxes
                if not_standard(mat) and regions_cross_boxes(mat, min_cross=4):
                    return mat
                else:
                    break  # restart
        # restart if stuck or invalid

    # If repeated failures, raise to signal the need to retry; caller can catch if desired.
    raise RuntimeError(
        "Failed to generate irregular jigsaw regions after many attempts."
    )


# ------------------------------
# Solver and generator
# ------------------------------


def region_index(regions: List[List[int]], r: int, c: int) -> int:
    return regions[r][c]


def compute_candidates(
    grid: List[List[int]], regions: List[List[int]], r: int, c: int
) -> List[int]:
    if grid[r][c] != 0:
        return []
    used = set()
    # row
    used.update(n for n in grid[r] if n != 0)
    # col
    used.update(grid[i][c] for i in range(GRID_SIZE) if grid[i][c] != 0)
    # region
    ridx = region_index(regions, r, c)
    for rr in range(GRID_SIZE):
        for cc in range(GRID_SIZE):
            if regions[rr][cc] == ridx and grid[rr][cc] != 0:
                used.add(grid[rr][cc])
    return [d for d in DIGITS if d not in used]


def find_unassigned_with_mrv(
    grid: List[List[int]], regions: List[List[int]]
) -> Optional[Tuple[int, int, List[int]]]:
    best = None
    best_cands = None
    for r in range(GRID_SIZE):
        for c in range(GRID_SIZE):
            if grid[r][c] == 0:
                cands = compute_candidates(grid, regions, r, c)
                if not cands:
                    return (r, c, [])
                if best is None or len(cands) < len(best_cands):
                    best = (r, c)
                    best_cands = cands
    if best is None:
        return None
    random.shuffle(best_cands)
    return (best[0], best[1], best_cands)


def solve_backtracking(
    grid: List[List[int]], regions: List[List[int]]
) -> Optional[List[List[int]]]:
    """Solve a Jigsaw Sudoku via backtracking; returns solution grid or None."""
    # Deep copy grid for safety
    g = [row[:] for row in grid]

    def dfs() -> bool:
        pos = find_unassigned_with_mrv(g, regions)
        if pos is None:
            return True
        r, c, cands = pos
        if not cands:
            return False
        for d in cands:
            g[r][c] = d
            if dfs():
                return True
            g[r][c] = 0
        return False

    if dfs():
        return g
    return None


def count_solutions(
    grid: List[List[int]], regions: List[List[int]], limit: int = 2
) -> int:
    """Count number of solutions up to 'limit'. Returns <= limit."""
    count = 0
    g = [row[:] for row in grid]

    def dfs() -> bool:
        nonlocal count
        if count >= limit:
            return True  # early stop
        pos = find_unassigned_with_mrv(g, regions)
        if pos is None:
            count += 1
            return count >= limit
        r, c, cands = pos
        if not cands:
            return False
        for d in cands:
            g[r][c] = d
            if dfs():
                if count >= limit:
                    return True
            g[r][c] = 0
        return False

    dfs()
    return count


def generate_full_solution(regions: List[List[int]]) -> List[List[int]]:
    """Generate a fully solved grid using backtracking from empty."""
    empty = [[0] * GRID_SIZE for _ in range(GRID_SIZE)]
    sol = solve_backtracking(empty, regions)
    # In pathological rare cases, try regenerating regions
    tries = 0
    while sol is None and tries < 5:
        tries += 1
        sol = solve_backtracking(empty, regions)
    if sol is None:
        raise RuntimeError("Failed to generate a full solution for given regions.")
    return sol


def generate_puzzle_from_solution(
    solution: List[List[int]], regions: List[List[int]], target_givens: int
) -> List[List[int]]:
    """Remove clues while maintaining uniqueness until target_givens reached."""
    grid = [row[:] for row in solution]
    cells = [(r, c) for r in range(GRID_SIZE) for c in range(GRID_SIZE)]
    random.shuffle(cells)

    # Ensure we don't go below target_givens
    current_givens = GRID_SIZE * GRID_SIZE
    for r, c in cells:
        if current_givens <= target_givens:
            break
        saved = grid[r][c]
        grid[r][c] = 0
        # uniqueness check
        sols = count_solutions(grid, regions, limit=2)
        if sols == 1:
            current_givens -= 1
        else:
            grid[r][c] = saved
    return grid


# ------------------------------
# SVG rendering
# ------------------------------


def svg_render(
    grid: List[List[int]],
    regions: List[List[int]],
    svg_path: str,
    difficulty: int,
    puzzle_id: str,
    show_all_numbers: bool,
) -> None:
    """Render grid to SVG, draw thick lines on region borders, show difficulty at top and ID bottom-left."""
    cell = 50
    margin = 24
    top_h = 10
    bottom_h = 24
    width = margin * 2 + GRID_SIZE * cell
    height = top_h + margin + GRID_SIZE * cell + bottom_h
    grid_top = top_h
    # Start SVG
    parts = []
    parts.append(
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>"
    )
    parts.append(
        "<style> .num{font-family:Arial; font-size:22px;} .title{font-family:Arial; font-size:16px;} .id{font-family:Arial; font-size:14px;} </style>"
    )

    # Title (difficulty) at top center
    # title = f"Jigsaw Sudoku – Schwierigkeit {difficulty}"
    # parts.append(f"<text x='{width/2}' y='{top_h-8}' class='title' text-anchor='middle' dominant-baseline='ideographic'>{title}</text>")

    # Draw cell grid thin lines
    for r in range(GRID_SIZE + 1):
        y = grid_top + margin + r * cell
        x1 = margin
        x2 = margin + GRID_SIZE * cell
        stroke_w = 1.0
        if r == 0 or r == GRID_SIZE:
            stroke_w = 3.0
        parts.append(
            f"<line x1='{x1}' y1='{y}' x2='{x2}' y2='{y}' stroke='black' stroke-width='{stroke_w}' />"
        )
    for c in range(GRID_SIZE + 1):
        x = margin + c * cell
        y1 = grid_top + margin
        y2 = grid_top + margin + GRID_SIZE * cell
        stroke_w = 1.0
        if c == 0 or c == GRID_SIZE:
            stroke_w = 3.0
        parts.append(
            f"<line x1='{x}' y1='{y1}' x2='{x}' y2='{y2}' stroke='black' stroke-width='{stroke_w}' />"
        )

    # Region boundaries (thicker lines between different regions)
    # Vertical boundaries between (r,c) and (r,c+1)
    for r in range(GRID_SIZE):
        for c in range(GRID_SIZE - 1):
            if regions[r][c] != regions[r][c + 1]:
                x = margin + (c + 1) * cell
                y1 = grid_top + margin + r * cell
                y2 = y1 + cell
                parts.append(
                    f"<line x1='{x}' y1='{y1}' x2='{x}' y2='{y2}' stroke='black' stroke-width='3' />"
                )
    # Horizontal boundaries between (r,c) and (r+1,c)
    for r in range(GRID_SIZE - 1):
        for c in range(GRID_SIZE):
            if regions[r][c] != regions[r + 1][c]:
                y = grid_top + margin + (r + 1) * cell
                x1 = margin + c * cell
                x2 = x1 + cell
                parts.append(
                    f"<line x1='{x1}' y1='{y}' x2='{x2}' y2='{y}' stroke='black' stroke-width='3' />"
                )

    # Numbers
    for r in range(GRID_SIZE):
        for c in range(GRID_SIZE):
            val = grid[r][c]
            cx = margin + c * cell + cell / 2
            cy = grid_top + margin + r * cell + cell / 2 + 7  # slight vertical offset
            text_val = str(val) if (show_all_numbers or val != 0) else ""
            parts.append(
                f"<text x='{cx}' y='{cy}' class='num' text-anchor='middle'>{text_val}</text>"
            )

    # Bottom-left ID
    parts.append(
        f"<text x='{margin}' y='{height-6}' class='id' text-anchor='start' style='font-size:10; fill:gray'>ID: {puzzle_id} - Difficulty / Schwierigkeit: {difficulty}</text>"
    )

    parts.append("</svg>")
    svg = "\n".join(parts)

    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg)


def solution_placeholder_digit() -> str:
    """Return empty string; reserved for potential pencil marks. Kept for clarity."""
    return ""


# ------------------------------
# Utility
# ------------------------------


def new_id(length: int = 8) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def ensure_output_dir(path: str) -> None:
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def make_filename(base_dir: str, puzzle_id: str, difficulty: int, kind: str) -> str:
    # kind: 'puzzle' or 'solution'
    return os.path.join(base_dir, f"jigsaw-{difficulty}-{puzzle_id}-{kind}.svg")


# ------------------------------
# CLI
# ------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Jigsaw Sudokus and export to SVG."
    )
    parser.add_argument(
        "-d", "--difficulty", type=int, default=3, help="Difficulty level 1–6"
    )
    parser.add_argument(
        "-n", "--count", type=int, default=1, help="Number of Sudokus to generate"
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default="output/jigsaw",
        help="Output directory for SVGs",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    d = max(1, min(6, args.difficulty))
    count = max(1, args.count)
    out_dir = args.output
    ensure_output_dir(out_dir)

    for _ in range(count):
        pid = new_id()
        # Generate regions and a full solution
        regions = None
        retry_ttl = 7
        while not regions and retry_ttl > 0:
            try:
                regions = generate_regions()
                print(f"Generated regions for puzzle ID {pid}")
            except Exception:
                print("Region generation failed, retrying...")
                time.sleep(1)
                # retry_ttl -= 1
                # continue
        solution = generate_full_solution(regions)
        target_givens = DIFFICULTY_GIVENS.get(d, DIFFICULTY_GIVENS[3])
        puzzle = generate_puzzle_from_solution(solution, regions, target_givens)

        puzzle_path = make_filename(out_dir, pid, d, "puzzle")
        solution_path = make_filename(out_dir, pid, d, "solution")

        svg_render(puzzle, regions, puzzle_path, d, pid, show_all_numbers=False)
        svg_render(solution, regions, solution_path, d, pid, show_all_numbers=True)
        print(
            f"Generated: {os.path.basename(puzzle_path)} and {os.path.basename(solution_path)}"
        )


if __name__ == "__main__":
    main()
