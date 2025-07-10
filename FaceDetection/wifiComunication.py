import socket
import json

HOST = "10.252.90.84"  # AI-deck IP
PORT = 5000           # CPX port

# CPX source/dest definitions
CPX_T_WIFI_HOST = 3
CPX_T_GAP8      = 4

# CPX functions
CPX_F_WIFI_CTRL = 4
CPX_F_APP       = 5

# CPX VERSION 
CPX_VERSION = 0

def build_cpx_header(source, destination, version, function, lp=0, rsv=0):
    header = (
        (rsv & 0x1) << 15 |
        (lp  & 0x1) << 14 |
        (source      & 0x7) << 11 |
        (destination & 0x7) <<  8 |
        (version     & 0x3) <<  6 |
        (function    & 0x3F)
    )
    return header.to_bytes(2, 'big')

def build_cpx_packet(source, destination, function, data_bytes):
    hdr = build_cpx_header(source, destination, version=CPX_VERSION, function=function)
    return hdr + data_bytes

def parse_cpx_header(hdr_bytes):
    h = int.from_bytes(hdr_bytes, 'big')
    return {
        'rsv': (h >> 15) & 0x1,
        'lp':  (h >> 14) & 0x1,
        'src': (h >> 11) & 0x7,
        'dst': (h >>  8) & 0x7,
        'ver': (h >>  6) & 0x3,
        'fun':  h         & 0x3F
    }

def recv_packet(sock):
    # 1. leggi la lunghezza totale
    length_bytes = sock.recv(2)
    if len(length_bytes) < 2:
        return None, None
    total_len = int.from_bytes(length_bytes, 'big')
    # 2. leggi header+data
    buf = b''
    while len(buf) < total_len:
        chunk = sock.recv(total_len - len(buf))
        if not chunk:
            return None, None
        buf += chunk
    hdr = buf[:2]
    data = buf[2:]
    info = parse_cpx_header(hdr)
    return info, data

def handle_alert(data_bytes):
    try:
        msg = json.loads(data_bytes.decode())
        count = msg.get('count', 0)
        drone = msg.get('drone_id', 'drone-?')
        print(f"\n🚨 Alert da {drone}: trovate {count} facce!\n")
    except json.JSONDecodeError:
        print("⚠️  Ricevuto JSON malformato:", data_bytes)


def receive_only(sock):
    print("🔊 In ascolto alert face-detect… (Ctrl-C per stop)\n")
    buf = b''
    try:
        while True:
            chunk = sock.recv(1024)
            if not chunk:
                print("❌ Connessione chiusa.")
                break
            buf += chunk

            # Estrai tutti i JSON completi
            while True:
                start = buf.find(b'{')
                end = buf.find(b'}\n', start)
                if start == -1 or end == -1:
                    # o non ho ancora {}, o non ho il newline
                    break

                # Prendo il JSON puro
                raw = buf[start:end+1]
                # Avanzo il buffer
                buf = buf[end+2:]

                # Provo a decodificare
                try:
                    s = raw.decode('utf-8')
                    alert = json.loads(s)
                    drone = alert.get('drone_id', '?')
                    count = alert.get('count', 0)
                    print(f"\n🚨 ALERT da {drone}: " f"{'trovata 1 faccia' if count == 1 else f'trovate {count} facce'}!\n")
                except Exception as e:
                    print("⚠️ Errore decoding JSON:", e, raw)

    except KeyboardInterrupt:
        print("\n👋 Ricezione terminata.")

import time
import json

def send_and_receive(sock):
    print("✏️  Invia e ricevi (exit per uscire)\n")
    buf = b''
    try:
        while True:
            msg = input("> ")             # digiti "1"
            n = int(msg)                  # lo converto in intero
            pkt = build_cpx_packet(
                source=CPX_T_WIFI_HOST,
                destination=CPX_T_GAP8,
                function=CPX_F_APP,
                data_bytes=n.to_bytes(1, 'big')
            )
            sock.sendall(len(pkt).to_bytes(2, 'big') + pkt)
            print(f"📤 Sent: {msg}")

            # Ora leggo in loop, esattamente come in receive_only
            # ma con un timeout per non bloccare l'input
            deadline = time.time() + 2.0
            while time.time() < deadline:
                sock.settimeout(deadline - time.time())
                try:
                    chunk = sock.recv(1024)
                except socket.timeout:
                    break  # torno al prompt

                if not chunk:
                    print("❌ Connessione chiusa.")
                    return
                buf += chunk

                # Stesso parsing JSON di receive_only:
                while True:
                    start = buf.find(b'{')
                    end   = buf.find(b'}\n', start)
                    if start == -1 or end == -1:
                        break

                    raw = buf[start:end+1]
                    buf = buf[end+2:]

                    try:
                        s = raw.decode('utf-8')
                        alert = json.loads(s)
                        drone = alert.get('drone_id', '?')
                        count = alert.get('count', 0)
                        # inline ternary per singolare/plurale
                        text = (
                            f"trovata 1 faccia"
                            if count == 1
                            else f"trovate {count} facce"
                        )
                        print(f"\n🚨 ALERT da {drone}: {text}!\n")
                    except Exception as e:
                        print("⚠️ Errore decoding JSON:", e, raw)

    except KeyboardInterrupt:
        print("\n👋 Stop.")

if __name__ == "__main__":
    mode = input("Scegli: [1] Solo ricevi  [2] Invia e ricevi: ").strip()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        print(f"✅ Connesso a {HOST}:{PORT}\n")
        if mode == '1':
            receive_only(s)
        elif mode == '2':
            send_and_receive(s)
        else:
            print("⚠️  Modalità non valida.")
            exit(1)
