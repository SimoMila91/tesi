import socket
import struct

HOST = "172.20.10.2"  # AI-deck IP
PORT = 5000           # CPX port

# Target definitions
CPX_T_STM32 = 1
CPX_T_ESP32 = 2
CPX_T_WIFI_HOST = 3
CPX_T_GAP8 = 4

# Function definitions
CPX_F_SYSTEM = 1
CPX_F_CONSOLE = 2
CPX_F_CRTP = 3
CPX_F_WIFI_CTRL = 4
CPX_F_APP = 5

def build_cpx_header(source, destination, version, function, lp=0, rsv=0):
    header = (
        (rsv & 0x1) << 15 |
        (lp & 0x1) << 14 |
        (source & 0x7) << 11 |
        (destination & 0x7) << 8 |
        (version & 0x3) << 6 |
        (function & 0x3F)
    )
    return header.to_bytes(2, 'big')

def build_cpx_packet(source, destination, function, data):
    header = build_cpx_header(
        source=source,
        destination=destination,
        version=1,
        function=function
    )
    return header + data

def parse_cpx_packet(packet):
    if len(packet) < 2:
        return None

    header = int.from_bytes(packet[:2], 'big')
    return {
        'rsv': (header >> 15) & 0x1,
        'lp': (header >> 14) & 0x1,
        'source': (header >> 11) & 0x7,
        'destination': (header >> 8) & 0x7,
        'version': (header >> 6) & 0x3,
        'function': header & 0x3F,
        'data': packet[2:]
    }

def recv_all(sock, n):
    """Garantisce la ricezione di n byte da un socket."""
    data = b''
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data += packet
    return data

def receive_only(sock):
    print("Listening for incoming messages...\nPress Ctrl+C to stop.")
    try:
        while True:
            # 1. Leggi i 2 byte di lunghezza (CPX header + data)
            length_bytes = sock.recv(2)
            print(f"Received length bytes: {length_bytes}")
            print(len(length_bytes))
            if not length_bytes or len(length_bytes) < 2:
                print("Connection closed or incomplete length.")
                break

            total_len = int.from_bytes(length_bytes, 'big')
            print(f"Total length of packet: {total_len}")

            # 2. Leggi tutto il pacchetto (header + data)
            packet = b''
            while len(packet) < total_len:
                chunk = sock.recv(total_len - len(packet))
                print(f"Received chunk: {chunk}")
                print(len(chunk))
                if not chunk:
                    print("Connection closed while receiving packet.")
                    return
                packet += chunk

            if len(packet) < 2:
                print("Incomplete CPX header.")
                continue

            # 3. Dividi header e payload
            cpx_header = packet[:2]
            data = packet[2:]

            # 4. Parsifica l’header
            header0 = cpx_header[0]
            header1 = cpx_header[1]

            destination = (header0 >> 5) & 0x07
            source = (header0 >> 2) & 0x07
            last_packet = (header0 >> 1) & 0x01
            function = (header1 >> 2) & 0x3F
            version = header1 & 0x03

            print(f"\n📨 Received CPX packet:")
            print(f"From {source} → {destination}, function {function}, version {version}, last={last_packet}")
            print(f"Data (raw): {data}")
            try:
                print(f"Data (utf8): {data.decode('utf-8', errors='ignore')}")
            except:
                print("Data not decodable")

    except KeyboardInterrupt:
        print("\nStopped listening.")


def send_and_receive(sock):
    try:
        while True:
            message = input("Enter message (or 'exit' to quit): ")
            if message.lower() == 'exit':
                break

            msg_data = message.encode('utf-8')
            cpx_pkt = build_cpx_packet(
                source=CPX_T_WIFI_HOST,
                destination=CPX_T_GAP8,
                function=CPX_F_APP,
                data=msg_data
            )

            sock.sendall(len(cpx_pkt).to_bytes(2, 'big'))
            sock.sendall(cpx_pkt)
            print(f"Sent: {message}")

            length_bytes = sock.recv(2)
            if len(length_bytes) < 2:
                print("Failed to receive length")
                continue

            length = int.from_bytes(length_bytes, 'big')
            packet = sock.recv(length)
            while len(packet) < length:
                packet += sock.recv(length - len(packet))

            parsed = parse_cpx_packet(packet)
            if parsed and parsed['data']:
                print(f"Received: {parsed['data'].decode('utf-8', errors='ignore')}")
    except KeyboardInterrupt:
        print("\nInterrupted by user.")

# Main
mode = input("Choose mode: [1] Receive only, [2] Send and receive: ").strip()

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
    print(f"Connected to AI-deck at {HOST}:{PORT}")

    if mode == '1':
        receive_only(s)
    elif mode == '2':
        send_and_receive(s)
    else:
        print("Invalid mode selected.")
