import copy
import hashlib
import logging
import math
import os
import socket
from _thread import *
from datetime import datetime
from multiprocessing.dummy import Pool as ThreadPool
from sys import platform
import hashlib
from threading import Thread

import serverconfig as cfg
from tqdm.notebook import tqdm
from functools import lru_cache
import io
import queue

# Si no existe la carpeta de logs, entonces se crea
if not os.path.exists(f"{os.getcwd()}/logs/"):
    os.makedirs(f"{os.getcwd()}/logs/")

# region CONSTANTES
LOGS_FILE = f"{os.getcwd()}{os.path.sep}logs{os.path.sep}{str.replace(str(datetime.now()), ':', '-')}.log"
BUFFER_SIZE = 4096
SEPARATOR = "<SEPARATOR>"
BLOCKSIZE = 65536
# endregion

# region CARGA DE CONFIGURACIÓN
logging.basicConfig(handlers=[logging.FileHandler(filename=LOGS_FILE,
                                                  encoding='utf-8', mode='a+')],
                    format="%(asctime)s {%(name)s} [%(levelname)s] %(message)s",
                    datefmt="%F %T",
                    level=logging.DEBUG)
logger_connections = logging.getLogger("Connection")
logger_progress = logging.getLogger("Progress")
logger_tcp = logging.getLogger("TCP_Packets")
logger_tcp_bytes = logging.getLogger("TCP_Bytes")
logger_threads = logging.getLogger("Threads")

print("------------Cargar configuraciones por defecto------------")
try:
    with open("serverconfig.py", 'r') as f:
        print(f.read())
except Exception as e:
    print(e)
config = input("Seleccione una configuración por defecto: (valor por defecto: Azure) ")
if config not in cfg.ServerConfig:
    print(f"Valor no admitido {config}, se utilizará valor por defecto")
    config = cfg.ServerConfig["Azure"]
else:
    config = cfg.ServerConfig[config]

SERVER_HOST = config['defaultIP']
SERVER_PORT = config['defaultPort']
DEFAULT_DIRECTORY = config['defaultDir']
HASHING_METHOD = config['hashingMethod']
IGNORE_PACKET_COUNT = config['ignorePacketCount']
IGNORE_BYTES_COUNT = config['ignoreBytesCount']
IGNORE_CLIENT_LIMIT = config['ignoreClientLimit']
CLONE_FILE = config['cloneFile']
DISABLE_PROGRESS_BAR = config['disableProgressBar']
EXCLUDE_MESSAGE_COMPARISON = config['excludeMessageComparison']
if HASHING_METHOD != "sha256":
    print(f"Método de hashing {HASHING_METHOD} no soportado actualmente, utilizando sha256")


# endregion


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

