import os
import subprocess

from pathlib import Path
from time import sleep

def test_stop_and_wait_download_file():
    if os.path.exists('tests/data/net.py'):
        os.remove('tests/data/net.py')
    
    server = subprocess.Popen([
        'python3', 'src/start-server.py', '-H', '127.0.0.1', '-p', '2223', '-s', './'
    ])

    sleep(1)

    subprocess.run([
        'python3', 'src/download.py', '-H', '127.0.0.1', '-p', '2223', '-d', 'tests/data/', '-n', 'net.py', '-r', 'SW'
    ])

    assert Path('tests/data/').is_dir() and Path('tests/data/net.py').is_file()

    with open('tests/data/net.py') as file:
        got = file.read()

        with open('net.py') as file:
            expected = file.read()

            assert got == expected

    server.kill()

def test_go_back_n_download_file():
    if os.path.exists('tests/data/net.py'):
        os.remove('tests/data/net.py')
    
    server = subprocess.Popen([
        'python3', 'src/start-server.py', '-H', '127.0.0.1', '-p', '2223', '-s', './'
    ])

    sleep(1)

    subprocess.run([
        'python3', 'src/download.py', '-H', '127.0.0.1', '-p', '2223', '-d', 'tests/data/', '-n', 'net.py', '-r', 'GBN'
    ])

    assert Path('tests/data/').is_dir() and Path('tests/data/net.py').is_file()

    with open('tests/data/net.py') as file:
        got = file.read()

        with open('net.py') as file:
            expected = file.read()

            assert got == expected

    server.kill()