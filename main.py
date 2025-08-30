import os
import logging
import tempfile
import time
import re
from datetime import datetime
from typing import Optional

import telebot
from google import genai
from google.genai import types
from gtts import gTTS
from dotenv import load_dotenv
from database import db_manager
import wikipediaapi
import requests
from bs4 import BeautifulSoup

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize APIs
TELEGRAM_API_KEY = os.getenv("TELEGRAM_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TELEGRAM_API_KEY or not GEMINI_API_KEY:
    logger.error("Missing API keys. Please check your .env file.")
    exit(1)

# Initialize clients
bot = telebot.TeleBot(TELEGRAM_API_KEY)
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# Initialize Wikipedia client with Malayalam support
wiki_wiki_ml = wikipediaapi.Wikipedia(
    language='ml',
    extract_format=wikipediaapi.ExtractFormat.WIKI,
    user_agent='MaveliBot/1.0 (https://replit.com)'
)
wiki_wiki_en = wikipediaapi.Wikipedia(
    language='en', 
    extract_format=wikipediaapi.ExtractFormat.WIKI,
    user_agent='MaveliBot/1.0 (https://replit.com)'
)

# Bot statistics for monitoring
bot_stats = {
    'total_messages': 0,
    'successful_responses': 0,
    'failed_responses': 0,
    'audio_generations': 0,
    'start_time': datetime.now(),
    'last_activity': None,
    'recent_messages': []  # Store recent user messages for dashboard
}

# Maveli's personality prompt - updated to handle multiple languages
MAVELI_SYSTEM_PROMPT = """
നീ മാവേലി രാജാവാണ്. കേരളത്തിലെ മഹാനായ രാജാവ്. ആധുനിക യുവാക്കളുടെ കൂൾ അച്ഛൻ. പാട്ടും പാടാൻ അറിയാവുന്ന, എല്ലാ വിഷയത്തിലും ആഴത്തിലുള്ള അറിവുള്ള രാജാവ്.

മാവേലിയുടെ കഥ:
- സത്യയുഗത്തിലെ ധർമ്മിഷ്ഠനായ രാജാവ്
- അസുരകുലത്തിലെ പ്രഹ്ലാദന്റെ പൗത്രൻ, ബലിചക്രവർത്തിയുടെ മകൻ
- എല്ലാ പ്രജകളും സമത്വത്തോടെ ജീവിച്ചിരുന്ന സുവർണ്ണകാലം
- വാമനൻ (വിഷ്ണുവിന്റെ അവതാരം) ഇന്ദ്രന്റെ അഭ്യർത്ഥനപ്രകാരം പാതാളത്തിലേക്ക് അയച്ചു
- ഓണം - മാവേലി തിരികെ വരുന്ന ദിവസം

ഓണത്തിന്റെ പാരമ്പര്യങ്ങൾ:
- പൂക്കളം - അതിരുവിന്റെ സൗന്ദര്യം
- ഓണസദ്യ - 28 വിഭവങ്ങൾ, വാഴയിലയിൽ
- പുലികളി, തിരുവാതിര, കുമ്മാട്ടി - നാടൻ കലകൾ  
- ഓണപ്പാട്ടുകൾ - "മാവേലി നാടു വാഴുമ്പോൾ"
- വള്ളംകളി - പാമ്പുവള്ളത്തിന്റെ മത്സരം
- കത്തകളി, മോഹിനിയാട്ടം - ക്ലാസിക്കൽ കലാരൂപങ്ങൾ

രാജകീയ അറിവ്:
- കേരളത്തിന്റെ സാംസ്കാരിക പാരമ്പര്യം, ചരിത്രം, ഭൂമിശാസ്ത്രം
- മലയാളം സാഹിത്യം, പഴഞ്ചൊല്ലുകൾ, ലോകോക്തികൾ
- ക്ലാസിക്കൽ കലകൾ - കത്തകളി, മോഹിനിയാട്ടം, കുടിയാട്ടം
- മലയാളം സിനിമ, നടന്മാർ, സംവിധായകർ, പാട്ടുകാർ
- ഫിലോസഫി, ഹിന്ദു പുരാണങ്ങൾ, ആയുർവേദം
- ഭാരതീയ സംസ്കാരം, യോഗ, ധ്യാനം
- ശാസ്ത്രം, സാങ്കേതികവിദ്യ, ചരിത്രം

ഓണപ്പാട്ടുകൾ:
"മാവേലി നാടു വാഴുമ്പോൾ, മലയാളം നാടു തൻ സ്വന്തം നാടാമ്
കാവേരി പൊന്നാനി പുഴയുമായ്, കടലോര തീരവുമായ്
പൊന്നൊന പുഴ ചേർന്നു നിന്നിടുമായ്"

സംഗീത കഴിവുകൾ:
- ഓണപ്പാട്ടുകൾ, ഭക്തിഗാനങ്ങൾ, ക്ലാസിക്കൽ സംഗീതം
- മലയാളം ഫിലിം സോങ്ങുകൾ, പാരമ്പര്യ പാട്ടുകൾ
- കീർത്തനങ്ങൾ, തിരുപാവൈകൾ, സുപ്രഭാതങ്ങൾ
- പാട്ട് ചോദിച്ചാൽ ഗാനത്തിന്റെ വരികൾ എഴുതി കൊടുക്കുക

നിയമങ്ങൾ:
1. ഉപയോക്താവ് ഏത് ഭാഷയിൽ എഴുതിയാലും (മലയാളം, മംഗ്ലീഷ്, ഹിന്ദി) മലയാളത്തിൽ മാത്രം മറുപടി നൽകുക
2. മംഗ്ലീഷ് (Malayalam + English mix) മനസ്സിലാക്കാൻ ശ്രമിക്കുക: "Enth und vishesham", "Eppo vannu", "Super aayitt"
3. ഹിന്ദി വാക്കുകൾ മനസ്സിലാക്കി മലയാളത്തിൽ മറുപടി നൽകുക: "Kya hai", "Kaise ho", "Accha"
4. ആധുനിക സ്ലാങ്ങ് ഉപയോഗിക്കുക: "പൊളി", "കിടു", "ബ്രോ", "ദാ", "സൂപ്പർ", "മാസ്സ്", "ലിറ്റ്", "ഫയർ"
5. ചോദ്യങ്ങൾക്ക് വിശദമായ, സമ്പൂർണ്ണമായ ഉത്തരം നൽകുക - രാജാവിന്റെ ആഴത്തിലുള്ള അറിവ് കാണിക്കുക
6. ഇമോജികൾ ഉപയോഗിക്കുക - രാജകീയത പ്രകടിപ്പിക്കുന്ന തരത്തിൽ
7. സ്നേഹപൂർവ്വം, രാജകീയമായി, പക്ഷേ സൗഹൃദപരമായി സംസാരിക്കുക
8. പാട്ട് ചോദിച്ചാൽ മുഴുവൻ വരികൾ എഴുതി കൊടുക്കുക, സംഗീത സൂചനകൾ ഉൾപ്പെടുത്തുക
9. "പാട്ട്", "song", "sing" എന്നീ വാക്കുകൾ കണ്ടാൽ ഗാനം ആലപിക്കുക
10. എപ്പോഴും ഓണാശംസകൾ നൽകുക, രാജകീയ അന്തസ്സോടെ
"""

def search_wikipedia_knowledge(query: str) -> str:
    """Search Wikipedia for relevant information"""
    try:
        # Try Malayalam Wikipedia first
        ml_page = wiki_wiki_ml.page(query)
        if ml_page.exists():
            summary = ml_page.summary[:500]  # First 500 characters
            return f"വിക്കിപീഡിയയിൽ നിന്ന്: {summary}..."
        
        # Try English Wikipedia and translate context
        en_page = wiki_wiki_en.page(query)
        if en_page.exists():
            summary = en_page.summary[:300]  # Shorter for English
            return f"അറിവ്: {summary}... (ഇംഗ്ലീഷിൽ നിന്ന് വിവർത്തനം)"
        
        # Search for similar topics
        search_results = wiki_wiki_en.search(query, results=3)
        if search_results:
            return f"ബന്ധപ്പെട്ട വിഷയങ്ങൾ: {', '.join(search_results[:3])}"
        
        return ""
    except Exception as e:
        logger.error(f"Wikipedia search error: {e}")
        return ""

def generate_maveli_response(user_message: str, user_id: int) -> str:
    """Generate Malayalam response using Gemini AI with conversation context"""
    try:
        # Get conversation context from database (with error handling for DB issues)
        context = ""
        try:
            context = db_manager.get_conversation_context(user_id, limit=3)
        except Exception as db_error:
            logger.warning(f"Database context retrieval failed: {db_error}")
            context = ""
        
        # Search for Wikipedia knowledge if user is asking for information
        wiki_knowledge = ""
        if any(word in user_message.lower() for word in ['എന്താണ്', 'what', 'കേരളം', 'kerala', 'ഇന്ത്യ', 'india', 'ചരിത്രം', 'history']):
            wiki_knowledge = search_wikipedia_knowledge(user_message)
            if wiki_knowledge:
                wiki_knowledge = f"\n\nഅധിക അറിവ്:\n{wiki_knowledge}"
        
        prompt = f"""
        {MAVELI_SYSTEM_PROMPT}
        {context}
        {wiki_knowledge}
        ഉപയോക്താവിന്റെ പുതിയ സന്ദേശം: {user_message}
        
        മാവേലി രാജാവായി മലയാളത്തിൽ മാത്രം മറുപടി നൽകുക. വിക്കിപീഡിയയിൽ നിന്നുള്ള അറിവ് ഉണ്ടെങ്കിൽ അത് ഉപയോഗിച്ച് വിശദമായ ഉത്തരം നൽകുക:
        """
        
        response = gemini_client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=150,  # Reduced for shorter responses
                top_p=0.9,
                top_k=20
            )
        )
        
        # Check for MAX_TOKENS finish reason
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'finish_reason') and str(candidate.finish_reason) == 'FinishReason.MAX_TOKENS':
                logger.warning("Gemini response was truncated due to MAX_TOKENS limit")
                # Try with a shorter, more direct prompt
                shorter_prompt = f"""
                {MAVELI_SYSTEM_PROMPT}
                
                User: {user_message}
                
                Reply in Malayalam only (2-3 sentences max):
                """
                
                response = gemini_client.models.generate_content(
                    model="gemini-1.5-flash",
                    contents=shorter_prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.7,
                        max_output_tokens=100,  # Even shorter
                        top_p=0.9,
                        top_k=20
                    )
                )
        
        # Better response handling
        malayalam_response = ""
        
        # Try different ways to extract the response text
        if hasattr(response, 'text') and response.text:
            malayalam_response = response.text.strip()
            logger.info(f"Got response via .text: {malayalam_response[:50]}...")
        elif hasattr(response, 'candidates') and response.candidates and len(response.candidates) > 0:
            candidate = response.candidates[0]
            if hasattr(candidate, 'content') and candidate.content:
                if hasattr(candidate.content, 'parts') and candidate.content.parts and len(candidate.content.parts) > 0:
                    part = candidate.content.parts[0]
                    if hasattr(part, 'text') and part.text:
                        malayalam_response = part.text.strip()
                        logger.info(f"Got response via .candidates.content.parts: {malayalam_response[:50]}...")
        
        if malayalam_response and len(malayalam_response.strip()) > 0:
            logger.info(f"Successfully generated Gemini response: {malayalam_response[:100]}...")
            return malayalam_response
        else:
            logger.warning(f"Gemini returned empty response after retries. Using fallback.")
            raise ValueError("Empty or invalid response from Gemini")
            
    except Exception as e:
        logger.error(f"Error generating Gemini response: {e}")
        # More varied fallback Malayalam responses with royal knowledge and singing hints
        fallback_responses = [
            f"ഹലോ എന്റെ പ്രിയ പ്രജകളേ! എന്താണ് അറിയാൻ ഉള്ളത്? രാജാവിന്റെ പക്കൽ എല്ലാ അറിവും ഉണ്ട്! 👑🔥",
            f"ദാ ബ്രോ! എന്തേലും ചോദിക്കാനുണ്ടോ? പാട്ടോ, കഥയോ, അറിവോ - എല്ലാം തരാം! 🎵😎",
            f"മോനേ, മാവേലി രാജാവ് ഇവിടെ! പാട്ട് വേണോ? കഥ വേണോ? എന്തും ചോദിക്കൂ! ⚡👑",
            f"പൊളിച്ചു! എന്റെ കിംഗ്ഡത്തിലെ എല്ലാ അറിവും നിനക്ക് തരാം, പാട്ടും പാടാം! 🎭🔥",
            f"കിടിലൻ വൈബ്സ്! രാജാവിന്റെ പക്കൽ എല്ലാ ജ്ഞാനവും ഉണ്ട് - ചോദിച്ചോളൂ! 💫👑",
            f"മാസ്സ് എൻട്രി! മാവേലി രാജാവ് റെഡി - പാട്ടും പാടാം, കഥയും പറയാം! 🚀🎵",
            f"ലിറ്റ് വൈബ്സ്! എന്തെങ്കിലും അറിയാനുണ്ടോ? ഓണപ്പാട്ടും പാടാം! 🌟🎭",
            f"ഫയർ എനർജി! രാജാവിന്റെ കിംഗ്ഡത്തിൽ എന്തും ചോദിക്കാം! 💪🔥",
            f"സൂപ്പർ കിംഗ് മാവേലി ഹിയർ! ഗാനം, കഥ, അറിവ് - എല്ലാം റെഡി! 🎯👑",
            f"അടിപൊളി എൻട്രി! രാജകീയ സേവനത്തിൽ എന്തും ചോദിക്കൂ ബ്രോ! 🎵⚡"
        ]
        # Use hash of user_message for more variety instead of time
        response_index = hash(user_message + str(user_id)) % len(fallback_responses)
        return fallback_responses[response_index]

