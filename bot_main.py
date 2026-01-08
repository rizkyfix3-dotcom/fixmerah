
#!/usr/bin/env python3
"""
WHATSAPP APPEAL BOT - MAIN RUNNER
"""

import os
import sys

print("="*60)
print("🤖 WHATSAPP APPEAL BOT v3.0")
print("👑 Created by: @Fixmerahbydho")
print("="*60)

# Check Python version
if sys.version_info < (3, 7):
    print("❌ Python 3.7 or higher required!")
    sys.exit(1)

print("📦 Loading modules...")

# Check and create data directory
if not os.path.exists("data"):
    os.makedirs("data")
    print("✅ Created data directory")

# Check if required files exist
required_files = ["bot_part1.py", "bot_part2.py", "bot_part3.py"]
missing_files = []

for file in required_files:
    if not os.path.exists(file):
        missing_files.append(file)

if missing_files:
    print(f"❌ Missing files: {', '.join(missing_files)}")
    print("Please make sure all bot_part files exist!")
    sys.exit(1)

# Try to import modules
try:
    import bot_part1
    import bot_part2
    import bot_part3
    print("✅ All modules loaded successfully!")
    
    # Check dependencies
    print("🔍 Checking dependencies...")
    
    deps = {
        "python-telegram-bot": "telegram",
        "email": "email",
        "smtplib": "smtplib"
    }
    
    missing_deps = []
    for dep_name, dep_module in deps.items():
        try:
            __import__(dep_module)
            print(f"✅ {dep_name}: OK")
        except ImportError:
            missing_deps.append(dep_name)
    
    if missing_deps:
        print(f"\n⚠️ Missing dependencies: {', '.join(missing_deps)}")
        print("Installing required packages...")
        
        if "python-telegram-bot" in missing_deps:
            os.system("pip3 install python-telegram-bot==20.7")
        
        print("\n✅ Dependencies installed!")
    
    print("="*60)
    print("🚀 Starting WhatsApp Appeal Bot...")
    print("="*60)
    
    # Run the bot
    bot_part3.main()
    
except ImportError as e:
    print(f"❌ Import Error: {e}")
    print("\nPlease install missing dependencies:")
    print("pip3 install python-telegram-bot==20.7")
    print("\nOr run: pip3 install -r requirements.txt")
    
except Exception as e:
    print(f"❌ Unexpected Error: {e}")
    print("\nTroubleshooting:")
    print("1. Check your bot token is correct")
    print("2. Make sure all files are in same directory")
    print("3. Check internet connection")
    print("4. Contact @Fixmerahbydho for support")
    
    import traceback
    traceback.print_exc()
    
    # Auto-restart after 30 seconds
    print("\n🔄 Auto-restarting in 30 seconds...")
    import time
    time.sleep(30)
    
    # Restart
    os.execv(sys.executable, ['python3'] + sys.argv)
EOF
