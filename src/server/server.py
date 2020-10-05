import socket
import tqdm
import os

# device's IP address
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 9898
# receive 4096 bytes each time
BUFFER_SIZE = 4096
SEPARATOR = "<SEPARATOR>"


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


# create the server socket
# TCP socket
s = socket.socket()

# bind the socket to our local address
s.bind((SERVER_HOST, SERVER_PORT))
directory = "archivos"
filename = "Media1.mp4"
filename = os.path.join(directory, filename)
filesize = os.path.getsize(filename)
# enabling our server to accept connections
# 25 here is the number of unaccepted connections that
# the system will allow before refusing new connections
s.listen(25)
print(f"[*] Listening as {SERVER_HOST}:{SERVER_PORT}")

lista = read_listdir(directory)

print("---------------------------------------------------------------------------\n\n")
for l in lista:
    print(l)
print("\n\n---------------------------------------------------------------------------")
opt = input("Seleccione el archivo que quiere enviar: ")
while opt > len(lista):
    opt = input("Seleccione una opción válida: ")
filename = os.path.join(directory, lista[opt-1].split("-")[1])

usrs = input("Seleccione la cantidad de usuarios a los que quiere enviar el archivo: ")
# accept connection if there is any
conns = 0
while True:
    client_socket, address = s.accept() 
    # if below code is executed, that means the sender is connected
    print(f"[+] {address} is connected.")
    
    notification = client_socket.recv(BUFFER_SIZE).decode()
    # receive the file infos
    # receive using client socket, not server socket
    client_socket.send(f"{filename}{SEPARATOR}{filesize}".encode())
    
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
            client_socket.sendall(bytes_read)
            # update the progress bar
            progress.update(len(bytes_read))
    # start receiving the file from the socket
    # and writing to the file stream
    
    # close the client socket
    client_socket.close()
# close the server socket
s.close()