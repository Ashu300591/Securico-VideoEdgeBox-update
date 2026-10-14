     

from datetime import datetime, timedelta
from dotenv import load_dotenv
import mysql.connector
import subprocess
import requests
import socket
import time
import re
import os

load_dotenv()

# =========================
# DATABASE CONFIG
# =========================

DB_CONFIG = {
    "host": 'localhost',
    "user": 'videoedge',
    "password": 'cms@12345',
    "database": 'videoedgeboxdb',
    "connection_timeout": 5
}

# =========================
# SOCKET CONFIG
# =========================

HOST = os.environ.get('FLASK_HOST', '0.0.0.0')
PORT = int(os.environ.get('LISTENER_PORT', 5000))
LogPORT = os.environ.get('FLASK_PORT', '5050')

# =========================
# DASHBOARD FORWARDING
# =========================
# Every received packet is forwarded here for live viewing on the web
# dashboard. This is best-effort only - it must never block or break real
# alarm processing if the dashboard is down, slow, or unreachable.
DASHBOARD_URL = os.environ.get(
    "DASHBOARD_INGEST_URL", f"http://{HOST}:{LogPORT}/api/ingest"
)

POLY = 0xA001


def get_db_connection():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as ex:
        print("MySQL connection failed:", ex)
        return None


def forward_to_dashboard(remote_addr, raw_packet):
    """
    Best-effort forward of the raw packet to the live dashboard. Any
    failure here (dashboard down, network issue, timeout) is swallowed and
    logged - it must never interrupt real alarm processing.
    """
    try:
        requests.post(
            DASHBOARD_URL,
            json={"remote": f"{remote_addr[0]}:{remote_addr[1]}", "raw": raw_packet},
            timeout=1,
        )
    except Exception as e:
        print("dashboard ingest failed (non-fatal):", e)


# =========================
# CRC16
# =========================

def crc16_arc(data: bytes):
    crc = 0x0000
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ POLY
            else:
                crc >>= 1
            crc &= 0xFFFF
    return crc


# =========================
# GENERATE ACK
# =========================

def generate_ack(sequence, receiver, line, account):
    body = f'"ACK"{sequence}{receiver}{line}#{account}[]'
    length = f"{len(body):04X}"
    crc = f"{crc16_arc(body.encode()):04X}"
    return crc + length + body


# =========================
# CREATE ACK FROM ALARM
# =========================

def create_ack_from_alarm(packet):
    sequence_match = re.search(r'"SIA-DCS"(\d{4})', packet)
    receiver_match = re.search(r'(R\d{6})', packet)
    line_match = re.search(r'(L\d{6})', packet)
    account_match = re.search(r'#(\d+)', packet)

    if not sequence_match:
        raise ValueError("Sequence not found")
    if not receiver_match:
        raise ValueError("Receiver not found")
    if not line_match:
        raise ValueError("Line not found")
    if not account_match:
        raise ValueError("Account not found")

    sequence = sequence_match.group(1)
    receiver = receiver_match.group(1)
    line = line_match.group(1)
    account = account_match.group(1)

    return generate_ack(sequence, receiver, line, account)


# =========================
# MAIN LISTENER
# =========================

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

server.bind((HOST, PORT))
server.listen(5)

print(f"Listening on {HOST}:{PORT}")
print(f"Forwarding received packets to dashboard at {DASHBOARD_URL}")

