"""
import socket
import json

# Diccionario de comandos basado en el código C#
commands = {
    "Pause": {"Command": "Pause"},
    "Continue": {"Command": "Continue"},
    "Stop": {"Command": "Stop"},
    "Ground Walking": {"Command": "Ground Walking"},
    "Stair Up": {"Command": "Stair Up"},
    "Stair Down": {"Command": "Stair Down"},
    "Slope Up": {"Command": "Slope Up"},
    "Slope Down": {"Command": "Slope Down"},
    "Speed Up": {"Command": "Speed Up"},
    "Speed Down": {"Command": "Speed Down"},
}

# Función para crear un mensaje JSON basado en un comando seleccionado
def create_json_message(command_key):
    if command_key in commands:
        return json.dumps(commands[command_key])
    else:
        return json.dumps({"Error": "Invalid Command"})

# Configuración de conexión TCP
def start_tcp_connection(host, port, message):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp_socket:
        tcp_socket.connect((host, port))
        tcp_socket.sendall(message.encode('utf-8'))
        response = tcp_socket.recv(1024)
        print("Respuesta TCP:", response.decode('utf-8'))

# Configuración de conexión UDP
def start_udp_connection(host, port, message):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:
        udp_socket.sendto(message.encode('utf-8'), (host, port))
        response, _ = udp_socket.recvfrom(1024)
        print("Respuesta UDP:", response.decode('utf-8'))

# Configuración del servidor y puerto
SERVER_HOST = "192.168.102.1"  # Dirección IP del servidor
UDP_PORT = 50000  # Puerto UDP
# TCP_PORT = 50000  # Puerto TCP

# Selección de un comando para enviar
selected_command = "Speed Up"  # Se puede cambiar por otro comando del diccionario
json_message = create_json_message(selected_command)

# Enviar el mensaje a través de TCP y UDP
# start_tcp_connection(SERVER_HOST, TCP_PORT, json_message)
start_udp_connection(SERVER_HOST, UDP_PORT, json_message)

"""
import socket
import json

# Configuración del cliente UDP
SERVER_IP = "192.168.102.1"  # Dirección del servidor
SERVER_PORT = 50000       # Mismo puerto que el servidor

# Diccionario con comandos
commands = {
    "Pause": {"Command": "Pause"},
    "Continue": {"Command": "Continue"},
    "Stop": {"Command": "Stop"},
    "Ground Walking": {"Command": "Ground Walking"},
    "Stair Up": {"Command": "Stair Up"},
    "Stair Down": {"Command": "Stair Down"},
    "Slope Up": {"Command": "Slope Up"},
    "Slope Down": {"Command": "Slope Down"},
    "Speed Up": {"Command": "Speed Up"},
    "Speed Down": {"Command": "Speed Down"},
}

# Crear socket UDP
client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Enviar un comando
command_key = "Pause"  # Comando a enviar
message = json.dumps(commands[command_key])  # Convertir a JSON
client_socket.sendto(message.encode(), (SERVER_IP, SERVER_PORT))

print(f"Enviado: {message}")

# Cerrar socket
client_socket.close()

