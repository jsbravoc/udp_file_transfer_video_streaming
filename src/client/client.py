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
import numpy as np
import cv2 as cv
import struct

# Si no existe la carpeta de logs, entonces se crea
if not os.path.exists(f"{os.getcwd()}{os.path.sep}logs{os.path.sep}"):
    os.makedirs(f"{os.getcwd()}{os.path.sep}logs{os.path.sep}")

# region CONSTANTES
LOGS_FILE = f"{os.getcwd()}{os.path.sep}logs{os.path.sep}{str.replace(str(datetime.now()), ':', '-')}.log"
SEPARATOR = "<SEPARATOR>"
BUFFER_SIZE = 64000
BLOCKSIZE = 65536
# endregion

# region CARGA DE CONFIGURACIÓN
print("------------Cargar configuraciones por defecto------------")
try:
    with open("clientconfig.py", 'r') as f:
        print(f.read())
except Exception as e:
    print(e)
config = input("Seleccione una configuración por defecto: (valor por defecto: Azure) ")
if config not in cfg.ClientConfig:
    print(f"Valor no admitido {config}, se utilizará valor por defecto")
    config = cfg.ClientConfig["Azure"]
else:
    config = cfg.ClientConfig[config]
IGNORE_PACKET_COUNT = config["ignorePacketCount"]
IGNORE_BYTES_COUNT = config["ignoreBytesCount"]
DEFAULT_IP = config["defaultIP"]
DEFAULT_DIR = config["defaultDir"]
# endregion

# region LOGGING
logging.basicConfig(handlers=[logging.FileHandler(filename=LOGS_FILE,
                                                  encoding='utf-8', mode='a+')],
                    format="%(asctime)s {%(name)s} [%(levelname)s] %(message)s",
                    datefmt="%F %T",
                    level=logging.DEBUG)
logger_progress = logging.getLogger("Progress")
logger_udp = logging.getLogger("UDP_Packets")
logger_udp_bytes = logging.getLogger("UDP_Bytes")
# endregion


# region PARÁMETROS DEL CLIENTE
print("** Para utilizar valores por defecto, ingresar cadena vacía **")
host = input(f"Ingrese la IP del servidor: (por defecto '{DEFAULT_IP}') ")
if host == "":
    host = DEFAULT_IP
opciones = ["Recepción de archivo UDP", "Sintonización de vídeo (streaming)"]
opcionValida = False
process = ""
while not opcionValida:
    strOpcion = "Seleccione qué desea realizar:\n"
    it = 1
    for opcion in opciones:
        strOpcion += f"[{it}] - {opcion}\n"
        it += 1
    process = str(input(strOpcion))
    if not process.isnumeric() or int(process) >= len(opciones) + 1 or int(process) <= 0:
        print(f"Opción no válida {process}")
        continue
    else:
        opcionValida = True

