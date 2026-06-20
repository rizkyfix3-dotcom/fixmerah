#!/usr/bin/env python3
"""WHATSAPP APPEAL BOT - PART 1 (Config & Classes)"""

import os
import sys
import logging
import json
import smtplib
import imaplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import re
import random
import threading
import asyncio
from email import message_from_bytes
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

# ==================== CONFIG ====================
BOT_TOKEN = os.getenv("BOT_TOKEN", "")  # set in .env or environment
OWNER_ID = int(os.getenv("OWNER_ID", "6937393813"))
BOT_OWNER = os.getenv("BOT_OWNER", "@Newfixredbot")
OWNER_CHANNEL = os.getenv("OWNER_CHANNEL", "https://t.me/Luanyi0035")

# Verifikasi Channel & Group
VERIFICATION_CHANNEL = int(os.getenv("VERIFICATION_CHANNEL", "-1003917661378"))
VERIFICATION_GROUP = int(os.getenv("VERIFICATION_GROUP", "-1004294541134"))
VERIFICATION_CHANNEL_LINK = os.getenv("VERIFICATION_CHANNEL_LINK", "https://t.me/LuanyiOTP")
VERIFICATION_GROUP_LINK = os.getenv("VERIFICATION_GROUP_LINK", "https://t.me/Luanyi0035")

# System Config
MAX_BATCH_SIZE = int(os.getenv("MAX_BATCH_SIZE", "5"))
BATCH_DELAY_SECONDS = int(os.getenv("BATCH_DELAY_SECONDS", "2"))
PREMIUM_COOLDOWN_MINUTES = int(os.getenv("PREMIUM_COOLDOWN_MINUTES", "10"))
EMAIL_CHECK_INTERVAL = int(os.getenv("EMAIL_CHECK_INTERVAL", "3"))  # seconds

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

MAINTENANCE = False

