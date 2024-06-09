import vlc
import time
import requests
import os
from flask import Flask, request, Response, jsonify, send_from_directory
import subprocess
import signal

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

@app.route('/main', methods=['GET'])
def main_route():
    return send_from_directory('static', 'index.html')
  
if __name__ == '__main__':
    app.run(host='0.0.0.0',port=5003)
