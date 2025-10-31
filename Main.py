import os
import random
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

TOKEN = os.getenv("BOT_TOKEN")
MANAGERS_CHAT_ID = int(os.getenv("MANAGERS_CHAT_ID", "-1003173446264"))

if not TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

user_messages = {}
user_data = {}
tickets = {}
user_active_ticket = {}

TEXTS = {
    'ru': {
        'welcome': '👋 Добро пожаловать! Выберите язык:',
        'menu': '📋 Выберите категорию вашего вопроса:',
        'describe': '✍️ Опишите ваш вопрос:',
        'ticket_created': '✅ Ваш тикет #{ticket_id} создан и отправлен в поддержку!\n\nОжидайте ответа. Вы можете закрыть тикет в любой момент.',
        'ticket_closed': '✅ Тикет #{ticket_id} успешно закрыт.',
        'close_ticket': '🔴 Закрыть тикет',
        'no_active_ticket': 'У вас нет активного тикета.',
        'categories': {
            'tech': '🔧 Техническая помощь',
            'payment': '💳 Помощь с платежами',
            'hwid': '🔄 Сброс HWID',
            'partner': '🤝 Сотрудничество',
            'faq': '❓ FAQ / Цены / Товары'
        }
    },
    'en': {
        'welcome': '👋 Welcome! Choose your language:',
        'menu': '📋 Select your question category:',
        'describe': '✍️ Describe your question:',
        'ticket_created': '✅ Your ticket #{ticket_id} has been created and sent to support!\n\nPlease wait for a response. You can close the ticket at any time.',
        'ticket_closed': '✅ Ticket #{ticket_id} has been closed.',
        'close_ticket': '🔴 Close ticket',
        'no_active_ticket': 'You have no active ticket.',
        'categories': {
            'tech': '🔧 Technical Support',
            'payment': '💳 Payment Help',
            'hwid': '🔄 HWID Reset',
            'partner': '🤝 Partnership',
            'faq': '❓ FAQ / Prices / Products'
        }
    }
}

def generate_ticket_id():
    return random.randint(10000, 99999)

def get_language_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
        InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
    )
    return keyboard

def get_category_keyboard(lang):
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    cats = TEXTS[lang]['categories']
    keyboard.add(
        KeyboardButton(cats['tech']),
        KeyboardButton(cats['payment']),
        KeyboardButton(cats['hwid']),
        KeyboardButton(cats['partner']),
        KeyboardButton(cats['faq'])
    )
    return keyboard

def get_close_ticket_keyboard(lang):
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton(TEXTS[lang]['close_ticket']))
    return keyboard

def get_manager_close_keyboard(ticket_id):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🔴 Закрыть тикет", callback_data=f"close_{ticket_id}"))
    return keyboard

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_data:
        user_data[user_id] = {}
    await message.answer(TEXTS['ru']['welcome'], reply_markup=get_language_keyboard())

