
# Importing libraries
import socket
import os
import tqdm


SEPARATOR = "<SEPARATOR>"
BUFFER_SIZE = 4096 # send 4096 bytes each time step


# the ip address or hostname of the server, the receiver
host = '52.186.137.191'
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

# send the filename and filesize
#s.send(f"{filename}{SEPARATOR}{filesize}".encode())
received = s.recv(BUFFER_SIZE).decode()
filename, filesize = received.split(SEPARATOR)
filename = os.path.basename(filename)
# convert to integer
filesize = int(filesize)

progress = tqdm.tqdm(range(filesize), f"Receiving {filename}", unit="B", unit_scale=True, unit_divisor=1024)
with open(filename, "wb") as f:
    for _ in progress:
        # read 1024 bytes from the socket (receive)
        bytes_read = s.recv(BUFFER_SIZE)
        if not bytes_read:    
            # nothing is received
            # file transmitting is done
            break
        # write to the file the bytes we just received
        f.write(bytes_read)
        # update the progress bar
        progress.update(len(bytes_read))

# close the socket
s.close()