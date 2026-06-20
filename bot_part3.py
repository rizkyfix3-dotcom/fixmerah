#!/usr/bin/env python3
"""
WHATSAPP APPEAL BOT - PART 3 (Main & Run)
"""

import asyncio
import threading
import time
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from bot_part1 import (
    BOT_TOKEN, OWNER_ID, premium, email,
    VERIFICATION_CHANNEL, VERIFICATION_GROUP,
    VERIFICATION_CHANNEL_LINK, VERIFICATION_GROUP_LINK,
    EMAIL_CHECK_INTERVAL
)
from bot_part2 import (
    start_command, button_handler, fixmerah_command, 
    fixmerahall_command, validate_phone, handle_phone_message, get_realtime_date
)

# Global variable untuk bot instance
app_instance = None
_email_thread_stop = threading.Event()

# ==================== EMAIL CHECK TASK (BACKGROUND THREAD) ====================
def check_email_replies_background():
    """Background thread untuk check email replies setiap EMAIL_CHECK_INTERVAL detik"""
    global app_instance, _email_thread_stop

    print("[EMAIL CHECK] ✅ Background thread dimulai")
    
    while not _email_thread_stop.is_set():
        try:
            # lakukan blocking check pada thread (imap is blocking) - aman di thread
            replies = email.check_for_replies()
            
            if replies:
                print(f"[EMAIL CHECK] 🔔 Ditemukan {len(replies)} balasan baru")
                
                for reply in replies:
                    phone_number = reply.get("phone")
                    user_id = premium.get_appeal_user(phone_number) if phone_number else None
                    
                    if user_id:
                        try:
                            notification = f"""📧 BALASAN DARI WHATSAPP! ✅

Nomor: {phone_number}

Detail Balasan:
• Dari: {reply.get('from', 'Unknown')}
• Subject: {reply.get('subject', 'No Subject')}
• Waktu Diterima: {reply.get('received_time', 'Unknown')}

Isi Balasan:
{reply.get('body', 'Tidak ada konten')}

— 
Cek email Anda untuk balasan lengkapnya!
Email: {email.config.get('active_email', 'Not set')}"""
                            
                            # post coroutine ke event loop (safely)
                            if app_instance and getattr(app_instance, "loop", None):
                                asyncio.run_coroutine_threadsafe(
                                    app_instance.bot.send_message(
                                        chat_id=int(user_id),
                                        text=notification
                                    ),
                                    app_instance.loop
                                )
                                print(f"[EMAIL CHECK] ✅ Notifikasi terkirim ke user {user_id}")
                            else:
                                print("[EMAIL CHECK] ❌ App loop belum tersedia, skip notification")
                            
                        except Exception as e:
                            print(f"[EMAIL CHECK] ❌ Error sending notification: {e}")
            
            # sleep interval
            _email_thread_stop.wait(EMAIL_CHECK_INTERVAL)
            
        except Exception as e:
            print(f"[EMAIL CHECK] ❌ Error in background thread: {e}")
            time.sleep(5)

