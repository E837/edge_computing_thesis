from flask import Flask, request, jsonify
import os

app = Flask(__name__)

# Get the Node Type and ID from Environment Variables (set in docker-compose)
NODE_TYPE = os.getenv('NODE_TYPE', 'unknown')
NODE_ID = os.getenv('NODE_ID', 'unknown')

@app.route('/')
def health_check():
    return jsonify({
        "status": "online",
        "node_type": NODE_TYPE,
        "node_id": NODE_ID,
        "message": f"Hello from {NODE_TYPE} {NODE_ID}"
    })

# This endpoint will receive container deployment requests (as per your PDF)
@app.route('/deploy', methods=['POST'])
def deploy_container():
    data = request.json
    # TODO: Implement the logic to check RAM/CPU and assign to a cluster
    print(f"Received deployment request: {data}")
    return jsonify({"status": "processing", "target": "TBD"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
