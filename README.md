# Automated MQTT Load Tester

A robust Python automation script designed to execute and monitor Apache JMeter load tests against various MQTT brokers over SSH. 

This tool automates the process of configuring the JMeter test plan (`.jmx`), restarting the target broker, gathering server hardware statistics, executing the test, and parsing the `.jtl` results to calculate latency and throughput.

## Features
- **Dynamic Configuration:** Automatically updates Target Host, Port, and Thread (User) counts directly in your `.jmx` file before execution.
- **Multi-Broker Support:** Select and restart target brokers via SSH (Mosquitto, EMQX, RabbitMQ, VerneMQ).
- **Server Telemetry:** Fetches and logs remote server CPU model, core count, clock speed, and RAM usage.
- **Automated Parsing:** Reads the output `.jtl` file to calculate Total Samples, Success/Error rates, Latency (Min/Max/Avg), and Throughput (Requests per Second).
- **Comprehensive Logging:** Outputs real-time execution details to the console while safely appending everything to a `bench.log` file.

## Prerequisites
1. **Python 3.x**
2. **Paramiko:** Install via pip: `pip install paramiko`
3. **Apache JMeter:** Must be installed and accessible via your system's `PATH`.
4. **JMX File:** A valid JMeter test plan (e.g., `MQTT Connect.jmx`) located in the same directory.

## Configuration
Before running the script, edit the `--- Configuration ---` section at the top of `main.py` with your SSH credentials and target IP:

## Replace with your information
```python
SERVER_IP = "your_hostname"  # Your target/Tailscale IP
USERNAME = "your_username"
PASSWORD = "your_password"
```