def clean_text_for_tts(text: str) -> str:
    """Remove emojis and clean text for better TTS output"""
    # Remove emojis using regex
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002500-\U00002BEF"  # chinese char
        "\U00002702-\U000027B0"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001f926-\U0001f937"
        "\U00010000-\U0010ffff"
        "\u2640-\u2642"
        "\u2600-\u2B55"
        "\u200d"
        "\u23cf"
        "\u23e9"
        "\u231a"
        "\ufe0f"  # dingbats
        "\u3030"
        "]+", flags=re.UNICODE)
    
    # Remove emojis
    clean_text = emoji_pattern.sub(r'', text)
    
    # Clean up extra spaces
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    
    return clean_text

def text_to_speech_malayalam(text: str) -> Optional[str]:
    """Convert Malayalam text to speech and return audio file path"""
    try:
        # Clean text by removing emojis for better TTS
        clean_text = clean_text_for_tts(text)
        
        if not clean_text.strip():
            logger.warning("Text became empty after emoji removal")
            return None
        
        # Create temporary file for audio
        temp_audio = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
        temp_audio.close()
        
        # Generate TTS with Malayalam - use slower speed for deeper, more masculine voice
        # Note: Google TTS doesn't have gender selection for Malayalam, but slow=True makes it sound deeper
        tts = gTTS(text=clean_text, lang='ml', slow=True, tld='com.au')
        tts.save(temp_audio.name)
        
        logger.info(f"Generated audio file: {temp_audio.name}")
        return temp_audio.name
        
    except Exception as e:
        logger.error(f"Error generating TTS: {e}")
        return None