# ==================== OWNER COMMANDS ====================
async def setemail_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set email configuration"""
    user_id = update.effective_user.id
    if not premium.is_any_owner(user_id):
        await update.message.reply_text("❌ Hanya owner!")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Format: `/setemail email@gmail.com password`\n\n"
            "Contoh: `/setemail mybot@gmail.com mypassword123`\n\n"
            "*Note:* Gunakan App Password jika 2FA aktif",
            parse_mode='Markdown'
        )
        return
    
    email_addr = context.args[0]
    password = " ".join(context.args[1:])   
    if "@" not in email_addr or "." not in email_addr:
        await update.message.reply_text("❌ Format email tidak valid!")
        return
    
    success, message = email.set_email(email_addr, password)
    await update.message.reply_text(message, parse_mode='Markdown')

async def listemail_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all email (active & backup)"""
    user_id = update.effective_user.id
    if not premium.is_any_owner(user_id):
        await update.message.reply_text("❌ Hanya owner!")
        return
    
    emails = email.get_email_list()
    
    if not emails:
        await update.message.reply_text("❌ Belum ada email yang dikonfigurasi!")
        return
    
    text = f"📧 *DAFTAR EMAIL BOT*\n\n⏰ Waktu: {get_realtime_date()}\n\n"
    for i, email_data in enumerate(emails, 1):
        text += f"{i}. {email_data['status']}\n"
        text += f"   Email: `{email_data['email']}`\n"
        text += f"   Tanggal: {email_data['added_date']}\n"
        text += f"   Digunakan: {email_data['used_count']} kali\n\n"
    
    text += "\n*PERINTAH:*\n"
    text += "• `/restoreemail email@gmail.com` - Restore email\n"
    text += "• `/deleteemail email@gmail.com` - Hapus email backup"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def restoreemail_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Restore email dari backup"""
    user_id = update.effective_user.id
    if not premium.is_any_owner(user_id):
        await update.message.reply_text("❌ Hanya owner!")
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ Format: `/restoreemail email@gmail.com`\n"
            "Contoh: `/restoreemail backup@gmail.com`",
            parse_mode='Markdown'
        )
        return
    
    email_addr = context.args[0]
    success, message = email.restore_email(email_addr)
    await update.message.reply_text(message, parse_mode='Markdown')

async def deleteemail_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete email backup"""
    user_id = update.effective_user.id
    if not premium.is_any_owner(user_id):
        await update.message.reply_text("❌ Hanya owner!")
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ Format: `/deleteemail email@gmail.com`\n"
            "Contoh: `/deleteemail backup@gmail.com`",
            parse_mode='Markdown'
        )
        return
    
    email_addr = context.args[0]
    success, message = email.delete_backup_email(email_addr)
    await update.message.reply_text(message, parse_mode='Markdown')

async def addowner_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add sub-owner"""
    user_id = update.effective_user.id
    if not premium.is_main_owner(user_id):
        await update.message.reply_text("❌ Hanya main owner bisa menambah sub-owner!")
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ Format: `/addowner user_id`\n"
            "Contoh: `/addowner 123456789`",
            parse_mode='Markdown'
        )
        return
    
    try:
        target_id = int(context.args[0])
        target_user = await context.bot.get_chat(target_id)
        username = target_user.username or target_user.first_name
        
        success, message = premium.add_sub_owner(target_id, username)
        await update.message.reply_text(message)
        
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=f"""👑 SELAMAT! ANDA SEKARANG SUB-OWNER

Halo {target_user.first_name},

Anda sekarang memiliki akses owner di WhatsApp Appeal Bot!

FITUR YANG DIDAPAT:
• Semua perintah owner
• Bisa manage user lain
• Akses statistik lengkap

PERHATIAN:
• Jangan menyalahgunakan akses
• Jaga kerahasiaan data

Ditambahkan oleh: {update.effective_user.first_name}
Waktu: {get_realtime_date()}""",
                parse_mode='Markdown'
            )
        except:
            pass
            
    except ValueError:
        await update.message.reply_text("❌ User ID harus angka!")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def removeowner_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove sub-owner"""
    user_id = update.effective_user.id
    if not premium.is_main_owner(user_id):
        await update.message.reply_text("❌ Hanya main owner bisa menghapus sub-owner!")
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ Format: `/removeowner user_id`\n"
            "Contoh: `/removeowner 123456789`",
            parse_mode='Markdown'
        )
        return
    
    try:
        target_id = int(context.args[0])
        success, message = premium.remove_sub_owner(target_id)
        await update.message.reply_text(message)
        
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=f"""AKSES OWNER DIHAPUS

Halo,

Akses owner Anda telah dihapus dari WhatsApp Appeal Bot.

Jika ini kesalahan, hubungi @Fixmerahbydho

Waktu: {get_realtime_date()}""",
                parse_mode='Markdown'
            )
        except:
            pass
            
    except ValueError:
        await update.message.reply_text("❌ User ID harus angka!")

