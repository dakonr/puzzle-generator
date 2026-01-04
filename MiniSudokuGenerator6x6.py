#!/usr/bin/env python3

import random
import sys
import time
import string
import uuid
from datetime import datetime


class Sudoku6x6:
    def __init__(self):
        self.reset()

    def reset(self):
        # create empty 6x6 board
        rows = 6
        columns = 6
        self.board = [[0 for j in range(columns)] for i in range(rows)]
        self.puzzle_id = None
        self.difficulty = 0
        self.scale = {
            0: "Undefined / Undefiniert",
            1: "Really Easy / Sehr Leicht",
            2: "Easy / Leicht",
            3: "Medium / Mittel",
            4: "Hard / Schwer",
            5: "Very Hard / Sehr Schwer",
            6: "Devilish / Teuflisch",
        }

    def toSVG(self, board=None):
        # render given board or current board
        if board is None:
            board = self.board
        # Variables
        cell_size = 40
        line_color = "black"

        rows = len(board)
        cols = len(board[0])

        # creating a rectangle in white with the size of the Sudoku
        svg = '<svg xmlns="http://www.w3.org/2000/svg" version="1.1">'
        svg += f'<rect x="0" y="0" width="{cols * cell_size}" height="{rows * cell_size + 20}" fill="white" />'

        # Draw vertical grid lines (columns)
        for i in range(cols + 1):
            line_width = 2 if i % 3 == 0 else 0.5  # thick every 3 columns
            svg += f'<line x1="{i * cell_size}" y1="0" x2="{i * cell_size}" y2="{rows * cell_size}" style="stroke:{line_color}; stroke-width:{line_width}" />'

        # Draw horizontal grid lines (rows)
        for j in range(rows + 1):
            line_width = 2 if j % 2 == 0 else 0.5  # thick every 2 rows
            svg += f'<line x1="0" y1="{j * cell_size}" x2="{cols * cell_size}" y2="{j * cell_size}" style="stroke:{line_color}; stroke-width:{line_width}" />'

        # Draw the numbers
        for row in range(rows):
            for column in range(cols):
                if board[row][column] != 0:
                    svg += f'<text x="{(column + 0.5) * cell_size}" y="{(row + 0.5) * cell_size}" style="font-size:20; text-anchor:middle; dominant-baseline:middle"> {str(board[row][column])} </text>'

        # Draw ID at bottom left corner (outside grid)
        if self.puzzle_id:
            svg += f'<text x="5" y="{rows * cell_size + 15}" style="font-size:10; fill:gray"> ID: {self.puzzle_id} - {self.scale[self.difficulty]} </text>'

        svg += "</svg>"
        return svg

    def generate(self, difficulty):
        self.difficulty = difficulty
        # Generate unique alphanumeric ID
        self.puzzle_id = "".join(
            random.choices(string.ascii_uppercase + string.digits, k=8)
        )

        # fill diagonal 2x3 boxes at positions (0,0), (2,3), (4,0)
        # Try to prefill these boxes, but ensure global validity using backtracking per box.
        positions = [(0, 0), (2, 3), (4, 0)]
        for start_row, start_col in positions:
            if not self.fill_box(start_row, start_col):
                # cannot prefill this box without conflict -> fail generation so caller can retry
                return False

        # fill rest (use deterministic fill that leaves the board filled)
        if not self.fill_solution():
            print("Failed to create a full solution.", file=sys.stderr)
            return False

        # save full solution before removing numbers
        self.solution = [row[:] for row in self.board]

        # difficulty
        empty_cells = self.evaluate(difficulty)

        # creating a list of coordinates to visit and shuffeling them
        unvisited = [(r, c) for r in range(6) for c in range(6)]
        random.shuffle(unvisited)
        # remove numbers
        while empty_cells > 0 and len(unvisited) > 0:
            # saving a copy of the number, just in case, if we cant remove it
            r, c = unvisited.pop()
            copy = self.board[r][c]
            self.board[r][c] = 0

            # checking how many solutions are in the board
            solutions = [solution for solution in self.solve()]

            # if there is more than one solution, we put the number back
            if len(solutions) > 1:
                self.board[r][c] = copy
            else:
                empty_cells -= 1

        # if unvisited is empty, but empty_cells not -> trying again
        if empty_cells > 0:
            print("No Sudoku found. Trying again.")
            return False
        else:
            return True

    def evaluate(self, difficulty):
        # 1 = really easy, 3 = middle, 6 = devilish (lowest number possible, takes a long time to calculate)
        empty_cells = [0, 10, 15, 20, 24, 26, 28]
        if difficulty < 1 or difficulty > len(empty_cells) - 1:
            print("invalid difficulty", file=sys.stderr)
        return empty_cells[difficulty]

    # method to print the board in console
    def print(self):
        for i in range(6):
            print(" ".join([str(x) if x != 0 else "." for x in self.board[i]]))

    def number_is_valid(self, row, column, number):
        # check row and column
        for i in range(6):
            if self.board[row][i] == number or self.board[i][column] == number:
                return False

        # check 2x3 box
        start_column = column // 3 * 3
        start_row = row // 2 * 2
        for i in range(2):
            for j in range(3):
                if self.board[i + start_row][j + start_column] == number:
                    return False
        return True

    def solve(self):
        # generate random numbers from 1 to 6
        digits = list(range(1, 7))

        # find an empty cell
        for r in range(6):
            for c in range(6):
                if self.board[r][c] == 0:
                    # for every empty cell fill a random valid number into it
                    random.shuffle(digits)
                    for n in digits:
                        if self.number_is_valid(r, c, n):
                            self.board[r][c] = n
                            # is it solved?
                            yield from self.solve()
                            # backtrack
                            self.board[r][c] = 0
                    return
        yield True

    # deterministic backtracking that fills the board and leaves it filled on success
    def fill_solution(self):
        digits = list(range(1, 7))
        # find an empty cell
        for r in range(6):
            for c in range(6):
                if self.board[r][c] == 0:
                    random.shuffle(digits)
                    for n in digits:
                        if self.number_is_valid(r, c, n):
                            self.board[r][c] = n
                            if self.fill_solution():
                                return True
                            # backtrack
                            self.board[r][c] = 0
                    return False
        # no empty cells -> solved
        return True

    # method to print the solved board in console
    def print_solution(self):
        if not hasattr(self, "solution") or self.solution is None:
            print("No solution available", file=sys.stderr)
            return
        for i in range(len(self.solution)):
            print(" ".join([str(x) if x != 0 else "." for x in self.solution[i]]))

    # fill one 2x3 box at (start_row, start_col) using backtracking ensuring numbers are valid globally
    def fill_box(self, start_row, start_col):
        cells = [(start_row + r, start_col + c) for r in range(2) for c in range(3)]
        numbers = list(range(1, 7))

        def helper(idx, avail):
            if idx == len(cells):
                return True
            r, c = cells[idx]
            random.shuffle(avail)
            for i, n in enumerate(avail):
                if self.number_is_valid(r, c, n):
                    self.board[r][c] = n
                    next_avail = avail[:i] + avail[i + 1 :]
                    if helper(idx + 1, next_avail):
                        return True
                    # backtrack
                    self.board[r][c] = 0
            return False

        # attempt to fill box; returns True on success, False if impossible with current board state
        return helper(0, numbers)


