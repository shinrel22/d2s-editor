import io
import os
import zlib
import uuid
from itertools import zip_longest
from cryptography.fernet import Fernet

from config import ROOT_PATH


def gen_uuid():
    return uuid.uuid4().hex


def dec_to_bin(value: int,
               length: int = None,
               padding: str = None):
    if not padding:
        padding = '0'

    if not length:
        length = 2

    template = '{:' + '{padding}{length}b'.format(
        padding=padding,
        length=length
    ) + '}'
    return template.format(value)


def bin_to_dec(data: str) -> int:
    result = int(data, 2)
    return result


def dec_to_hex(number: int,
               length: int = None,
               padding: str = None) -> str:
    if not length:
        length = 2

    if not padding:
        padding = '0'

    template = '{:' + '{padding}{length}x'.format(
        padding=padding,
        length=length
    ) + '}'

    result = template.format(number)

    if len(result) % 2:
        result = padding + result

    return result


def bin_to_hex(data: str,
               length: int = None,
               padding: str = None):
    if not padding:
        padding = '0'

    dec = bin_to_dec(data)

    result = dec_to_hex(dec, length=length, padding=padding)

    return result


def split_array(array, n, padding=None):
    return zip_longest(*[iter(array)] * n, fillvalue=padding)


def make_byte_array_from_hex(data):
    return [
        dec_to_hex(b)
        for b in bytearray.fromhex(data)
    ]


def convert_byte_array_to_bit(data: list[str], length: int = None) -> list[str]:
    joined_data = ''.join(data)
    if length:
        bin_data = dec_to_bin(int(joined_data, 16), length=length)
    else:
        bin_data = dec_to_bin(int(joined_data, 16))

    return list(bin_data)


def make_d2s_file_path(file_name: str, path: list):
    target = os.path.join(ROOT_PATH, 'd2s_storage')

    for p in path:
        target = os.path.join(target, p)

    if not os.path.exists(target):
        os.makedirs(target)

    if not file_name.endswith('.d2s'):
        file_name = file_name + '.d2s'

    return os.path.join(target, file_name)


def get_dict_key_from_value(data: dict, value: any):
    result = None

    for k, v in data.items():
        if v == value:
            result = k
            break
    return result


def decompress_data(data: bytes, encryption_key: str = None) -> bytes:
    if encryption_key:
        cipher_suite = Fernet(encryption_key)
        data = cipher_suite.decrypt(data)

    decompressed_data = zlib.decompress(data)

    return decompressed_data


def compress_data(data: bytes, encryption_key: str = None) -> bytes:

    compressed_data = zlib.compress(data)

    if encryption_key:
        cipher_suite = Fernet(encryption_key)
        compressed_data = cipher_suite.encrypt(compressed_data)

    return compressed_data


def convert_tsv_to_json(data: str) -> list:
    file = io.BytesIO(data.encode())

    result = []
    first_line = file.readline().decode()

    # The first line consist of headings of the record,
    # so we will store it in an array and move to
    # next line in input_file.
    titles = [t.strip() for t in first_line.split('\t')]

    for index, line in enumerate(file):
        d = dict()
        for t, f in zip(titles, line.decode().split('\t')):
            # Convert each row into dictionary with keys as titles
            d[t] = f.strip()

            # we will use strip to remove '\n'.
        result.append(d)

    return result
