import sys
import os
from enum import Enum
from rply import Token
from rply.lexer import LexingError, LexerStream
from argparse import ArgumentParser
from instructions import INSTRUCTIONS, PSEUDOINSTRUCTIONS
from lexer import G2_LEXER
from data import parse_data_entry, G2ADataException


COLOR_ERROR = '\x1b[31m'
COLOR_WARN = '\x1b[33m'
COLOR_RESET = '\x1b[0m'

META_VARS = {'width': 64, 'height': 64, 'memory': 64}
DEFAULT_CONSTANTS = {'CONTROL1': 3, 'CONTROL2': 4, 'A': 5, 'B': 6, 'UP': 7, 'DOWN': 8, 'LEFT': 9, 'RIGHT': 10, 'DELTA': 11}

FILE_SIGNATURE = b'g2'


class AssemblerState(Enum):
    META = 1
    CODE = 2


class Intermediate:
    pass


class Label(Intermediate):
    def __init__(self, token: Token, name: str):
        self.token = token
        self.name = name
    
    def __repr__(self):
        return f'Label({self.name})'


class UnparsedInstruction(Intermediate):
    def __init__(self, token: Token, name: str, args: list[Token]):
        self.token = token
        self.name = name
        self.args = args
    
    def __repr__(self):
        return f'UnparsedInstruction({self.name}, {self.args})'

    def get_emitted_length(self):
        return 1


class Pseudoinstruction(UnparsedInstruction):
    def __init__(self, token: Token, name: str, args: list[Token]):
        super().__init__(token, name, args)
    
    def __repr__(self):
        return f'Pseudoinstruction({self.name}, {self.args})'

    def get_emitted_length(self):
        return PSEUDOINSTRUCTIONS[self.name]['code'].strip().count('\n') + 1


class Instruction:
    def __init__(self, opcode: int, args: list[int]):
        self.opcode = opcode
        self.args = args
        while len(self.args) < 3:
            self.args.append(0)

    def to_bytes(self) -> bytes:
        result = self.opcode.to_bytes(1)
        for value in self.args:
            result += value.to_bytes(4, 'little', signed=True)
        return result

    def __repr__(self):
        return f'Instruction(opcode: {self.opcode}, args: {self.args})'