def main(difficulty):
    sudoku = Sudoku6x6()

    # trying in Total for 10 mins to find a sudoku
    timeout = 600
    start_time = time.time()
    end_time = start_time + timeout

    while time.time() < end_time:
        if sudoku.generate(difficulty) == True:
            break
        else:
            sudoku.reset()

    # printing puzzle with ID
    print(f"Puzzle ID: {sudoku.puzzle_id}")
    sudoku.print()

    print()
    print(f"Solution for ID: {sudoku.puzzle_id}")
    # printing solution to console
    sudoku.print_solution()

    # creating the .svg-File with current date, time, difficulty and ID for puzzle
    svg = sudoku.toSVG()
    now = datetime.now()
    name = f"output/sudoku6x6-{difficulty}-{sudoku.puzzle_id}-puzzle.svg"
    with open(name, "w") as f:
        f.write(svg)

    # creating the .svg-File for the solution
    solution_svg = sudoku.toSVG(sudoku.solution)
    sname = f"output/sudoku6x6-{difficulty}-{sudoku.puzzle_id}-solution.svg"
    with open(sname, "w") as f:
        f.write(solution_svg)


if __name__ == "__main__":
    # takes difficulty as an argument, if not provided the program removes half of the board (level 3)
    args = [int(x) if x.isdecimal() else x for x in sys.argv[1:]]
    difficulty = args[0] if len(args) > 0 else 3
    count = args[1] if len(args) > 1 else 1
    for _ in range(count):
        main(difficulty)