async def addakses_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add premium access"""
    user_id = update.effective_user.id
    if not premium.is_any_owner(user_id):
        await update.message.reply_text("❌ Hanya owner!")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Format: `/addakses user_id days`\n"
            "Contoh: `/addakses 123456789 30` (30 hari)",
            parse_mode='Markdown'
        )
        return
    
    try:
        target_id = int(context.args[0])
        days = int(context.args[1])
        
        if days <= 0:
            await update.message.reply_text("❌ Days harus lebih dari 0!")
            return
        
        success, message = premium.add_premium_access(target_id, days)
        
        try:
            target_user = await context.bot.get_chat(target_id)
            await context.bot.send_message(
                chat_id=target_id,
                text=f"""SELAMAT! ANDA SEKARANG PREMIUM

Halo {target_user.first_name},

Anda sekarang memiliki akses premium selama {days} hari!

FITUR PREMIUM:
• Unlimited /fixmerah
• Tanpa batas harian
• Prioritas support

Expired: {premium.data['premium_users'][str(target_id)]['expires']}
Ditambahkan: {get_realtime_date()}

Ditambahkan oleh: {update.effective_user.first_name}""",
                parse_mode='Markdown'
            )
        except:
            pass
        
        await update.message.reply_text(message)
        
    except ValueError:
        await update.message.reply_text("❌ ID dan days harus angka!")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def addbuyer_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add buyer access"""
    user_id = update.effective_user.id
    if not premium.is_any_owner(user_id):
        await update.message.reply_text("❌ Hanya owner!")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Format: `/addbuyer user_id days`\n"
            "Contoh: `/addbuyer 123456789 30` (30 hari)",
            parse_mode='Markdown'
        )
        return
    
    try:
        target_id = int(context.args[0])
        days = int(context.args[1])
        
        if days <= 0:
            await update.message.reply_text("❌ Days harus lebih dari 0!")
            return
        
        success, message = premium.add_buyer_access(target_id, days)
        
        try:
            target_user = await context.bot.get_chat(target_id)
            await context.bot.send_message(
                chat_id=target_id,
                text=f"""SELAMAT! ANDA SEKARANG BUYER

Halo {target_user.first_name},

Anda sekarang memiliki akses buyer selama {days} hari!

FITUR BUYER:
• Semua fitur premium
• Batch sending (/fixmerahall)
• Prioritas tinggi
• Support 24/7

Expired: {premium.data['buyer_users'][str(target_id)]['expires']}
Ditambahkan: {get_realtime_date()}

Ditambahkan oleh: {update.effective_user.first_name}""",
                parse_mode='Markdown'
            )
        except:
            pass
        
        await update.message.reply_text(message)
        
    except ValueError:
        await update.message.reply_text("❌ ID dan days harus angka!")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot statistics"""
    user_id = update.effective_user.id
    if not premium.is_any_owner(user_id):
        await update.message.reply_text("❌ Hanya owner!")
        return
    
    total_users = len(premium.data["users"])
    premium_users = len(premium.data["premium_users"])
    buyer_users = len(premium.data["buyer_users"])
    verified = len(premium.data.get("verified_users", []))
    sub_owners = len(premium.data["owners"]["sub_owners"])
    
    total_fixmerah = 0
    today_fixmerah = 0
    today = datetime.now().strftime("%Y-%m-%d")
    
    for user_id_str, user_data in premium.data["users"].items():
        total_fixmerah += user_data.get("fixmerah_count", 0)
        
        last_used = user_data.get("last_used")
        if last_used and last_used.startswith(today):
            today_fixmerah += 1
    
    email_list = email.get_email_list()
    active_email = email.config.get('active_email', 'Not set')
    
    text = f"""STATISTIK BOT

USERS:
• Total Users: {total_users}
• Premium: {premium_users}
• Buyer: {buyer_users}
• Verified: {verified}
• Sub-Owners: {sub_owners}

