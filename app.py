from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
from datetime import timedelta,datetime
from dotenv import load_dotenv,set_key
import mysql.connector
import subprocess
import ipaddress
import shutil
import bcrypt
import socket
import fcntl
import struct
import psutil
import threading
import time
import os

import hmac
import hashlib

load_dotenv()

APP_START_TIME = datetime.now()
SECRET_KEY = b"BISPM4632F"
app = Flask(__name__,
            template_folder="templates",
            static_folder="static"
            )

DB = {
    "host":'localhost',
    "user":'videoedge',
    "password":'cms@12345',
    "database":'videoedgeboxdb'
}

app.secret_key = "MyVerySecretKey123"

app.config["SESSION_COOKIE_HTTPONLY"]=True
app.config["SESSION_COOKIE_SAMESITE"]="Lax"
app.config["PERMANENT_SESSION_LIFETIME"]=timedelta(minutes=10)

def subnet_to_cidr(mask):
    return ipaddress.IPv4Network(f"0.0.0.0/{mask}").prefixlen

@app.route("/")
def index():
    return render_template("login.html")
# ("index.html")
 
@app.route("/dashboard")
def dashboard():
    
    print("SESSION",dict(session))

    if not session.get("logged_in"):
        print("NOT LOGGED IN")
        return redirect(url_for("index"))

    print("LOGGED IN")
    return render_template("index.html")


@app.route("/add-user")
def adduser():
    
    print("SESSION",dict(session))

    if not session.get("logged_in"):
        print("NOT LOGGED IN")
        return redirect(url_for("index"))

    print("LOGGED IN")
    return render_template("adduser.html")


@app.route("/addUser", methods=["POST"])
def addUser():
    try:
        data=request.get_json()
        print(data)

        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            return jsonify({
                "status": False,
                "message": "username and password are required."
            }),400
        
        username = username.strip()

        if username=="":
            return jsonify({
                "status": False,
                "message": "username required."
            }),400
        
        db = mysql.connector.connect(
            host='localhost',
            user='videoedge',
            password='cms@12345',
            database='videoedgeboxdb'
        )

        cursor=db.cursor()

        cursor.execute(
            "SELECT userId FROM usertbl WHERE username = %s",
            (username,)
        )

        existing_user = cursor.fetchone()

        if existing_user:

            cursor.close()
            db.close()

            return jsonify({
                "status": False,
                "message": "Username already exists."
            }), 409

        password_hash = bcrypt.hashpw(
            password.encode('utf-8'),
            bcrypt.gensalt()
        )

        password_hash = password_hash.decode('utf-8')

        cursor.execute(
            """
            INSERT INTO usertbl (username, pwd)
            VALUES (%s, %s)
            """,
            (username, password_hash)
        )

        db.commit()


        cursor.close()
        db.close()

        return jsonify({"status": "success", "message": "Record Saved."})   
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/reboot', methods=['POST'])
def reboot_pi():
    try:
        subprocess.Popen(["sudo", "reboot"])
        return jsonify({"status": "success", "message": "Rebooting Raspberry Pi..."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})
        