class Assembler:
    def __init__(self, source_code: str):
        self.source_code = source_code
        self.source_lines = source_code.split('\n')

        self.meta_vars = META_VARS.copy()
        self.labels: dict[str, int] = {}
        self.constants: dict[str, int] = DEFAULT_CONSTANTS.copy()
        self.data_entries: dict[str, tuple[list[int], Token]] = {}
        self.data_start_address = 0

        self.instructions: list[Instruction] = []
    
    def error(self, message: str, token: Token | None=None):
        if token is not None:
            line_number = token.source_pos.lineno-1
            column_number = token.source_pos.colno-1
            print(f'{COLOR_ERROR}ASSEMBLER ERROR: {message}')
            print(f'{line_number+1} | {self.source_lines[line_number]}')
            print(f'{" " * (len(str(line_number))+3+column_number)}^')
        else:
            print(f'{COLOR_ERROR}ASSEMBLER ERROR: {message}')

        print(COLOR_RESET, end='')

        sys.exit(1)
    
    def warning(self, message: str, token: Token | None=None):
        if token is not None:
            line_number = token.source_pos.lineno-1
            column_number = token.source_pos.colno-1
            print(f'{COLOR_WARN}ASSEMBLER WARNING: {message}')
            print(f'{line_number+1} | {self.source_lines[line_number]}')
            print(f'{" " * (len(str(line_number))+3+column_number)}^')
        else:
            print(f'{COLOR_WARN}ASSEMBLER WARNING: {message}')
        print(COLOR_RESET, end='')
    
    def next_token(self, tokens: LexerStream, expected_kind: str|set[str]) -> Token:
        try:
            next_tok = tokens.next()
        except StopIteration:
            self.error(f'Reached end of token stream while trying to get token of kind "{expected_kind}"')
            return None

        if isinstance(expected_kind, str):
            expected_kind = set([expected_kind])
        
        if next_tok.name not in expected_kind:
            self.error(f'Expected "{expected_kind}" token but got "{next_tok.name}"', next_tok)
            return None
        
        return next_tok

    def parse_int_token(self, token: Token) -> int:
        value_str: str = token.value
        is_negative = False

        if value_str.startswith('-'):
            is_negative = True
            value_str = value_str[1:]
        
        value = 0
        if value_str.startswith('0x'):
            value = int(value_str[2:], base=16)
        elif value_str.startswith('0b'):
            value = int(value_str[2:], base=2)
        else:
            value = int(value_str, base=10)
        
        return -value if is_negative else value

    def declare_constant(self, name: str, value: int, name_token: Token):
        if name in self.constants:
            self.warning(f'Constant "{name}" declared more than once.', name_token)
        else:
            self.constants[name] = value
    
    def initial_pass(self) -> list[Intermediate]:
        """
        Records meta variables and constants then converts the program into a list of
        Labels, UnparsedInstructions, and Pseudoinstructions
        """
        intermediates: list[Intermediate] = []
        state = AssemblerState.META

        try:
            tokens = G2_LEXER.lex(self.source_code)
        except LexingError:
            self.error('Unrecognized token')

        for token in tokens:
            if token.name == 'COMMENT':
                continue

            if token.name == 'DEFINE':
                name_token = self.next_token(tokens, 'NAME')
                value_token = self.next_token(tokens, 'INT')
                self.declare_constant(name_token.value, self.parse_int_token(value_token), name_token)
                continue

            if state == AssemblerState.META:
                if token.name == 'NAME':
                    state = AssemblerState.CODE
                elif token.name == 'META_VAR':
                    meta_var_name = token.value.removeprefix('#')
                    if meta_var_name not in META_VARS:
                        self.error(f'Unrecognized meta variable "{meta_var_name}".', token)
                    int_token = self.next_token(tokens, 'INT')
                    self.meta_vars[meta_var_name] = self.parse_int_token(int_token)
                elif token.name == 'LOAD':
                    name_token = self.next_token(tokens, 'NAME')
                    data_op_token = self.next_token(tokens, 'DATA_OP')
                    data_type_token = self.next_token(tokens, 'DATA_TYPE')
                    if data_type_token.value == 'bytes':
                        data_token = self.next_token(tokens, 'INT')
                        data = data_token.value
                    else:
                        data_token = self.next_token(tokens, 'STRING')
                        data = data_token.value[1:-1]
                    try:
                        int_data = parse_data_entry(data_type_token.value, data_op_token.value, data)
                        self.data_entries[name_token.value] = (int_data, name_token)
                    except G2ADataException as e:
                        self.error(str(e), data_token)
                else:
                    self.error(f'Expected meta variable definition but got "{token.value}".', token)
            
            if state == AssemblerState.CODE:
                if token.name == 'LABEL':
                    intermediates.append(Label(token, token.value.removesuffix(':')))
                elif token.name == 'NAME':
                    instruction_name: str = token.value
                    if instruction_name in INSTRUCTIONS:
                        arg_count = INSTRUCTIONS[instruction_name]['args']
                        args = [self.next_token(tokens, {'INT', 'NAME', 'META_CONST'}) for _ in range(arg_count)]
                        intermediates.append(UnparsedInstruction(token, instruction_name, args))
                    elif instruction_name in PSEUDOINSTRUCTIONS:
                        arg_count = len(PSEUDOINSTRUCTIONS[instruction_name]['args'])
                        args = [self.next_token(tokens, {'INT', 'NAME', 'META_CONST'}) for _ in range(arg_count)]
                        intermediates.append(Pseudoinstruction(token, instruction_name, args))
                    else:
                        self.error('Unrecognized instruction', token)
                else:
                    self.error(f'Expected label or instruction but got "{token.value}"', token)
        
        return intermediates

    def add_data_constants(self):
        self.data_start_address = self.meta_vars['memory']

        for name, tup in self.data_entries.items():
            ints, name_token = tup
            self.declare_constant(name, self.meta_vars['memory'], name_token)
            self.meta_vars['memory'] += len(ints)
        
    
    def expand_pseudoinstructions(self, intermediates: list[Intermediate]) -> list[Intermediate]:
        expanded: list[Intermediate] = []

        next_label = None  # A label pointing to the next instruction

        queued_skip_label = None
        skip_label = None  # A label pointing to the instruction after the next one

        for i, value in enumerate(intermediates[:]):
            if isinstance(value, UnparsedInstruction):
                if queued_skip_label is not None:
                    skip_label = queued_skip_label
                    queued_skip_label = None
                
            if isinstance(value, Pseudoinstruction):
                instruction_data = PSEUDOINSTRUCTIONS[value.name]
                format_kwargs: dict[str, str] = {}

                if 'NEXT_LABEL' in instruction_data['code']:
                    next_label = f'{value.name}_{value.token.source_pos.lineno}_{value.token.source_pos.colno}_next'
                    format_kwargs['NEXT_LABEL'] = next_label
                
                if 'SKIP_LABEL' in instruction_data['code']:
                    queued_skip_label = f'{value.name}_{value.token.source_pos.lineno}_{value.token.source_pos.colno}_skip'
                    format_kwargs['SKIP_LABEL'] = queued_skip_label
                

                for i, arg_token in enumerate(value.args):
                    if arg_token.name == 'INT':
                        format_kwargs[f'a{i}'] = str(self.parse_int_token(arg_token))
                    elif arg_token.name == 'NAME':
                        format_kwargs[f'a{i}'] = arg_token.value
                    else:
                        self.error('Unrecognized pseudoinstruction argument')
                
                formatted_code: str = instruction_data['code'].format(**format_kwargs)
                code_tokens = G2_LEXER.lex(formatted_code)
                for ins_token in code_tokens:
                    arg_count = INSTRUCTIONS[ins_token.value]['args']
                    args = [self.next_token(code_tokens, {'INT', 'NAME', 'META_CONST'}) for _ in range(arg_count)]
                    expanded.append(UnparsedInstruction(value.token, ins_token.value, args))
                
                if next_label is not None:
                    expanded.append(Label(None, next_label))
                    next_label = None
            else:
                expanded.append(value)
            
            # Add skip label after the next instruction
            if skip_label is not None:
                expanded.append(Label(None, skip_label))
                skip_label = None
        
        return expanded

    def get_label_lookup(self, intermediates: list[Intermediate]) -> dict[str, int]:
        labels: dict[str, int] = {}
        instruction_index = 0

        for value in intermediates:
            if isinstance(value, Label):
                if value.name in labels:
                    self.warning(f'Label "{value.name}" declared more than once.', value.token)
                else:
                    labels[value.name] = instruction_index
            else:
                instruction_index += 1

        return labels

    def parse_instructions(self, unparsed_instructions: list[UnparsedInstruction], labels: dict[str, int]) -> list[Instruction]:
        instructions: list[Instruction] = []
        for ins in unparsed_instructions:
            opcode = INSTRUCTIONS[ins.name]['opcode']
            parsed_args: list[int] = []
            for arg in ins.args:
                if arg.name == 'INT':
                    parsed_value = self.parse_int_token(arg)
                elif arg.name == 'META_CONST':
                    parsed_value = self.meta_vars[arg.value.lower()]
                elif arg.name == 'NAME':  # Label or defined constant
                    if arg.value in labels:
                        parsed_value = labels[arg.value]
                    elif arg.value in self.constants:
                        parsed_value = self.constants[arg.value]
                    else:
                        self.error(f'Unrecognized name "{arg.value}"', ins.token)
                parsed_args.append(parsed_value)

            instructions.append(Instruction(opcode, parsed_args))
        
        return instructions

    def assemble(self):
        intermediates = self.initial_pass()
        self.add_data_constants()
        print(self.data_entries)
        intermediates = self.expand_pseudoinstructions(intermediates)
        self.labels = self.get_label_lookup(intermediates)
        unparsed_instructions = [v for v in intermediates if not isinstance(v, Label)]
        self.instructions = self.parse_instructions(unparsed_instructions, self.labels)
    
    def get_bytes(self) -> bytes:
        out_bytes = FILE_SIGNATURE

        # Write metadata
        out_bytes += self.meta_vars['memory'].to_bytes(4, 'little')
        out_bytes += self.meta_vars['width'].to_bytes(4, 'little')
        out_bytes += self.meta_vars['height'].to_bytes(4, 'little')

        # Write instructions
        for instruction in self.instructions:
            out_bytes += instruction.to_bytes()
        out_bytes += 0xFF.to_bytes(1)  # End code section opcode

        # Write data entries
        out_bytes += len(self.data_entries).to_bytes(4, 'little')   # Number of entries
        out_bytes += self.data_start_address.to_bytes(4, 'little')  # Address of the data section in memory
        for ints, _ in self.data_entries.values():
            out_bytes += len(ints).to_bytes(4, 'little', signed=False)                 # Entry size
            out_bytes += b''.join(i.to_bytes(4, 'little', signed=True) for i in ints)  # Entry data

        return out_bytes

    def disassemble(self, add_instruction_indices=False) -> str:
        """
        Disassemble the program back into a readable format
        """
        lines: list[str] = []

        for name, value in self.meta_vars.items():
            lines.append(f'#{name} {value}')
        
        label_lookup = {}
        for k, v in self.labels.items():
            label_lookup.setdefault(v, []).append(k)
        
        ins_name_lookup = {data['opcode']: name for name, data in INSTRUCTIONS.items()}
        for i, ins in enumerate(self.instructions):
            if i in label_lookup:
                for label in label_lookup[i]:
                    lines.append(f'{label}:')
            instruction_name = ins_name_lookup[ins.opcode]
            arg_count = INSTRUCTIONS[instruction_name]['args']
            args_str = ' '.join(map(str, ins.args[:arg_count]))
            line = f'    {instruction_name} {args_str}'
            if add_instruction_indices:
                line = f'{i} |{line}'
            lines.append(line)
        

        return '\n'.join(lines)


def assemble(input_path: str, output_path: str):
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f'File "{input_path}" does not exist.')

    with open(input_path, 'r') as f:
        source_code = f.read()

    assembler = Assembler(source_code)
    assembler.assemble()

    print(assembler.disassemble(True))
    
    with open(output_path, 'wb') as f:
        f.write(assembler.get_bytes())


def main() -> int:
    try:
        parser = ArgumentParser('g2a', description='Assemble a g2 program')
        parser.add_argument('input_path', help='The path to the input g2 assembly program')
        parser.add_argument('output_path', help='The path to the assembled g2 program')
        args = parser.parse_args()
    except Exception as e:
        print(e)
        return 1

    if not os.path.isfile(args.input_path):
        print(f'Could not find file "{args[1]}"')
        return 2

    assemble(args.input_path, args.output_path)
    return 0


if __name__ == '__main__':
    sys.exit(main())