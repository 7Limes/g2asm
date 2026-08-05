"""
Allows external data to be attached to assembled programs.
"""

import os
import re


HEX_REGEX = r'(:?[0-9a-fA-F]{2})+$'


class G2ADataException(Exception):
    """Base class for data parsing exceptions"""


def load_file(file_path: str) -> bytes:
    """
    Raises:
        G2ADataException: If the file was not found
    """
    if not os.path.isfile(file_path):
        raise G2ADataException(f'Could not find file "{file_path}".')

    with open(file_path, 'rb') as f:
        file_bytes = f.read()
    return file_bytes


def load_bytes(bytes_hex: str) -> bytes:
    """
    Raises:
        G2ADataException: If the bytes are improperly formatted
    """

    if not re.match(HEX_REGEX, bytes_hex):
        raise G2ADataException('Expected hex value for byte data.')
    
    return bytes(bytes_hex)


def load_string(string: str) -> bytes:
    return bytes(string, 'ascii')


def raw_operation(data: bytes) -> list[int]:
    return list(data)


def pack_operation(data: bytes) -> list[int]:
    amount_padding = (4 - len(data) % 4) % 4
    data += b'0' * amount_padding
    
    result = []
    for i in range(0, len(data), 4):
        chunk = data[i:i+4]
        value = int.from_bytes(chunk, byteorder='big', signed=True)
        result.append(value)
    
    return result


def parse_data_entry(data_type: str, operation: str, data: str) -> list[int]:
    """
    Raises:
        G2ADataException: If a data parsing error occurs
    """

    load_result: bytes = b''
    if data_type == 'file':
        load_result = load_file(data)
    elif data_type == 'bytes':
        load_result = load_bytes(data)
    elif data_type == 'string':
        load_result = load_string(data)
    else:
        raise G2ADataException(f'Invalid data type "{data_type}".')

    data_bytes = load_result
    operation_result: list[int] = None
    if operation == 'raw':
        operation_result = raw_operation(data_bytes)
    elif operation == 'pack':
        operation_result = pack_operation(data_bytes)
    else:
        raise G2ADataException(f'Invalid operation "{operation}".')
    
    # Insert length of string if necessary
    if data_type == 'string':
        operation_result.insert(0, len(operation_result))
    
    return operation_result