APPEAL STATS:
• Total Appeal: {total_fixmerah}
• Hari Ini: {today_fixmerah}
• Rata-rata: {total_fixmerah/max(total_users, 1):.1f}

OWNERSHIP:
• Main Owner: {OWNER_ID}
• Sub Owners: {len(premium.data['owners']['sub_owners'])}

EMAIL SYSTEM:
• Email Aktif: {active_email}
• Total Email: {len(email_list)}
• Status: Configured
• Email Acak: AKTIF
• Prioritas: Email belum digunakan

UPDATE: {get_realtime_date()}"""
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast message to all users"""
    user_id = update.effective_user.id
    if not premium.is_any_owner(user_id):
        await update.message.reply_text("❌ Hanya owner!")
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ Format: `/broadcast pesan_anda`\n"
            "Contoh: `/broadcast Update baru tersedia!`",
            parse_mode='Markdown'
        )
        return
    
    message = " ".join(context.args)
    users = premium.data["users"]
    
    if not users:
        await update.message.reply_text("❌ Tidak ada user untuk dikirimi broadcast!")
        return
    
    progress_msg = await update.message.reply_text(
        f"""MEMULAI BROADCAST...

Target: {len(users)} user
Pesan: {message[:50]}...
Mulai: {get_realtime_date()}

Mohon tunggu...""")
    
    sent = 0
    failed = 0
    
    for uid_str in users:
        try:
            await context.bot.send_message(
                chat_id=int(uid_str),
                text=f"""BROADCAST FROM OWNER

{message}

—
WhatsApp Appeal Bot
Owner: @khanzaAura
Waktu: {get_realtime_date()}""",
                parse_mode='Markdown'
            )
            sent += 1
            
            if sent % 10 == 0:
                await progress_msg.edit_text(
                    f"""BROADCAST ONGOING...

Terkirim: {sent}
Gagal: {failed}
Progress: {sent}/{len(users)} ({sent/len(users)*100:.1f}%)""")
            
            await asyncio.sleep(0.2)
            
        except Exception as e:
            failed += 1
    
    await progress_msg.edit_text(f"""BROADCAST SELESAI!

HASIL:
• Berhasil: {sent}
• Gagal: {failed}
• Total: {len(users)}
• Waktu: {get_realtime_date()}""", parse_mode='Markdown')

async def checkreplies_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check email replies manually"""
    user_id = update.effective_user.id
    if not premium.is_any_owner(user_id):
        await update.message.reply_text("❌ Hanya owner!")
        return
    
    status_msg = await update.message.reply_text("Mengecek balasan WhatsApp...")
    
    replies = email.check_for_replies()
    
    if not replies:
        await status_msg.edit_text(f"""CEK SELESAI

Hasil: Tidak ada balasan baru
Waktu: {get_realtime_date()}

Bot otomatis check setiap {EMAIL_CHECK_INTERVAL} detik!""")
        return
    
    reply_text = f"""BALASAN DARI WHATSAPP

Ditemukan: {len(replies)} balasan

—\n"""
    
    for i, reply in enumerate(replies, 1):
        reply_text += f"""{i}. {reply.get('subject', 'No Subject')}
   From: {reply.get('from', 'Unknown')}
   Phone: {reply.get('phone', 'Unknown')}
   Received: {reply.get('received_time', 'Unknown')}
   
