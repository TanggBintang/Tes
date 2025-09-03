# app.py - Service Account Version (Drive dan Sheets)
import os
import logging
import asyncio
import threading
import time
from flask import Flask, request, jsonify
from telegram import Update
from bot import TelegramBot

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration from environment variables
BOT_TOKEN = os.environ.get("BOT_TOKEN")
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
SHEET_NAME = os.environ.get("SHEET_NAME", "Sheet1")  # Default to Sheet1 if not set

# Validate required environment variables
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN environment variable is required!")
    exit(1)

if not SPREADSHEET_ID:
    logger.error("❌ SPREADSHEET_ID environment variable is required!")
    exit(1)

# Log sheet configuration
logger.info(f"📊 Using spreadsheet: {SPREADSHEET_ID}")
logger.info(f"📄 Using sheet: {SHEET_NAME}")

# Validate SHEET_NAME format
if not SHEET_NAME or not SHEET_NAME.strip():
    logger.warning("⚠️ SHEET_NAME is empty, using default 'Sheet1'")
    SHEET_NAME = "Sheet1"
    os.environ["SHEET_NAME"] = SHEET_NAME

# Create Flask app
app = Flask(__name__)

# Global variables
bot = None
loop = None
loop_thread = None
bot_ready = False

def create_and_run_loop():
    """Create and run event loop in dedicated thread"""
    global loop
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        logger.info("🔄 Event loop created and running")
        loop.run_forever()
    except Exception as e:
        logger.error(f"❌ Error in event loop: {e}")

def start_event_loop():
    """Start event loop in background thread"""
    global loop_thread
    loop_thread = threading.Thread(target=create_and_run_loop, daemon=True)
    loop_thread.start()
    
    # Wait for loop to be ready
    time.sleep(0.5)
    return loop is not None

async def initialize_bot_async():
    """Initialize bot asynchronously"""
    global bot, bot_ready
    try:
        logger.info("🤖 Creating TelegramBot instance...")
        bot = TelegramBot(BOT_TOKEN, SPREADSHEET_ID)
        
        logger.info("🔧 Initializing Telegram Application...")
        success = await bot.initialize_application()
        
        if success:
            bot_ready = True
            logger.info("✅ Bot fully initialized and ready")
            return True
        else:
            logger.error("❌ Failed to initialize bot application")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error initializing bot: {e}")
        return False

def initialize_bot():
    """Initialize bot synchronously"""
    if not loop:
        logger.error("❌ Event loop not available")
        return False
    
    try:
        future = asyncio.run_coroutine_threadsafe(initialize_bot_async(), loop)
        return future.result(timeout=60)  # Wait up to 60 seconds
    except Exception as e:
        logger.error(f"❌ Error initializing bot: {e}")
        return False

def test_service_account_access():
    """Test Service Account access for both Drive and Sheets"""
    if not bot or not bot.google_service:
        logger.warning("⚠️ Bot or Google service not available for access test")
        return False
    
    try:
        logger.info("🧪 Testing Service Account access...")
        test_result = bot.google_service.test_service_account_access()
        
        if test_result:
            logger.info("✅ Service Account access test PASSED - Drive and Sheets ready!")
        else:
            logger.warning("⚠️ Service Account access test FAILED - check credentials")
        
        return test_result
        
    except Exception as e:
        logger.error(f"❌ Error testing Service Account: {e}")
        return False

@app.route('/')
def index():
    # Get system info
    system_info = {
        'status': 'running',
        'bot_ready': bot_ready,
        'loop_running': loop is not None and not loop.is_closed(),
        'message': 'Telegram Bot with Service Account (Drive & Sheets)',
        'spreadsheet_config': {
            'spreadsheet_id': SPREADSHEET_ID,
            'sheet_name': SHEET_NAME
        },
        'services': {
            'drive': 'service_account',
            'sheets': 'service_account'
        }
    }
    
    # Get service account info if available
    if bot and bot.google_service:
        try:
            service_info = bot.google_service.get_service_account_info()
            if service_info:
                system_info['service_account_info'] = service_info
        except Exception as e:
            logger.error(f"Error getting service account info: {e}")
    
    return jsonify(system_info)

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy' if bot_ready else 'initializing',
        'bot': 'ready' if bot_ready else 'not_ready',
        'loop': 'running' if loop and not loop.is_closed() else 'not_running',
        'services': {
            'drive_service_account': 'ready' if (bot and bot.google_service and bot.google_service.service_drive) else 'not_ready',
            'sheets_service_account': 'ready' if (bot and bot.google_service and bot.google_service.service_sheets) else 'not_ready'
        }
    })

