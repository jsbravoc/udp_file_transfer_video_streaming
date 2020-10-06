# Importing libraries
import hashlib
import logging
import os
import socket
from datetime import datetime
from sys import platform
import hashlib
import clientconfig as cfg
import tqdm

# Si no existe la carpeta de logs, entonces se crea
if not os.path.exists(f"{os.getcwd()}/logs/"):
    os.makedirs(f"{os.getcwd()}/logs/")

# region CONSTANTES
LOGS_FILE = f"{os.getcwd()}\\logs\\{str.replace(str(datetime.now()), ':', '-')}.log"
SEPARATOR = "<SEPARATOR>"
BUFFER_SIZE = 4096
BLOCKSIZE = 65536
# endregion

# region CARGA DE CONFIGURACIÓN
print("------------Cargar configuraciones por defecto------------")
with open("clientconfig.py", 'r') as f:
    print(f.read())
config = input("Seleccione una configuración por defecto: (valor por defecto: Azure) ")
if config not in cfg.ClientConfig:
    print(f"Valor no admitido {config}, se utilizará valor por defecto")
    config = cfg.ClientConfig["Azure"]
else:
    config = cfg.ClientConfig[config]
IGNORE_PACKET_COUNT = config["ignorePacketCount"]
DEFAULT_IP = config["defaultIP"]
DEFAULT_DIR = config["defaultDir"]
# endregion

# region LOGGING
logging.basicConfig(handlers=[logging.FileHandler(filename=LOGS_FILE,
                                                  encoding='utf-8', mode='a+')],
                    format="%(asctime)s %(name)s:%(levelname)s:%(message)s",
                    datefmt="%F %A %T",
                    level=logging.INFO)
logger_progress = logging.getLogger("Progress")
logger_tcp = logging.getLogger("TCP_Packets")
# endregion


# region PARÁMETROS DEL CLIENTE
print("** Para utilizar valores por defecto, ingresar cadena vacía **")
host = input(f"Ingrese la IP del servidor: (por defecto '{DEFAULT_IP}') ")
if host == "":
    host = DEFAULT_IP

port = config['defaultPort']
path = input(f"Ingrese la ruta donde se quiere guardar el archivo: (por defecto en {DEFAULT_DIR}) ")
if path == "" and DEFAULT_DIR != "/src/client/" :
    path = DEFAULT_DIR
elif path == "" and DEFAULT_DIR == "/src/client/":
    path = ""    
else:
    if not path.endswith("/"):
        path += "/"
    if not os.path.exists(path):
        os.makedirs(path)
# endregion

# region CONEXIÓN CON EL SERVIDOR
s = socket.socket()
print(f"[+] Conectando a {host}:{port}")
try:
    s.connect((host, port))
except Exception as e:
    print(f"[ERROR]: {e}")
    exit(-1)
print("[+] Conectado.")

# Validar conexión con el servidor
s.send("Notificación de inicio".encode())
# endregion

# region RECEPCIÓN ARCHIVO
received = s.recv(BUFFER_SIZE).decode()
filename, filesize, hashServer = received.split(SEPARATOR)
filename = os.path.basename(filename)
if path != "":
    filename = os.path.join(path, filename)
filesize = int(filesize)
#hash_rcvd = s.recv(BUFFER_SIZE).decode()
received = 0
progress = tqdm.tqdm(range(filesize), f"Recibiendo {filename} de {host}", unit="B", unit_scale=True,
                     unit_divisor=1024)
with open(filename, "wb") as f:
    for _ in progress:
        bytes_read = s.recv(BUFFER_SIZE)
        if received == filesize or not bytes_read:
            progress.n = filesize
            progress.refresh()
            logger_progress.info(str(progress))
            s.close()
            progress.close()
            break
        f.write(bytes_read)
        received += len(bytes_read)
        progress.update(len(bytes_read))

        if not IGNORE_PACKET_COUNT:
            logger_tcp.critical(f"Recibiendo {filename} de {host} Tamaño paquete: {BUFFER_SIZE}, "
                                f"paquete :{round(received / BUFFER_SIZE)}/{round(filesize / BUFFER_SIZE)}")
# endregion

# region VALIDACIÓN ARCHIVO
print("\n---------------------------------------------------------------------------\n")
print(f"   Se finalizó la transferencia del archivo {os.path.basename(filename)}            ")
print("\n---------------------------------------------------------------------------")

print("\n---------------------------------------------------------------------------\n")
print(f"                 Verificando hash SHA-256 del servidor             ")
print("\n---------------------------------------------------------------------------")
print(f"\n Hash del servidor: {hashServer} \n")

hasher = hashlib.sha256()
with open(filename, 'rb') as afile:
    buf = afile.read(BLOCKSIZE)
    while len(buf) > 0:
        hasher.update(buf)
        buf = afile.read(BLOCKSIZE)
hashClient = hasher.hexdigest()

print(f"\n Hash del servidor: {hashClient} \n")

if hashServer == hashClient:
    print("Hash SHA-256 verificado correctamente")
else:
    print("[ERROR] El hash del archivo no coincide con el del servidor")
# endregion

# region POST EJECUCIÓN
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
    except Exception as e:
        print(f"[ERROR] No se pudo abrir el archivo ({filename}), {e}")

if abrirLogs:
    try:
        if platform == "win32":
            os.startfile(LOGS_FILE)
    except Exception as e:
        print(f"[ERROR] No se pudo abrir el archivo ({LOGS_FILE}), {e}")
# endregion