
"""
=========================================================
NAND2TETRIS CAPSTONE PROJECT
HACK ASSEMBLER v1.0
=========================================================

Student: Manas Aggarwal
Roll Number: 2501730302
Personal Number K: 02

Required extra feature:
Warn when the same label is declared more than once.

Architecture:
1. Source cleaning
2. Pass 1: Label detection and symbol table
3. Pass 2: Machine code generation
4. A-instruction translation
5. C-instruction translation
6. Variable allocation
7. Error and warning reporting
8. .hack file generation

Usage:
    python assembler.py
    python assembler.py --self-test
    python assembler.py Add.asm
    python assembler.py Add.asm Add.hack
=========================================================
"""

import argparse
import re
import sys
from pathlib import Path


# =========================================================
# 1. PREDEFINED SYMBOL TABLE
# =========================================================

def create_predefined_symbols():
    """Create the predefined Hack assembly symbols."""

    symbols = {
        "SP": 0,
        "LCL": 1,
        "ARG": 2,
        "THIS": 3,
        "THAT": 4,
        "SCREEN": 16384,
        "KBD": 24576,
    }

    # Register symbols R0 through R15
    for i in range(16):
        symbols[f"R{i}"] = i

    return symbols


# =========================================================
# 2. SOURCE CODE CLEANING
# =========================================================

def clean_source(source_text):
    """
    Remove comments and blank lines.

    Returns:
        List of tuples:
        (original_line_number, cleaned_instruction)
    """

    instructions = []

    for line_number, line in enumerate(
        source_text.splitlines(), start=1
    ):

        # Remove inline comments
        line = line.split("//", 1)[0]

        # Remove leading and trailing whitespace
        line = line.strip()

        # Ignore blank lines
        if line:
            instructions.append((line_number, line))

    return instructions


# =========================================================
# 3. SYMBOL VALIDATION
# =========================================================

def is_valid_symbol(symbol):
    """
    Check whether a symbol follows Hack assembly naming rules.
    """

    return bool(
        re.fullmatch(
            r"[A-Za-z_.$:][A-Za-z0-9_.$:]*",
            symbol
        )
    )


# =========================================================
# 4. PASS 1 — LABEL DETECTION
# =========================================================

def first_pass(cleaned_instructions):
    """
    First pass of the assembler.

    Responsibilities:
    - Identify label declarations.
    - Assign ROM addresses.
    - Build the symbol table.
    - Detect duplicate labels.
    - Preserve the first definition of duplicate labels.

    Returns:
        symbols
        executable_instructions
        warnings
        errors
    """

    symbols = create_predefined_symbols()

    executable_instructions = []

    warnings = []
    errors = []

    rom_address = 0

    for line_number, instruction in cleaned_instructions:

        # Label declaration
        if instruction.startswith("(") and instruction.endswith(")"):

            label = instruction[1:-1].strip()

            if not is_valid_symbol(label):
                errors.append(
                    f"Line {line_number}: "
                    f"Invalid label '{label}'."
                )
                continue

            if label in symbols:

                warnings.append(
                    f"Line {line_number}: Duplicate label "
                    f"'{label}'. Existing address "
                    f"{symbols[label]} preserved."
                )

                continue

            symbols[label] = rom_address

        elif "(" in instruction or ")" in instruction:

            errors.append(
                f"Line {line_number}: "
                f"Malformed label declaration."
            )

        else:

            executable_instructions.append(
                (line_number, instruction)
            )

            rom_address += 1

    return (
        symbols,
        executable_instructions,
        warnings,
        errors
    )


# =========================================================
# 5. A-INSTRUCTION TRANSLATION
# =========================================================

def translate_a_instruction(
    instruction,
    symbols,
    next_variable
):
    """
    Translate an A-instruction.

    Examples:
        @100
        @R0
        @LOOP

    New variables are assigned RAM addresses
    beginning at address 16.
    """

    operand = instruction[1:]

    if not operand:
        raise ValueError(
            "Missing A-instruction operand."
        )

    # Numeric address
    if operand.isdigit():

        address = int(operand)

    else:

        if not is_valid_symbol(operand):
            raise ValueError(
                f"Invalid symbol '{operand}'."
            )

        # Allocate new variable if symbol is unknown
        if operand not in symbols:

            if next_variable > 16383:
                raise ValueError(
                    "Variable RAM address space exhausted."
                )

            symbols[operand] = next_variable

            next_variable += 1

        address = symbols[operand]

    # A-instruction supports 15-bit addresses
    if not 0 <= address <= 32767:
        raise ValueError(
            f"A-instruction address out of range: {address}."
        )

    binary = format(address, "016b")

    return binary, next_variable


# =========================================================
# 6. C-INSTRUCTION TRANSLATION TABLES
# =========================================================

DEST_TABLE = {

    None:  "000",

    "M":   "001",
    "D":   "010",
    "MD":  "011",

    "A":   "100",
    "AM":  "101",
    "AD":  "110",
    "AMD": "111",
}


