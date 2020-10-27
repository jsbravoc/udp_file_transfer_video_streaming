import copy
import hashlib
import logging
import math
import os
import socket
from _thread import *
from datetime import datetime, time
from multiprocessing.dummy import Pool as ThreadPool
from sys import platform
import hashlib
from threading import Thread
import time
import serverconfig as cfg
from tqdm.notebook import tqdm
from functools import lru_cache
import io
import queue
import cv2 as cv
# Si no existe la carpeta de logs, entonces se crea
if not os.path.exists(f"{os.getcwd()}{os.path.sep}logs{os.path.sep}"):
    os.makedirs(f"{os.getcwd()}{os.path.sep}logs{os.path.sep}")

# region CONSTANTES
LOGS_FILE = f"{os.getcwd()}{os.path.sep}logs{os.path.sep}{str.replace(str(datetime.now()), ':', '-')}.log"
BUFFER_SIZE = 64000
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
logger_udp = logging.getLogger("UDP_Packets")
logger_udp_bytes = logging.getLogger("UDP_Bytes")
logger_threads = logging.getLogger("Threads")

print("------------Cargar configuraciones por defecto------------")
try:
    with open("serverconfig.py", 'r') as f:
        print(f.read())
except Exception as e:
    print(e)
config = input(
    "Seleccione una configuración por defecto: (valor por defecto: Azure) ")
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
SEND_HEADER = config['sendHeader']
if HASHING_METHOD != "sha256":
    print(
        f"Método de hashing {HASHING_METHOD} no soportado actualmente, utilizando sha256")


# endregion

@lru_cache(maxsize=None, typed=True)
def get_cached_file(filename):
    m = io.BytesIO()
    with open(filename, 'rb') as f:
        m.write(f.read())
    return m


def read_listdir(process, dir):
    """
    Función que permite ver la lista de directorios
    dentro de un directorio
    :param dir: El directorio de interés
    :return: La lista de directorios ordenados.
    """
    listdir = os.listdir(dir)
    ind = 1
    archivos = list()
    if int(process) == 2:
        print("\tBuscando archivos únicamente .mp4 o .mkv")
    else:
        print("\tBuscando todos los archivos en el directorio")
    for d in listdir:
        if os.path.isdir(os.path.join(dir, d)):
            # skip directories
            continue
        # Transferencia de archivos == 1, Streaming == 2
        if int(process) == 2:
            if d.endswith(".mp4") or d.endswith(".mkv"):
                archivos.append(f"{ind}-{d}")
                ind += 1
        else:
            archivos.append(f"{ind}-{d}")
            ind += 1
    return archivos


