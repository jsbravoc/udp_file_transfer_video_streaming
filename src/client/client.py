# Importing libraries
import logging
import os
import socket
from datetime import datetime
from sys import platform
import hashlib

import clientconfig as cfg
import tqdm

def calculate_hash(file):
    file_hash = hashlib.md5()
    with open(file, 'rb') as f:
        fb = f.read(BUFFER_SIZE)
        while len(fb)>0:
            file_hash.update(fb)
            fb = f.read(BUFFER_SIZE)
    return file_hash.hexdigest()
if not os.path.exists(f"{os.getcwd()}/logs/"):
    os.makedirs(f"{os.getcwd()}/logs/")

LOGS_FILE = f"{os.getcwd()}\\logs\\{str.replace(str(datetime.now()), ':', '-')}.log"

logging.basicConfig(handlers=[logging.FileHandler(filename=LOGS_FILE,
                                                  encoding='utf-8', mode='a+')],
                    format="%(asctime)s %(name)s:%(levelname)s:%(message)s",
                    datefmt="%F %A %T",
                    level=logging.INFO)
logger_progress = logging.getLogger("Progress")
logger_tcp = logging.getLogger("TCP_Packets")

SEPARATOR = "<SEPARATOR>"
BUFFER_SIZE = 4096  # send 4096 bytes each time step

print("------------Cargar configuraciones por defecto------------")
with open("clientconfig.py", 'r') as f:
    print(f.read())
config = input("Seleccione una configuración por defecto: (valor por defecto: Azure) ")
if config not in cfg.ClientConfig:
    print(f"Valor no admitido {config}, se utilizará valor por defecto")
    config = cfg.ClientConfig["Azure"]
else:
    config = cfg.ClientConfig[config]

# the ip address or hostname of the server, the receiver
print("** Para utilizar valores por defecto, ingresar cadena vacía **")
host = input(f"Ingrese la IP del servidor: (por defecto '{config['defaultIP']}') ")
if host == "":
    host = config['defaultIP']

port = config['defaultPort']
path = input(f"Ingrese la ruta donde se quiere guardar el archivo: (por defecto en {config['defaultDir']}) ")
if path != "":
    if not path.endswith("/"):
        path += "/"
    if not os.path.exists(path):
        os.makedirs(path)

# create the client socket
s = socket.socket()

print(f"[+] Conectando a {host}:{port}")
s.connect((host, port))
print("[+] Conectado.")

s.send("Notificación de inicio".encode())

received = s.recv(BUFFER_SIZE).decode()
filename, filesize = received.split(SEPARATOR)
filename = os.path.basename(filename)

file_hash = s.recv(100000).decode()
if path != "":
    filename = os.path.join(path, filename)
# convert to integer
filesize = int(filesize)
received = 0
progress = tqdm.tqdm(range(filesize), f"Recibiendo {filename} de {host}", unit="B", unit_scale=True,
                     unit_divisor=1024)
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
        received += len(bytes_read)
        progress.update(len(bytes_read))

        logger_tcp.critical(f"Recibiendo {filename} de {host} Tamaño paquete: {BUFFER_SIZE}, "
                            f"paquete :{round(received / BUFFER_SIZE)}/{round(filesize / BUFFER_SIZE)}")

print("\n---------------------------------------------------------------------------\n")
print(f"   Se finalizó la transferencia del archivo {os.path.basename(filename)}            ")
print("\n---------------------------------------------------------------------------")

print("Calculando hash del archivo...")
local_hash = calculate_hash(filename)
if local_hash == file_hash:
    print("El hash calculado del archivo es igual al recibido")
else:
    print("El hash del archivo no coincide con el recibido")
abrirArchivo = input("¿Desea abrir el archivo (Y/N): (por defecto: N) ")
if abrirArchivo == "Y":
    abrirArchivo = True
else:
    if abrirArchivo != "" and abrirArchivo != "N":
        print(f"Valor no admitido {abrirArchivo}, se utilizará valor por defecto")
    abrirArchivo = False

abrirLogs = input("¿Desea abrir el archivo de logs  (Y/N): (por defecto: N) ")
if abrirLogs == "Y":
    abrirLogs = True
else:
    if abrirLogs != "" and abrirLogs != "N":
        print(f"Valor no admitido {abrirLogs}, se utilizará valor por defecto")
    abrirLogs = False

if abrirArchivo:
    try:
        if platform == "win32":
            os.startfile(filename)
    except:
        print(f"No se pudo abrir el archivo ({filename})")

if abrirLogs:
    try:
        if platform == "win32":
            os.startfile(LOGS_FILE)
    except:
        print(f"No se pudo abrir el archivo ({LOGS_FILE})")