def multiThreaded():
    while True:
        client = threadQueue.get()
        logger_threads.info(f"Thread empezando a atender a {client[1]}")
        cached_file = get_cached_file(filename)
        try:
            if CLONE_FILE:
                file = copy.deepcopy(cached_file)
            else:
                file = cached_file

            logger_tcp.info(
                f"Enviando INFO al Cliente: {os.path.basename(filename)}{SEPARATOR}{filesize}{SEPARATOR}{FILE_HASH}")
            client[0].send(f"{os.path.basename(filename)}{SEPARATOR}{filesize}{SEPARATOR}{FILE_HASH}".encode())
            sended = 0
            initialTime = datetime.now()
            file.seek(0)
            bytes_read = file.read(BUFFER_SIZE)

            if DISABLE_PROGRESS_BAR:
                while bytes_read:
                    client[0].sendall(bytes_read)
                    sended += len(bytes_read)
                    if not IGNORE_PACKET_COUNT:
                        logger_tcp.debug(f"Enviando {filename} a {client[1][0]} Tamaño paquete: {BUFFER_SIZE}, "
                                         f"paquete: {round(sended / BUFFER_SIZE)}/{round(filesize / BUFFER_SIZE)}")
                    if not IGNORE_BYTES_COUNT:
                        logger_tcp_bytes.debug(f"Enviando {filename} a {client[1][0]} Tamaño paquete: {BUFFER_SIZE}, "
                                               f"bytes enviados: {sended}/{filesize}")
                    bytes_read = file.read(BUFFER_SIZE)
                now = datetime.now()
                client[0].close()
                logger_progress.info(f"Enviando {filename} a {client[1][0]}: 100%|██████████| "
                                     f"{round(filesize / (1024 * 1024), 2)}MB/{round(filesize / (1024 * 1024), 2)}MB "
                                     f"[{str(math.floor((now - initialTime).total_seconds() / 60)).zfill(2)}:"
                                     f"{str(math.ceil((now - initialTime).total_seconds()) % 60).zfill(2)}]")

            else:
                progress = tqdm(range(filesize), f"Enviando {filename} a {client[1][0]}", unit="B", unit_scale=True,
                                unit_divisor=BUFFER_SIZE)

                while bytes_read:
                    for _ in progress:
                        if sended == filesize:
                            progress.n = filesize
                            progress.refresh()
                            logger_progress.info(str(progress))
                            client[0].close()
                            logger_connections.info(f"El usuario {address} se ha desconectado")
                            progress.close()
                            break
                        client[0].sendall(bytes_read)
                        sended += len(bytes_read)
                        progress.update(len(bytes_read))
                        if not IGNORE_PACKET_COUNT:
                            logger_tcp.debug(f"Enviando {filename} a {client[1][0]} Tamaño paquete: {BUFFER_SIZE}, "
                                             f"paquete :{round(sended / BUFFER_SIZE)}/{round(filesize / BUFFER_SIZE)}")
                        if not IGNORE_BYTES_COUNT:
                            logger_tcp_bytes.debug(f"Enviando {filename} a {client[1][0]} Tamaño paquete: {BUFFER_SIZE}, "
                                                   f"bytes enviados :{sended}/{filesize}")
                        bytes_read = file.read(BUFFER_SIZE)

        except Exception as e:
            print(f"[ERROR]: {e}")
            logger_connections.exception(e)
            client[0].close()
        threadQueue.task_done()
        logger_threads.info(f"Thread finalizó de atender a {client[1]}")


def threaded(client):
    logger_threads.info(f"Thread empezando a atender a {client[1]}")
    cached_file = get_cached_file(filename)
    try:
        if CLONE_FILE:
            file = copy.deepcopy(cached_file)
        else:
            file = cached_file

        logger_tcp.info(
            f"Enviando INFO al Cliente: {os.path.basename(filename)}{SEPARATOR}{filesize}{SEPARATOR}{FILE_HASH}")
        client[0].send(f"{os.path.basename(filename)}{SEPARATOR}{filesize}{SEPARATOR}{FILE_HASH}".encode())
        sended = 0
        initialTime = datetime.now()
        file.seek(0)
        bytes_read = file.read(BUFFER_SIZE)

        if DISABLE_PROGRESS_BAR:
            while bytes_read:
                client[0].sendall(bytes_read)
                sended += len(bytes_read)
                if not IGNORE_PACKET_COUNT:
                    logger_tcp.debug(f"Enviando {filename} a {client[1][0]} Tamaño paquete: {BUFFER_SIZE}, "
                                     f"paquete :{round(sended / BUFFER_SIZE)}/{round(filesize / BUFFER_SIZE)}")
                if not IGNORE_BYTES_COUNT:
                    logger_tcp_bytes.debug(f"Enviando {filename} a {client[1][0]} Tamaño paquete: {BUFFER_SIZE}, "
                                           f"bytes enviados :{sended}/{filesize}")
                bytes_read = file.read(BUFFER_SIZE)
            now = datetime.now()
            client[0].close()
            logger_progress.info(f"Enviando {filename} a {client[1][0]}: 100%|██████████| "
                                 f"{round(filesize / (1024 * 1024), 2)}MB/{round(filesize / (1024 * 1024), 2)}MB "
                                 f"[{str(math.floor((now - initialTime).total_seconds() / 60)).zfill(2)}:"
                                 f"{str(math.ceil((now - initialTime).total_seconds()) % 60).zfill(2)}]")

        else:
            progress = tqdm(range(filesize), f"Enviando {filename} a {client[1][0]}", unit="B", unit_scale=True,
                            unit_divisor=BUFFER_SIZE)

            while bytes_read:
                for _ in progress:
                    if sended == filesize:
                        progress.n = filesize
                        progress.refresh()
                        logger_progress.info(str(progress))
                        client[0].close()
                        logger_connections.info(f"El usuario {address} se ha desconectado")
                        progress.close()
                        break
                    client[0].sendall(bytes_read)
                    sended += len(bytes_read)
                    progress.update(len(bytes_read))
                    if not IGNORE_PACKET_COUNT:
                        logger_tcp.debug(f"Enviando {filename} a {client[1][0]} Tamaño paquete: {BUFFER_SIZE}, "
                                         f"paquete :{round(sended / BUFFER_SIZE)}/{round(filesize / BUFFER_SIZE)}")
                    if not IGNORE_BYTES_COUNT:
                        logger_tcp_bytes.debug(f"Enviando {filename} a {client[1][0]} Tamaño paquete: {BUFFER_SIZE}, "
                                               f"bytes enviados :{sended}/{filesize}")
                    bytes_read = file.read(BUFFER_SIZE)

    except Exception as e:
        print(f"[ERROR]: {e}")
        logger_connections.exception(e)
        client[0].close()
    logger_threads.info(f"Thread finalizó de atender a {client[1]}")

