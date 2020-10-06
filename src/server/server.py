import io
import logging
import os
import socket
from _thread import *
from datetime import datetime
from multiprocessing.dummy import Pool as ThreadPool
from sys import platform
import hashlib

import serverconfig as cfg
from tqdm.auto import tqdm

if not os.path.exists(f"{os.getcwd()}/logs/"):
    os.makedirs(f"{os.getcwd()}/logs/")

if not os.path.exists(f"{os.getcwd()}/logs/tqdm"):
    os.makedirs(f"{os.getcwd()}/logs/tqdm")

LOGS_FILE = f"{os.getcwd()}{os.path.sep}logs{os.path.sep}{str.replace(str(datetime.now()), ':', '-')}.log"

logging.basicConfig(handlers=[logging.FileHandler(filename=LOGS_FILE,
                                                  encoding='utf-8', mode='a+')],
                    format="%(asctime)s %(name)s:%(levelname)s:%(message)s",
                    datefmt="%F %A %T",
                    level=logging.INFO)
logger_progress = logging.getLogger("Progress")
logger_tcp = logging.getLogger("TCP_Packets")

print("------------Cargar configuraciones por defecto------------")
with open("serverconfig.py", 'r') as f:
    print(f.read())
config = input("Seleccione una configuración por defecto: (valor por defecto: Azure) ")
if config not in cfg.ServerConfig:
    print(f"Valor no admitido {config}, se utilizará valor por defecto")
    config = cfg.ServerConfig["Azure"]
else:
    config = cfg.ServerConfig[config]

# CONSTANTS
SERVER_HOST = config['defaultIP']
SERVER_PORT = config['defaultPort']
BUFFER_SIZE = 4096
SEPARATOR = "<SEPARATOR>"
DEFAULT_DIRECTORY = config['defaultDir']

STRING_BUFFER = io.StringIO("")


def read_listdir(dir):
    """
    Función que permite ver la lista de directorios
    dentro de un directorio
    :param dir: El directorio de interés
    :return: La lista de directorios ordenados.
    """
    listdir = os.listdir(dir)
    ind = 1
    archivos = list()
    for d in listdir:
        if os.path.isdir(os.path.join(dir, d)):
            # skip directories
            continue
        archivos.append(f"{ind}-{d}")
        ind += 1
    return archivos


def threaded(client):
    client[0].send(f"{filename}{SEPARATOR}{filesize}".encode())
    client[0].send(file_hash.encode())
    # start sending the file
    progress = tqdm(range(filesize), f"Enviando {filename} a {client[1][0]}", unit="B", unit_scale=True,
                    unit_divisor=1024)
    sended = 0
    with open(filename, "rb") as f:
        for _ in progress:
            # read the bytes from the file
            bytes_read = f.read(BUFFER_SIZE)
            if sended == filesize:
                # file transmitting is done
                progress.n = filesize
                progress.refresh()
                logger_progress.info(str(progress))
                client[0].close()
                progress.close()
                break
            # we use sendall to assure transimission in
            # busy networks
            client[0].sendall(bytes_read)
            # update the progress bar
            sended += len(bytes_read)
            progress.update(len(bytes_read))
            logger_tcp.critical(f"Enviando {filename} a {client[1][0]} Tamaño paquete: {BUFFER_SIZE}, "
                                f"paquete :{round(sended / BUFFER_SIZE)}/{round(filesize / BUFFER_SIZE)}")

def calculate_hash(file):
    file_hash = hashlib.sha256()
    
    with open(file, 'rb') as f:
        fb = f.read(BUFFER_SIZE)
        while len(fb)>0:
            file_hash.update(fb)
            fb = f.read(BUFFER_SIZE)
    return file_hash.hexdigest()
    