"""
    
    reply_text += f"\nWaktu: {get_realtime_date()}"
    
    await status_msg.edit_text(reply_text, parse_mode='Markdown')

# ==================== USER COMMANDS ====================
async def cekakses_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check user access"""
    user_id = update.effective_user.id
    access_type = premium.get_user_access_type(user_id)
    user_data = premium.data["users"].get(str(user_id), {})
    fixmerah_count = user_data.get("fixmerah_count", 0)
    join_date = user_data.get("join_date", "Unknown")
    last_used = user_data.get("last_used", "Belum pernah")
    
    if access_type == "owner":
        status = "ANDA ADALAH OWNER"
        features = "• Akses penuh ke semua fitur\n• Menu Owner tersedia\n• Bisa manage user lain"
        color = "OWNER"
    elif access_type == "buyer":
        status = "ANDA ADALAH BUYER"
        features = "• Fitur /fixmerah & /fixmerahall\n• Akses batch sending\n• Prioritas support"
        color = "BUYER"
    elif access_type == "premium":
        status = "ANDA ADALAH PREMIUM"
        features = "• Fitur /fixmerah unlimited\n• Tanpa batas harian\n• Support reguler"
        color = "PREMIUM"
    else:
        status = "BELUM ADA AKSES KHUSUS"
        features = "• Harus verifikasi dulu (/start)\n• Akses fitur dasar\n• Hubungi owner untuk upgrade"
        color = "FREE"
    
    expiry_info = ""
    if access_type == "premium" and str(user_id) in premium.data["premium_users"]:
        expiry = premium.data["premium_users"][str(user_id)].get("expires", "Unknown")
        expiry_info = f"\nExpired: {expiry}"
    elif access_type == "buyer" and str(user_id) in premium.data["buyer_users"]:
        expiry = premium.data["buyer_users"][str(user_id)].get("expires", "Unknown")
        expiry_info = f"\nExpired: {expiry}"
    
    text = f"""INFO AKUN ANDA

{status}

DATA USER:
• Nama: {update.effective_user.first_name}
• Username: @{update.effective_user.username or 'Tidak ada'}
• ID: {user_id}
• Bergabung: {join_date}

STATISTIK:
• Total appeal: {fixmerah_count}
• Terakhir digunakan: {last_used}{expiry_info}

FITUR YANG DAPAT DIAKSES:
{features}

FITUR BARU:
• Auto-send saat kirim nomor
• Email acak prioritas belum digunakan
• Check reply otomatis {EMAIL_CHECK_INTERVAL} detik
• Timestamp realtime

UPGRADE: Hubungi @khanzaAura"""
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def hubungiowner_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Contact owner"""
    if not context.args:
        await update.message.reply_text(
            "Format: `/hubungiowner pesan_anda`\n"
            "Contoh: `/hubungiowner Saya mau upgrade ke buyer`",
            parse_mode='Markdown'
        )
        return
    
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    username = f"@{update.effective_user.username}" if update.effective_user.username else "No username"
    message = " ".join(context.args)
    
    try:
        await context.bot.send_message(
            chat_id=OWNER_ID,
            text=f"""PESAN DARI USER

User: {user_name}
ID: {user_id}
Username: {username}
Pesan: {message}

Waktu: {get_realtime_date()}""",
            parse_mode='Markdown'
        )
        await update.message.reply_text("Pesan terkirim ke owner!")
    except:
        await update.message.reply_text("Gagal mengirim pesan.\nHubungi langsung: @Fixmerahbydho")

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show menu"""
    await start_command(update, context)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help"""
    help_text = f"""BANTUAN WHATSAPP APPEAL BOT

FITUR UTAMA:
• /start - Mulai bot & verifikasi
• /menu - Tampilkan menu utama
• /help - Bantuan ini
• /about - Info tentang bot

FITUR APPEAL:
• /fixmerah [nomor] - Kirim appeal ke WhatsApp
• /fixmerahall [nomor1 nomor2] - Kirim batch (buyer only)
• Kirim nomor langsung - Auto-send appeal

FITUR USER:
• /cekakses - Cek status akses Anda
• /hubungiowner [pesan] - Hubungi owner

FITUR OWNER:
• /setemail [email] [pass] - Atur email bot
• /listemail - Lihat semua email backup
• /restoreemail [email] - Restore email backup
• /deleteemail [email] - Hapus email backup
• /addowner [user_id] - Tambah sub-owner
• /removeowner [user_id] - Hapus sub-owner
• /addakses [id] [days] - Tambah premium user
• /addbuyer [id] [days] - Tambah buyer user
• /stats - Lihat statistik bot
• /broadcast [pesan] - Kirim pesan ke semua user
• /checkreplies - Cek balasan WhatsApp