# region PARÁMETROS DEL SERVIDOR
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
        continue
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
            continue
        while usrs != "" and (not usrs.isnumeric() or int(usrs) < 1):
            usrs = input("Seleccione una opción válida [min. 1] (valor por defecto: 1): ")
        if usrs == "":
            usrs = 1
        usrs = int(usrs)
        fileConfirmed = True
    directoryConfirmed = True
    logger_progress.info(f"Se enviará el siguiente archivo: {os.path.basename(filename)},"
                         f" con tamaño: {filesize / (1024 * 1024)} MB")

# endregion

# region MANIPULACIÓN DE ARCHIVO
hasher = hashlib.sha256()
with open(filename, 'rb') as afile:
    buf = afile.read(BLOCKSIZE)
    while len(buf) > 0:
        hasher.update(buf)
        buf = afile.read(BLOCKSIZE)
FILE_HASH = hasher.hexdigest()


@lru_cache(maxsize=None, typed=True)
def get_cached_file(filename):
    m = io.BytesIO()
    with open(filename, 'rb') as f:
        m.write(f.read())
    return m


# endregion

conns = 0
logger_connections.info(f"Escuchando desde {SERVER_HOST}:{SERVER_PORT}")
s = socket.socket()
s.bind((SERVER_HOST, SERVER_PORT))
print(f"[*] Escuchando desde {SERVER_HOST}:{SERVER_PORT}")
logger_connections.info(f"Se espera la conexión de {'un' if usrs == 1 else usrs} "
                        f"{'usuario' if usrs == 1 else 'usuarios'} para empezar la transmisión")
if not IGNORE_CLIENT_LIMIT:
    logger_connections.info(f"Máximo número de clientes aceptados: {usrs}")
    s.listen(usrs)
else:
    logger_connections.info(f"Máximo número de clientes aceptados {128}")
    s.listen(128)

arrayOfUsers = []

try:
    # region CONEXIÓN CLIENTES
    while conns < usrs:
        c, address = s.accept()
        logger_connections.info(f"El usuario {address} se ha conectado {conns + 1}/{usrs}")
        print(f"[+] El usuario {address} se ha conectado {conns + 1}/{usrs}")
        notification = c.recv(BUFFER_SIZE)
        if not EXCLUDE_MESSAGE_COMPARISON:
            if notification.decode() == "Notificación de inicio":
                conns += 1
            else:
                break
        else:
            conns += 1
        if usrs == 1:
            threaded([c, address])
        else:
            arrayOfUsers.append([c, address])

    if usrs > 1:
        if usrs > 25:
            threadQueue = queue.Queue()
            for j in range(len(arrayOfUsers)):
                threadQueue.put(arrayOfUsers[j])

            for i in range(25):
                t = Thread(target=multiThreaded, daemon=True)
                t.start()

            threadQueue.join()
        else:
            pool = ThreadPool(usrs)
            pool.map(threaded, arrayOfUsers)
    # endregion
    # region POST EJECUCIÓN
    print("\n---------------------------------------------------------------------------\n")
    print(
        f"        Se finalizó la transferencia para {'el' if usrs == 1 else 'los'} {usrs} "
        f"{'usuario' if usrs == 1 else 'usuarios'}           ")
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
            except Exception as e:
                print(f"[ERROR] No se pudo abrir el archivo ({LOGS_FILE}), {e}")
    exit()
    # endregion


except Exception as e:
    print(e)
    s.close()
