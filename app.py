from flask import Flask, request, jsonify, render_template
import requests
import json
import os
import logging
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

STATUS_URL = "https://duckduckgo.com/duckchat/v1/status"
CHAT_URL = "https://duckduckgo.com/duckchat/v1/chat"
STATUS_HEADERS = {"x-vqd-accept": "1"}

class Model:
    GPT_4O_MINI = "gpt-4o-mini"
    CLAUDE_3_HAIKU = "claude-3-haiku-20240307"
    META_LLAMA = "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo"
    MISTRALAI = "mistralai/Mixtral-8x7B-Instruct-v0.1"

class Chat:
    def __init__(self, vqd: str, model: str):
        self.old_vqd = vqd
        self.new_vqd = vqd
        self.model = model
        self.messages = []

    def fetch(self, content: str):
        self.messages.append({"content": content, "role": "user"})
        payload = {
            "model": self.model,
            "messages": self.messages,
        }
        response = requests.post(
            CHAT_URL,
            headers={"x-vqd-4": self.new_vqd, "Content-Type": "application/json"},
            json=payload
        )
        if not response.ok:
            raise Exception(f"{response.status_code}: Failed to send message. {response.text}")
        return response

    def fetch_full(self, content: str) -> str:
        message = self.fetch(content)
        full_message = self.stream_events(message)
        self.old_vqd = self.new_vqd
        self.new_vqd = message.headers.get("x-vqd-4")
        self.messages.append({"content": full_message, "role": "assistant"})
        return full_message

    def stream_events(self, message):
        full_message = ""
        for line in message.iter_lines():
            if line:
                line = line.decode('utf-8')[len("data: "):].strip()
                if line == "[DONE]":
                    break
                try:
                    json_data = json.loads(line)
                    if "message" in json_data:
                        full_message += json_data["message"]
                except json.JSONDecodeError:
                    print(f"Skipping invalid JSON line: {line}")
        return full_message

def init_chat(model: str) -> Chat:
    status = requests.get(STATUS_URL, headers=STATUS_HEADERS)
    vqd = status.headers.get("x-vqd-4")
    if not vqd:
        raise Exception(f"{status.status_code}: Failed to initialize chat. {status.text}")
    return Chat(vqd, model)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    logging.info("Received chat request")
    data = request.json
    if not data or 'message' not in data:
        logging.error("Invalid input")
        return jsonify({"error": "Invalid input"}), 400

    model = data.get('model', Model.GPT_4O_MINI)
    message = data['message']

    try:
        chat_instance = init_chat(model)
        response = chat_instance.fetch_full(message)
        return jsonify({"response": response})
    except Exception as e:
        logging.error(f"Error during chat: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