@app.route('/test-service-account')
def test_service_account_endpoint():
    """Test endpoint for Service Account access"""
    try:
        if not bot or not bot.google_service:
            return jsonify({
                'status': 'error',
                'message': 'Bot or Google service not available'
            }), 503
        
        # Test Service Account access
        access_test = test_service_account_access()
        
        # Get service account info
        service_account_info = bot.google_service.get_service_account_info()
        
        # Get quota info
        quota_info = bot.google_service.get_drive_quota_info()
        
        return jsonify({
            'status': 'success' if access_test else 'failed',
            'service_account_working': access_test,
            'service_account_info': service_account_info,
            'quota_info': quota_info,
            'message': 'Service Account test completed'
        })
        
    except Exception as e:
        logger.error(f"❌ Error in Service Account test endpoint: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/cleanup')
def cleanup_endpoint():
    """Cleanup endpoint for service account files"""
    try:
        if not bot or not bot.google_service:
            return jsonify({
                'status': 'error',
                'message': 'Bot or Google service not available'
            }), 503
        
        # Service account cleanup
        cleanup_result = bot.google_service.cleanup_service_account_files()
        
        return jsonify({
            'status': 'success',
            'message': 'Service Account manages its own files',
            'note': 'Files are owned by service account - cleanup handled automatically'
        })
        
    except Exception as e:
        logger.error(f"❌ Error in cleanup endpoint: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        # Check if bot is ready
        if not bot_ready or not bot:
            logger.warning("⚠️ Bot not ready, ignoring webhook")
            return jsonify({'status': 'bot_not_ready'}), 503
        
        # Check loop
        if not loop or loop.is_closed():
            logger.error("❌ Event loop not available")
            return jsonify({'status': 'loop_error'}), 503
        
        # Get and validate JSON data
        json_data = request.get_json(force=True)
        if not json_data:
            logger.error("❌ Empty JSON data received")
            return jsonify({'status': 'invalid_data'}), 400
        
        logger.info(f"📨 Processing webhook update")
        
        try:
            # Create Update object
            update = Update.de_json(json_data, bot.application.bot)
            
            # Schedule processing (don't wait for result)
            future = asyncio.run_coroutine_threadsafe(
                bot.process_update(update), 
                loop
            )
            
            logger.info("✅ Update queued successfully")
            return jsonify({'status': 'ok'})
            
        except Exception as parse_error:
            logger.error(f"❌ Error parsing update: {parse_error}")
            return jsonify({'status': 'parse_error'}), 400
        
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# Application startup
def startup():
    global bot_ready
    
    logger.info("🚀 Starting Telegram Bot with Service Account for Drive & Sheets...")
    
    # Start event loop
    logger.info("⚡ Starting event loop...")
    if not start_event_loop():
        logger.error("❌ Failed to start event loop")
        exit(1)
    
    # Initialize bot
    logger.info("🤖 Initializing bot...")
    if not initialize_bot():
        logger.error("❌ Failed to initialize bot")
        exit(1)
    
    # Test Service Account capability
    logger.info("🧪 Testing Service Account access...")
    service_account_test_passed = test_service_account_access()
    
    if service_account_test_passed:
        logger.info("✅ SERVICE ACCOUNT WORKING - Both Drive and Sheets ready!")
    else:
        logger.warning("⚠️ SERVICE ACCOUNT NOT WORKING - Check credentials!")
        logger.warning("⚠️ Required: GOOGLE_SERVICE_ACCOUNT_KEY, PARENT_FOLDER_ID, OWNER_EMAIL")
    
    logger.info("✅ Application startup complete!")

# Run startup
startup()

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🌐 Starting Flask server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
