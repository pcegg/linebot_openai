from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *
import tempfile, os, datetime, anythingllm, time, traceback

app = Flask(__name__)
static_tmp_path = os.path.join(os.path.dirname(__file__), 'static', 'tmp')

# Channel Access Token
line_bot_api = LineBotApi(os.getenv('CHANNEL_ACCESS_TOKEN'))
# Channel Secret
handler = WebhookHandler(os.getenv('CHANNEL_SECRET'))

# ANYTHINGLLM API Key initialization with error check
api_key = os.getenv('ANYTHINGLM_API_KEY')
if not api_key:
    raise ValueError("Missing ANYTHINGLLM_API_KEY environment variable.")
anythingllm.api_key = api_key

def GPT_response(text):
    try:
        response = anythingllm.Completion.create(model="Breeze Instruct 64K v01 7b Q2_k gguf", prompt=text, temperature=0.5, max_tokens=500)
        answer = response['choices'][0]['text'].replace('。', '')
        return answer
    except Exception as e:
        app.logger.error(f"Error during GPT response: {e}")
        return "Error in processing your request."

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
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
        GPT_answer = GPT_response(msg)
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
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
