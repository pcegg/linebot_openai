import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, PostbackEvent, MemberJoinedEvent
import requests
import traceback

app = Flask(__name__)

# Retrieve environment variables
channel_access_token = os.getenv('CHANNEL_ACCESS_TOKEN')
channel_secret = os.getenv('CHANNEL_SECRET')

# Check if the environment variables are set properly
if not channel_access_token:
    raise ValueError("Missing CHANNEL_ACCESS_TOKEN environment variable.")
if not channel_secret:
    raise ValueError("Missing CHANNEL_SECRET environment variable.")

# Initialize the LineBotApi and WebhookHandler with the environment variables
line_bot_api = LineBotApi(channel_access_token)
handler = WebhookHandler(channel_secret)

# URL of your Anything LLM service exposed via ngrok
ANYTHING_LLM_API_URL = "https://104a-111-248-75-161.ngrok-free.app/v1/completions"

def GPT_response(text):
    try:
        # Log the request to Anything LLM
        app.logger.info(f"Sending request to Anything LLM with prompt: {text}")
        
        # Send the prompt to Anything LLM via the ngrok-exposed API URL
        response = requests.post(
            ANYTHING_LLM_API_URL, 
            json={
                "prompt": text, 
                "model": "default_model", 
                "temperature": 0.7,
                "max_tokens": 500  # 限制生成的最大 token 數
            },
            timeout=30  # 延長超時時間
        )
        
        # Log the raw response
        app.logger.info(f"Received raw response from Anything LLM: {response.text}")
        
        # Raise an error if the response status code is not successful (not 2xx)
        response.raise_for_status()
        
        # Process the JSON response
        result = response.json()
        answer = result.get('choices', [{}])[0].get('text', '').replace('。', '')
        
        # 確保回應的長度不超過 LINE 訊息的限制 (5000 個字元)
        if len(answer) > 5000:
            answer = answer[:5000]  # 截斷回應
        
        return answer
    
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Request to Anything LLM failed: {e}")
        return "Error in processing your request."
    
    except ValueError as e:
        app.logger.error(f"Invalid JSON received from Anything LLM: {e}")
        return "Error in processing your request."
    
    except Exception as e:
        app.logger.error(f"Unexpected error: {e}")
        return "Error in processing your request."

@app.route("/callback", methods=['POST'])
def callback():
    # Get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']
    # Get request body as text
    body = request.get_data(as_text=True)
    app.logger.info(f"Request body: {body}")

    # Handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError as e:
        app.logger.error(f"Invalid signature: {e}")
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    msg = event.message.text
    try:
        # Get GPT response from Anything LLM
        GPT_answer = GPT_response(msg)
        # Send the generated response back to the user
        line_bot_api.reply_message(event.reply_token, TextSendMessage(GPT_answer))
    except Exception as e:
        app.logger.error(f"Failed to send message: {e}")
        line_bot_api.reply_message(event.reply_token, TextSendMessage('系統錯誤，請稍後再試'))

@handler.add(PostbackEvent)
def handle_postback(event):
    app.logger.info(f"Postback received: {event.postback.data}")

@handler.add(MemberJoinedEvent)
def welcome(event):
    uid = event.joined.members[0].user_id
    gid = event.source.group_id
    profile = line_bot_api.get_group_member_profile(gid, uid)
    name = profile.display_name
    message = TextSendMessage(text=f'{name}歡迎加入')
    line_bot_api.reply_message(event.reply_token, message)

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 4040))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
