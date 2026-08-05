INSTRUCTIONS = {
    'ldi': {'opcode': 0, 'args': 2},
    'rdi': {'opcode': 1, 'args': 2},
    'sti': {'opcode': 2, 'args': 2},

    'add': {'opcode': 3, 'args': 3},
    'mul': {'opcode': 4, 'args': 3},
    'div': {'opcode': 5, 'args': 3},
    'mod': {'opcode': 6, 'args': 3},

    'cmp': {'opcode': 7, 'args': 3},
    'jne': {'opcode': 8, 'args': 3},

    'col': {'opcode': 9, 'args': 3},
    'pix': {'opcode': 10, 'args': 2},
}

PSEUDOINSTRUCTIONS = {
    'cpy': {
        'args': ['INT', 'INT'],
        'code': """
            add {a0} {a1} 0
        """
    },
    'sub': {
        'args': ['INT', 'INT', 'INT'],
        'code': """
            mul 14 2 {a2}
            add {a0} {a1} 14
        """
    },
    'addi': {
        'args': ['INT', 'INT', 'INT'],
        'code': """
            ldi 14 {a2}
            add {a0} {a1} 14
        """
    },
    'subi': {
        'args': ['INT', 'INT', 'INT'],
        'code': """
            ldi 14 {a2}
            mul 14 14 2
            add {a0} {a1} 14
        """
    },
    'muli': {
        'args': ['INT', 'INT', 'INT'],
        'code': """
            ldi 14 {a2}
            mul {a0} {a1} 14
        """
    },
    'divi': {
        'args': ['INT', 'INT', 'INT'],
        'code': """
            ldi 14 {a2}
            div {a0} {a1} 14
        """
    },
    'modi': {
        'args': ['INT', 'INT', 'INT'],
        'code': """
            ldi 14 {a2}
            mod {a0} {a1} 14
        """
    },
    'inc': {
        'args': ['INT'],
        'code': """
            add {a0} {a0} 1
        """
    },
    'dec': {
        'args': ['INT'],
        'code': """
            add {a0} {a0} 2
        """
    },
    'abs': {
        'args': ['INT', 'INT'],
        'code': """
            cmp 14 {a1} 0
            mul 14 14 {a1}
            mul {a0} 14 2
        """
    },
    'jnea': {
        'args': ['NAME', 'INT', 'INT'],
        'code': """
            ldi 14 {a0}
            jne 14 {a1} {a2}
        """
    },
    'ja': {
        'args': ['NAME'],
        'code': """
            ldi 14 {a0}
            jne 14 0 1
        """
    },
    'sne': {
        'args': ['INT', 'INT'],
        'code': """
            ldi 14 {SKIP_LABEL}
            jne 14 {a0} {a1}
        """
    },
    'call': {
        'args': ['NAME'],
        'code': """
            ldi 14 {NEXT_LABEL}
            sti 15 14
            add 15 15 1
            ldi 14 {a0}
            jne 14 0 1
        """
    },
    'ret': {
        'args': [],
        'code': """
            add 15 15 2
            rdi 14 15
            jne 14 0 1
        """
    }
}