COMP_TABLE = {

    "0":   "0101010",
    "1":   "0111111",
    "-1":  "0111010",

    "D":   "0001100",
    "A":   "0110000",
    "!D":  "0001101",
    "!A":  "0110001",

    "-D":  "0001111",
    "-A":  "0110011",

    "D+1": "0011111",
    "A+1": "0110111",

    "D-1": "0001110",
    "A-1": "0110010",

    "D+A": "0000010",
    "D-A": "0010011",
    "A-D": "0000111",

    "D&A": "0000000",
    "D|A": "0010101",

    "M":   "1110000",
    "!M":  "1110001",
    "-M":  "1110011",

    "M+1": "1110111",
    "M-1": "1110010",

    "D+M": "1000010",
    "D-M": "1010011",
    "M-D": "1000111",

    "D&M": "1000000",
    "D|M": "1010101",
}


JUMP_TABLE = {

    None:  "000",

    "JGT": "001",
    "JEQ": "010",
    "JGE": "011",

    "JLT": "100",
    "JNE": "101",
    "JLE": "110",

    "JMP": "111",
}


# =========================================================
# 7. C-INSTRUCTION TRANSLATION
# =========================================================

def translate_c_instruction(instruction):
    """
    Translate a C-instruction.

    General format:

        dest=comp;jump

    Binary format:

        111 a c1c2c3c4c5c6 d1d2d3 j1j2j3
    """

    if instruction.count("=") > 1:
        raise ValueError(
            "Multiple destination separators."
        )

    if instruction.count(";") > 1:
        raise ValueError(
            "Multiple jump separators."
        )

    # Extract destination
    if "=" in instruction:

        destination, remainder = instruction.split(
            "=", 1
        )

        if not destination:
            raise ValueError(
                "Missing destination."
            )

    else:

        destination = None
        remainder = instruction

    # Extract computation and jump
    if ";" in remainder:

        computation, jump = remainder.split(
            ";", 1
        )

        if not jump:
            raise ValueError(
                "Missing jump instruction."
            )

    else:

        computation = remainder
        jump = None

    if not computation:
        raise ValueError(
            "Missing computation."
        )

    # Validate destination
    if destination not in DEST_TABLE:
        raise ValueError(
            f"Invalid destination '{destination}'."
        )

    # Validate computation
    if computation not in COMP_TABLE:
        raise ValueError(
            f"Invalid computation '{computation}'."
        )

    # Validate jump
    if jump not in JUMP_TABLE:
        raise ValueError(
            f"Invalid jump '{jump}'."
        )

    # Construct 16-bit instruction
    binary = (
        "111"
        + COMP_TABLE[computation]
        + DEST_TABLE[destination]
        + JUMP_TABLE[jump]
    )

    return binary


# =========================================================
# 8. PASS 2 — MACHINE CODE GENERATION
# =========================================================

def second_pass(instructions, symbols):
    """
    Second pass of the assembler.

    Converts executable instructions into
    16-bit Hack machine code.
    """

    machine_code = []

    errors = []

    next_variable = 16

    for line_number, instruction in instructions:

        try:

            # A-instruction
            if instruction.startswith("@"):

                binary, next_variable = (
                    translate_a_instruction(
                        instruction,
                        symbols,
                        next_variable
                    )
                )

            # C-instruction
            else:

                binary = translate_c_instruction(
                    instruction
                )

            # Ensure every instruction is 16 bits
            if len(binary) != 16:
                raise ValueError(
                    "Generated instruction is not 16 bits."
                )

            machine_code.append(binary)

        except ValueError as error:

            errors.append(
                f"Line {line_number}: {error}"
            )

    return machine_code, symbols, errors


# =========================================================
# 9. COMPLETE ASSEMBLER PIPELINE
# =========================================================

def assemble(source_text):
    """
    Execute both assembler passes.

    Returns:
        machine_code
        symbols
        warnings
        errors
    """

    # Clean source code
    cleaned_instructions = clean_source(
        source_text
    )

    # Pass 1
    (
        symbols,
        instructions,
        warnings,
        errors
    ) = first_pass(cleaned_instructions)

    if errors:
        return [], symbols, warnings, errors

    # Pass 2
    (
        machine_code,
        symbols,
        pass2_errors
    ) = second_pass(
        instructions,
        symbols
    )

    errors.extend(pass2_errors)

    if errors:
        return [], symbols, warnings, errors

    return machine_code, symbols, warnings, errors


# =========================================================
# 10. REPORTING
# =========================================================

def display_results(
    machine_code,
    symbols,
    warnings,
    errors
):

    print("\n========== ASSEMBLER RESULTS ==========")

    print("\nMachine Code:")

    for address, binary in enumerate(machine_code):

        print(
            f"ROM[{address:04}] : {binary}"
        )

    print("\nWarnings:")

    if warnings:

        for warning in warnings:
            print("WARNING:", warning)

    else:

        print("No warnings.")

    print("\nErrors:")

    if errors:

        for error in errors:
            print("ERROR:", error)

    else:

        print("No errors.")

    print("\nSymbol Table:")

    for symbol, address in sorted(
        symbols.items()
    ):

        print(
            f"{symbol:15} -> {address}"
        )

    print("\n=======================================")


