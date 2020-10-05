import socket
from tqdm.auto import tqdm
import os
from _thread import *
from multiprocessing.dummy import Pool as ThreadPool
from datetime import datetime
import io
import shutil
import logging
import os

if not os.path.exists(f"{os.getcwd()}/logs/"):
    os.makedirs(f"{os.getcwd()}/logs/")

if not os.path.exists(f"{os.getcwd()}/logs/tqdm"):
    os.makedirs(f"{os.getcwd()}/logs/tqdm")

logging.basicConfig(filename=f'{os.getcwd()}/logs/{str.replace(str(datetime.now()),":","-")}.log',
                    format='%(levelname)s %(asctime)s :: %(message)s',
                    level=logging.DEBUG)

# CONSTANTS
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 9898
BUFFER_SIZE = 4096
SEPARATOR = "<SEPARATOR>"
DEFAULT_DIRECTORY = "D:\\Downloads"

LOGS_FILE = f"{os.getcwd()}\\logs\\tqdm\\{str.replace(str(datetime.now()),':','-')}.txt"
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
    progress = tqdm(range(filesize), f"Sending {filename} to {client[1][0]}", unit="B", unit_scale=True,
                    unit_divisor=BUFFER_SIZE, leave=False, file=STRING_BUFFER)
    with open(filename, "rb") as f:
        for _ in progress:
            # read the bytes from the file
            bytes_read = f.read(BUFFER_SIZE)
            if not bytes_read:
                # file transmitting is done
                break
            # we use sendall to assure transimission in
            # busy networks
            client[0].sendall(bytes_read)
            # update the progress bar
            progress.update(len(bytes_read))
    # start receiving the file from the socket
    # and writing to the file stream

    # close the client socket
    c.close()


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
opt = int(input("Seleccione el archivo que quiere enviar: "))
while opt > len(lista):
    opt = input("Seleccione una opción válida: ")
filename = os.path.join(directory, lista[opt - 1].partition("-")[len(lista[opt - 1].partition("-")) - 1])
filesize = os.path.getsize(filename)
usrs = int(input("Seleccione la cantidad de usuarios a los que quiere enviar el archivo: "))
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
    print("\n---------------------------------------------------------------------------\n")
    print(f"                            Abriendo logs           ")
    print("\n---------------------------------------------------------------------------")
    with open (LOGS_FILE, 'a') as fd:
        STRING_BUFFER.seek (0)
        shutil.copyfileobj (STRING_BUFFER, fd)
    os.startfile(LOGS_FILE)
    exit()


except KeyboardInterrupt:
    s.close()

# close the server socket
s.close()