def multiThreaded():
    while True:
        client = threadQueue.get()
        logger_threads.info(f"Thread empezando a atender a {client}")
        cached_file = get_cached_file(filename)
        try:
            if CLONE_FILE:
                file = copy.deepcopy(cached_file)
            else:
                file = cached_file

            logger_udp.info(
                f"Enviando INFO al Cliente: {os.path.basename(filename)}{SEPARATOR}{filesize}{SEPARATOR}{FILE_HASH}")
            if SEND_HEADER:
                UDPSocket.sendto(
                    f"{os.path.basename(filename)}{SEPARATOR}{filesize}{SEPARATOR}{FILE_HASH}".encode(), client)
            sended = 0
            initialTime = datetime.now()
            file.seek(0)
            bytes_read = file.read(BUFFER_SIZE)

            if DISABLE_PROGRESS_BAR:
                while bytes_read:
                    UDPSocket.sendto(bytes_read, client)
                    sended += len(bytes_read)
                    if not IGNORE_PACKET_COUNT:
                        logger_udp.debug(f"Enviando {filename} a {client} Tamaño paquete: {BUFFER_SIZE}, "
                                         f"paquete: {math.ceil(sended / BUFFER_SIZE)}/{round(filesize / BUFFER_SIZE)}")
                    if not IGNORE_BYTES_COUNT:
                        logger_udp_bytes.debug(f"Enviando {filename} a {client} Tamaño paquete: {BUFFER_SIZE}, "
                                               f"bytes enviados: {sended}/{filesize}")
                    bytes_read = file.read(BUFFER_SIZE)
                now = datetime.now()
                logger_progress.info(f"Enviando {filename} a {client}: 100%|██████████| "
                                     f"{round(filesize / (1024 * 1024), 2)}MB/{round(filesize / (1024 * 1024), 2)}MB "
                                     f"[{str(math.floor((now - initialTime).total_seconds() / 60)).zfill(2)}:"
                                     f"{str(math.ceil((now - initialTime).total_seconds()) % 60).zfill(2)}]")

            else:
                progress = tqdm(range(filesize), f"Enviando {filename} a {client}", unit="B", unit_scale=True,
                                unit_divisor=BUFFER_SIZE)

                while bytes_read:
                    for _ in progress:
                        if sended == filesize:
                            progress.n = filesize
                            progress.refresh()
                            logger_progress.info(str(progress))
                            client[0].close()
                            logger_connections.info(
                                f"El usuario {client} se ha desconectado")
                            progress.close()
                            break
                        UDPSocket.sendto(bytes_read, client)
                        sended += len(bytes_read)
                        progress.update(len(bytes_read))
                        if not IGNORE_PACKET_COUNT:
                            logger_udp.debug(f"Enviando {filename} a {client} Tamaño paquete: {BUFFER_SIZE}, "
                                             f"paquete :{round(sended / BUFFER_SIZE)}/{round(filesize / BUFFER_SIZE)}")
                        if not IGNORE_BYTES_COUNT:
                            logger_udp_bytes.debug(
                                f"Enviando {filename} a {client} Tamaño paquete: {BUFFER_SIZE}, "
                                f"bytes enviados :{sended}/{filesize}")
                        bytes_read = file.read(BUFFER_SIZE)

        except Exception as e:
            print(f"[ERROR]: {e}")
            logger_connections.exception(e)
        threadQueue.task_done()
        logger_threads.info(f"Thread finalizó de atender a {client}")


def threaded(client):
    logger_threads.info(f"Thread empezando a atender a {client}")
    cached_file = get_cached_file(filename)
    try:
        if CLONE_FILE:
            file = copy.deepcopy(cached_file)
        else:
            file = cached_file

        logger_udp.info(
            f"Enviando INFO al Cliente: {os.path.basename(filename)}{SEPARATOR}{filesize}{SEPARATOR}{FILE_HASH}")

        if SEND_HEADER:
            UDPSocket.sendto(
                f"{os.path.basename(filename)}{SEPARATOR}{filesize}{SEPARATOR}{FILE_HASH}".encode(), client)
        sended = 0
        initialTime = datetime.now()
        file.seek(0)
        bytes_read = file.read(BUFFER_SIZE)

        if DISABLE_PROGRESS_BAR:
            while bytes_read:
                UDPSocket.sendto(bytes_read, client)
                sended += len(bytes_read)
                if not IGNORE_PACKET_COUNT:
                    logger_udp.debug(f"Enviando {filename} a {client} Tamaño paquete: {BUFFER_SIZE}, "
                                     f"paquete :{round(sended / BUFFER_SIZE)}/{round(filesize / BUFFER_SIZE)}")
                if not IGNORE_BYTES_COUNT:
                    logger_udp_bytes.debug(f"Enviando {filename} a {client} Tamaño paquete: {BUFFER_SIZE}, "
                                           f"bytes enviados :{sended}/{filesize}")
                bytes_read = file.read(BUFFER_SIZE)
            now = datetime.now()
            logger_progress.info(f"Enviando {filename} a {client}: 100%|██████████| "
                                 f"{round(filesize / (1024 * 1024), 2)}MB/{round(filesize / (1024 * 1024), 2)}MB "
                                 f"[{str(math.floor((now - initialTime).total_seconds() / 60)).zfill(2)}:"
                                 f"{str(math.ceil((now - initialTime).total_seconds()) % 60).zfill(2)}]")

        else:
            progress = tqdm(range(filesize), f"Enviando {filename} a {client}", unit="B", unit_scale=True,
                            unit_divisor=BUFFER_SIZE)

            while bytes_read:
                for _ in progress:
                    if sended == filesize:
                        progress.n = filesize
                        progress.refresh()
                        logger_progress.info(str(progress))
                        logger_connections.info(
                            f"El usuario {client} se ha desconectado")
                        progress.close()
                        break
                    UDPSocket.sendto(bytes_read, client)
                    sended += len(bytes_read)
                    progress.update(len(bytes_read))
                    if not IGNORE_PACKET_COUNT:
                        logger_udp.debug(f"Enviando {filename} a {client} Tamaño paquete: {BUFFER_SIZE}, "
                                         f"paquete :{round(sended / BUFFER_SIZE)}/{round(filesize / BUFFER_SIZE)}")
                    if not IGNORE_BYTES_COUNT:
                        logger_udp_bytes.debug(f"Enviando {filename} a {client} Tamaño paquete: {BUFFER_SIZE}, "
                                               f"bytes enviados :{sended}/{filesize}")
                    bytes_read = file.read(BUFFER_SIZE)

    except Exception as e:
        print(f"[ERROR]: {e}")
        logger_connections.exception(e)
    logger_threads.info(f"Thread finalizó de atender a {client}")