Waktu: {get_realtime_date()}

SUPPORT: @khanzaAura"""
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show about info"""
    about_text = f"""WHATSAPP APPEAL BOT v3.1

Versi: 3.1+ (Email Random + Auto Check Reply)
Dibuat oleh: @Luanyi0032
Channel: https://t.me/LuanyiOTP

FITUR UTAMA:
- Verifikasi channel & group wajib
- Kirim appeal via email ke WhatsApp Support
- Support semua kode negara (200+ countries)
- Batch sending untuk buyer
- Multi-level access system
- Email backup system
- Auto-send nomor telepon
- Email acak dengan prioritas yang belum digunakan
- Check reply otomatis setiap {EMAIL_CHECK_INTERVAL} detik
- Notifikasi real-time saat ada balasan
- Timestamp realtime lengkap

STATISTIK:
• Total Users: {len(premium.data['users'])}
• Total Appeal: {sum(u.get('fixmerah_count', 0) for u in premium.data['users'].values())}
• Email Status: Configured
• Total Email: {len(email.get_email_list())}

FITUR BARU v3.1:
- Email Acak (Random Email Selection)
- Auto Check Reply setiap {EMAIL_CHECK_INTERVAL} detik
- Notifikasi User Real-time
- Timestamp Lengkap

SUPPORT: @khanzaAura

Waktu Update: {get_realtime_date()}"""
    
    await update.message.reply_text(about_text, parse_mode='Markdown')

# ==================== MAIN FUNCTION ====================
def main():
    """Start the bot"""
    global app_instance, _email_thread_stop
    
    app = Application.builder().token(BOT_TOKEN).build()
    app_instance = app

    # Set bot app in email system (so it can use when needed)
    try:
        email.set_bot_app(app)
    except Exception:
        pass

    # Ensure the app instance has a loop reference for thread notifications
    try:
        loop = asyncio.get_event_loop()
        app_instance.loop = loop
    except Exception:
        app_instance.loop = None
    
    # Add handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("about", about_command))
    
    # Appeal commands
    app.add_handler(CommandHandler("fixmerah", fixmerah_command))
    app.add_handler(CommandHandler("fixmerahall", fixmerahall_command))
    
    # User commands
    app.add_handler(CommandHandler("cekakses", cekakses_command))
    app.add_handler(CommandHandler("hubungiowner", hubungiowner_command))
    
    # Owner commands
    app.add_handler(CommandHandler("setemail", setemail_command))
    app.add_handler(CommandHandler("listemail", listemail_command))
    app.add_handler(CommandHandler("restoreemail", restoreemail_command))
    app.add_handler(CommandHandler("deleteemail", deleteemail_command))
    app.add_handler(CommandHandler("addowner", addowner_command))
    app.add_handler(CommandHandler("removeowner", removeowner_command))
    app.add_handler(CommandHandler("addakses", addakses_command))
    app.add_handler(CommandHandler("addbuyer", addbuyer_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("checkreplies", checkreplies_command))
    
    # Button handler
    app.add_handler(CallbackQueryHandler(button_handler))
    
    # Auto-send nomor telepon handler - HARUS SEBELUM OTHER HANDLERS
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_phone_message))
    
    # Start background thread untuk check email replies (daemon)
    _email_thread_stop.clear()
    email_thread = threading.Thread(target=check_email_replies_background, daemon=True)
    email_thread.start()
    
    print("="*60)
    print("Bot started successfully!")
    print(f"Owner ID: {OWNER_ID}")
    print(f"Email: {email.config.get('active_email', 'Not set')}")
    print(f"Total Email: {len(email.get_email_list())}")
    print(f"Features: Email Random, Auto Check Reply")
    print(f"Waktu: {get_realtime_date()}")
    print("="*60)
    
    try:
        app.run_polling()
    finally:
        # signal thread to stop when application stops
        _email_thread_stop.set()

if __name__ == "__main__":
    main()