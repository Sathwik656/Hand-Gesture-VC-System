from flask import Flask, Response, jsonify
from flask_cors import CORS
from main import GestureServer

app = Flask(__name__)
CORS(app)

# Global gesture server instance
server = None

@app.before_request
def init_server():
    global server
    if server is None:
        server = GestureServer()

@app.route('/api/video_feed')
def video_feed():
    return Response(
        server.generate_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

@app.route('/api/status')
def status():
    if server is None:
        return jsonify({"error": "Server not initialized"}), 500
    return jsonify(server.get_status())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)