@app.route('/shutdown', methods=['POST'])
def shutdown():
    try:
        subprocess.Popen(["sudo", "shutdown"])
        return jsonify({"status": "success", "message": "Shutdown Raspberry Pi..."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route("/networkconfiguraton")
def networkconfiguraton():
    if not session.get("logged_in"):
        return redirect(url_for("index"))

    return render_template("network.html")

@app.route('/api/getmacid')
def getmacid():
    try:
        with open('/sys/class/net/eth0/address', 'r') as f:
            mac = f.read().strip().lower()

        return jsonify({"mac": mac})

    except Exception as e:
        print("MAC error:", e)
        return jsonify({"mac": "", "error": str(e)}), 500


@app.route('/api/network')
def network_info():
    ip = ""
    subnet = ""
    mac = ""
    interface_name = ""

    # Network Interface Details
    for interface, addrs in psutil.net_if_addrs().items():

        if interface == "lo":
            continue

        for addr in addrs:

            if addr.family == socket.AF_INET:
                ip = addr.address
                subnet = addr.netmask
                interface_name = interface

            elif str(addr.family) == "AddressFamily.AF_PACKET":
                mac = addr.address

        if ip:
            break

    # Default Gateway
    gateway = ""
    
    try:
        output = subprocess.check_output(
            ["ip", "route", "show", "default"],
            text=True
        ).strip()

        # print("Route Output:", output)

        if output:
            gateway = output.split()[2]

    except Exception as e:
        print("Gateway Error:", e)

    # print("Gateway:", gateway)

    # DNS Servers
    primary_dns = ""
    secondary_dns = ""

    try:
        dns_servers = []

        with open("/etc/resolv.conf") as f:
            for line in f:
                if line.startswith("nameserver"):
                    dns_servers.append(line.split()[1])

        if len(dns_servers) > 0:
            primary_dns = dns_servers[0]

        if len(dns_servers) > 1:
            secondary_dns = dns_servers[1]

    except:
        pass

    # Timezone
    try:
        timezone = datetime.now().astimezone().tzinfo.tzname(None)
    except:
        timezone = ""

    return jsonify({
        "interface": interface_name,
        "ip": ip,
        "subnet": subnet,
        "gateway": gateway,
        "primary_dns": primary_dns,
        "secondary_dns": secondary_dns,
        "timezone": timezone,
        "mac": mac
    })

@app.route('/api/getstorage')
def getstorage():
    total, used, free = shutil.disk_usage("/")

    total_space= total // (1024**3)
    used=used // (1024**3)
    free=free // (1024**3)

    print(f"Total: {total_space} GB")
    print(f"Used: {used} GB")
    print(f"Free: {free} GB")

    return jsonify({
        "total_space":total_space,
        "used":used,
        "free":free
    })

def get_connection():

    return mysql.connector.connect(

        host="localhost",
        user="videoedge",
        password="cms@12345",
        database="videoedgeboxdb"
    )

def get_ip_address(interface='eth0'):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(
        fcntl.ioctl(
            s.fileno(),
            0x8915,  # SIOCGIFADDR
            struct.pack('256s', interface[:15].encode('utf-8'))
        )[20:24]
    )

def backend_applications_running():
    applications = [
        "consumer.py",
        "listener.py",
        "tcp_listener_dashboard.py"
    ]

    for app in applications:

        result = subprocess.run(
            ["pgrep", "-f", app],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        if result.returncode != 0:
            return False

    return True

@app.route("/login", methods=["POST"])
def login():
    data=request.get_json()

    username=data["username"]

    password=data["password"]

    conn=get_connection()

    cursor=conn.cursor(dictionary=True)

    cursor.execute(

        """
        SELECT *
        FROM usertbl
        WHERE username=%s
        """,
        (username,)
    )

    user=cursor.fetchone()

    if user is None:

        cursor.close()
        conn.close()

        return jsonify({
            "message":"Invalid Username"
        }),401

    stored_hash=user["pwd"]

    if bcrypt.checkpw(
        password.encode("utf-8"),
        stored_hash.encode("utf-8")
    ):
        cursor.execute("""UPDATE usertbl SET last_login=NOW(),isloggedin=1 WHERE userId=%s""",(user["userId"],))
        conn.commit()
        session["logged_in"] = True
        session["user_id"] = user["userId"]
        session["username"] = user["username"]

        cursor.close()
        conn.close()

        # get network ip

        try:
            ip = get_ip_address('eth0')
            print("Ethernet IP:", ip)

            ip=ip.strip().strip("'")

            set_key(".env","FLASK_HOST",ip)

        except Exception as e:
            print("Error:", e)

        if backend_applications_running():
            print("Backend applications are already running.")
            print("Not starting videoedgeprog.sh again.")
        else:
            print("Backend applications are not running.")
            print("Starting videoedgeprog.sh...")

            # subprocess.Popen(
            #     ["/bin/bash", "/home/pi/videoedgeprog.sh"],
            #     stdout=subprocess.DEVNULL,
            #     stderr=subprocess.DEVNULL
            # )

        # start other programs

        # subprocess.Popen(
        #     ["/bin/bash", "/home/pi/videoedgeprog.sh"],
        #     stdout=subprocess.DEVNULL,
        #     stderr=subprocess.DEVNULL
        # )

    #    if backend_applications_running():
    #         print("Backend applications are already running.")
    #         print("Not starting videoedgeprog.sh again.")
    #     else:
    #         print("Backend applications are not running.")
    #         print("Starting videoedgeprog.sh...")

    #         subprocess.Popen(
    #             ["/bin/bash", "/home/pi/videoedgeprog.sh"],
    #             stdout=subprocess.DEVNULL,
    #             stderr=subprocess.DEVNULL
    #         )

        return jsonify({
            "status": True,
            "message": "Login Successful"
        })

    return jsonify({
        "message":"Invalid Password"
    }),401



@app.route("/configuration")
def configuration():
    if not session.get("logged_in"):
        return redirect(url_for("index"))
    return render_template("conf.html")
    
@app.post("/savepanelconfiguration")
def savepanelconfiguration():
    data = request.get_json()
    # print("data: ",data)
    return jsonify("OK")

@app.route("/alarms/<int:id>",methods=["DELETE"])
def delete_alarm(id):
    conn = mysql.connector.connect(**DB)
    cursor = conn.cursor(dictionary=True)

    try:
    
        cursor.execute(
            "DELETE FROM panelconfig WHERE id=%s",
            (id,)
        )
        conn.commit()

        return jsonify({
            "status":True,
            "message":"Record Deleted Successfully."
        })
    
    except Exception as e:
        conn.rollback()
        return jsonify({
            "status":False,
            "message":str(e)
        }),500
    finally:
        cursor.close()
        conn.close()

@app.get("/alarms")
def alarms():

    conn = mysql.connector.connect(**DB)
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        select * from panelconfig
    """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return jsonify(rows)

@app.route('/api/getactivationkey')
def getactivationkey():
    conn = mysql.connector.connect(**DB)
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        select * from activationTbl
    """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return jsonify(rows)



@app.route('/api/getpanelid')
def getpanelid():
    conn = mysql.connector.connect(**DB)
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        select distinct panelid from panelconfig
    """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return jsonify(rows)


 

@app.route("/addAlarm", methods=["POST"])
def addAlarm():

    conn = None
    cur = None

    try:

        data = request.get_json()

        conn = mysql.connector.connect(**DB)
        cur = conn.cursor()

        siaevent=data.get("sia_event")
        camera=data.get("camera_no")

        siaevent = siaevent.upper()
        dvr=data.get("dvr_make")

        sql=f"select count(*) as count from panelconfig where sia_event='{siaevent}' and camera_no='{camera}' and dvr_nvr='{dvr}'"
        cur.execute(sql,)
        rows = cur.fetchone()
        print(int(rows[0]))

        print()

        if int(rows[0]) == 0:

            sql = """
            INSERT INTO panelconfig
            (panelid,sia_event,zone,dvr_nvr,ip,rtsp_url,camera_no,stream_type,username,password) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""

            values = (
                data.get("panelid"),
                siaevent,
                data.get("zone"),
                data.get("dvr_make"),
                data.get("ip_address"),
                "",
                data.get("camera_no"),
                data.get("stream_type"),
                data.get("username"),
                data.get("password")
            )

            # print(values)

            cur.execute(sql, values)

            conn.commit()

            inserted_id = cur.lastrowid

            return jsonify({
                "status": True,
                "message": "Record inserted successfully.",
                "id": inserted_id
            })
        else:
            return jsonify({
            "status": True,
            "message": "Record Already Exists.",
            
        })


    except Exception as e:
        print('<----------------------------- * ERROR STARTS * ----------------------------->')
        print('error: ',e)
        print('<----------------------------- * ERROR ENDS * ----------------------------->')

        import traceback
        traceback.print_exc()

        return jsonify({
            "status": False,
            "message": str(e)
        }), 500

    finally:

        if cur:
            cur.close()

        if conn:
            conn.close()


# @app.route("/activation",methods=["POST"])
# def activation():
#     try:

#         data = request.get_json()
#         conn = mysql.connector.connect(**DB)
#         cur = conn.cursor()

#         sql = """INSERT INTO activationTbl (activationkey) VALUES (%s)"""
#         values = (data.get("activationkey"),)

#         cur.execute(sql, values)

#         conn.commit()

#         return jsonify({
#             "status": True,
#             "message": "Product Activated Successfully.",
#         })
#     except Exception as e:
#         print('635: ',e)
#         return jsonify({
#             "status": False,
#             "message": "Product Activated Failed.",
#         })
@app.route("/activation", methods=["POST"])
def activation():
    try:
        data = request.get_json()

        activation_key = data.get("activationkey", "").strip().upper()

        # Get MAC ID
        with open("/sys/class/net/eth0/address") as f:
            mac = f.read().strip().lower()

        print("MAC:", mac)

        # Generate HMAC from MAC
        full_hash = hmac.new(
            SECRET_KEY,
            mac.encode(),
            hashlib.sha256
        ).hexdigest().upper()

        # First 16 characters
        mac_hash = full_hash[:16]

        # Format: XXXX-XXXX-XXXX-XXXX
        mac_license_key = "-".join(
            mac_hash[i:i+4]
            for i in range(0, 16, 4)
        )

        print("Generated License:", mac_license_key)
        print("Received License :", activation_key)

        # Compare
        if mac_license_key == activation_key:

            conn = mysql.connector.connect(**DB)
            cur = conn.cursor()

            sql = """
                INSERT INTO activationTbl (activationkey)
                VALUES (%s)
            """

            cur.execute(sql, (activation_key,))
            conn.commit()

            cur.close()
            conn.close()

            return jsonify({
                "status": True,
                "message": "Product Activated Successfully."
            })

        else:
            return jsonify({
                "status": False,
                "message": "LICENSE KEY INVALID."
            })

    except Exception as e:
        print("Activation Error:", str(e))

        return jsonify({
            "status": False,
            "message": "Product Activation Failed."
        })
@app.route("/logout")
def logout():

    if session.get("user_id"):

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE usertbl
            SET isloggedin=0
            WHERE userId=%s
            """,
            (session["user_id"],)
        )

        conn.commit()
        cursor.close()
        conn.close()

    session.clear()
    return redirect(url_for("index"))

@app.get("/api/dashboard/status")
def dashboard_status():
    uptime = datetime.now() - APP_START_TIME

    days = uptime.days
    hours, rem = divmod(uptime.seconds, 3600)
    minutes, seconds = divmod(rem, 60)
 
    return {
        "application": "SERS",
        "status": "Running",
        "started_at": APP_START_TIME.strftime("%Y-%m-%d %H:%M:%S"),
        "uptime": f"{days}d {hours:02}:{minutes:02}:{seconds:02}"
    }

@app.route("/search", methods=["POST"])
def search():

    data = request.get_json()

    search_type = data["searchType"]

    conn = mysql.connector.connect(
        host="localhost",
        user="videoedge",
        password="cms@12345",
        database="videoedgeboxdb"
    )

    cursor = conn.cursor(dictionary=True)

    if search_type == "date":

        date = data["date"]

        cursor.execute(
            "SELECT * FROM alarms WHERE alarm_Date=%s",
            (date,)
        )

    elif search_type == "time":

        cursor.execute(
            """
            SELECT * FROM alarms
            WHERE alarm_Time BETWEEN %s AND %s
            """,
            (data["from"], data["to"])
        )

    elif search_type == "sia":

        cursor.execute(
            """
            SELECT *
            FROM alarms
            WHERE alarm_code LIKE %s
            """,
            ("%" + data["siaCode"] + "%",)
        )

    elif search_type == "zone":

        cursor.execute(
            "SELECT * FROM alarms WHERE zone=%s",
            (data["zone"],)
        )

    elif search_type == "camera":

        cursor.execute(
            "SELECT * FROM alarms WHERE camera_id=%s",
            (data["camera"],)
        )

    rows = cursor.fetchall()

    for row in rows:
        for key, value in row.items():

            if isinstance(value, timedelta):
                row[key] = str(value)

            elif isinstance(value, datetime):
                row[key] = value.strftime("%Y-%m-%d %H:%M:%S")

    cursor.close()
    conn.close()

    return jsonify(rows)

@app.route("/play/<int:alarm_id>")
def play_video(alarm_id):

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT video_file_name FROM alarms WHERE id=%s",
        (alarm_id,)
    )

    row = cursor.fetchone()

    cursor.close()
    conn.close()

    if not row:
        return "Video not found", 404

    filepath = row["video_file_name"]

    if not os.path.exists(filepath):
        return "File not found", 404

    return send_file(filepath, mimetype="video/mp4")

@app.route("/download/<int:alarm_id>")
def download_video(alarm_id):

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT video_file_name FROM alarms WHERE id=%s",
        (alarm_id,)
    )

    row = cursor.fetchone()

    cursor.close()
    conn.close()

    if not row:
        return "Video not found", 404

    filepath = row["video_file_name"]

    if not os.path.exists(filepath):
        return "File not found", 404

    return send_file(
        filepath,
        as_attachment=True,
        download_name=os.path.basename(filepath)
    )

# def update_flask_host(new_ip):
#     env_file=".env"

#     with open(env_file,"r",encoding="utf-8") as f:
#         lines=f.readlines()

#     updated=False
#     new_lines=[]

#     for line in lines:
#         if line.strip().startswith("FLASK_HOST="):
#             new_lines.append(f"FLASK_HOST={new_ip}\n")
#             updated=True
#         else:
#             new_lines.append(line)
#     if not updated:
#         new_lines.append(f"FLASK_HOST={new_ip}\n")

#     with open(env_file,"w",encoding="utf-8") as f:
#         f.writelines(new_lines)


def update_flask_host(new_ip):
    """Save FLASK_HOST to .env without quotes."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

    # Remove any surrounding single or double quotes
    new_ip = str(new_ip).strip().strip("'\"")

    with open(env_path, "r", encoding="utf-8") as file:
        lines = file.readlines()

    updated_lines = []
    host_found = False

    for line in lines:
        if line.strip().startswith("FLASK_HOST="):
            updated_lines.append(f"FLASK_HOST={new_ip}\n")
            host_found = True
        else:
            updated_lines.append(line)

    if not host_found:
        updated_lines.append(f"FLASK_HOST={new_ip}\n")

    with open(env_path, "w", encoding="utf-8") as file:
        file.writelines(updated_lines)

    print(f"FLASK_HOST saved as: {new_ip}")
    reboot_pi()

@app.route('/api/setnetwork', methods=['POST'])
def setnetwork():

    try:
        data = request.json
        print('data from /api/setnetwork API: ',data)
        # ip = data['ip']
        ip = str(data['ip']).strip().strip("'\"")
        gateway = data['gateway']
        dns1 = data['dns1']
        dns2 = data['dns2']
        subnet = data.get('subnet', '255.255.255.0')

        cidr = ipaddress.IPv4Network(f"0.0.0.0/{subnet}").prefixlen

        result = subprocess.run(
            ["sudo", "-n", "/usr/local/bin/set_network.sh", "eth0", ip, str(cidr), gateway, dns1, dns2],
            capture_output=True,
            text=True
        )

        print()
        print("RETURN CODE:", result.returncode)
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        print()

        # result = subprocess.run(
        #     ["sudo", "-n", "/usr/local/bin/set_network.sh", "eth0", ip, str(cidr), gateway, dns1, dns2],
        #     check=True, capture_output=True, text=True, timeout=15
        # )

        ip=ip.strip().strip("'")

        # set_key(".env","FLASK_HOST",ip)
        update_flask_host(ip)
      
        return {
            "status": "success",
            "message":"Network Configuration Applied Successfully. The EDGE BOX will restart in a few seconds. Kindly Re-Login usering the changes applied.",
            "stdout":result.stdout,
            "stderr":result.stderr
            }

    except subprocess.CalledProcessError as e:
        return {
            "status": "success",
            "message":"Network Configuration Applied Successfully. The EDGE BOX will restart in a few seconds. Kindly Re-Login usering the changes applied.",
            "stdout":result.stdout,
            "stderr":result.stderr
            }
        # return {"status":"Restart the Video Box to See the Changes."}
        # return {"status": "error", "message": f"Script failed: {e.stderr}"}, 500
    except Exception as e:
        return {"status":"Restart the Video Box to See the Changes."}

@app.route('/api/videoedgeconfig')
def videoedgeconfig():
    return jsonify({
        "ip":os.getenv("FLASK_HOST"),
        "port": os.getenv("FLASK_PORT")
    })

@app.route('/api/config', methods=['GET'])
def get_config():
    return {
        "host": os.environ.get('FLASK_HOST', '0.0.0.0'),
        "port": int(os.environ.get('FLASK_PORT', 5000))
    }

@app.route('/update_env', methods=['POST'])
def update_env():
    data = request.get_json()
     
    license_number = data.get("LICENSE_NUMBER", "VED-1")
    listener_port = data.get("LISTENER_PORT", "5001")
    webaccessport = data.get("DASHBOARD_PORT", "5001")
    # currentIp = data.get("FLASK_HOST", "127.0.0.1")
    currentIp = str(data.get("FLASK_HOST", "127.0.0.1")).strip().strip("'\"")
    

    env_path = os.path.join(os.path.dirname(__file__), ".env")
    with open(env_path, "r") as f:
        lines = f.readlines()

    updated_lines = []
    license_found = False
    port_found = False
    webaccessport_found = False
    currentIp_found = False

    for line in lines:
        if line.startswith("LICENSE_NUMBER="):
            updated_lines.append(f"LICENSE_NUMBER={license_number}\n")
            license_found = True
        elif line.startswith("LISTENER_PORT="):
            updated_lines.append(f"LISTENER_PORT={listener_port}\n")
            port_found = True
        elif line.startswith("APPPORT="):
            updated_lines.append(f"APPPORT={webaccessport}\n")
            webaccessport_found = True
        elif line.startswith("FLASK_HOST="):
            updated_lines.append(f"FLASK_HOST={currentIp}\n")
            currentIp_found = True
        else:
            updated_lines.append(line)

    if not license_found:
        updated_lines.append(f"LICENSE_NUMBER={license_number}\n")
    if not port_found:
        updated_lines.append(f"LISTENER_PORT={listener_port}\n")
    if not currentIp_found:
        updated_lines.append(f"FLASK_HOST={currentIp}\n")
    if not webaccessport_found:
        updated_lines.append(f"FLASK_PORT={webaccessport}\n")

    with open(env_path, "w") as f:
        f.writelines(updated_lines)

    return jsonify({
        "success": True,
        "message": ".env updated successfully"
    })

@app.route('/update_dvrsettings', methods=['POST'])
def update_dvrsettings():
    data = request.get_json()

    print('update_dvrsettings : ',data)

    dvrip = data.get("dvrip", "192.168.0.111")
    dvrrtspport = data.get("dvrrtspport", "554")
    dvrusername = data.get("dvrusername", "admin")
    dvrpassword = data.get("dvrpassword", "Ashu@9769")

    sia_event = data.get("sia_event")
    zone_name = data.get("zone_name")
    dvr_make = data.get("dvr_make")
    camera_no = data.get("camera_no")
    stream_type = data.get("stream_type")
    username = data.get("username")
    password = data.get("password")
    id = data.get("id")
    ip = data.get("ip_address")

    message=""


    # UPDATE DATABASE TABLE PANELCONFIG

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # Check duplicate, excluding the current record
        sql = """
            SELECT COUNT(*) AS count
            FROM panelconfig
            WHERE sia_event = %s
            AND camera_no = %s
            AND dvr_nvr=%s
            AND id != %s
        """

        print('sql: ',sql)

        cursor.execute(sql, (sia_event, camera_no,dvr_make, id))

        rows = cursor.fetchone()

        print("Existing duplicate records:", rows["count"])

        if int(rows["count"]) == 0:
            print("In IF loop - updating record")
            print("ID:", id)
            print("sia_event:", sia_event)
            print("camera_no:", camera_no)


            updatedOn = datetime.now()

            update_sql = """
            UPDATE panelconfig
                SET
                    sia_event=%s,
                    zone=%s,
                    dvr_nvr=%s,
                    camera_no=%s,
                    stream_type=%s,
                    username=%s,
                    password=%s,
                    updated_on=%s,
                    ip=%s
                WHERE id=%s
            """

            values = (
                sia_event,
                zone_name,
                dvr_make,
                camera_no,
                stream_type,
                username,
                password,
                updatedOn,
                ip,
                id
            )

            cursor.execute(update_sql, values)

            print("Rows affected:", cursor.rowcount)

            conn.commit()

            message = "RECORD UPDATED."
        else:
            message = "RECORD ALREADY EXISTS."
        cursor.close()
        conn.close()

    except Exception as e:
        print(e)

    print()    
    


    env_path = os.path.join(os.path.dirname(__file__), ".env")
    with open(env_path, "r") as f:
        lines = f.readlines()

    updated_lines = []
    _dvrip = False
    _dvrrtspport = False
    _dvrusername = False
    _dvrpassword = False

    for line in lines:
        if line.startswith("DVRIP="):
            updated_lines.append(f"DVRIP={dvrip}\n")
            _dvrip = True
        elif line.startswith("DVRRTSPPORTNO="):
            updated_lines.append(f"DVRRTSPPORTNO={dvrrtspport}\n")
            _dvrrtspport = True
        elif line.startswith("DVRUSERNAME="):
            updated_lines.append(f"DVRUSERNAME={dvrusername}\n")
            _dvrusername = True
        elif line.startswith("DVRPASSWORD="):
            updated_lines.append(f"DVRPASSWORD={dvrpassword}\n")
            _dvrpassword = True
        else:
            updated_lines.append(line)
    
    with open(env_path, "w") as f:
        f.writelines(updated_lines)

    return jsonify({
        "success": True,
        "message": message
    })

@app.route('/get_env', methods=['GET'])
def get_env():
    env_path = os.path.join(os.path.dirname(__file__), ".env")

    if not os.path.exists(env_path):
        return jsonify({
            "success": False,
            "message": ".env file not found"
        }), 404

    env_data = {}
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            # skip blank lines and comments
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                env_data[key.strip()] = value.strip()

    ip=env_data.get("FLASK_HOST")
    ip=ip.strip().strip("'")

    return jsonify({
        "success": True,
        "LICENSE_NUMBER": env_data.get("LICENSE_NUMBER", ""),
        "LISTENER_PORT": env_data.get("LISTENER_PORT", ""),
        "FLASK_PORT": env_data.get("FLASK_PORT", ""),
        "FLASK_HOST": ip,
        "FLASK_DEBUG": env_data.get("FLASK_DEBUG", ""),
        "DVRIP": env_data.get("DVRIP", ""),
        "DVRRTSPPORTNO": env_data.get("DVRRTSPPORTNO", ""),
        "DVRUSERNAME": env_data.get("DVRUSERNAME", ""),
        "DVRPASSWORD": env_data.get("DVRPASSWORD", ""),
        "DASHBOARD_PORT": env_data.get("APPPORT", "")
    })

def is_lan_connected():
    try:
        with open("/sys/class/net/eth0/carrier", "r") as f:
            return f.read().strip() == "1"
    except Exception:
        return False


def check_and_start_programs():

    programs = [
        ("Consumer-2", "consumer-rev-2-1.py"),
        ("Listener", "listener.py"),
        ("TCP DASHBOARD", "tcp_listener_dashboard.py"),
        ("NTP Sync", "ntp.py")
    ]

    for title, program in programs:

        # Check whether Python program is already running
        result = subprocess.run(
            ["pgrep", "-f", program],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        if result.returncode == 0:
            print(f"{title} is already running.")

        else:
            print(f"{title} is NOT running. Starting it...")

            if program == "consumer-rev-2-1.py":
                subprocess.Popen([
                    "lxterminal",
                    "--title=Consumer-2",
                    "-e",
                    "python3 consumer-rev-2-1.py"
                ])

            elif program == "listener.py":
                subprocess.Popen([
                    "lxterminal",
                    "--title=Listener",
                    "-e",
                    "python3 listener.py"
                ])

            elif program == "tcp_listener_dashboard.py":
                subprocess.Popen([
                    "lxterminal",
                    "--title=TCP DASHBOARD",
                    "-e",
                    "python3 tcp_listener_dashboard.py"
                ])

            elif program == "ntp.py":
                subprocess.Popen([
                    "lxterminal",
                    "--title=NTP Sync",
                    "-e",
                    "python3 ntp.py --interval 5"
                ])


def monitor_lan():

    previous_status = None

    while True:

        connected = is_lan_connected()

        # Cable status changed
        if connected != previous_status:

            if connected:

                print("======================================")
                print("LAN CABLE CONNECTED")
                print("Checking backend applications...")
                print("======================================")

               # check_and_start_programs()

            else:

                print("======================================")
                print("LAN CABLE REMOVED")
                print("Flask will continue running.")
                print("======================================")

            previous_status = connected

        # If LAN is connected, continuously make sure
        # the required programs are running.
     #   if connected:
          #  check_and_start_programs()

        time.sleep(5)

if __name__=="__main__":

    try:

        # Start LAN monitoring in background
        lan_thread = threading.Thread(
            target=monitor_lan,
            daemon=True
        )

        lan_thread.start()

        # Start Flask
        port = int(os.environ.get("APPPORT", 5000))

        print("======================================")
        print("Starting Flask Application")
        print(f"Port: {port}")
        print("======================================")

        app.run(
            host="0.0.0.0",
            port=port,
            debug=False
        )

    except Exception as e:

        print("Flask Error:", e)
    # try:
    #     host = os.environ.get('FLASK_HOST', '0.0.0.0')
    #     port = int(os.environ.get('APPPORT', 5000))
    #     debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'

    #     app.run(host=host,port=port,debug=False)
    # except:
    #     pass
