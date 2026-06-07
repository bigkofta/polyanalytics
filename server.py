from flask import Flask, request, jsonify, send_from_directory
import requests, os

app = Flask(__name__, static_folder='.')

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzg2MDA2NjA0LCJpYXQiOjE3ODA4MjI2MDQsImp0aSI6IjNmNWU4ZGEzODk0ZDQ5YzA4OGMyMDliYWU5NTg0OGY4IiwidXNlcl9pZCI6ODk4LCJzY29wZSI6InJldHJpZXZlcjplY2hvLWdlbmVyYXRpb24scmV0cmlldmVyOmFnZW50LW9wdGlvbi1yZXRyaWV2YWwsbGF1bmNocGFkOmFnZW50LXJlYWQscmV0cmlldmVyOnNlbWFudGljLXJldHJpZXZhbCxsYXVuY2hwYWQ6YWdlbnQtY3JlYXRpb24sdXNlcjpyZWFkLGxhdW5jaHBhZDphZ2VudC11cGRhdGUsbGF1bmNocGFkOmVjaG8tc3R5bGUtY3JlYXRpb24sdXNlcjp3cml0ZSxyZXRyaWV2ZXI6ZmVhdHVyZS1leHRyYWN0aW9uIiwidG9rZW5fbmFtZSI6ImJhc2VfbG9naW4ifQ.Wd6MMBFTP6secI7NQ-DRvJ2a0iNNTVGrex_gm-HRsfQ"
API_URL = "https://narrative.agent.heisenberg.so/api/v2/semantic/retrieve/parameterized"

@app.route('/')
def index():
    return send_from_directory('.', 'dashboard.html')

@app.route('/api', methods=['POST'])
def proxy():
    body = request.get_json()
    if 'formatter_config' not in body:
        body['formatter_config'] = {'format_type': 'raw'}
    r = requests.post(API_URL, json=body, headers={
        'Authorization': f'Bearer {TOKEN}',
        'Content-Type': 'application/json',
    })
    return jsonify(r.json())

if __name__ == '__main__':
    print("Dashboard: http://localhost:5050")
    app.run(port=5050, debug=False)
