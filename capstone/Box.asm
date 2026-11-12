// Make the Computer Draw a Box
// Roll number: 2501730302
// K = 02
// Starting row = 2
// Height = 20 rows
// Width = 48 pixels = 3 words per row

(LOOP)
    // Check whether a key is pressed
    @KBD
    D=M
    @SET_BLACK
    D;JNE

    // No key pressed: clear the box
    @SET_WHITE
    0;JMP

(SET_BLACK)
    @R12
    M=-1
    @FILL_SETUP
    0;JMP

(SET_WHITE)
    @R12
    M=0

(FILL_SETUP)
    // SCREEN + (2 * 32) = SCREEN + 64
    @SCREEN
    D=A
    @64
    D=D+A
    @R13
    M=D

    // 20 rows
    @20
    D=A
    @R14
    M=D

(ROW)
    // 3 words = 48 pixels
    @3
    D=A
    @R15
    M=D

(WORD)
    // Write the selected colour to the current screen word
    @R12
    D=M
    @R13
    A=M
    M=D

    // Advance to the next word
    @R13
    M=M+1

    // Repeat for all 3 words
    @R15
    MD=M-1
    @WORD
    D;JGT

    // Skip the remaining 29 words in this screen row
    @29
    D=A
    @R13
    M=D+M

    // Repeat for all 20 rows
    @R14
    MD=M-1
    @ROW
    D;JGT

    // Check the keyboard again
    @LOOP
    0;JMP