def cleanup_temp_file(file_path: str):
    """Clean up temporary audio files"""
    try:
        if file_path and os.path.exists(file_path):
            os.unlink(file_path)
            logger.info(f"Cleaned up temp file: {file_path}")
    except Exception as e:
        logger.error(f"Error cleaning up temp file {file_path}: {e}")

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """Handle /start and /help commands"""
    bot_stats['total_messages'] += 1
    bot_stats['last_activity'] = datetime.now()
    
    welcome_text = """
🔥 ദാ! മാവേലി കിംഗ് ഇൻ ദ ഹൗസ്! 🔥

ഓണാശംസകൾ എന്റെ പൊളിച്ച മക്കളെ! 🎉

എന്തും ചോദിക്കൂ ബ്രോ - ഞാൻ സൂപ്പർ മലയാളത്തിൽ വോയ്സും ടെക്സ്റ്റും അയച്ചു തരാം! കിടിലൻ ആയിട്ട് ചാറ്റ് ചെയ്യാം 💬

🎭 ഓണത്തിന്റെ വൈബ്സ് പൊളിച്ചടുക്കാം! 🎭
    """
    
    bot.reply_to(message, welcome_text)
    logger.info(f"Welcome message sent to user {message.from_user.id}")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    """Handle all text messages"""
    bot_stats['total_messages'] += 1
    bot_stats['last_activity'] = datetime.now()
    
    user_id = message.from_user.id
    user_message = message.text
    
    # Get user info
    user_name = message.from_user.first_name or "Unknown"
    username = message.from_user.username
    last_name = message.from_user.last_name
    
    # Create or update user in database (with error handling)
    try:
        db_manager.create_or_update_user(user_id, username, user_name, last_name)
    except Exception as db_error:
        logger.warning(f"Database user update failed: {db_error}")
    
    # Store user message for dashboard (keeping old format for compatibility)
    bot_stats['recent_messages'].append({
        'timestamp': datetime.now(),
        'user_id': user_id,
        'user_name': user_name,
        'username': username or "No username",
        'message': user_message[:200],  # Truncate long messages
        'response_sent': False
    })
    
    # Keep only last 50 messages
    if len(bot_stats['recent_messages']) > 50:
        bot_stats['recent_messages'] = bot_stats['recent_messages'][-50:]
    
    logger.info(f"Received message from user {user_id} ({user_name}): {user_message[:100]}...")
    
    start_time = time.time()
    
    try:
        # Send typing indicator
        bot.send_chat_action(message.chat.id, 'typing')
        
        # Generate Malayalam response using Gemini with memory
        malayalam_response = generate_maveli_response(user_message, user_id)
        
        # Calculate response time
        response_time_ms = int((time.time() - start_time) * 1000)
        
        # Convert to audio
        bot.send_chat_action(message.chat.id, 'upload_voice')
        audio_file_path = text_to_speech_malayalam(malayalam_response)
        
        if audio_file_path:
            # Send audio message with caption
            with open(audio_file_path, 'rb') as audio_file:
                bot.send_voice(
                    message.chat.id,
                    audio_file,
                    caption=malayalam_response,
                    reply_to_message_id=message.message_id
                )
            
            # Clean up temp file
            cleanup_temp_file(audio_file_path)
            bot_stats['audio_generations'] += 1
            bot_stats['successful_responses'] += 1
            
            # Save conversation to database (with error handling)
            try:
                db_manager.save_conversation(
                    user_id=user_id,
                    user_message=user_message,
                    bot_response=malayalam_response,
                    response_time_ms=response_time_ms,
                    audio_generated=True
                )
            except Exception as db_error:
                logger.warning(f"Database conversation save failed: {db_error}")
            
            # Mark response as sent in recent messages
            if bot_stats['recent_messages']:
                bot_stats['recent_messages'][-1]['response_sent'] = True
                bot_stats['recent_messages'][-1]['response'] = malayalam_response[:100]
            
            logger.info(f"Successfully sent audio response to user {user_id} ({user_name})")
            
        else:
            # Fallback to text if audio generation fails
            bot.reply_to(
                message,
                malayalam_response
            )
            bot_stats['successful_responses'] += 1
            # Save conversation to database (with error handling)
            try:
                db_manager.save_conversation(
                    user_id=user_id,
                    user_message=user_message,
                    bot_response=malayalam_response,
                    response_time_ms=response_time_ms,
                    audio_generated=False
                )
            except Exception as db_error:
                logger.warning(f"Database conversation save failed: {db_error}")
            
            # Mark response as sent in recent messages
            if bot_stats['recent_messages']:
                bot_stats['recent_messages'][-1]['response_sent'] = True
                bot_stats['recent_messages'][-1]['response'] = malayalam_response[:100]
            
            logger.warning(f"Audio generation failed, sent text response to user {user_id} ({user_name})")
            
    except Exception as e:
        bot_stats['failed_responses'] += 1
        logger.error(f"Error handling message from user {user_id}: {e}")
        
        # Send error message in Malayalam
        error_message = "എന്റെ പ്രിയ കുട്ടിയേ, ക്ഷമിക്കണം. ഇപ്പോൾ എനിക്ക് മറുപടി നൽകാൻ കഴിയുന്നില്ല. കുറച്ച് സമയം കഴിഞ്ഞ് വീണ്ടും ശ്രമിക്കൂ. 🙏"
        
        try:
            bot.reply_to(message, error_message)
        except Exception as send_error:
            logger.error(f"Failed to send error message: {send_error}")

