
import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *

app = Flask(__name__)

ACCESS_TOKEN = '0/BrDPJ0LLT9/s0M/Lsadb6WpA1zrmRBXNoXT0qPE3txmJqr780m7wnOgxdJWvMutQheE7Lv71yw00XHbpR/rHG9qEaC2Hlw/o2x3rcdyuh2Rm3EidFKcbIPFbFi7nNvjvSEFtWckr1NR/1nM3WpxQdB04t89/1O/w1cDnyilFU='
CHANNEL_SECRET = 'c4485d07c997249825988371f0a9897b'

line_bot_api = LineBotApi(ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

admin_list = set()
blacklist = set()
read_tracking = {}

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

@handler.add(JoinEvent)
def handle_join(event):
    group_id = event.source.group_id
    welcome_text = (
        "✅ บอทเข้าร่วมกลุ่มแล้ว\n"
        "คำสั่งบอทที่ใช้ได้:\n"
        "!startread → เริ่มจับคนอ่านข้อความ\n"
        "!read → แจ้งว่าคุณอ่านข้อความแล้ว\n"
        "!whoread → ดูว่าใครอ่านข้อความ\n"
        "!addadmin @ชื่อ → เพิ่มแอดมิน\n"
        "!adminlist → รายชื่อแอดมิน\n"
        "!unblock user_id → ปลดบล็อก\n"
    )
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=welcome_text))

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    group_id = getattr(event.source, 'group_id', None)
    text = event.message.text.strip()

    if group_id:
        if 'messages' not in read_tracking:
            read_tracking['messages'] = {}
        read_tracking['messages'][event.message.id] = {
            'text': text,
            'user_id': user_id,
            'display_name': get_user_name(user_id, group_id)
        }

    if not group_id:
        return

    if text.startswith('!addadmin') and user_id in admin_list:
        if event.message.mention:
            for mentionee in event.message.mention.mentionees:
                admin_list.add(mentionee.user_id)
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text='เพิ่มแอดมินแล้ว'))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text='โปรดเมนชันคนที่ต้องการเพิ่ม'))

    elif text.startswith('!adminlist') and user_id in admin_list:
        names = [get_user_name(uid, group_id) for uid in admin_list]
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text='แอดมิน:\n' + '\n'.join(names)))

    elif text.startswith('!unblock') and user_id in admin_list:
        parts = text.split()
        if len(parts) == 2:
            blocked_id = parts[1]
            blacklist.discard(blocked_id)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text='ปลดบล็อกแล้ว'))

    elif text == '!startread' and user_id in admin_list:
        read_tracking[group_id] = set()
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text='เริ่มจับคนอ่านแล้ว (ให้พิมพ์ !read)'))

    elif text == '!read':
        if group_id in read_tracking:
            read_tracking[group_id].add(user_id)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text='รับทราบการอ่านข้อความ'))

    elif text == '!whoread' and user_id in admin_list:
        if group_id in read_tracking:
            readers = [get_user_name(uid, group_id) for uid in read_tracking[group_id]]
            msg = '\n'.join(readers) if readers else 'ยังไม่มีใครอ่านข้อความ'
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text='คนที่อ่านแล้ว:\n' + msg))

@handler.add(UnsendEvent)
def handle_unsend(event):
    unsend_id = event.unsend.message_id
    if unsend_id in read_tracking.get('messages', {}):
        info = read_tracking['messages'][unsend_id]
        name = info['display_name']
        text = info['text']
        group_id = getattr(event.source, 'group_id', None)
        if group_id:
            line_bot_api.push_message(group_id, TextSendMessage(text=f'{name} ลบข้อความ: {text}'))

@handler.add(MemberLeftEvent)
def handle_kick(event):
    group_id = getattr(event.source, 'group_id', None)
    kicked = event.left.members[0].user_id if event.left.members else None
    kicker = event.source.user_id
    if kicker not in admin_list:
        blacklist.add(kicker)
        line_bot_api.kickout_from_group(group_id, kicker)
        line_bot_api.push_message(group_id, TextSendMessage(text='บอทเตะผู้ไม่ใช่แอดมินที่เตะคนอื่น'))

def get_user_name(user_id, group_id):
    try:
        profile = line_bot_api.get_group_member_profile(group_id, user_id)
        return profile.display_name
    except:
        return user_id

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
