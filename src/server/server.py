import socket
import tqdm
import os
from _thread import *
from multiprocessing.dummy import Pool as ThreadPool
from datetime import datetime
import io
import shutil
import logging
import os
import sys
import copy
from sys import platform

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

# CONSTANTS
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 9898
BUFFER_SIZE = 4096
SEPARATOR = "<SEPARATOR>"
DEFAULT_DIRECTORY = "D:\\Downloads"

STRING_BUFFER = io.StringIO("some initial text data")


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
        if os.path.isdir(os.path.join(directory, d)):
            # skip directories
            continue
        archivos.append(f"{ind}-{d}")
        ind += 1
    return archivos


def threaded(client):
    client[0].send(f"{filename}{SEPARATOR}{filesize}".encode())
    # start sending the file
    progress = tqdm.tqdm(range(filesize), f"Enviando {filename} a {client[1][0]}", unit="B", unit_scale=True,
                unit_divisor=BUFFER_SIZE)
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
                    f"paquete :{round(sended/BUFFER_SIZE)}/{round(filesize/BUFFER_SIZE)}" )

print("** Para utilizar valores por defecto, ingresar cadena vacía **")
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
print("Mostrando lista de archivos:")
print("---------------------------------------------------------------------------\n")
for l in lista:
    print(l)
print("\n---------------------------------------------------------------------------")
opt = input("Seleccione el archivo que quiere enviar: ")
while not opt.isnumeric() or int(opt) > len(lista):
    opt = input("Seleccione una opción válida: ")
opt = int(opt)
filename = os.path.join(directory, lista[opt - 1].partition("-")[len(lista[opt - 1].partition("-")) - 1])
filesize = os.path.getsize(filename)
usrs = input("Seleccione la cantidad de usuarios a los que quiere enviar el archivo: ")
while not usrs.isnumeric() or int(usrs) < 1:
    usrs = input("Seleccione una opción válida: ")
usrs = int(usrs)
# accept connection if there is any
conns = 0
cmpltd = usrs
s = socket.socket()
s.bind((SERVER_HOST, SERVER_PORT))
print(f"[*] Listening as {SERVER_HOST}:{SERVER_PORT}")
s.listen(usrs)



arrayOfUsers = []

try:
    while conns < usrs:
        c, address = s.accept()
        print(f"[+] {address} is connected.")

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
        pool.close()
        pool.join()
    print("\n---------------------------------------------------------------------------\n")
    print(f"            Se finalizó la transferencia para los {usrs} usuarios           ")
    print("\n---------------------------------------------------------------------------")
    s.close()
    if platform == "linux" or platform == "linux2":
        print(f"El archivo de logs se encuentra en:\n {LOGS_FILE}")
    elif platform == "win32":
        os.startfile(LOGS_FILE)
    exit()



except KeyboardInterrupt:
    s.close()

# close the server socket
s.close()
