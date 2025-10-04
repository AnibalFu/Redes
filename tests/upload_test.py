import os
import subprocess

from pathlib import Path
from time import sleep

def test_stop_and_wait_upload_file():
    if os.path.exists('tests/data/24LeMans.txt'):
        os.remove('tests/data/24LeMans.txt')

    server = subprocess.Popen([
        'python3', 'src/start-server.py', '-H', '127.0.0.1', '-p', '2223', '-s', 'tests/data'
    ])

    sleep(1)

    subprocess.run([
        'python3', 'src/upload.py', '-H', '127.0.0.1', '-p', '2223', '-s', 'data/file.bin', '-n', '24LeMans.txt', '-r', 'SW'
    ])

    assert Path('tests/data/').is_dir() and Path('tests/data/24LeMans.txt').is_file()

    with open('tests/data/24LeMans.txt') as file:
        got = file.read()

        with open('data/file.bin') as file:
            expected = file.read()

            assert got == expected

    server.kill()

def test_go_back_n_upload_file():
    if os.path.exists('tests/data/24LeMans.txt'):
        os.remove('tests/data/24LeMans.txt')

    server = subprocess.Popen([
        'python3', 'src/start-server.py', '-H', '127.0.0.1', '-p', '2223', '-s', 'tests/data'
    ])

    sleep(1)

    subprocess.run([
        'python3', 'src/upload.py', '-H', '127.0.0.1', '-p', '2223', '-s', 'data/file.bin', '-n', '24LeMans.txt', '-r', 'GBN'
    ])

    assert Path('tests/data/').is_dir() and Path('tests/data/24LeMans.txt').is_file()

    with open('tests/data/24LeMans.txt') as file:
        got = file.read()

        with open('data/file.bin') as file:
            expected = file.read()

            assert got == expected

    server.kill()