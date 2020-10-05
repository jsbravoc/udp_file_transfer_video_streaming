import socket
import tqdm
import os
from _thread import *
import threading 

# device's IP address
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 9898
# receive 4096 bytes each time
BUFFER_SIZE = 4096
SEPARATOR = "<SEPARATOR>"
print_lock = threading.Lock() 

def read_listdir(dir):
    """
    Función que permite ver la lista de directorios
    dentro de un directorio
    :param dir: El directorio de interés
    :return: La lista de directorios ordenados.
    """
    listdir = os.listdir(dir)
    ind = 1
    archivs = list()
    for d in listdir:
        archivs.append(f"{ind}-{d}")
        ind += 1
    return archivs

def threaded(c):
    c.send(f"{filename}{SEPARATOR}{filesize}".encode())
    # start sending the file
    progress = tqdm.tqdm(range(filesize), f"Sending {filename}", unit="B", unit_scale=True, unit_divisor=1024)
    with open(filename, "rb") as f:
        for _ in progress:
            # read the bytes from the file
            bytes_read = f.read(BUFFER_SIZE)
            if not bytes_read:
                # file transmitting is done
                break
            # we use sendall to assure transimission in 
            # busy networks
            c.sendall(bytes_read)
            # update the progress bar
            progress.update(len(bytes_read))
            #print_lock.release()
    # start receiving the file from the socket
    # and writing to the file stream
    
    # close the client socket
    c.close() 
    
    
# create the server socket
# TCP socket
s = socket.socket()

# bind the socket to our local address
s.bind((SERVER_HOST, SERVER_PORT))
directory = "archivos"

# enabling our server to accept connections
# 25 here is the number of unaccepted connections that
# the system will allow before refusing new connections
s.listen(25)

lista = read_listdir(directory)

print("---------------------------------------------------------------------------\n\n")
for l in lista:
    print(l)
print("\n\n---------------------------------------------------------------------------")
opt = int(input("Seleccione el archivo que quiere enviar: "))
while opt > len(lista):
    opt = input("Seleccione una opción válida: ")
filename = os.path.join(directory, lista[opt-1].split("-")[1])
filesize = os.path.getsize(filename)
usrs = int(input("Seleccione la cantidad de usuarios a los que quiere enviar el archivo: "))
# accept connection if there is any
conns = 0
cmpltd = usrs
print(f"[*] Listening as {SERVER_HOST}:{SERVER_PORT}")
try:
    while True:
        c, address = s.accept()
        #print_lock.acquire()
        # if below code is executed, that means the sender is connected
        print(f"[+] {address} is connected.")
        
        notification = c.recv(BUFFER_SIZE).decode()
        if notification == "Notificación de inicio":
            conns += 1
        else:
            break
    
        start_new_thread(threaded, (c,))
        # receive the file infos
        # receive using client socket, not server socket
except KeyboardInterrupt:
    s.close()
    
# close the server socket
s.close()