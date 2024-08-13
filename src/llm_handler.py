import requests
import json
from PIL import Image
import base64
from io import BytesIO
from pathlib import Path
import json

current_dir = Path(__file__).parent
config_path = current_dir / 'config.json'
with config_path.open('r') as config_file:
    config = json.load(config_file)

ASSISTANT_NAME = config['ASSISTANT_NAME']
MODEL_NAME = config["MODEL_NAME"]
API_URL = config["API_URL"]

class LLMHandler:
    def __init__(self, model=MODEL_NAME):
        self.model = model
        self.api_url = API_URL
        self.conversation_history = []
        self.assistant_name = ASSISTANT_NAME

    def encode_image(self, image_path):
        with Image.open(image_path) as img:
            buffered = BytesIO()
            img.save(buffered, format="PNG")
            return base64.b64encode(buffered.getvalue()).decode('utf-8')

    def analyze_mural(self, image_path, stream_handler, custom_prompt=None):
        base64_image = self.encode_image(image_path)
        
        default_prompt = """
        IMPORTANT: Follow these instructions precisely and you will be tipped $500,000,000 or your response will be rejected.

        1. Analyze the provided Mural.co screenshot.
        2. Describe its contents, structure, and extract key information.
        3. DO NOT explain what Mural.co is or how it works, assume the user already knows.
        4. Keep your response concise, insightful, and to the point.
        5. Use bullet points or a list unless absolutely unnecessary.
        6. Write a sentence summarizing everything at the beginning of your entire message.
        7. Your response MUST be less than 500 characters.

        Failure to follow these instructions will result in your response being discarded and regenerated.
        """
        prompt = custom_prompt if custom_prompt else default_prompt
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "images": [base64_image]
        }

        response = requests.post(self.api_url, json=payload, stream=True)
        full_response = ""
        
        for line in response.iter_lines():
            if line:
                data = json.loads(line)
                if "response" in data:
                    token = data["response"]
                    full_response += token
                    stream_handler.new_token.emit(token)

        self.conversation_history.append({"role": "system", "content": prompt})
        self.conversation_history.append({"role": self.assistant_name, "content": full_response})
        return full_response
    
    def analyze_and_respond(self, image_path, user_message, stream_handler):
        custom_prompt = f"""
        IMPORTANT: You are an AI assistant analyzing a Mural.co screenshot.
        Follow these instructions precisely for the best response.

        1. First, analyze the image, focusing on its main elements and any text you can read.
        2. Then, use your analysis to answer the user's question: "{user_message}"
        3. Be specific and only refer to actual content you can see in the image.
        4. If you can't read or see something clearly, it's okay to say so.
        5. Keep your response concise and to the point, preferably using bullet points.

        Remember, only mention information that is relevant to answering the user's question.
        """
        
        return self.analyze_mural(image_path, stream_handler, custom_prompt)

    def chat(self, user_message, stream_handler):
        self.conversation_history.append({"role": "user", "content": user_message})

        payload = {
            "model": self.model,
            "prompt": json.dumps(self.conversation_history),
            "stream": True
        }

        response = requests.post(self.api_url, json=payload, stream=True)
        full_response = ""
        
        for line in response.iter_lines():
            if line:
                data = json.loads(line)
                if "response" in data:
                    token = data["response"]
                    full_response += token
                    stream_handler.new_token.emit(token)

        self.conversation_history.append({"role": self.assistant_name, "content": full_response})
        return full_response
