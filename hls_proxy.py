import vlc
import time
import requests
import os
from flask import Flask, request, Response, jsonify, send_from_directory, stream_with_context
import subprocess
import signal
import asyncio
import re
import threading

def sigchld_handler(signum, frame):
    global vlc_process
    if vlc_process is not None:
    # Check if the exited process is the VLC process
        try:
            pid, _ = os.waitpid(vlc_process.pid, os.WNOHANG)
            if pid == vlc_process.pid:
                print("VLC subprocess exited.")
                vlc_process.terminate()
                vlc_process = None
        except ChildProcessError:
            pass  # No child processes

signal.signal(signal.SIGCHLD, sigchld_handler)

# Flask configuration
class Config:
    SERVER_SOURCE = os.environ.get('stream_source')
    LOGIN_URL = f'{SERVER_SOURCE}/login'
    STREAM_USER = os.environ.get('stream_user')
    STREAM_PASSWORD = os.environ.get('stream_password')

app = Flask(__name__)
app.config.from_object(Config)

# Start a session
session = requests.Session()
response = session.post(app.config['LOGIN_URL'], data={'user': app.config['STREAM_USER'], 'password': app.config['STREAM_PASSWORD']}, verify=False)

# Check if login was successful
if response.ok:
    print("Logged in successfully!")
    cookies = session.cookies.get_dict()
else:
    print("Failed to log in")
    cookies = {}

@app.route('/<path:url>', methods=['GET'])
def proxy(url):
    try:
        resp = requests.get(f"{app.config['SERVER_SOURCE']}/{url}", cookies=cookies, stream=True, verify=False)
        return Response(resp.iter_content(chunk_size=10*1024), content_type=resp.headers['Content-Type'])
    except requests.RequestException as e:
        return jsonify({'error': str(e)}), 404

@app.route('/hls.m3u8', methods=['GET'])
def default():
    try:
        resp = requests.get(f"{app.config['SERVER_SOURCE']}/cur-src", cookies=cookies, verify=False)
        stream_code = resp.text
        stream_url = f"{app.config['SERVER_SOURCE']}/{stream_code}.m3u8"
        resp = requests.get(stream_url, verify=False, cookies=cookies, stream=True)
        return Response(resp.iter_content(chunk_size=10*1024), content_type=resp.headers['Content-Type'])
    except requests.RequestException as e:
        return jsonify({'error': str(e)}), 404

# VLC control
vlc_process = None

@app.route('/vlc/start', methods=['GET'])
def start_vlc():
    global vlc_process
    if vlc_process is None:
        vlc_process = subprocess.Popen([
            os.path.join(os.path.dirname(__file__), 'venv', 'bin', 'python'), 
            os.path.join(os.path.dirname(__file__),'hls_player.py'),
        ])
        return jsonify({'status': 'VLC started'}), 200
    else:
        return jsonify({'status': 'VLC already running'}), 200

@app.route('/vlc/stop', methods=['GET'])
def stop_vlc():
    global vlc_process
    if vlc_process is not None:
        vlc_process.terminate()
        vlc_process = None
        return jsonify({'status': 'VLC stopped'}), 200
    else:
        return jsonify({'status': 'VLC not running'}), 200

timer = None
sleep_set_at = None
sleep_expires_at = None
def delayed_stop(seconds):
    global sleep_set_at
    global sleep_expires_at
    """Function to stop VLC after a delay."""
    def timer_action():
        print("Stopping for sleep timer.")
        sleep_set_at = None
        sleep_expires_at = None
        with app.app_context():  # Pushing an application context
            stop_vlc()

    global timer
    if timer is not None:
        timer.cancel()  # Cancel existing timer if there is one

    timer = threading.Timer(seconds, timer_action)
    timer.start()

@app.route('/sleep/<int:minutes>', methods=['GET'])
def set_sleep_timer(minutes):
    global sleep_set_at, sleep_expires_at
    sleep_set_at = time.time()
    seconds = minutes * 60
    sleep_expires_at = sleep_set_at + seconds
    delayed_stop(seconds)
    return jsonify({'status': f'Sleep timer set for {minutes} minutes'}), 200

@app.route('/sleep', methods=['GET'])
def get_sleep():
    global sleep_set_at, sleep_expires_at
    if sleep_set_at is not None:
        return jsonify({'sleep_set_at':sleep_set_at,'sleep_expires_in':sleep_expires_at-time.time()})
    else:
        return jsonify(['no sleep'])

@app.route('/alsa/volup', methods=['GET'])
def volup():
    amixer_process = subprocess.Popen([
        '/usr/bin/amixer',
        '-D',
        'pulse',
        'sset',
        'Master',
        '5%+', 
    ])
    return jsonify({'status': 'Volume Increased'}), 200

@app.route('/alsa/voldown', methods=['GET'])
def voldown():
    amixer_process = subprocess.Popen([
        '/usr/bin/amixer',
        '-D',
        'pulse',
        'sset',
        'Master',
        '5%-', 
    ])
    return jsonify({'status': 'Volume Decreased'}), 200

