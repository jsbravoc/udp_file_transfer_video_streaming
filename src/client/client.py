
# Importing libraries
import socket
import os
import tqdm
import logging
from datetime import datetime

if not os.path.exists(f"{os.getcwd()}/logs/"):
    os.makedirs(f"{os.getcwd()}/logs/")

if not os.path.exists(f"{os.getcwd()}/logs/tqdm"):
    os.makedirs(f"{os.getcwd()}/logs/tqdm")


LOGS_FILE = f"{os.getcwd()}\\logs\\{str.replace(str(datetime.now()),':','-')}.log"

logging.basicConfig(handlers=[logging.FileHandler(filename=LOGS_FILE,
                                                  encoding='utf-8', mode='a+')],
                    format="%(asctime)s %(name)s:%(levelname)s:%(message)s",
                    datefmt="%F %A %T",
                    level=logging.INFO)
logger_progress = logging.getLogger("Progress")
logger_tcp = logging.getLogger("TCP_Packets")

SEPARATOR = "<SEPARATOR>"
BUFFER_SIZE = 4096 # send 4096 bytes each time step


# the ip address or hostname of the server, the receiver
host = '52.186.137.191'
host = 'localhost'
# the port, let's use 5001
port = 9898
# the name of file we want to send, make sure it exists
#filename = "Media1.mp4"
# get the file size
#filesize = os.path.getsize(filename)

# create the client socket
s = socket.socket()

print(f"[+] Conectando a {host}:{port}")
s.connect((host, port))
print("[+] Conectado.")

s.send("Notificación de inicio".encode())


received = s.recv(BUFFER_SIZE).decode()
filename, filesize = received.split(SEPARATOR)
filename = os.path.basename(filename)
# convert to integer
filesize = int(filesize)
received = 0
progress = tqdm.tqdm(range(filesize), f"Receiving {filename}", unit="B", unit_scale=True, unit_divisor=BUFFER_SIZE)
with open(filename, "wb") as f:
    for _ in progress:
        # read 1024 bytes from the socket (receive)
        bytes_read = s.recv(BUFFER_SIZE)
        if received == filesize or not bytes_read:
            progress.n = filesize
            progress.refresh()
            logger_progress.info(str(progress))
            s.close()
            progress.close()
            break
        # write to the file the bytes we just received
        f.write(bytes_read)
        # update the progress bar
        progress.update(len(bytes_read))