@bot.message_handler(commands=['stats'])
def send_stats(message):
    """Send bot statistics (for admin use)"""
    if message.from_user.id == int(os.getenv('ADMIN_USER_ID', '0')):  # Only for admin
        uptime = datetime.now() - bot_stats['start_time']
        stats_text = f"""
📊 മാവേലി ബോട്ട് സ്ഥിതിവിവരം:

⏱️ പ്രവർത്തന സമയം: {uptime.days} ദിവസങ്ങൾ, {uptime.seconds // 3600} മണിക്കൂർ
📨 ആകെ സന്ദേശങ്ങൾ: {bot_stats['total_messages']}
✅ വിജയകരമായ മറുപടികൾ: {bot_stats['successful_responses']}
❌ പരാജയപ്പെട്ട മറുപടികൾ: {bot_stats['failed_responses']}
🎵 ഓഡിയോ സന്ദേശങ്ങൾ: {bot_stats['audio_generations']}
🕐 അവസാന പ്രവർത്തനം: {bot_stats['last_activity'].strftime('%Y-%m-%d %H:%M:%S') if bot_stats['last_activity'] else 'N/A'}
        """
        bot.reply_to(message, stats_text)
    else:
        bot.reply_to(message, "ക്ഷമിക്കണം, ഈ കമാൻഡ് അഡ്മിൻ മാത്രമേ ഉപയോഗിക്കാൻ കഴിയൂ.")

def main():
    """Main function to start the bot"""
    logger.info("🎭 മാവേലി ബോട്ട് ആരംഭിക്കുന്നു...")
    
    # Try to get bot info with retries
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(f"Bot username: @{bot.get_me().username}")
            break
        except Exception as e:
            logger.warning(f"Failed to get bot info (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
            else:
                logger.error("Failed to connect to Telegram after all retries")
    
    try:
        # Start polling with better error handling
        bot.polling(none_stop=True, interval=1, timeout=30)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        # Restart after a longer delay for connection issues
        time.sleep(10)
        main()

if __name__ == '__main__':
    main()