@app.route('/alsa/vol', methods=['GET'])
def get_volume():
    try:
        # Run the amixer command and capture its output
        amixer_process = subprocess.Popen(
            ['/usr/bin/amixer', '-D', 'pulse', 'sget', 'Master'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        output, errors = amixer_process.communicate()

        if amixer_process.returncode != 0:
            return jsonify({'error': errors.decode()}), 500

        # Process the output to find the volume percentage
        for line in output.decode().split('\n'):
            if 'Left:' in line:
                # Assuming the volume information is formatted like '[XX%]'
                volume = line.split('[')[1].split(']')[0]
                return jsonify({'volume': volume}), 200

        return jsonify({'error': 'Volume info not found'}), 404

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/bt/on', methods=['GET'])
def bt_on():
  commands = ['power on', 'agent on']
  for command in commands:
    process_command = f"echo '{command}' | bluetoothctl"
    time.sleep(2)
    try:
      result = subprocess.run(process_command, shell=True, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
      return jsonify({'status': 'success', 'output': result.stdout}), 200
    except subprocess.CalledProcessError as e:
      return jsonify({'status': 'error', 'message': str(e), 'stderr': e.stderr}), 500

@app.route('/bt/off', methods=['GET'])
def bt_off():
  commands = ['disconnect', 'agent off', 'power off']
  for command in commands:
    process_command = f"echo '{command}' | bluetoothctl"
    time.sleep(2)
    try:
      result = subprocess.run(process_command, shell=True, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
      return jsonify({'status': 'success', 'output': result.stdout}), 200
    except subprocess.CalledProcessError as e:
      return jsonify({'status': 'error', 'message': str(e), 'stderr': e.stderr}), 500

# def process_output(output):
#     """Process the output from bluetoothctl to turn device IDs into clickable links."""
#     processed_lines = []
#     for line in output.splitlines():
#         # Example match: Device 00:11:22:33:44:55 My Bluetooth Device
#         matches = re.findall(r"Device (\w\w:\w\w:\w\w:\w\w:\w\w:\w\w) ", line)
#         if match:
#             print('match')
#             device_id = match.group(1)
#             device_name = match.group(2)
#             # Create a clickable link
#             clickable_link = f'<a href="/bt/connect/{device_id}">{device_id} - {device_name}</a>'
#             processed_lines.append(clickable_link)
#         else:
#             processed_lines.append(line)
#     return "<br>".join(processed_lines)
# 
# @app.route('/bt/scan', methods=['GET'])
# async def bt_scan():
#     command = "timeout 20 bluetoothctl --timeout 18 scan on"
#     process = await asyncio.create_subprocess_shell(
#         command,
#         stdout=asyncio.subprocess.PIPE,
#         stderr=asyncio.subprocess.PIPE
#     )
# 
#     try:
#         stdout, stderr = await process.communicate()
#         if process.returncode == 0:
#             processed_output = process_output(stdout.decode())
#             return jsonify({'status': 'success', 'output': processed_output}), 200
#         else:
#             return jsonify({'status': 'error', 'message': stderr.decode()}), 500
#     except asyncio.TimeoutError:
#         return jsonify({'status': 'timeout', 'message': 'Bluetooth scan timed out'}), 408
# 

def create_clickable_links(line):
    clean_line = re.sub(r'\x1B[@-_][0-?]*[ -/]*[@-~]', '', line)  # Strip ANSI codes
    match = re.search(r'Device ([0-9A-F:]{17}) (.+)', clean_line)
    if match:
        device_id = match.group(1)
        device_name = match.group(2)
        return f'data: <a href="/bt/connect/{device_id}">{device_id} - {device_name}</a><br>\n\n'
    return f'data: {clean_line}<br>\n\n'

def scan_bluetooth(timeout=20):
    """Start bluetoothctl, turn on scanning, and manage output."""
    cmd = ["bluetoothctl"]
    with subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1) as process:
        # Turn on the agent and start scanning
        process.stdin.write("agent on\n")
        process.stdin.write("scan on\n")
        process.stdin.flush()

        # Stop scan after a timeout
        def stop_scan():
            time.sleep(timeout)
            process.stdin.write("scan off\n")
            process.stdin.write("exit\n")
            process.stdin.flush()

        timer = threading.Timer(timeout, stop_scan)
        timer.start()

        # Process output
        try:
            for line in iter(process.stdout.readline, ''):
                yield create_clickable_links(line.strip())
        finally:
            timer.cancel()
            process.stdin.write("exit\n")
            process.stdin.flush()

@app.route('/bt/scan', methods=['GET'])
def bt_scan():
    return Response(stream_with_context(scan_bluetooth()), mimetype='text/event-stream')

@app.route('/main', methods=['GET'])
def main_route():
    return send_from_directory('static', 'index.html')
  
if __name__ == '__main__':
    app.run(host='0.0.0.0',port=5003)
