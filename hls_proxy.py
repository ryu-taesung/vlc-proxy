import vlc
import time
import requests
import os
from flask import Flask, request, Response, jsonify
import subprocess

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
response = session.post(app.config['LOGIN_URL'], data={'user': app.config['STREAM_USER'], 'password': app.config['STREAM_PASSWORD']})

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
        resp = requests.get(f"{app.config['SERVER_SOURCE']}/{url}", cookies=cookies, stream=True)
        return Response(resp.iter_content(chunk_size=10*1024), content_type=resp.headers['Content-Type'])
    except requests.RequestException as e:
        return jsonify({'error': str(e)}), 404

@app.route('/hls.m3u8', methods=['GET'])
def default():
    try:
        resp = requests.get(f"{app.config['SERVER_SOURCE']}/cur-src", cookies=cookies)
        stream_code = resp.text
        stream_url = f"{app.config['SERVER_SOURCE']}/{stream_code}.m3u8"
        print(f"stream_url={stream_url}")
        resp = requests.get(stream_url, cookies=cookies, stream=True)
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
            'cvlc', 
            '--http-reconnect', 
            '--repeat', 
            '--loop', 
           # '--network-caching=1000',   # Increase network caching to 1000 ms
           # '--file-caching=1000',      # Increase file caching to 1000 ms
           # '--live-caching=1000',      # Increase live caching to 1000 ms
            'http://localhost:5003/hls.m3u8'
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

if __name__ == '__main__':
    app.run(host='0.0.0.0',port=5003)
