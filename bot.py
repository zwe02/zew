import os
from dotenv import load_dotenv
import telebot
from telebot.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from services.durian_api import get_new_number, get_otp, delete_number
from db import (
    init_db,
    add_user,
    has_credit,
    deduct_credit,
    redeem_code,
    get_credits,
    is_allowed,
    add_allowed_user,
    remove_user,
    get_user
)
from handlers.admin_handlers import setup_admin_handlers

# تهيئة قاعدة البيانات
init_db()

# تحميل المتغيرات البيئية
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID", "883337742")

# إنشاء كائن البوت
bot = telebot.TeleBot(TOKEN)
bot.ADMIN_ID = ADMIN_ID

# دالة التحقق من الصلاحية
def has_access(user_id):
    return is_allowed(user_id) or str(user_id) == str(bot.ADMIN_ID)

# المتغيرات المؤقتة
user_numbers = {}
current_pid = {}
current_country = {}

# الكيبورد الرئيسي
def main_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton('/num'), KeyboardButton('/otp'), KeyboardButton('/delete'))
    kb.add(KeyboardButton('/PID'), KeyboardButton('/COUNTRY'))
    kb.add(KeyboardButton('🎟️ شحن رصيد'), KeyboardButton('💰 رصيدي'), KeyboardButton('/admin'))
    return kb

# دالة شحن الرصيد
def redeem_code_logic(message: Message, code: str):
    success, msg = redeem_code(code, message.from_user.id)
    if success:
        bot.send_message(message.chat.id, f"✅ تم شحن رصيدك بـ {msg} كريديت.")
    else:
        bot.send_message(message.chat.id, msg)

# ===== الأوامر الأساسية =====

@bot.message_handler(commands=['start'])
def start(message: Message):
    user_id = message.from_user.id
    if not has_access(user_id):
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📩 تواصل مع المالك", url="https://t.me/jadzwe"))
        return bot.send_message(
            message.chat.id,
            "🚫 أنت غير مصرح لك باستخدام هذا البوت.\n"
            "📩 للتفعيل تواصل مع المالك.\n"
            f"🆔 ID الخاص بك: {user_id}",
            reply_markup=markup
        )

    add_user(user_id)
    bot.send_message(message.chat.id, "👋 مرحباً بك! استخدم الأزرار 👇", reply_markup=main_menu())

@bot.message_handler(commands=['allow'])
def allow_user_command(message: Message):
    user_id = message.from_user.id
    if str(user_id) != str(bot.ADMIN_ID):
        return bot.reply_to(message, "🚫 هذا الأمر مخصص للإدارة فقط.")

    args = message.text.split()
    if len(args) != 2 or not args[1].isdigit():
        return bot.reply_to(message, "❗ استخدم الأمر بهذا الشكل:\n/allow <USER_ID>")

    target_id = int(args[1])
    add_allowed_user(target_id)
    bot.send_message(message.chat.id, f"✅ تم السماح للمستخدم:\n`{target_id}`", parse_mode="Markdown")

@bot.message_handler(commands=['block'])
def block_user_command(message: Message):
    user_id = message.from_user.id
    if str(user_id) != str(bot.ADMIN_ID):
        return bot.reply_to(message, "🚫 هذا الأمر مخصص للإدارة فقط.")

    args = message.text.strip().split()
    if len(args) != 2 or not args[1].isdigit():
        return bot.reply_to(message, "❗ استخدم الأمر بهذا الشكل:\n/block <USER_ID>")

    target_id = int(args[1])
    remove_user(target_id)
    bot.send_message(message.chat.id, f"🗑️ تم حذف المستخدم ومنعه من الوصول:\n`{target_id}`", parse_mode="Markdown")

@bot.message_handler(commands=['num'])
def handle_num(message: Message):
    if not has_access(message.from_user.id):
        return bot.reply_to(message, "🚫 غير مصرح لك.")

    user_id = message.from_user.id

    if user_id in user_numbers:
        return bot.reply_to(message, f"❗ لديك رقم بالفعل: {user_numbers[user_id]}\nاستخدم /otp أو /delete أولاً.")

    if not has_credit(user_id):
        return bot.reply_to(message, "❌ لا يوجد لديك رصيد كافٍ. استخدم كود شحن أولاً.")

    pid = current_pid.get(user_id, "3917")
    country = current_country.get(user_id, "eg")

    number = get_new_number(pid=pid, country=country)
    if number:
        user_numbers[user_id] = number
        bot.send_message(message.chat.id, f"📱 رقمك هو: {number}\nاستخدم /otp للحصول على الكود.")
    else:
        bot.send_message(message.chat.id, "🚫 لا يوجد أرقام متاحة حالياً.")

