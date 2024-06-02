import re
import os
import sys
import config
import requests
import tempfile
import datetime
import threading
import urllib3
import urllib.request
from time import sleep
import subprocess
from urllib.parse import urlparse
import http.client as httplib

VERSION = "2.0-beta"
CURRENT_PATH = sys.path[0]
TS_PATH = os.path.join(CURRENT_PATH, "CHUNKS")
OUT_PATH = os.path.join(CURRENT_PATH, "OUTPUT")
TEMP_DIR = tempfile.TemporaryDirectory(prefix="dump_", suffix="_Baiskoafu")
TS_LINKS = []

HOST = ""
# file_size = 0 # multiprocessing bug --> global var # TODO

def clear():
    if 'linux' in sys.platform: os.system('clear')
    if 'win' in sys.platform: os.system('cls')

def wait(sec): sleep(sec)
clear()
banner = f'''\033[01;36m\
  ____        _     _                __       
 |  _ \      (_)   | |              / _|      
 | |_) | __ _ _ ___| | _____   __ _| |_ _   _ 
 |  _ < / _` | / __| |/ / _ \ / _` |  _| | | |  
 | |_) | (_| | \__ \   < (_) | (_| | | | |_| |  \033[01;37m
 |____/ \__,_|_|___/_|\_\___/ \__,_|_|  \__,_|  \x1b[1;32m

 Downloader for Baiskoafu | proxygod | {VERSION} \033[1;33m\033[0;0m
  Thanks to r00t173 [1;33m\033[0;0m
'''
print(banner)
print("Please wait ...", end='\r')
wait(1)

def make_dirs():
    if not os.path.isdir(TS_PATH):
        os.mkdir("CHUNKS")
    if not os.path.isdir(OUT_PATH):
        os.mkdir("OUTPUT")

make_dirs()

def is_connected():
    conn = httplib.HTTPConnection("13.126.170.202", timeout=3)
    try: conn.request("HEAD", "/"); conn.close(); return True
    except: conn.close(); return False

def extract_ts_url(m3u8_path, base_url):
    urls = []
    with open(m3u8_path, "r") as file:
        lines = file.readlines()
        for line in lines:
            if line.endswith(".ts\n"):
                urls.append(base_url + line.strip("\n"))
    for i in urls:
        TS_LINKS.append(i)

def get_ts_files(m3u8_url):
    p = m3u8_url.split('/')
    p.pop(len(p) - 1)
    p = '/'.join(p) + '/'

    tmp_file = os.path.join(TEMP_DIR.name, "data.m3u8")
    urllib.request.urlretrieve(m3u8_url, tmp_file)
    extract_ts_url(tmp_file, p)

def remove_old_files():
    old_chunks = [i for i in os.listdir(TS_PATH)]
    if len(old_chunks) >= 1:
        inp = input(f"Old files found!\n{TS_PATH}\nRemove? (Y/n) : ")
        if inp.lower() == 'n':
            print("Remove or move old files to continue ...")
            wait(3)
            exit()  # TODO go to main
        else:
            os.chdir(TS_PATH)
            print("Removing files ....", end='\r')
            for i in old_chunks: os.remove(i)
            os.chdir(CURRENT_PATH)

def meter():
    remove_old_files()
    global file_size
    print("Collecting segments... This might take a while")

    chunk_size = []
    def get_chunks(i):
        response = requests.head(TS_LINKS[i], allow_redirects=True)
        size = response.headers.get('content-length', 0)
        chunk_size.append(int(size))

    chunk_list = []
    for i in range(len(TS_LINKS)):
        t = threading.Thread(target=get_chunks, args=(i,))
        chunk_list.append(t)

    for i in chunk_list:
        i.start()
    for i in chunk_list:
        i.join()

    MBytes = float(1 << 20)
    file_size = int(sum(chunk_size)) / MBytes
    print(f"\nTotal file size: {round(file_size, 2)} MB")

def download():
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    meter()
    if config.ASK_BEFORE_DOWNLOAD:
        d = input("Continue to download: (Y/n) : ")
    else:
        d = 'y'

    if d.lower() == 'y':
        def down_chunk(i):
            ts_url = TS_LINKS[i]
            file_name = ts_url.split("/")[-1]
            try:
                response = requests.get(ts_url, stream=True, verify=False)
            except Exception as e:
                pass

            ts_path = os.path.join(TS_PATH, f"{i}.ts")
            with open(ts_path, "wb+") as file:
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        file.write(chunk)

        down_chunk_list = []
        for i in range(len(TS_LINKS)):
            t = threading.Thread(target=down_chunk, args=(i,))
            down_chunk_list.append(t)
        for i in down_chunk_list:
            i.start()
        for i in down_chunk_list:
            current_file_size = 0
            for ts in os.listdir(TS_PATH):
                if ts.endswith('.ts'): current_file_size += os.path.getsize(os.path.join(TS_PATH, ts))
            print(f"Downloading  ....  {round(current_file_size / 1024 / 1024, 2)} / {round(file_size)} MB", end='\r')
            i.join()

        print()

    else:
        print("Download canceled!")
        wait(3)
        exit()

def file_walker(path):
    file_list = []
    for root, dirs, files in os.walk(path):
        for fn in files:
            p = str(root + '/' + fn)
            file_list.append(p)
    return file_list

def combine(file_name):
    file_list = file_walker(TS_PATH)
    
    file_list.sort(key=lambda x: int(re.search(r'\d+', x).group()))
    
    
    list_file_path = os.path.join(TEMP_DIR.name, "file_list.txt")
    with open(list_file_path, 'w') as list_file:
        for file_path in file_list:
            list_file.write(f"file '{file_path}'\n")
    
    output_path = os.path.join(OUT_PATH, file_name)
    ffmpeg_command = [
        'ffmpeg', '-f', 'concat', '-safe', '0', '-i', list_file_path,
        '-c', 'copy', '-bsf:a', 'aac_adtstoasc', output_path
    ]
    subprocess.run(ffmpeg_command)
    
    print("\nDownload completed!")
    print(f"File location : {output_path}")
    input("")


def check_ffmpeg():
    try:
        subprocess.run(['ffmpeg', '-version'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("ffmpeg is installed and available.")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("ffmpeg is not installed or not found in PATH.")
        exit()

check_ffmpeg()
