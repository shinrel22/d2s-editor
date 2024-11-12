import zlib


def decompress_dat_file_from_decapitator(file_path: str) -> str:
    # The files we're decompressing are from a CPP source code,
    # it uses 2 more bytes for padding after a default 6-byte header.
    # https://github.com/kambala-decapitator/MedianXLOfflineTools/blob/a928ee871d09fae85720c8d39aca9cc8f5a3ddb5/utils/CompressFiles/main.cpp
    data_offset = 8

    with open(file_path, 'rb') as f:
        data = f.read()

        decompressed_data = zlib.decompress(data[data_offset:])

    return decompressed_data.decode()