# region PARÁMETROS DEL SERVIDOR
opciones = ["Transferencia de archivos UDP",
            "Transmisión de vídeo (streaming)"]
processPrompt = ["Seleccione la cantidad de usuarios a los que quiere enviar el archivo (valor por defecto: 1): ",
                 f"Escriba la dirección del grupo multicast por donde quiere hacer la transmisión (valor por defecto: 224.1.1.1):  "]
prompt = {"Directory": f"Ingrese la dirección del directorio (valor por defecto: {DEFAULT_DIRECTORY}): ",
          "File": "Seleccione el archivo que quiere enviar/transmitir (valor por defecto: 1): "
          }
lista = []
directory = ""
filename = ""
filesize = ""
threadQueue = None
FILE_HASH = ""
UDPSocket = None
print("** Para utilizar valores por defecto, ingresar cadena vacía **")


def selectProcess(nextFunction):
    processConfirmed = False
    responses = {}
    while not processConfirmed:
        strOpcion = "Seleccione qué desea realizar:\n"
        it = 1
        for opcion in opciones:
            strOpcion += f"[{it}] - {opcion}\n"
            it += 1
        process = str(input(strOpcion))
        if not process.isnumeric() or int(process) >= len(opciones) + 1 or int(process) <= 0:
            print(f"Opción no válida {process}")
            continue
        responses["Process"] = process
        print("Si desea cambiar de opción, utilizar [<]")
        promptResponse = str(input(prompt["Directory"]))
        if promptResponse == "<":
            continue
        responses["Directory"] = promptResponse
        return nextFunction(selectProcess, selectFile, responses)


def selectDirectory(previousFunction, nextFunction, responses):
    directoryConfirmed = False
    global directory, lista
    directory = responses["Directory"]
    while not directoryConfirmed:
        print("Si desea cambiar de opción, utilizar [<]")
        if directory == "":
            print(
                f"Utilizando dirección del directorio por defecto: {DEFAULT_DIRECTORY}")
            directory = DEFAULT_DIRECTORY
        elif directory == "<":
            return previousFunction(selectDirectory)
        while not os.path.isdir(directory):
            print(
                f"La dirección del directorio {directory} no existe, intente nuevamente")
            directory = str(input(prompt["Directory"]))
            if directory == "":
                print(
                    f"Utilizando dirección del directorio por defecto: {DEFAULT_DIRECTORY}")
                directory = DEFAULT_DIRECTORY
            elif directory == "<":
                return previousFunction(selectDirectory)
        lista = read_listdir(responses["Process"], directory)
        if len(lista) == 0:
            print(
                f"El directorio no contiene archivos válidos, intente con otro directorio")
            directory = str(input(prompt["Directory"]))
            continue
        print("Mostrando lista de archivos:")
        print(
            "---------------------------------------------------------------------------\n")
        for l in lista:
            print(l)
        print(
            "\n---------------------------------------------------------------------------")
        print("Si quiere cambiar de directorio, utilizar [<]")
        promptResponse = str(input(prompt["File"]))
        if promptResponse == "<":
            directory = str(input(prompt["Directory"]))
            continue
        responses["File"] = promptResponse
        return nextFunction(selectDirectory, responses)