# =========================================================
# 11. FILE ASSEMBLY
# =========================================================

def assemble_file(input_path, output_path=None):
    """
    Read an .asm file and generate its .hack file.
    """

    input_file = Path(input_path)

    if not input_file.is_file():
        print(
            f"ERROR: Input file not found: {input_file}"
        )
        return False

    if input_file.suffix.lower() != ".asm":
        print(
            "ERROR: Input file must have .asm extension."
        )
        return False

    if output_path is None:

        output_file = input_file.with_suffix(
            ".hack"
        )

    else:

        output_file = Path(output_path)

        if output_file.suffix.lower() != ".hack":
            print(
                "ERROR: Output file must have .hack extension."
            )
            return False

    try:

        source_text = input_file.read_text(
            encoding="utf-8"
        )

        (
            machine_code,
            symbols,
            warnings,
            errors
        ) = assemble(source_text)

        display_results(
            machine_code,
            symbols,
            warnings,
            errors
        )

        if errors:

            print(
                "\nAssembly failed. No output file generated."
            )

            return False

        output_file.write_text(
            "\n".join(machine_code) + (
                "\n" if machine_code else ""
            ),
            encoding="ascii"
        )

        print(
            f"\nSUCCESS: Machine code saved to {output_file}"
        )

        print(
            f"Total instructions: {len(machine_code)}"
        )

        return True

    except OSError as error:

        print(
            f"FILE ERROR: {error}"
        )

        return False


# =========================================================
# 12. BUILT-IN SELF-TESTS
# =========================================================

def run_self_test():

    print("\n===== HACK ASSEMBLER SELF-TEST =====")

    # Test 1: Basic addition program
    addition_program = """
        // Addition program

        @2
        D=A

        @3
        D=D+A

        @0
        M=D
    """

    expected_output = [
        "0000000000000010",
        "1110110000010000",
        "0000000000000011",
        "1110000010010000",
        "0000000000000000",
        "1110001100001000",
    ]

    machine_code, symbols, warnings, errors = assemble(
        addition_program
    )

    if machine_code == expected_output and not errors:

        print("\nTEST 1: Addition translation PASSED")

    else:

        print("\nTEST 1: Addition translation FAILED")

        for error in errors:
            print(error)

    # Test 2: Variable allocation
    variable_program = """
        @counter
        M=1
        @result
        M=0
    """

    machine_code, symbols, warnings, errors = assemble(
        variable_program
    )

    variable_passed = (
        symbols.get("counter") == 16
        and symbols.get("result") == 17
        and len(machine_code) == 4
        and not errors
    )

    if variable_passed:

        print("TEST 2: Variable allocation PASSED")

    else:

        print("TEST 2: Variable allocation FAILED")

    # Test 3: Duplicate-label warning
    duplicate_program = """
        @0
        (LOOP)
        @LOOP
        0;JMP
        (LOOP)
        @1
    """

    machine_code, symbols, warnings, errors = assemble(
        duplicate_program
    )

    duplicate_passed = (
        len(warnings) == 1
        and symbols.get("LOOP") == 1
        and not errors
    )

    if duplicate_passed:

        print("TEST 3: Duplicate-label warning PASSED")

        for warning in warnings:
            print(" ", warning)

    else:

        print("TEST 3: Duplicate-label warning FAILED")

    # Test 4: Label address
    label_program = """
        @0
        @1
        (START)
        @START
        0;JMP
    """

    machine_code, symbols, warnings, errors = assemble(
        label_program
    )

    label_passed = (
        symbols.get("START") == 2
        and not errors
    )

    if label_passed:

        print("TEST 4: Label address resolution PASSED")

    else:

        print("TEST 4: Label address resolution FAILED")

    # Test 5: C-instruction translation
    c_instruction_tests = {
        "D=A": "1110110000010000",
        "D=D+A": "1110000010010000",
        "M=D": "1110001100001000",
        "0;JMP": "1110101010000111",
    }

    c_passed = True

    for instruction, expected in c_instruction_tests.items():

        try:

            actual = translate_c_instruction(
                instruction
            )

            if actual != expected:
                c_passed = False

        except ValueError:
            c_passed = False

    if c_passed:

        print("TEST 5: C-instruction translation PASSED")

    else:

        print("TEST 5: C-instruction translation FAILED")

    print("\n===== SELF-TEST COMPLETE =====")


# =========================================================
# 13. MAIN PROGRAM
# =========================================================

def main():

    parser = argparse.ArgumentParser(
        description="Nand2Tetris Hack Assembler"
    )

    parser.add_argument(
        "input",
        nargs="?",
        help="Input Hack assembly file (.asm)"
    )

    parser.add_argument(
        "output",
        nargs="?",
        help="Optional output machine-code file (.hack)"
    )

    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run built-in assembler tests"
    )

    args = parser.parse_args()

    if args.self_test or args.input is None:

        run_self_test()

    else:

        success = assemble_file(
            args.input,
            args.output
        )

        if not success:
            sys.exit(1)


if __name__ == "__main__":
    main()
