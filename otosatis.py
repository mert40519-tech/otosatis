import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# Ayarlar
BOT_TOKEN = "8424668193:AAEDATyRHmmejUxvFv_klhV2a9xWGO1oiQ0"
ADMIN_ID = 8342400585  # Admin Telegram ID'nizi buraya yazın
IBAN = "TR00 1234 5678 9012 3456 7890 12  YELİZ MERT"  # IBAN adresiniz

# Fiyatlar
PRICES = {
    'kart': 300,
    'kanal': 600,
    'hesap': 600,  # Belirtilmemişti, örnek fiyat
    'ship': 600,
    'checker_aylik': 300,
    'checker_yillik': 1000
}

# Durumlar
SELECTING_PRODUCT, WAITING_PAYMENT, WAITING_RECEIPT = range(3)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("💳 Kart (300₺)", callback_data='kart')],
        [InlineKeyboardButton("📢 Kanal (600₺)", callback_data='kanal')],
        [InlineKeyboardButton("👤 Hesap (600₺)", callback_data='hesap')],
        [InlineKeyboardButton("🚢 Ship (600₺)", callback_data='ship')],
        [InlineKeyboardButton("🔍 Checker", callback_data='checker_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🛍️ *Ürün Seçimi*\n\nSatın almak istediğiniz ürünü seçin:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return SELECTING_PRODUCT

async def checker_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📅 Aylık (300₺)", callback_data='checker_aylik')],
        [InlineKeyboardButton("📆 Yıllık (1000₺)", callback_data='checker_yillik')],
        [InlineKeyboardButton("🔙 Geri", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🔍 *Checker Paketi Seçin:*",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return SELECTING_PRODUCT

async def select_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    product = query.data
    
    if product == 'checker_menu':
        return await checker_menu(update, context)
    elif product == 'back_to_main':
        return await start(update, context)
    
    # Fiyat ve ürün bilgisi
    price = PRICES.get(product, 0)
    product_names = {
        'kart': '💳 Kart',
        'kanal': '📢 Kanal', 
        'hesap': '👤 Hesap',
        'ship': '🚢 Ship',
        'checker_aylik': '🔍 Checker (Aylık)',
        'checker_yillik': '🔍 Checker (Yıllık)'
    }
    
    product_name = product_names.get(product, product)
    context.user_data['selected_product'] = product_name
    context.user_data['price'] = price
    context.user_data['user_id'] = query.from_user.id
    context.user_data['username'] = query.from_user.username or "Yok"
    
    text = f"""✅ *Seçilen Ürün:* {product_name}
💰 *Fiyat:* {price}₺

📌 *Ödeme Bilgileri:*
IBAN: `{IBAN}`

⚠️ Ödemeyi yaptıktan sonra dekontu göndermek için "Ödemeyi Yaptım" butonuna basın."""
    
    keyboard = [[InlineKeyboardButton("💸 Ödemeyi Yaptım", callback_data='paid')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    return WAITING_PAYMENT

async def confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📸 *Dekont Gönderimi*\n\nLütfen ödeme dekontunu fotoğraf olarak gönderin.\n"
        "Süre sınırı yoktur, dekontu gönderdiğinizde işlem başlatılacaktır.",
        parse_mode='Markdown'
    )
    return WAITING_RECEIPT

async def receive_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    photo = update.message.photo[-1]  # En yüksek çözünürlük
    caption = update.message.caption or ""
    
    product = context.user_data.get('selected_product', 'Bilinmiyor')
    price = context.user_data.get('price', 0)
    
    # Admin'e gönder
    admin_text = f"""🆕 *Yeni Ödeme Bildirimi*

👤 *Kullanıcı:* @{user.username or 'Yok'} (`{user.id}`)
🛍️ *Ürün:* {product}
💰 *Tutar:* {price}₺
📝 *Not:* {caption}

⏳ *İşlem:* Beklemede"""
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Kabul Et", callback_data=f'approve_{user.id}'),
            InlineKeyboardButton("❌ Reddet", callback_data=f'reject_{user.id}')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Fotoğrafı admin'e ilet
    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=photo.file_id,
        caption=admin_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    await update.message.reply_text(
        "⏳ *Dekont Alındı!*\n\nÖdemeniz admin tarafından inceleniyor. "
        "Onaylandığında size bildirilecektir.",
        parse_mode='Markdown'
    )
    return ConversationHandler.END

async def admin_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data.split('_')
    decision = data[0]  # approve veya reject
    user_id = int(data[1])
    
    product = context.user_data.get('selected_product', 'Seçili ürün')
    
    if decision == 'approve':
        # Kullanıcıya onay mesajı
        await context.bot.send_message(
            chat_id=user_id,
            text=f"""✅ *Ödemeniz Onaylandı!*

🛍️ Ürün: {product}
💼 Admin sizinle kısa süre içinde iletişime geçecektir.

ℹ️ Lütfen sabırla bekleyin, admin sizinle özel mesaj yoluyla iletişim kuracaktır.""",
            parse_mode='Markdown'
        )
        
        await query.edit_message_caption(
            caption=query.message.caption + "\n\n✅ *Durum:* ONAYLANDI",
            parse_mode='Markdown'
        )
        
    else:  # reject
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ *Ödemeniz Reddedildi*\n\nLütfen dekontunuzu kontrol edip tekrar deneyin veya admin ile iletişime geçin.",
            parse_mode='Markdown'
        )
        
        await query.edit_message_caption(
            caption=query.message.caption + "\n\n❌ *Durum:* REDDEDİLDİ",
            parse_mode='Markdown'
        )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("İşlem iptal edildi.")
    return ConversationHandler.END

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SELECTING_PRODUCT: [
                CallbackQueryHandler(checker_menu, pattern='^checker_menu$'),
                CallbackQueryHandler(select_product, pattern='^(kart|kanal|hesap|ship|checker_aylik|checker_yillik|back_to_main)$')
            ],
            WAITING_PAYMENT: [
                CallbackQueryHandler(confirm_payment, pattern='^paid$')
            ],
            WAITING_RECEIPT: [
                MessageHandler(filters.PHOTO, receive_receipt)
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(admin_decision, pattern='^(approve|reject)_'))
    
    print("Bot çalışıyor...")
    application.run_polling()

if __name__ == '__main__':
    main()
