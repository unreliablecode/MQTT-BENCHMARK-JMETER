import paramiko
import subprocess
import time
import sys
import csv
from datetime import datetime
import xml.etree.ElementTree as ET

# --- Configuration ---
SERVER_IP = "your.hostname.net"  # SSH and Target JMeter IP (Tailscale P2P)
USERNAME = "your_good_username"
PASSWORD = "your_password"

JMX_FILE = r"MQTT Connect.jmx" 
JMETER_CMD = r"jmeter.bat" 

def log_msg(msg):
    """Log to file AND print to console"""
    print(msg)  # Print to console
    with open("bench.log", "a", encoding="utf-8") as f:
        f.write(str(msg) + "\n")

def run_ssh_command(ip, username, password, command, is_sudo=False):
    log_msg(f"\n[SSH] Connecting to {ip}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        client.connect(hostname=ip, username=username, password=password)
        log_msg(f"[SSH] Executing: {command}")

        if is_sudo:
            command = f"sudo -S {command}"
            stdin, stdout, stderr = client.exec_command(command, get_pty=True)
            time.sleep(0.5) 
            stdin.write(password + '\n')
            stdin.flush()
        else:
            stdin, stdout, stderr = client.exec_command(command, get_pty=True)

        time.sleep(1)
        
        output = stdout.read().decode('utf-8', errors='ignore').strip()
        error = stderr.read().decode('utf-8', errors='ignore').strip()
        exit_status = stdout.channel.recv_exit_status()
        
        if output:
            log_msg(f"[SSH] Command Output:\n{output}")
        else:
            log_msg(f"[SSH] No output received from command (exit code: {exit_status})")
            
        if error:
            log_msg(f"[SSH] Error Output:\n{error}")
            
        if exit_status != 0:
            log_msg(f"[SSH] Warning: Command exited with status {exit_status}")
        
        return output

    except Exception as e:
        log_msg(f"[SSH Error] {e}")
        sys.exit(1)
    finally:
        client.close()

def update_jmx_config(jmx_path, new_port, new_host, new_threads):
    """Updates port, host, and thread configurations in the JMeter JMX file"""
    try:
        tree = ET.parse(jmx_path)
        root = tree.getroot()
        updated = False
        
        # 1. Update Port
        for port_node in root.findall('.//stringProp[@name="mqtt.port"]') + root.findall('.//stringProp[@name="port"]'):
            port_node.text = str(new_port)
            updated = True
            
        # 2. Update Host
        for host_node in root.findall('.//stringProp[@name="mqtt.server"]') + root.findall('.//stringProp[@name="mqtt.broker"]') + root.findall('.//stringProp[@name="server"]'):
            host_node.text = str(new_host)
            updated = True
            
        # 3. Update Threads
        for thread_node in root.findall('.//*[@name="ThreadGroup.num_threads"]'):
            thread_node.text = str(new_threads)
            updated = True

        if updated:
            tree.write(jmx_path, encoding='UTF-8', xml_declaration=True)
            log_msg(f"[JMX Update] Config updated -> Host: {new_host} | Port: {new_port} | Threads: {new_threads}")
        else:
            log_msg(f"[JMX Update Warning] Could not find settings to update in {jmx_path}")
            
    except Exception as e:
        log_msg(f"[Error] Failed to update JMX configuration: {e}")
        sys.exit(1)

def run_jmeter_test(jmx_path):
    log_msg(f"\n[JMeter] Starting load test using {jmx_path}...")
    
    now = datetime.now()
    jtl_filename = now.strftime("%Y-%m-%d_%H-%M-%S") + "_results.jtl"
    command = [JMETER_CMD, "-n", "-t", jmx_path, "-l", jtl_filename]  

    try:
        with open("bench.log", "a") as logf:
            logf.write(f"\n--- JMETER EXECUTION OUTPUT ---\n")
            subprocess.run(command, check=True, stdout=logf, stderr=subprocess.STDOUT)
            logf.write(f"--- END JMETER OUTPUT ---\n")
            
        log_msg("[JMeter] Test completed successfully.")
        return jtl_filename
        
    except subprocess.CalledProcessError as e:
        log_msg(f"[JMeter Error] Test failed: {e}")
        print(f"[Error] JMeter test failed. Check bench.log for details.")
        sys.exit(1)
    except FileNotFoundError:
        log_msg(f"[JMeter Error] Could not find JMeter executable. Make sure it is in your PATH.")
        sys.exit(1)

def print_jmx_details(jmx_path):
    log_msg(f"\n--- JMeter Test Configuration ---")
    try:
        tree = ET.parse(jmx_path)
        root = tree.getroot()

        threads = root.find('.//*[@name="ThreadGroup.num_threads"]')
        if threads is not None:
            log_msg(f"Threads (Users) : {threads.text}")
        else:
            log_msg("Threads (Users) : Not found")

        host = root.find('.//stringProp[@name="mqtt.server"]')
        if host is None:
            host = root.find('.//stringProp[@name="mqtt.broker"]')
        if host is None:
            host = root.find('.//stringProp[@name="server"]')
            
        if host is not None:
            log_msg(f"MQTT Host       : {host.text}")
        else:
            log_msg("MQTT Host       : Not found")

        port = root.find('.//stringProp[@name="mqtt.port"]')
        if port is None:
            port = root.find('.//stringProp[@name="port"]')
            
        if port is not None:
            log_msg(f"MQTT Port       : {port.text}")
        else:
            log_msg("MQTT Port       : Not found")
            
    except FileNotFoundError:
        log_msg(f"[Error] Could not find the file: {jmx_path}")
    except Exception as e:
        log_msg(f"[Error] Failed to read JMX details: {e}")
    log_msg("---------------------------------")

def parse_jtl_and_print_results(jtl_file):
    success_count = 0
    error_count = 0
    elapsed_times = []
    timestamps = []

    try:
        with open(jtl_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if 'success' in row:
                    if row['success'].lower() == 'true':
                        success_count += 1
                    elif row['success'].lower() == 'false':
                        error_count += 1
                
                if 'elapsed' in row and row['elapsed'].isdigit():
                    elapsed_times.append(int(row['elapsed']))
                
                if 'timeStamp' in row and row['timeStamp'].isdigit():
                    timestamps.append(int(row['timeStamp']))
        
        total_requests = success_count + error_count
        
        log_msg(f"\n=== Final Test Results ===")
        log_msg(f"Total Samples  : {total_requests}")
        log_msg(f"Success        : {success_count}")
        log_msg(f"Errors         : {error_count}")
        
        if elapsed_times:
            avg_latency = sum(elapsed_times) / len(elapsed_times)
            min_latency = min(elapsed_times)
            max_latency = max(elapsed_times)
            log_msg(f"Latency (ms)   : Avg: {avg_latency:.2f} | Min: {min_latency} | Max: {max_latency}")
            
        if timestamps and len(timestamps) > 1:
            duration_seconds = (max(timestamps) - min(timestamps)) / 1000.0
            if duration_seconds > 0:
                throughput = total_requests / duration_seconds
                log_msg(f"Throughput     : {throughput:.2f} req/sec (over {duration_seconds:.2f}s)")
            else:
                log_msg("Throughput     : N/A (Test duration too short)")
                
        log_msg(f"==========================\n")

    except Exception as e:
        log_msg(f"Failed to parse JTL results: {e}")

if __name__ == "__main__":
    with open("bench.log", "w", encoding="utf-8") as f:
        f.write(f"=== Automated Test Log Started: {datetime.now()} ===\n")
        
    print("=== Starting Automated MQTT Load Test ===")
    
    # --- 1. BROKER SELECTION ---
    while True:
        print("\nPlease Choose Broker:")
        print("1 - Mosquitto (Port 1883)")
        print("2 - EMQX (Port 1884)")
        print("3 - RabbitMQ (Port 1885)")
        print("4 - VerneMQ (Port 1886)")
        b_sel = input("Which broker? : ")
        
        if b_sel == "1":
            service_name = "mosquitto"
            target_port = 1883
            break
        elif b_sel == "2":
            service_name = "snap.emqx-enterprise.emqx.service"
            target_port = 1884
            break
        elif b_sel == "3":
            service_name = "rabbitmq-server"
            target_port = 1885
            break
        elif b_sel == "4":
            service_name = "vernemq"
            target_port = 1886
            break
        else:
            print("[!] Invalid selection. Please enter 1, 2, 3, or 4.")

    # We hardcode the target host to the Tailscale IP
    target_host = SERVER_IP

    # --- 2. THREADS SELECTION ---
    while True:
        print("\nPlease Choose Threads Amount:")
        print("1 - 50")
        print("2 - 100")
        print("3 - 150")
        print("4 - Custom")
        t_sel = input("How many threads? : ")
        
        if t_sel == "1":
            target_threads = 50
            break
        elif t_sel == "2":
            target_threads = 100
            break
        elif t_sel == "3":
            target_threads = 150
            break
        elif t_sel == "4":
            custom_threads = input("Enter custom thread amount: ").strip()
            if custom_threads.isdigit() and int(custom_threads) > 0:
                target_threads = int(custom_threads)
                break
            else:
                print("[!] Invalid input. Must be a positive integer.")
        else:
            print("[!] Invalid selection. Please enter 1, 2, 3, or 4.")

    # --- EXECUTION PHASE ---
    print("\nRunning test... All execution logs are being redirected to 'bench.log'.")
    print("Please wait, this may take a while depending on your test duration...")

    log_msg(f"Selected Service: {service_name}")
    
    # Update the JMX file before testing
    update_jmx_config(JMX_FILE, target_port, target_host, target_threads)

    print("\n--- Fetching Server Hardware Info ---")
    # Added hostname fetch to the start of the bash command string
    hw_cmd = """
    echo "Hostname  : $(hostname)"
    echo "CPU Model : $(grep -m 1 'model name' /proc/cpuinfo | cut -d: -f2 | xargs)"
    echo "CPU Cores : $(nproc)"
    echo "CPU Speed : $(lscpu | grep 'CPU MHz' | awk '{print $3}' || grep -m 1 'cpu MHz' /proc/cpuinfo | cut -d: -f2 | xargs) MHz"
    echo "RAM Info  : $(free -h | awk '/^Mem:/ {print $2 " Total / " $3 " Used"}')"
    """
    run_ssh_command(SERVER_IP, USERNAME, PASSWORD, hw_cmd, is_sudo=False)

    print("\n--- Restarting MQTT Broker ---")
    run_ssh_command(SERVER_IP, USERNAME, PASSWORD, f"systemctl restart {service_name}", is_sudo=True)

    log_msg(f"\n[System] Waiting 3 seconds for {service_name} broker to fully spin up...")
    time.sleep(3)

    # Print the verified updated details
    print_jmx_details(JMX_FILE)

    # Run the test
    jtl_output_file = run_jmeter_test(JMX_FILE)

    print("\n--- Checking Broker Statistics ---")
    stats_cmd = f"ps -C {service_name.split('.')[0]} -o %cpu,%mem,rss,cmd 2>/dev/null || echo 'Process not found'"
    run_ssh_command(SERVER_IP, USERNAME, PASSWORD, stats_cmd, is_sudo=False)
    
    if jtl_output_file:
        parse_jtl_and_print_results(jtl_output_file)
        
    log_msg("\n=== Automation Complete ===")
    print("Test Complete! You can view the full details in 'bench.log'.")