def selectFile(previousFunction, responses):
    opt = responses["File"]
    fileConfirmed = False
    global filename, filesize
    while not fileConfirmed:
        if opt == "<":
            return previousFunction(selectProcess, selectFile, responses)
        while opt != "" and (not opt.isnumeric() or int(opt) > len(lista)):
            opt = input(
                f"Seleccione una opción válida [1-{len(lista)}] (valor por defecto: 1): ")
        if opt == "":
            opt = 1
        opt = int(opt)
        filename = os.path.join(
            directory, lista[opt - 1].partition("-")[len(lista[opt - 1].partition("-")) - 1])
        filesize = os.path.getsize(filename)
        print(
            f"Archivo seleccionado: {filename}, con tamaño: {filesize / (1024 * 1024)} MB")
        print("Si quiere cambiar de archivo, utilizar [<]")
        # Imprime siguiente paso según proceso
        nextStep = input(str(processPrompt[int(responses["Process"]) - 1]))
        if nextStep == "<":
            opt = str(input(prompt["File"]))
            continue
        return sendFile(nextStep) if int(responses["Process"]) == 1 else prepareStream(nextStep, responses)


# endregion

def sendFile(usrs):
    global FILE_HASH, UDPSocket, threadQueue
    while usrs != "" and (not usrs.isnumeric() or int(usrs) < 1):
        usrs = input(
            "Seleccione una opción válida [min. 1] (valor por defecto: 1): ")
    if usrs == "":
        usrs = 1
    usrs = int(usrs)
    logger_progress.info(f"Se enviará el siguiente archivo: {os.path.basename(filename)},"
                         f" con tamaño: {filesize / (1024 * 1024)} MB")

    # region MANIPULACIÓN DE ARCHIVO
    hasher = hashlib.sha256()
    with open(filename, 'rb') as afile:
        buf = afile.read(BLOCKSIZE)
        while len(buf) > 0:
            hasher.update(buf)
            buf = afile.read(BLOCKSIZE)
    FILE_HASH = hasher.hexdigest()

    conns = 0
    logger_connections.info(f"Escuchando desde {SERVER_HOST}:{SERVER_PORT}")
    print(f"[*] Escuchando desde {SERVER_HOST}:{SERVER_PORT}\n")
    # UDP Socket
    UDPSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    UDPSocket.bind((SERVER_HOST, SERVER_PORT))
    logger_connections.info(f"Se espera la conexión de {'un' if usrs == 1 else usrs} "
                            f"{'usuario' if usrs == 1 else 'usuarios'} para empezar la transmisión")

    arrayOfUsers = []

    try:
        # region CONEXIÓN CLIENTES
        while usrs > conns:

            notification, address = UDPSocket.recvfrom(BUFFER_SIZE)

            logger_connections.info(
                f"El usuario {address} se ha conectado {conns + 1}/{usrs}")
            print(
                f"[+] El usuario {address} se ha conectado {conns + 1}/{usrs}")

            if not EXCLUDE_MESSAGE_COMPARISON:
                if notification.decode() == "Connection approval":
                    conns += 1
                else:
                    break

            else:
                conns += 1
            if usrs == 1:
                threaded(address)
            else:
                arrayOfUsers.append(address)

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
        print(
            "\n---------------------------------------------------------------------------")
        UDPSocket.close()
        if platform == "linux" or platform == "linux2":
            print(f"El archivo de logs se encuentra en:\n {LOGS_FILE}")
        elif platform == "win32":
            abrirLogs = input(
                "¿Desea abrir el archivo de logs?: (por defecto: N) ")
            if abrirLogs == "Y":
                abrirLogs = True
            else:
                if abrirLogs != "" and abrirLogs != "N":
                    print(
                        f"Valor no admitido {abrirLogs}, se utilizará valor por defecto")
                abrirLogs = False
            if abrirLogs:
                try:
                    if platform == "win32":
                        os.startfile(LOGS_FILE)
                except Exception as e:
                    print(
                        f"[ERROR] No se pudo abrir el archivo ({LOGS_FILE}), {e}")
        exit()
        # endregion

    except Exception as e:
        logger_progress.exception(f"[ERROR]: {str(e)}")
        UDPSocket.close()