@dp.callback_query_handler(lambda c: c.data.startswith('lang_'))
async def process_language(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    lang = callback.data.split('_')[1]
    user_data[user_id] = {'lang': lang}
    await callback.message.edit_text(TEXTS[lang]['menu'])
    await bot.send_message(user_id, TEXTS[lang]['menu'], reply_markup=get_category_keyboard(lang))

@dp.message_handler(lambda m: m.chat.id != MANAGERS_CHAT_ID and not (m.text and m.text.startswith('/')))
async def handle_user_message(message: types.Message):
    user_id = message.from_user.id
    
    if user_id not in user_data or 'lang' not in user_data[user_id]:
        await message.answer(TEXTS['ru']['welcome'], reply_markup=get_language_keyboard())
        return
    
    lang = user_data[user_id]['lang']
    text = message.text or ""
    
    if text == TEXTS[lang]['close_ticket']:
        if user_id in user_active_ticket:
            ticket_id = user_active_ticket[user_id]
            await close_ticket(ticket_id, lang)
        else:
            await message.answer(TEXTS[lang]['no_active_ticket'], reply_markup=get_category_keyboard(lang))
        return
    
    category = None
    for cat_key, cat_name in TEXTS[lang]['categories'].items():
        if text == cat_name:
            category = cat_key
            user_data[user_id]['category'] = category
            await message.answer(TEXTS[lang]['describe'])
            return
    
    if user_id in user_active_ticket:
        ticket_id = user_active_ticket[user_id]
        if ticket_id in tickets:
            forwarded = await bot.forward_message(MANAGERS_CHAT_ID, message.chat.id, message.message_id)
            tickets[ticket_id]['messages'].append(forwarded.message_id)
            user_messages[forwarded.message_id] = ticket_id
            return
    
    if 'category' not in user_data[user_id]:
        await message.answer(TEXTS[lang]['menu'], reply_markup=get_category_keyboard(lang))
        return
    
    category = user_data[user_id]['category']
    category_name = TEXTS[lang]['categories'][category]
    
    ticket_id = generate_ticket_id()
    while ticket_id in tickets:
        ticket_id = generate_ticket_id()
    
    forwarded = await bot.forward_message(MANAGERS_CHAT_ID, message.chat.id, message.message_id)
    
    info_text = f"🎫 Тикет #{ticket_id}\n"
    info_text += f"👤 Пользователь: @{message.from_user.username or message.from_user.id}\n"
    info_text += f"📂 Категория: {category_name}\n"
    info_text += f"🌐 Язык: {'Русский' if lang == 'ru' else 'English'}"
    
    info_msg = await bot.send_message(MANAGERS_CHAT_ID, info_text, reply_markup=get_manager_close_keyboard(ticket_id))
    
    tickets[ticket_id] = {
        'user_id': user_id,
        'messages': [forwarded.message_id, info_msg.message_id],
        'category': category,
        'lang': lang
    }
    user_messages[forwarded.message_id] = ticket_id
    user_messages[info_msg.message_id] = ticket_id
    user_active_ticket[user_id] = ticket_id
    
    await message.answer(TEXTS[lang]['ticket_created'].format(ticket_id=ticket_id), reply_markup=get_close_ticket_keyboard(lang))
    del user_data[user_id]['category']

async def close_ticket(ticket_id, lang=None):
    if ticket_id not in tickets:
        return
    
    ticket = tickets[ticket_id]
    user_id = ticket['user_id']
    
    if not lang:
        lang = ticket.get('lang', 'ru')
    
    for msg_id in ticket['messages']:
        try:
            await bot.delete_message(MANAGERS_CHAT_ID, msg_id)
        except Exception:
            pass
        if msg_id in user_messages:
            del user_messages[msg_id]
    
    if user_id in user_active_ticket and user_active_ticket[user_id] == ticket_id:
        del user_active_ticket[user_id]
        await bot.send_message(user_id, TEXTS[lang]['ticket_closed'].format(ticket_id=ticket_id), reply_markup=get_category_keyboard(lang))
    
    del tickets[ticket_id]

@dp.callback_query_handler(lambda c: c.data.startswith('close_'))
async def manager_close_ticket(callback: types.CallbackQuery):
    ticket_id = int(callback.data.split('_')[1])
    await close_ticket(ticket_id)
    await callback.answer("Тикет закрыт")

@dp.message_handler(lambda m: m.chat.id == MANAGERS_CHAT_ID, content_types=['text'])
async def reply_to_client(message: types.Message):
    if message.reply_to_message:
        ticket_id = user_messages.get(message.reply_to_message.message_id)
        if ticket_id and ticket_id in tickets:
            ticket = tickets[ticket_id]
            user_id = ticket['user_id']
            
            reply_msg = await bot.send_message(user_id, message.text)
            ticket['messages'].append(message.message_id)

executor.start_polling(dp)