# ==================== PREMIUM SYSTEM ====================
class PremiumSystem:
    def __init__(self):
        self.users_file = "data/users.json"
        self._lock = threading.Lock()
        self.load_data()

    def load_data(self):
        try:
            with self._lock:
                if os.path.exists(self.users_file):
                    with open(self.users_file, 'r') as f:
                        self.data = json.load(f)
                else:
                    self.data = self.create_default_data()
                    self.save_data()
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            self.data = self.create_default_data()
            self.save_data()

    def create_default_data(self):
        return {
            "users": {},
            "premium_users": {},
            "buyer_users": {},
            "owners": {"main_owners": [OWNER_ID], "sub_owners": {}},
            "verified_users": [],
            "processed_emails": [],
            "appeal_tracking": {}
        }

    def save_data(self):
        try:
            os.makedirs("data", exist_ok=True)
            with self._lock:
                with open(self.users_file, 'w') as f:
                    json.dump(self.data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving data: {e}")

    # ==================== VERIFIKASI ====================
    def mark_user_verified(self, user_id):
        user_id_str = str(user_id)
        if user_id_str not in self.data.get("verified_users", []):
            self.data.setdefault("verified_users", []).append(user_id_str)
            self.save_data()
            return True
        return False

    def is_user_verified(self, user_id):
        user_id_str = str(user_id)
        if self.is_any_owner(user_id):
            return True
        return user_id_str in self.data.get("verified_users", [])

    # ==================== OWNER ====================
    def is_any_owner(self, user_id):
        user_id_str = str(user_id)
        # check main owners list and sub owners dict
        if str(OWNER_ID) == user_id_str:
            return True
        if user_id_str in map(str, self.data.get("owners", {}).get("main_owners", [])):
            return True
        return user_id_str in self.data["owners"].get("sub_owners", {})

    def is_main_owner(self, user_id):
        return str(user_id) == str(OWNER_ID)

    def add_sub_owner(self, user_id, username):
        user_id_str = str(user_id)
        if user_id_str not in self.data["owners"]["sub_owners"]:
            self.data["owners"]["sub_owners"][user_id_str] = {
                "username": username,
                "added_date": self.get_realtime_date(),
                "added_by": "main_owner"
            }
            self.save_data()
            return True, f"✅ Sub-owner ditambahkan: {username} (ID: {user_id})"
        return False, f"❌ User sudah menjadi sub-owner"

    def remove_sub_owner(self, user_id):
        user_id_str = str(user_id)
        if user_id_str in self.data["owners"]["sub_owners"]:
            username = self.data["owners"]["sub_owners"][user_id_str].get("username", "Unknown")
            del self.data["owners"]["sub_owners"][user_id_str]
            self.save_data()
            return True, f"✅ Sub-owner dihapus: {username} (ID: {user_id})"
        return False, "❌ User bukan sub-owner"

    # ==================== USER ====================
    def add_user(self, user_id, username):
        user_id_str = str(user_id)
        if user_id_str not in self.data["users"]:
            self.data["users"][user_id_str] = {
                "username": username,
                "join_date": self.get_realtime_date(),
                "fixmerah_count": 0,
                "last_used": None
            }
            self.save_data()
            return True
        return False

    def get_user_access_type(self, user_id):
        user_id_str = str(user_id)
        if self.is_any_owner(user_id):
            return "owner"
        elif user_id_str in self.data["buyer_users"]:
            return "buyer"
        elif user_id_str in self.data["premium_users"]:
            return "premium"
        return "none"

    # ==================== PREMIUM/BUYER ====================
    def add_premium_access(self, user_id, days):
        user_id_str = str(user_id)
        self.data["premium_users"][user_id_str] = {
            "added": self.get_realtime_date(),
            "days": days,
            "expires": self.calculate_expiry_date(days)
        }
        self.save_data()
        return True, f"✅ Premium access ditambahkan! {days} hari."

    def add_buyer_access(self, user_id, days):
        user_id_str = str(user_id)
        self.data["buyer_users"][user_id_str] = {
            "added": self.get_realtime_date(),
            "days": days,
            "expires": self.calculate_expiry_date(days)
        }
        self.save_data()
        return True, f"✅ Buyer access ditambahkan! {days} hari."

    def calculate_expiry_date(self, days):
        return (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    def get_realtime_date(self):
        """Get realtime datetime dengan format lengkap"""
        now = datetime.now()
        hari_list = ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu']
        hari_nama = hari_list[now.weekday()]
        
        bulan_list = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
                     'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember']
        bulan_nama = bulan_list[now.month - 1]
        
        return now.strftime(f"{hari_nama}, %d {bulan_nama} %Y %H:%M:%S")

    def update_fixmerah_count(self, user_id):
        user_id_str = str(user_id)
        if user_id_str in self.data["users"]:
            self.data["users"][user_id_str]["fixmerah_count"] = self.data["users"][user_id_str].get("fixmerah_count", 0) + 1
            self.data["users"][user_id_str]["last_used"] = self.get_realtime_date()
            self.save_data()

    def remove_expired_premium(self, user_id):
        user_id_str = str(user_id)
        if user_id_str in self.data["premium_users"]:
            del self.data["premium_users"][user_id_str]
            self.save_data()
            return True
        return False

    def remove_expired_buyer(self, user_id):
        user_id_str = str(user_id)
        if user_id_str in self.data["buyer_users"]:
            del self.data["buyer_users"][user_id_str]
            self.save_data()
            return True
        return False

    def add_processed_email(self, email_id):
        """Catat email yang sudah diproses"""
        if email_id not in self.data.get("processed_emails", []):
            self.data.setdefault("processed_emails", []).append(email_id)
            if len(self.data["processed_emails"]) > 1000:
                self.data["processed_emails"] = self.data["processed_emails"][-1000:]
            self.save_data()

    def is_email_processed(self, email_id):
        """Cek apakah email sudah diproses"""
        return email_id in self.data.get("processed_emails", [])

    def add_appeal_tracking(self, phone_number, user_id):
        """Track appeal untuk matching dengan reply"""
        appeal_key = self.format_phone_for_tracking(phone_number)
        if appeal_key not in self.data.get("appeal_tracking", {}):
            self.data.setdefault("appeal_tracking", {})[appeal_key] = {
                "user_id": user_id,
                "sent_date": self.get_realtime_date(),
                "phone": phone_number
            }
            self.save_data()

    def get_appeal_user(self, phone_number):
        """Dapatkan user ID dari appeal tracking"""
        appeal_key = self.format_phone_for_tracking(phone_number)
        appeal_data = self.data.get("appeal_tracking", {}).get(appeal_key, {})
        return appeal_data.get("user_id")

    def format_phone_for_tracking(self, phone_number):
        """Format phone untuk tracking, gunakan full normalized digits (lebih aman)"""
        digits = re.sub(r'\D', '', phone_number)
        # use full digits; if too long, keep last 15 for uniqueness across countries
        return digits[-15:]

premium = PremiumSystem()

# ==================== EMAIL SYSTEM ====================
class EmailSystem:
    def __init__(self):
        self.config_file = "data/email_config.json"
        self._lock = threading.Lock()
        self.load_config()
        self.bot_app = None
        self.last_check = {}
        # support email - used for IMAP FROM searching
        self.support_email = os.getenv("SUPPORT_EMAIL", "support@support.whatsapp.com")

    def load_config(self):
        try:
            with self._lock:
                if os.path.exists(self.config_file):
                    with open(self.config_file, 'r') as f:
                        self.config = json.load(f)
                else:
                    self.config = {
                        "active_email": "",
                        "active_password": "",
                        "active_used_count": 0,
                        "email_list": [],
                        "smtp_server": "smtp.gmail.com",
                        "smtp_port": 587,
                        "imap_server": "imap.gmail.com",
                        "imap_port": 993
                    }
                    self.save_config()
        except Exception as e:
            logger.error(f"Error loading email config: {e}")
            self.config = {
                "active_email": "",
                "active_password": "",
                "active_used_count": 0,
                "email_list": [],
                "smtp_server": "smtp.gmail.com",
                "smtp_port": 587,
                "imap_server": "imap.gmail.com",
                "imap_port": 993
            }
            self.save_config()

    def save_config(self):
        try:
            os.makedirs("data", exist_ok=True)
            with self._lock:
                with open(self.config_file, 'w') as f:
                    json.dump(self.config, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving email config: {e}")

    def get_realtime_date(self):
        """Get realtime datetime"""
        now = datetime.now()
        hari_list = ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu']
        hari_nama = hari_list[now.weekday()]
        
        bulan_list = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
                     'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember']
        bulan_nama = bulan_list[now.month - 1]
        
        return now.strftime(f"{hari_nama}, %d {bulan_nama} %Y %H:%M:%S")

    def set_email(self, email_addr, password):
        """Set email baru dengan backup email lama"""
        email_addr = email_addr.strip()
        password = password.replace(" ", "")
        
        # archive current active if exists
        if self.config.get("active_email"):
            old_email_entry = {
                "email": self.config["active_email"],
                "password": self.config["active_password"],
                "added_date": self.get_realtime_date(),
                "status": "backup",
                "used_count": self.config.get("active_used_count", 0)
            }
            email_exists = any(e["email"] == self.config["active_email"] for e in self.config.get("email_list", []))
            if not email_exists:
                self.config["email_list"].append(old_email_entry)
        
        self.config["active_email"] = email_addr
        self.config["active_password"] = password
        self.config["active_used_count"] = 0
        self.save_config()
        
        return True, f"""✅ Email diatur: {email_addr}

📊 *INFO:*
• Email aktif: {email_addr}
• Total email backup: {len(self.config.get('email_list', []))} email
• Waktu: {self.get_realtime_date()}

💾 *EMAIL BACKUP TERSIMPAN:*
Ketik /listemail untuk melihat semua email backup"""

    def get_email_list(self):
        """Ambil daftar semua email (aktif + backup)"""
        emails = []
        
        if self.config.get("active_email"):
            emails.append({
                "email": self.config["active_email"],
                "status": "🟢 AKTIF",
                "added_date": "Current",
                "used_count": self.config.get("active_used_count", 0)
            })
        
        for email_data in self.config.get("email_list", []):
            emails.append({
                "email": email_data.get("email"),
                "status": "🔵 BACKUP",
                "added_date": email_data.get("added_date", "Unknown"),
                "used_count": email_data.get("used_count", 0)
            })
        
        return emails

    def restore_email(self, email_address):
        """Restore email dari backup"""
        email_list = self.config.get("email_list", [])
        
        for email_data in list(email_list):
            if email_data["email"] == email_address:
                if self.config.get("active_email"):
                    old_active = {
                        "email": self.config["active_email"],
                        "password": self.config["active_password"],
                        "added_date": self.get_realtime_date(),
                        "status": "backup",
                        "used_count": self.config.get("active_used_count", 0)
                    }
                    email_list.append(old_active)
                
                self.config["active_email"] = email_data["email"]
                self.config["active_password"] = email_data["password"]
                self.config["active_used_count"] = email_data.get("used_count", 0)
                
                email_list.remove(email_data)
                self.config["email_list"] = email_list
                self.save_config()
                
                return True, f"✅ Email diperbarui ke: {email_address}\n⏰ Waktu: {self.get_realtime_date()}"
        
        return False, f"❌ Email {email_address} tidak ditemukan di backup!"

    def delete_backup_email(self, email_address):
        """Hapus email dari backup"""
        email_list = self.config.get("email_list", [])
        
        for email_data in list(email_list):
            if email_data["email"] == email_address:
                email_list.remove(email_data)
                self.config["email_list"] = email_list
                self.save_config()
                return True, f"✅ Email backup dihapus: {email_address}\n⏰ Waktu: {self.get_realtime_date()}"
        
        return False, f"❌ Email {email_address} tidak ditemukan!"

    def get_best_email(self):
        """Dapatkan email terbaik - prioritas email yang belum digunakan (RANDOM)"""
        emails = self.config.get("email_list", [])
        
        if not emails and not self.config.get("active_email"):
            return None, None
        
        all_emails = []
        if self.config.get("active_email"):
            all_emails.append({
                "email": self.config["active_email"],
                "password": self.config["active_password"],
                "used_count": self.config.get("active_used_count", 0),
                "is_active": True
            })
        
        for email_data in emails:
            all_emails.append({
                "email": email_data.get("email"),
                "password": email_data.get("password"),
                "used_count": email_data.get("used_count", 0),
                "is_active": False
            })
        
        if not all_emails:
            return None, None
        
        # Prioritas: email yang belum digunakan (used_count = 0) - PILIH RANDOM
        unused_emails = [e for e in all_emails if e["used_count"] == 0]
        
        if unused_emails:
            selected = random.choice(unused_emails)
            logger.info(f"✅ Selected unused email (random): {selected['email']}")
        else:
            # Jika semua sudah digunakan, pilih yang used_count terkecil
            min_count = min(e["used_count"] for e in all_emails)
            least_used = [e for e in all_emails if e["used_count"] == min_count]
            selected = random.choice(least_used)
            logger.info(f"✅ Selected least used email (random): {selected['email']}")
        
        return selected["email"], selected["password"]

    def increment_email_usage(self, email_address):
        """Increment used_count untuk email"""
        with self._lock:
            if self.config.get("active_email") == email_address:
                self.config["active_used_count"] = self.config.get("active_used_count", 0) + 1
                self.save_config()
            else:
                email_list = self.config.get("email_list", [])
                for email_data in email_list:
                    if email_data["email"] == email_address:
                        email_data["used_count"] = email_data.get("used_count", 0) + 1
                        self.config["email_list"] = email_list
                        self.save_config()
                        break

    def send_appeal(self, phone_number, user_id):
        """Kirim appeal menggunakan email terbaik dengan template lengkap"""
        
        email_addr, password = self.get_best_email()
        
        if not email_addr or not password:
            return False, "❌ Email belum dikonfigurasi!"

        try:
            formatted_phone = self.format_phone_number(phone_number)
            
            # Buat appeal yang lebih detail
            appeal_body = self.generate_appeal_body(formatted_phone)
            
            msg = MIMEMultipart()
            msg['From'] = email_addr
            msg['To'] = self.support_email
            msg['Subject'] = "Pertanyaan mengenai WhatsApp untuk Android"

            msg.attach(MIMEText(appeal_body, 'plain'))

            server = smtplib.SMTP(
                self.config.get("smtp_server", "smtp.gmail.com"),
                self.config.get("smtp_port", 587)
            )
            server.starttls()
            server.login(email_addr, password)
            server.send_message(msg)
            server.quit()

            # Increment usage count
            self.increment_email_usage(email_addr)
            
            # Track appeal
            premium.add_appeal_tracking(formatted_phone, user_id)
            
            logger.info(f"✅ Email sent successfully from {email_addr} to WhatsApp support for {formatted_phone}")
            return True, f"✅ Appeal terkirim dari: {email_addr}"
            
        except smtplib.SMTPAuthenticationError:
            logger.error(f"SMTP Authentication Error for {email_addr}")
            return False, f"❌ Gagal login email: {email_addr}"
        except smtplib.SMTPException as e:
            logger.error(f"SMTP Error: {e}")
            return False, f"❌ Error SMTP: {str(e)}"
        except Exception as e:
            logger.error(f"Email sending error: {e}")
            return False, f"❌ Error mengirim email: {str(e)}"

    def generate_appeal_body(self, phone_number):
        """Generate appeal body yang detail sesuai template"""
        now = datetime.now()
        current_time = now.strftime("%Y-%m-%d %H:%M:%S")
        
        body = f"""Isi pesan

Hallo WhatsApp kenapa saya tidak bisa login ke akun saya dan menerima notifikasi login tidak tersedia. {phone_number} itu adalah nomor saya yang mengalami masalah tersebut, mohon agar pihak whatsap mengembalikan akses akun saya kembali karena saya yakin tidak melanggar kebijakan dan ketentuan yang diterapkan oleh fihak WhatsApp dan aplikasi saya juga resmi diunduh dari play store..

Terimakasih



--Support Info--
App: com.whatsapp
Architecture: aarch64
AutoConf status: autoconf_server_enabled
Board: RM6769
Build: realme/RMX3910INT/RE5C42:16/BP2A.250605.015/U.R4T2.335c6a3-fe80bb:user/release-keys
CCode: 234 8092628603
CPU ABI: arm64-v8a
Carrier: 3SinyalKuatHemat
Description: 2.26.23.74
Device: RE5C42
Device ID: 0
Device ISO8601: {current_time}
...
pn: {phone_number}"""
        
        return body

    def check_for_replies(self):
        """Check Gmail untuk balasan dari WhatsApp Support"""
        if not self.config.get("active_email") or not self.config.get("active_password"):
            return []

        replies = []
        
        try:
            imap = imaplib.IMAP4_SSL(
                self.config.get("imap_server", "imap.gmail.com"),
                int(self.config.get("imap_port", 993))
            )
            imap.login(self.config["active_email"], self.config["active_password"])
            imap.select("INBOX")
            
            # Use proper IMAP search criteria
            criteria = f'(FROM "{self.support_email}")'
            status, messages = imap.search(None, criteria)
            
            if status == "OK" and messages and messages[0]:
                email_ids = messages[0].split()
                
                for email_id in email_ids[-20:]:  # Ambil 20 email terakhir
                    email_id_str = email_id.decode('utf-8') if isinstance(email_id, bytes) else str(email_id)
                    
                    if premium.is_email_processed(email_id_str):
                        continue
                    
                    status, msg_data = imap.fetch(email_id, '(RFC822)')
                    
                    if status == "OK":
                        msg = message_from_bytes(msg_data[0][1])
                        
                        subject = msg.get("Subject", "No Subject")
                        from_addr = msg.get("From", "Unknown")
                        date = msg.get("Date", "Unknown")
                        
                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                ctype = part.get_content_type()
                                cdisp = part.get_content_disposition()
                                if ctype == "text/plain" and cdisp in (None, "inline"):
                                    payload = part.get_payload(decode=True)
                                    if payload:
                                        try:
                                            body += payload.decode('utf-8', errors='ignore')
                                        except:
                                            body += str(payload)
                        else:
                            payload = msg.get_payload(decode=True)
                            if payload:
                                try:
                                    body = payload.decode('utf-8', errors='ignore')
                                except:
                                    body = str(payload)
                        
                        # mark processed immediately to avoid duplicates
                        premium.add_processed_email(email_id_str)
                        
                        # Extract phone number dari subject atau body (cari di subject dulu)
                        phone_match = re.search(r'\+?[\d\s\-\(\)]{8,}', subject)
                        if not phone_match:
                            phone_match = re.search(r'\+?[\d\s\-\(\)]{8,}', body)
                        phone_number = phone_match.group() if phone_match else None
                        
                        replies.append({
                            "subject": subject,
                            "from": from_addr,
                            "date": date,
                            "body": (body[:500] if body else ""),
                            "email_id": email_id_str,
                            "phone": phone_number,
                            "received_time": self.get_realtime_date()
                        })
            
            imap.close()
            imap.logout()
            
        except Exception as e:
            logger.error(f"Error checking email replies: {e}")
        
        return replies

    def format_phone_number(self, phone):
        """Format nomor telepon ke format internasional"""
        phone = re.sub(r'\D', '', phone)
        if phone.startswith('0'):
            phone = '62' + phone[1:]
        elif phone.startswith('8') and len(phone) <= 11:
            phone = '62' + phone
        if not phone.startswith('+'):
            phone = '+' + phone
        return phone

    def set_bot_app(self, app):
        """Set bot application untuk mengirim notifikasi"""
        self.bot_app = app

email = EmailSystem()