filesList = []
streamingThreads = []


def prepareStream(mcast_group, responses):
    MCAST_GRP = '224.1.1.1'
    if mcast_group == "":
        mcast_group = MCAST_GRP

    global UDPSocket, filesList
    if UDPSocket is None:
        thread = Thread(target=streamMenu)
        streamingThreads.append(thread)
        thread.start()
    
    mcast_port = input(str("Escriba el puerto que utilizará la transmisión de vídeo: "))
    while not mcast_port.isnumeric():
        print("Opción inválida")
        mcast_port = input(str("Escriba el puerto que utilizará la transmisión de vídeo: "))

    if [mcast_group, mcast_port, os.path.basename(filename)] not in filesList:
        filesList.append([mcast_group, mcast_port, os.path.basename(filename)])

    thread = Thread(target=streamFiles, args=(mcast_group, mcast_port, filename, filesize))
    streamingThreads.append(thread)
    thread.start()
    print("\t Si desea, puede iniciar la transmisión de otro archivo simultáneamente")
    print("\tDevolviendo al menú de directorios\n")
    responses["Directory"] = input(str(prompt["Directory"]))
    return selectDirectory(selectProcess, selectFile, responses)


def streamMenu():
    global UDPSocket, filesList
    if UDPSocket is None:
        logger_connections.info(f"Preparando transmisión de vídeo")
        print(f"\n[*] Empezando transmisión de menú desde {SERVER_HOST}:{SERVER_PORT}")
        UDPSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        UDPSocket.bind((SERVER_HOST, SERVER_PORT))

        # Main thread
        conns = 0
        while True:
            notification, address = UDPSocket.recvfrom(BUFFER_SIZE)
            print(f"[+] El usuario {address} se ha conectado.")
            if not EXCLUDE_MESSAGE_COMPARISON:
                if notification.decode() == "Connection approval":
                    conns += 1
                else:
                    break

            else:
                conns += 1

            strMenu = ""
            if len(filesList) > 0:
                for file in filesList:
                    strMenu += file[0]+SEPARATOR+file[1]+SEPARATOR+file[2]+SEPARATOR
                UDPSocket.sendto(strMenu[:-len(SEPARATOR)].encode(), address)


def streamFiles(group, port, filename, filesize):
    global BUFFER_SIZE
    port = int(port)
    # https://stackoverflow.com/questions/603852/how-do-you-udp-multicast-in-python
    logger_udp.info(
        f"Empezando transmisión de vídeo de {os.path.basename(filename)} en {group} - {port}")
    MCAST_GRP = '224.1.1.1'
    MCAST_GROUP = group
    MCAST_PORT = port

    MULTICAST_TTL = 32

    streamingSocket = socket.socket(
        socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    streamingSocket.setsockopt(
        socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, MULTICAST_TTL)
    sent = 0
    cap = cv.VideoCapture(filename)
    width = 640
    height = 360
    cap.set(3, width)
    cap.set(4, height)
    BUFFER_SIZE = 57600
    try:
        totalSent = 0
        while True:
            ret, frame = cap.read()
            if ret:
                data = frame.tobytes()
                for i in range(0, len(data), BUFFER_SIZE):
                    totalSent += BUFFER_SIZE
                    streamingSocket.sendto(
                        data[i:i+BUFFER_SIZE], (MCAST_GROUP, MCAST_PORT))
                    logger_udp_bytes.debug(
                        f"Se han transmitido {totalSent}/{filesize} bytes")
            else:
                break
    except Exception as e:
        logger_connections.exception(e)

    print(
        f"La transmisión de {os.path.basename(filename)} en el puerto {port} ha finalizado {sent}")


try:
    selectProcess(selectDirectory)
except KeyboardInterrupt as a:
    print("Deteniendo servicios a petición del usuario (Ctrl + C)...")
    exit(-1)