if int(process) == 1:
    port = config['defaultPort']
    path = input(f"Ingrese la ruta donde se quiere guardar el archivo: (por defecto en {DEFAULT_DIR}) ")
    if path == "" and DEFAULT_DIR != "/src/client/":
        path = DEFAULT_DIR
    elif path == "" and DEFAULT_DIR == "/src/client/":
        path = ""
    if not path.endswith(os.path.sep):
        path += os.path.sep
    if not os.path.exists(path):
        os.makedirs(path)
    # endregion
    print(f"[+] Abriendo socket, enviando solicitud a {host}:{port}")
    # region CONEXIÓN CON EL SERVIDOR
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.sendto("Connection approval".encode(), (host, port))
    except Exception as e:
        print(f"[ERROR]: {e}")
        exit(-1)
    # endregion
    print("[+] Solicitud enviada.")

    # region RECEPCIÓN ARCHIVO
    received, addr = s.recvfrom(BUFFER_SIZE)
    received = received.decode()
    filename, filesize, hashServer = received.split(SEPARATOR)
    if path != "":
        filename = os.path.join(path, filename)
    filesize = int(filesize)
    received = 0
    progress = tqdm.tqdm(range(filesize), f"Recibiendo {filename} de {host}", unit="B", unit_scale=True,
                         unit_divisor=BUFFER_SIZE)
    try:
        s.settimeout(5)
        with open(filename, "wb") as f:
            for _ in progress:
                bytes_read, addrServer = s.recvfrom(BUFFER_SIZE)
                received += len(bytes_read)
                progress.update(len(bytes_read))
                if not IGNORE_PACKET_COUNT:
                    logger_udp.critical(f"Recibiendo {filename} de {host} Tamaño paquete: {BUFFER_SIZE}, "
                                        f"paquete :{round(received / BUFFER_SIZE)}/{round(filesize / BUFFER_SIZE)}")
                if not IGNORE_BYTES_COUNT:
                    logger_udp_bytes.debug(f"Recibiendo {filename} de {host} Tamaño paquete: {BUFFER_SIZE}, "
                                       f"bytes enviados: {received}/{filesize}")
                if received == filesize or not bytes_read:
                    # progress.n = filesize
                    # progress.refresh()
                    logger_progress.info(str(progress))
                    s.close()
                    progress.close()
                    break
                f.write(bytes_read)



    except Exception as e:
        print(e)
        logger_progress.exception(f"[ERROR]: {str(e)}")
        s.close()
    # endregion

    # region VALIDACIÓN ARCHIVO
    print("\n---------------------------------------------------------------------------\n")
    print(f"   Se finalizó la transferencia del archivo {os.path.basename(filename)}            ")
    logger_progress.debug(f"Se finalizó la transferencia del archivo {os.path.basename(filename)}")
    print("\n---------------------------------------------------------------------------")

    print("\n---------------------------------------------------------------------------\n")
    print(f"                 Verificando hash SHA-256 del servidor             ")
    print("\n---------------------------------------------------------------------------")
    print(f"\n Hash del servidor: {hashServer} \n")
    logger_progress.debug(f"Hash del servidor: {hashServer}")
    hasher = hashlib.sha256()
    with open(filename, 'rb') as afile:
        buf = afile.read(BLOCKSIZE)
        while len(buf) > 0:
            hasher.update(buf)
            buf = afile.read(BLOCKSIZE)
    hashClient = hasher.hexdigest()

    logger_progress.debug(f"Hash del cliente: {hashClient}")
    print(f"\n Hash del cliente: {hashClient} \n")

    if hashServer == hashClient:
        logger_progress.debug(f"Hash SHA-256 verificado correctamente")
        print("Hash SHA-256 verificado correctamente")
    else:
        logger_progress.critical(f"[ERROR] El hash del archivo no coincide con el del servidor")
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
else:
    try:
        while True:
            BUFFER_SIZE = 57600
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.sendto("Connection approval".encode(), (host, int(config['defaultPort'])))
            #Recepcion menu
            received, addr = s.recvfrom(BUFFER_SIZE)
            received = received.decode()
            menu = received.split(SEPARATOR)
            strMenu = "Transmisiones disponibles:\n"
            puertosPosibles = []
            direccionesPosibles = []
            recorrerMenu: True
            i = 0
            while i < len(menu):
                direccionesPosibles.append(menu[i])
                puertosPosibles.append(menu[i+1])
                strMenu += f"[{menu[i]} - {menu[i+1]}] - {menu[i+2]}\n"
                i=i+3
            print(strMenu)
            transmisionCorrecta = False
            while not transmisionCorrecta:
                transmision = input(str("Elija la transmisión a sintonizar: "))
                try:
                    dirgroup, port = transmision.split("-")
                    dirgroup = dirgroup.strip()
                    port = port.strip()
                except Exception as e:
                    continue
                transmisionCorrecta = dirgroup in direccionesPosibles and port.isnumeric() and port in puertosPosibles
            width = 640
            height = 360
            num_of_chunks = width * height * 3 / BUFFER_SIZE
            MCAST_GRP = dirgroup
            MCAST_PORT = int(port)
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            except AttributeError:
                pass
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 32)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)


            sock.setsockopt(socket.SOL_IP, socket.IP_ADD_MEMBERSHIP,
                            socket.inet_aton(MCAST_GRP) +
                            socket.inet_aton((socket.gethostbyname(socket.gethostname()))))
            
            #MCAST_GRP
            sock.bind(('0.0.0.0', MCAST_PORT))
            struct.pack("4sl", socket.inet_aton(MCAST_GRP), socket.INADDR_ANY)
            print("Presione [Q] para detener la transmisión")
            while True:
                chunks = []
                start = False
                while len(chunks) < num_of_chunks:
                    chunk, _ = sock.recvfrom(BUFFER_SIZE)
                    chunks.append(chunk)

                byte_frame = b''.join(chunks)

                frame = np.frombuffer(
                    byte_frame, dtype=np.uint8).reshape(height, width, 3)

                cv.imshow("Transmisión en vivo", frame)

                if cv.waitKey(5) & 0xFF == ord('q'):
                    break
            print("Finalizando transmisión")
            cv.destroyAllWindows()
            s.close()
    except KeyboardInterrupt:
        exit()
    except ConnectionResetError as e:
        print("El servidor rechazó la conexión, seguro que está corriendo?")
        exit()





# endregion