@bot.message_handler(commands=['otp'])
def handle_otp(message: Message):
    if not has_access(message.from_user.id):
        return bot.reply_to(message, "🚫 غير مصرح لك.")
    user_id = message.from_user.id
    number = user_numbers.get(user_id)
    if not number:
        return bot.reply_to(message, "❗ استخدم /num أولاً للحصول على رقم")
    code = get_otp(number)
    if code:
        bot.send_message(message.chat.id, f"✅ الكود: {code}")
        deduct_credit(user_id)
        user_numbers.pop(user_id, None)
    else:
        bot.send_message(message.chat.id, "⌛️ لم يصل كود حتى الآن.")

@bot.message_handler(commands=['delete'])
def handle_delete(message: Message):
    if not has_access(message.from_user.id):
        return bot.reply_to(message, "🚫 غير مصرح لك.")
    user_id = message.from_user.id
    number = user_numbers.get(user_id)
    if not number:
        return bot.reply_to(message, "❗ لا يوجد رقم محفوظ لك")
    if delete_number(number):
        bot.send_message(message.chat.id, "🗑 تم حذف الرقم بنجاح")
        user_numbers.pop(user_id)
    else:
        bot.send_message(message.chat.id, "❌ فشل في حذف الرقم")

# ===== اختيار الدولة والخدمة =====
@bot.message_handler(commands=['PID'])
def choose_pid(message: Message):
    if not has_access(message.from_user.id):
        return bot.reply_to(message, "🚫 غير مصرح لك.")
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("🍕 Talabat 🥩"))
    kb.add(KeyboardButton("🔙 عودة"))
    bot.send_message(message.chat.id, "اختر نوع الخدمة:", reply_markup=kb)

@bot.message_handler(commands=['COUNTRY'])
def choose_country(message: Message):
    if not has_access(message.from_user.id):
        return bot.reply_to(message, "🚫 غير مصرح لك.")
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("🇪🇬 مصر"))
    kb.add(KeyboardButton("🔙 عودة"))
    bot.send_message(message.chat.id, "اختر الدولة:", reply_markup=kb)

@bot.message_handler(func=lambda msg: msg.text == "🍕 Talabat 🥩")
def set_pid(message: Message):
    if not has_access(message.from_user.id):
        return
    current_pid[message.from_user.id] = "3917"
    bot.send_message(message.chat.id, "✅ تم تعيين الخدمة: Talabat")

@bot.message_handler(func=lambda msg: msg.text == "🇪🇬 مصر")
def set_country(message: Message):
    if not has_access(message.from_user.id):
        return
    current_country[message.from_user.id] = "eg"
    bot.send_message(message.chat.id, "✅ تم تعيين الدولة: مصر")

@bot.message_handler(func=lambda msg: msg.text == "🔙 عودة")
def back_to_menu(message: Message):
    if not has_access(message.from_user.id):
        return
    bot.send_message(message.chat.id, "تم الرجوع للقائمة 👇", reply_markup=main_menu())

# ===== الأوامر العامة =====
@bot.message_handler(commands=['redeem'])
def redeem_handler(message: Message):
    if not has_access(message.from_user.id):
        return bot.reply_to(message, "🚫 غير مصرح لك! @jadzwe")
    parts = message.text.strip().split()
    if len(parts) != 2:
        return bot.send_message(message.chat.id, "❗ استخدم الأمر بهذا الشكل:\n/redeem <كود>")
    code = parts[1]
    redeem_code_logic(message, code)

@bot.message_handler(func=lambda msg: len(msg.text.strip()) == 10 and msg.text.strip().isalnum())
def handle_redeem_code_direct(message: Message):
    if not has_access(message.from_user.id):
        return
    redeem_code_logic(message, message.text.strip())

@bot.message_handler(func=lambda msg: msg.text == "🎟️ شحن رصيد")
def ask_for_code(message: Message):
    if not has_access(message.from_user.id):
        return bot.reply_to(message, "🚫 غير مصرح لك.")
    bot.send_message(message.chat.id, "📝 أرسل كود الشحن بهذا الشكل:\n/redeem <كود>")

@bot.message_handler(func=lambda msg: msg.text == "💰 رصيدي")
def show_balance(message: Message):
    if not has_access(message.from_user.id):
        return bot.reply_to(message, "🚫 غير مصرح لك.")
    balance = get_credits(message.from_user.id)
    bot.send_message(message.chat.id, f"💰 رصيدك الحالي: {balance} كريديت.")

# ===== تهيئة handlers المسؤول =====
setup_admin_handlers(bot)

# ===== تشغيل البوت =====
if __name__ == "__main__":
    print("Starting bot...")
    bot.infinity_polling()
