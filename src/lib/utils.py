from sqlite3 import Connection
import sys

from lib.flags import USER_FLAGS

def split(args: list[str]):
    result = []

    i = 1
    while i < len(args):
        if not args[i].startswith('-'):
            i += 1
            continue
        
        buf = args[i]
        while i + 1 < len(args) and not args[i + 1].startswith('-'):
            buf = buf + ' ' + args[i + 1]
            i += 1

        result.append(buf)
        i += 1

    return result