while True:

    print("\nWaiting for connection...")

    netconn, addr = server.accept()

    print(f"Client Connected : {addr}")

    buffer = ""

    try:
        while True:
            data = netconn.recv(4096)

            if not data:
                print("Client disconnected.")
                break

            buffer += data.decode(errors="ignore")

            while "\r" in buffer:
                packet, buffer = buffer.split("\r", 1)

                packet = packet.strip()

                if not packet:
                    continue

                print("\nReceived Packet:")
                print(packet)

                # Forward a copy to the live dashboard - never lets a
                # dashboard problem affect alarm processing below.
                print("FORWARD TO DASHBOARD: ",addr, packet)
                forward_to_dashboard(addr, packet)

                try:
                    nullpacket = packet.replace('_','"').split('"')
                    print()
                    print(nullpacket[1])
                    print(nullpacket[3])

                    dt = datetime.strptime(nullpacket[3], "%H:%M:%S,%m-%d-%Y")

                    print("Date:", dt.date())
                    print("Time:", dt.time())
                    print("Date and Time:", dt)

                    if nullpacket[1] == 'NULL':
                        print('NULL Packet Detected. Time sync in progress')
                        try:
                            # Disable NTP before manually setting the clock.
                            time_string = dt.strftime("%Y-%m-%d %H:%M:%S")

                            subprocess.run(
                                ["sudo", "-n", "/usr/bin/timedatectl", "set-ntp", "false"],
                                check=True,
                                capture_output=True,
                                text=True
                            )

                            subprocess.run(
                                ["sudo", "-n", "/usr/bin/timedatectl", "set-time", time_string],
                                check=True,
                                capture_output=True,
                                text=True
                            )

                            print("Device time synchronized successfully.")
                            print("Current device time:", datetime.now().strftime(
                                "%H:%M:%S %d-%m-%Y"
                            ))
                            continue
                        except Exception as ex:
                            print("Device time synchronization failed:", ex)
                            if isinstance(ex, subprocess.CalledProcessError) and ex.stderr:
                                print(ex.stderr)
                            continue

                    print()
                    ack = create_ack_from_alarm(packet)

                    print("Sending ACK:")
                    print(ack)

                    # SIA generally expects CR at end
                    netconn.sendall((ack + "\r").encode())

                    match = re.search(r'\[#(\d+)\|([A-Z]+\d+)\]_(.+)', packet)

                    if match:
                        account = match.group(1)
                        event = match.group(2)
                        timestamp = match.group(3)

                        time_part, date_part = timestamp.split(",")

                        print("Account :", account)
                        print("Event   :", event)
                        print("Time    :", time_part)
                        print("Date    :", date_part)

                        alarm_date = datetime.strptime(date_part, "%m-%d-%Y").strftime("%Y-%m-%d")

                        dvrmake = ""
                        camerano = ""

                        conn = get_db_connection()

                        if conn:
                            cur = conn.cursor(dictionary=True)

                            cur.execute(
                                """SELECT * FROM panelconfig WHERE sia_event=%s""",
                                (event,)
                            )

                            panel_rows = cur.fetchall()

                            print(panel_rows)

                            print('press enter to continue')
                            # input()

                            if not panel_rows:
                                print("No panel configuration found.")
                            else:
                                for panel_row in panel_rows:
                                    details = panel_row
                                    dvrmake = details["dvr_nvr"]
                                    camerano = details["camera_no"]

                                    timestamp_dt = datetime.strptime(
                                        timestamp,
                                        "%H:%M:%S,%m-%d-%Y"
                                    )
    
                                    end_time = timestamp_dt + timedelta(seconds=10)
                                    end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
    
                                    print("end_str:", end_str)
                                    print("DVR    :", dvrmake)
                                    print("Camera :", camerano)
    
                                    cur = conn.cursor(dictionary=True)
    
                                    cur.execute(
                                        """INSERT INTO alarms
                                           (panelid,camera_id,alarm_code,alarm_Date,alarm_Time,status,video_file_name,dvrmake,end_time)
                                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                                        (account, camerano, event, alarm_date, time_part, "PENDING", "", dvrmake, end_str)
                                    )
    
                                    conn.commit()
    
                                    print("Alarm inserted successfully.")
                                    print('press enter to continue')
                                    # input()

                            cur.close()
                            conn.close()

                except Exception as ex:
                    print("Invalid packet:", ex)
                    pass

    except Exception as ex:
        print("Connection error:", ex)
