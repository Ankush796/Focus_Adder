import asyncio
import logging
from telethon import TelegramClient, events, Button, functions, errors
from telethon.sessions import StringSession
from config import Config
import database as db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Start Manager Bot
bot = TelegramClient('ManagerBot', Config.API_ID, Config.API_HASH).start(bot_token=Config.BOT_TOKEN)

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    if event.sender_id != Config.ADMIN_ID: return
    
    sessions = await db.get_sessions()
    src = await db.get_val('src')
    trg = await db.get_val('trg')
    
    text = (f"🚀 **Adder Pro Panel (MongoDB Edition)**\n\n"
            f"Linked IDs: `{len(sessions)}`\n"
            f"Source: `{src or 'Not Set'}`\n"
            f"Target: `{trg or 'Not Set'}`")
    
    buttons = [
        [Button.inline("➕ Add Account", data="login")],
        [Button.inline("⚙️ Set Groups", data="groups")],
        [Button.inline("▶️ Start Task", data="start"), Button.inline("📊 Stats", data="stats")]
    ]
    await event.respond(text, buttons=buttons)

@bot.on(events.CallbackQuery(data="login"))
async def login_call(event):
    async with bot.conversation(event.chat_id) as conv:
        await conv.send_message("📱 Enter Phone Number (with +):")
        phone = (await conv.get_response()).text
        
        client = TelegramClient(StringSession(), Config.API_ID, Config.API_HASH)
        await client.connect()
        
        try:
            hash_obj = await client.send_code_request(phone)
            await conv.send_message("📩 Enter OTP:")
            otp = (await conv.get_response()).text
            
            try:
                await client.sign_in(phone, code=otp)
            except errors.SessionPasswordNeededError:
                await conv.send_message("🔐 2FA Password Required:")
                pwd = (await conv.get_response()).text
                await client.sign_in(password=pwd)
            
            # String session generation
            string = client.session.save()
            await db.save_session(phone, string)
            await conv.send_message(f"✅ Success! {phone} added to MongoDB.")
        except Exception as e:
            await conv.send_message(f"❌ Error: {str(e)}")
        finally:
            await client.disconnect()

@bot.on(events.CallbackQuery(data="groups"))
async def groups_call(event):
    async with bot.conversation(event.chat_id) as conv:
        await conv.send_message("📤 Enter Source Group link:")
        src = (await conv.get_response()).text
        await conv.send_message("📥 Enter Target Group link:")
        trg = (await conv.get_response()).text
        await db.set_val('src', src)
        await db.set_val('trg', trg)
        await conv.send_message("✅ Target/Source Saved!")

# --- THE ADDER ENGINE ---

async def adder_worker():
    while True:
        src = await db.get_val('src')
        trg = await db.get_val('trg')
        sessions = await db.get_sessions()
        
        if not src or not trg or not sessions:
            await asyncio.sleep(60)
            continue
        
        logger.info("Starting a new Hourly Rotation Cycle...")
        
        # Scrape members (using first healthy account)
        try:
            first_phone, first_str = list(sessions.items())[0]
            async with TelegramClient(StringSession(first_str), Config.API_ID, Config.API_HASH) as scraper:
                participants = await scraper.get_participants(src, aggressive=True)
                # Filtering active & non-added members
                members = [u for u in participants if not u.bot and not await db.is_added(u.id)]
        except Exception as e:
            logger.error(f"Scrape failed: {e}")
            await asyncio.sleep(60)
            continue

        idx = 0
        for phone, string in sessions.items():
            if idx >= len(members): break
            
            logger.info(f"Using Account: {phone}")
            try:
                async with TelegramClient(StringSession(string), Config.API_ID, Config.API_HASH) as adder:
                    # Point #6: Direct Join
                    try: 
                        await adder(functions.channels.JoinChannelRequest(trg))
                    except: 
                        pass
                    
                    added_this_id = 0
                    while added_this_id < Config.LIMIT_PER_ACC and idx < len(members):
                        user = members[idx]
                        idx += 1
                        
                        try:
                            await adder(functions.channels.InviteToChannelRequest(trg, [user]))
                            await db.mark_added(user.id)
                            added_this_id += 1
                            logger.info(f"[+] {phone} added {user.id}")
                            await asyncio.sleep(45) # Anti-spam delay
                        except errors.PeerFloodError:
                            logger.warning(f"Flood on {phone}. Moving to next ID.")
                            break
                        except Exception as e:
                            logger.info(f"User skipped: {e}")
            except Exception as e:
                logger.error(f"Error on account {phone}: {e}")
                continue

        logger.info(f"Cycle Done. Resting for {Config.REST_TIME}s...")
        await asyncio.sleep(Config.REST_TIME)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(adder_worker())
    bot.run_until_disconnected()