print("** Para utilizar valores por defecto, ingresar cadena vacía **")
directoryConfirmed = False
while not directoryConfirmed:
    directory = str(input(f"Ingrese la dirección del directorio (valor por defecto: {DEFAULT_DIRECTORY}): "))
    if directory == "":
        print(f"Utilizando dirección del directorio por defecto: {DEFAULT_DIRECTORY}")
        directory = DEFAULT_DIRECTORY
    while not os.path.isdir(directory):
        print(f"La dirección del directorio {directory} no existe, intente nuevamente")
        directory = str(input(f"Ingrese la dirección del directorio (valor por defecto: {DEFAULT_DIRECTORY}): "))
        if directory == "":
            print(f"Utilizando dirección del directorio por defecto: {DEFAULT_DIRECTORY}")
            directory = DEFAULT_DIRECTORY

    lista = read_listdir(directory)
    if len(lista) == 0:
        print("El directorio no contiene archivos, intente con otro directorio")
        continue;
    print("Mostrando lista de archivos:")
    print("---------------------------------------------------------------------------\n")
    for l in lista:
        print(l)
    print("\n---------------------------------------------------------------------------")
    print("Si quiere cambiar de directorio, utilizar [<]")
    opt = input("Seleccione el archivo que quiere enviar (valor por defecto: 1): ")
    if opt == "<":
        continue;
    fileConfirmed = False
    firstOption = True
    while not fileConfirmed:
        if not firstOption:
            opt = input("Seleccione el archivo que quiere enviar (valor por defecto: 1): ")
        while opt != "" and (not opt.isnumeric() or int(opt) > len(lista)):
            opt = input(f"Seleccione una opción válida [1-{len(lista)}] (valor por defecto: 1): ")
        if opt == "":
            opt = 1
        opt = int(opt)
        filename = os.path.join(directory, lista[opt - 1].partition("-")[len(lista[opt - 1].partition("-")) - 1])
        filesize = os.path.getsize(filename)
        print(f"Archivo seleccionado: {filename}, con tamaño: {filesize / (1024 * 1024)} MB")
        print("Si quiere cambiar de archivo, utilizar [<]")
        usrs = input("Seleccione la cantidad de usuarios a los que quiere enviar el archivo (valor por defecto: 1): ")
        if usrs == "<":
            firstOption = False
            continue;
        while usrs != "" and (not usrs.isnumeric() or int(usrs) < 1):
            usrs = input("Seleccione una opción válida [min. 1] (valor por defecto: 1): ")
        if usrs == "":
            usrs = 1
        usrs = int(usrs)
        fileConfirmed = True

    directoryConfirmed = True

# accept connection if there is any
conns = 0
s = socket.socket()
s.bind((SERVER_HOST, SERVER_PORT))
print(f"[*] Escuchando desde {SERVER_HOST}:{SERVER_PORT}")
s.listen(usrs)
file_hash = calculate_hash(filename)
arrayOfUsers = []

try:
    while conns < usrs:
        c, address = s.accept()
        print(f"[+] El usuario {address} se ha conectado {conns + 1}/{usrs}")

        notification = c.recv(BUFFER_SIZE).decode()
        if notification == "Notificación de inicio":
            conns += 1
        else:
            break
        if usrs == 1:
            threaded([c, address])
        else:
            arrayOfUsers.append([c, address])

    if usrs > 1:
        pool = ThreadPool(usrs)
        pool.map(threaded, arrayOfUsers)
    print("\n---------------------------------------------------------------------------\n")
    print(f"            Se finalizó la transferencia para los {usrs} usuarios           ")
    print("\n---------------------------------------------------------------------------")
    s.close()
    if platform == "linux" or platform == "linux2":
        print(f"El archivo de logs se encuentra en:\n {LOGS_FILE}")
    elif platform == "win32":
        abrirLogs = input("¿Desea abrir el archivo de logs?: (por defecto: N) ")
        if abrirLogs == "Y":
            abrirLogs = True
        else:
            if abrirLogs != "" and abrirLogs != "N":
                print(f"Valor no admitido {abrirLogs}, se utilizará valor por defecto")
            abrirLogs = False
        if abrirLogs:
            try:
                if platform == "win32":
                    os.startfile(LOGS_FILE)
            except:
                print(f"No se pudo abrir el archivo ({LOGS_FILE})")
    exit()



except:
    s.close()
