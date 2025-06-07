import time
import logging
import requests
import json
import sys
import re
import threading
import random
from datetime import datetime, timedelta
from colorama import Fore, Style, init
from tabulate import tabulate
import pyfiglet

init(autoreset=True)

logging.basicConfig(filename="activity.log", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def get_current_time():
    return datetime.now().strftime("%H:%M:%S")

def log_message(level, message):
    current_time = get_current_time()
    full_message = f"[{current_time}] {message}"
    colors = {"info": Fore.GREEN, "warning": Fore.YELLOW, "error": Fore.RED}
    color = colors.get(level, Fore.WHITE)
    print(color + full_message)
    if level == "info":
        logging.info(full_message)
    elif level == "warning":
        logging.warning(full_message)
    elif level == "error":
        logging.error(full_message)
        exit(1)

def display_banner():
    banner = pyfiglet.figlet_format("CLOWN BOT")
    print(Fore.CYAN + banner)

def format_time(remaining_seconds):
    formatted_time = str(timedelta(seconds=remaining_seconds))
    return formatted_time

def display_progress_bar(progress, total):
    bar_length = 30
    filled_length = int(bar_length * progress / total)
    bar = "█" * filled_length + "▒" * (bar_length - filled_length)
    return f"[{bar}]"

def countdown(start_time_minutes):
    total_seconds = start_time_minutes * 60
    if start_time_minutes >= 60:
        hours = start_time_minutes // 60
        minutes = start_time_minutes % 60
        log_message("info", f"\n🕒 Starting in {hours} hours {minutes} minutes...\n")
    while total_seconds > 0:
        time_str = format_time(total_seconds)
        bar = display_progress_bar(total_seconds, start_time_minutes * 60)
        print(Fore.CYAN + f"\r⏳ {bar} {time_str} remaining...", end="", flush=True)
        if total_seconds > 600:
            sleep_time = 300
        elif total_seconds > 300:
            sleep_time = 60
        elif total_seconds > 60:
            sleep_time = 30
        elif total_seconds > 10:
            sleep_time = 10
        else:
            for i in range(total_seconds, 0, -1):
                bar = display_progress_bar(i, start_time_minutes * 60)
                print(Fore.RED + f"\r⏳ {bar} {i} seconds remaining... ", end="", flush=True)
                time.sleep(1)
            break
        time.sleep(sleep_time)
        total_seconds -= sleep_time
    print(Fore.GREEN + "\n🚀 Starting now!\n")

def validate_token(token_name, token):
    headers = {"Authorization": token}
    try:
        response = requests.get("https://discord.com/api/v9/users/@me", headers=headers)
        if response.status_code == 200:
            log_message("info", f"✅ Token {token_name} is valid.")
            return True
        else:
            log_message("error", f"❌ Token {token_name} is invalid! (Status Code: {response.status_code})")
            return False
    except requests.exceptions.RequestException as e:
        log_message("error", f"⚠️ Error validating token {token_name}: {e}")
        return False

def get_user_id_from_token(token):
    headers = {"Authorization": token}
    try:
        response = requests.get("https://discord.com/api/v9/users/@me", headers=headers)
        if response.status_code == 200:
            return response.json().get("id")
        else:
            log_message("error", f"❌ Failed to get user ID for token: {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        log_message("error", f"⚠️ Error getting user ID: {e}")
        return None

def typing_indicator(channel_id, token, typing_time):
    headers = {'Authorization': token}
    start_time = time.time()
    log_message("info", f"💬 Bot is typing for {typing_time:.2f} seconds...")
    while time.time() - start_time < typing_time:
        try:
            response = requests.post(f"https://discord.com/api/v9/channels/{channel_id}/typing", headers=headers)
            if response.status_code not in [200, 204]:
                log_message("warning", f"⚠️ Typing request failed: {response.status_code}")
                break
            remaining_time = typing_time - (time.time() - start_time)
            sleep_time = min(remaining_time, 5)
            if sleep_time > 0:
                time.sleep(sleep_time)
            else:
                break
        except requests.exceptions.RequestException as e:
            log_message("error", f"❗ Error while sending typing indicator: {e}")
            break

def send_message(channel_id, token_name, token, message, message_reference=None):
    headers = {"Authorization": token, "Content-Type": "application/json"}
    payload = {"content": message}
    if message_reference:
        payload["message_reference"] = {"message_id": message_reference}
    word_count = len(message.split())
    typing_time = random.uniform(0.4 * word_count, 0.7 * word_count)
    thread = threading.Thread(target=typing_indicator, args=(channel_id, token, typing_time))
    thread.start()
    log_message("info", f"⌨️ Typing for {typing_time:.2f} seconds...")
    time.sleep(typing_time)
    while True:
        try:
            response = requests.post(f"https://discord.com/api/v9/channels/{channel_id}/messages", json=payload, headers=headers)
            if response.status_code == 200:
                message_id = response.json().get("id")
                log_message("info", f"📩 [{token_name}] Message sent: '{message}' (Message ID: {message_id})")
                return message_id
            elif response.status_code == 429:
                retry_after = response.json().get("retry_after", 1)
                log_message("warning", f"⚠️ [{token_name}] Rate limit! Retrying in {retry_after:.2f} seconds...")
                time.sleep(retry_after)
            else:
                log_message("error", f"❌ [{token_name}] Failed to send message: {response.status_code}")
                return None
        except requests.exceptions.RequestException as e:
            log_message("error", f"❗ Error while sending message: {e}")
            return None

def display_token_list(tokens):
    header = ["Token Name", "Min Interval (s)", "Max Interval (s)"]
    table = [(name, min_interval, max_interval) for name, _, min_interval, max_interval in tokens]
    print(Fore.CYAN + "\n" + "="*40)
    print(Fore.YELLOW + "           🎛️ TOKEN LIST")
    print(Fore.CYAN + "="*40)
    print(tabulate(table, headers=header, tablefmt="grid"))
    print(Fore.CYAN + "="*40 + "\n")

def load_templates(file_path="template.txt"):
    templates = {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            key = None
            for line in lines:
                line = line.strip()
                if line.startswith("[") and line.endswith("]"):
                    key = line[1:-1].lower().split("|")
                    for k in key:
                        if k not in templates:
                            templates[k] = []
                elif key and line:
                    for k in key:
                        templates[k].append(line)
    except FileNotFoundError:
        log_message("error", f"❗ Template file {file_path} not found.")
    except Exception as e:
        log_message("error", f"❗ Error loading templates: {e}")
    return templates

def load_reply_keywords(file_path="reply.txt"):
    keywords = {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            key = None
            for line in lines:
                line = line.strip()
                if line.startswith("[") and line.endswith("]"):
                    key = line[1:-1].lower().split("|")
                    for k in key:
                        if k not in keywords:
                            keywords[k] = []
                elif key and line:
                    for k in key:
                        keywords[k].append(line)
    except FileNotFoundError:
        log_message("error", f"❗ Reply file {file_path} not found.")
    except Exception as e:
        log_message("error", f"❗ Error loading reply keywords: {e}")
    return keywords

def get_reply(message, reply_templates, reply_indices, used_replies):
    available_keys = [key for key in reply_templates if key in message.lower()]
    if not available_keys:
        return None
    selected_key = available_keys[0]
    responses = reply_templates[selected_key]
    if not responses:
        return None
    index = reply_indices.get(selected_key, 0)
    reply = responses[index]
    used_replies.add(reply)
    reply_indices[selected_key] = (index + 1) % len(responses)
    return reply

def get_keyword_reply(keyword_replies, keyword, used_replies_per_keyword, token_name):
    responses = keyword_replies[keyword]
    if not responses:
        return None
    # Track used replies globally for this keyword
    if keyword not in used_replies_per_keyword:
        used_replies_per_keyword[keyword] = set()
    available_replies = [r for r in responses if r not in used_replies_per_keyword[keyword]]
    if not available_replies:
        used_replies_per_keyword[keyword] = set()
        available_replies = responses
    reply = random.choice(available_replies)
    used_replies_per_keyword[keyword].add(reply)
    return reply

def should_respond(data, bot_ids, processed_messages, manual_messages, auto_message_ids):
    message_id = data.get("id")
    if message_id in processed_messages:
        return []
    processed_messages.add(message_id)
    if data.get("edited_timestamp"):
        return []
    author_id = data.get("author", {}).get("id")
    if author_id in bot_ids:
        return []
    responding_bots = []
    referenced_message = data.get("referenced_message", {})
    if referenced_message:
        referenced_author_id = referenced_message.get("author", {}).get("id")
        if referenced_author_id in bot_ids:
            if referenced_author_id in manual_messages and manual_messages[referenced_author_id] > message_id and manual_messages[referenced_author_id] not in auto_message_ids:
                log_message("info", f"🚫 Bot {referenced_author_id} will not respond due to a more recent manual message.")
            else:
                responding_bots.append(referenced_author_id)
    mentions = data.get("mentions", [])
    for user in mentions:
        if user["id"] in bot_ids and user["id"] not in responding_bots:
            if user["id"] in manual_messages and manual_messages[user["id"]] > message_id and manual_messages[user["id"]] not in auto_message_ids:
                log_message("info", f"🚫 Bot {user['id']} will not respond due to a more recent manual message.")
            else:
                responding_bots.append(user["id"])
    return responding_bots

def detect_spam(author_id, message_timestamps, spam_threshold=3, spam_window=30, min_interval=5):
    current_time = time.time()
    if author_id not in message_timestamps:
        message_timestamps[author_id] = []
    message_timestamps[author_id].append(current_time)
    # Remove timestamps older than the spam window
    message_timestamps[author_id] = [t for t in message_timestamps[author_id] if current_time - t <= spam_window]
    # Check if user sent too many messages in the spam window
    if len(message_timestamps[author_id]) > spam_threshold:
        log_message("warning", f"🚫 Detected potential spam from user {author_id}: Too many messages in {spam_window} seconds.")
        return True
    # Check if messages are sent too quickly
    if len(message_timestamps[author_id]) >= 2:
        last_two = message_timestamps[author_id][-2:]
        if last_two[1] - last_two[0] < min_interval:
            log_message("warning", f"🚫 Detected potential spam from user {author_id}: Messages sent too quickly (less than {min_interval} seconds apart).")
            return True
    return False

def respond_to_message(channel_id, token_name, token, message_content, reply_text, message_reference, bot_id, manual_messages, auto_message_ids, delay):
    log_message("info", f"⏳ [{token_name}] Waiting {delay:.2f} seconds before replying...")
    time.sleep(delay)
    if bot_id in manual_messages and manual_messages[bot_id] > message_reference and manual_messages[bot_id] not in auto_message_ids:
        log_message("info", f"🚫 [{token_name}] Automatic message canceled due to a more recent manual message.")
        return
    message_id = send_message(channel_id, token_name, token, reply_text, message_reference)
    if message_id:
        auto_message_ids.add(message_id)

def poll_messages(channel_id, bot_ids, tokens_dict, names_dict, reply_templates, keyword_replies, processed_messages, reply_indices, manual_messages, auto_message_ids, reply_delay_min, reply_delay_max, keyword_reply_delay_min, keyword_reply_delay_max, max_keyword_users, keyword_cooldown):
    global last_processed_id
    user_bot_indices = {}
    keyword_users = set()  # Track users responded to by any bot for reply.txt
    used_replies = set()
    used_replies_per_keyword = {}  # Track used replies globally per keyword
    keyword_detection_active = True
    last_keyword_reset_time = time.time()
    message_timestamps = {}  # Track timestamps for spam detection
    responded_messages_per_bot = {bot_id: set() for bot_id in bot_ids}  # Track messages responded to by each bot
    user_bot_count = {}  # Track number of bots that have responded to each user for reply.txt

    while True:
        try:
            current_time = time.time()
            # Ubah keyword_cooldown ke detik (dikalikan 60 karena sekarang dalam menit)
            if not keyword_detection_active and (current_time - last_keyword_reset_time >= keyword_cooldown * 60):
                keyword_detection_active = True
                keyword_users.clear()
                user_bot_count.clear()  # Reset bot count when cooldown ends
                log_message("info", "🔍 Keyword detection for reply.txt is now active again.")

            params = {"limit": 100}
            if last_processed_id:
                params["after"] = last_processed_id
            response = requests.get(
                f"https://discord.com/api/v9/channels/{channel_id}/messages",
                headers={"Authorization": tokens_dict[bot_ids[0]]},
                params=params
            )
            if response.status_code == 200:
                messages = response.json()
                if messages:
                    for message in messages:
                        message_id = message["id"]
                        author_id = message["author"]["id"]

                        if author_id in bot_ids and message_id not in auto_message_ids:
                            manual_messages[author_id] = message_id
                            log_message("info", f"📝 Manual message detected from bot {author_id}: '{message['content']}' (Message ID: {message_id})")
                            processed_messages.add(message_id)

                        bot_ids_to_respond = should_respond(message, bot_ids, processed_messages, manual_messages, auto_message_ids)
                        if bot_ids_to_respond:
                            author = message["author"]["username"]
                            content = message["content"]
                            log_message("info", f"🔔 Message from {author}: '{content}'")
                            for bot_id in bot_ids_to_respond:
                                if message_id in responded_messages_per_bot[bot_id]:
                                    log_message("info", f"🚫 Bot {bot_id} already responded to message {message_id}.")
                                    continue
                                token = tokens_dict[bot_id]
                                token_name = names_dict[bot_id]
                                reply_text = get_reply(content, reply_templates, reply_indices, used_replies)
                                if reply_text:
                                    thread = threading.Thread(
                                        target=respond_to_message,
                                        args=(channel_id, token_name, token, content, reply_text, message_id, bot_id, manual_messages, auto_message_ids, random.uniform(reply_delay_min, reply_delay_max))
                                    )
                                    thread.start()
                                    responded_messages_per_bot[bot_id].add(message_id)
                                else:
                                    log_message("warning", f"❌ [{token_name}] No matching template found.")

                        if keyword_detection_active and author_id not in bot_ids and not message.get("referenced_message"):
                            # Check for spam
                            if detect_spam(author_id, message_timestamps):
                                continue

                            # Check if this user has already been responded to by all bots
                            if author_id in user_bot_count and user_bot_count[author_id] >= len(bot_ids):
                                log_message("info", f"🚫 User {author_id} has been responded to by all bots for reply.txt.")
                                continue

                            # Deteksi kata kunci dengan pencocokan substring (sama seperti template.txt)
                            message_content_lower = message["content"].lower()
                            available_keys = [key for key in keyword_replies if key in message_content_lower]
                            if available_keys:
                                if author_id not in user_bot_indices:
                                    user_bot_indices[author_id] = 0
                                bot_id = bot_ids[user_bot_indices[author_id] % len(bot_ids)]
                                # Check if this bot has already responded to this message
                                if message_id in responded_messages_per_bot[bot_id]:
                                    log_message("info", f"🚫 Bot {bot_id} already responded to message {message_id}.")
                                    continue
                                token = tokens_dict[bot_id]
                                token_name = names_dict[bot_id]
                                selected_key = available_keys[0]  # Pilih kata kunci pertama yang cocok
                                reply_text = get_keyword_reply(keyword_replies, selected_key, used_replies_per_keyword, token_name)
                                if reply_text:
                                    thread = threading.Thread(
                                        target=respond_to_message,
                                        args=(channel_id, token_name, token, message["content"], reply_text, message_id, bot_id, manual_messages, auto_message_ids, random.uniform(keyword_reply_delay_min, keyword_reply_delay_max))
                                    )
                                    thread.start()
                                    user_bot_indices[author_id] += 1
                                    if author_id not in user_bot_count:
                                        user_bot_count[author_id] = 0
                                    user_bot_count[author_id] += 1  # Increment the count of bots that responded
                                    keyword_users.add(author_id)  # Mark this user as responded to
                                    responded_messages_per_bot[bot_id].add(message_id)
                                    log_message("info", f"🔍 [{token_name}] Detected keyword '{selected_key}' from {message['author']['username']}: '{message['content']}'")
                                if len(keyword_users) >= max_keyword_users:
                                    keyword_detection_active = False
                                    last_keyword_reset_time = time.time()
                                    log_message("info", f"⏳ Keyword detection for reply.txt paused for {keyword_cooldown} minutes.")

                        last_processed_id = message["id"]
            else:
                log_message("warning", f"⚠️ Failed to fetch messages: {response.status_code}")
        except Exception as e:
            log_message("error", f"❗ Error in polling: {e}")
        time.sleep(5)

def get_latest_message_id(channel_id, token):
    response = requests.get(
        f"https://discord.com/api/v9/channels/{channel_id}/messages",
        headers={"Authorization": token},
        params={"limit": 1}
    )
    if response.status_code == 200 and response.json():
        return response.json()[0]["id"]
    else:
        log_message("error", "❗ Failed to get the latest message ID.")
        return None

def main():
    global last_processed_id
    display_banner()

    try:
        with open("dialog.txt", "r", encoding="utf-8") as f:
            dialog_list = json.load(f)
            if not dialog_list:
                raise ValueError("⚠️ dialog.txt file is empty.")

        with open("token.txt", "r") as f:
            tokens = []
            bot_ids = []
            for line in f.readlines():
                parts = line.strip().split(":")
                if len(parts) != 4:
                    raise ValueError("⚠️ Incorrect token.txt format! Use: token_name:token:min_interval:max_interval")
                token_name, token, min_interval, max_interval = parts
                try:
                    min_interval = int(min_interval)
                    max_interval = int(max_interval)
                except ValueError:
                    raise ValueError(f"⚠️ min_interval and max_interval must be numbers in token.txt. Invalid values: {min_interval}, {max_interval}")
                tokens.append((token_name, token, min_interval, max_interval))
                user_id = get_user_id_from_token(token)
                if user_id:
                    bot_ids.append(user_id)

        if len(tokens) < 2:
            raise ValueError("⚠️ Token file must contain at least 2 accounts.")

        reply_templates = load_templates()
        keyword_replies = load_reply_keywords()

        for token_name, token, _, _ in tokens:
            if not validate_token(token_name, token):
                return

        display_token_list(tokens)

        channel_id = input(Fore.CYAN + "🔢 Enter channel ID: " + Style.RESET_ALL).strip()
        if not channel_id.isdigit():
            raise ValueError("⚠️ Channel ID must be a number.")

        start_time_minutes = int(input(Fore.CYAN + "⏳ Enter start time in minutes (0 to start immediately): " + Style.RESET_ALL))
        if start_time_minutes < 0:
            raise ValueError("⚠️ Start time cannot be negative.")

        reply_delay_min = int(input(Fore.CYAN + "⏳ Enter min reply delay for template.txt (seconds): " + Style.RESET_ALL))
        reply_delay_max = int(input(Fore.CYAN + "⏳ Enter max reply delay for template.txt (seconds): " + Style.RESET_ALL))
        keyword_reply_delay_min = int(input(Fore.CYAN + "⏳ Enter min reply delay for reply.txt (seconds): " + Style.RESET_ALL))
        keyword_reply_delay_max = int(input(Fore.CYAN + "⏳ Enter max reply delay for reply.txt (seconds): " + Style.RESET_ALL))
        max_keyword_users = int(input(Fore.CYAN + "👥 Enter max number of users for keyword detection: " + Style.RESET_ALL))
        # Ubah input menjadi menit
        keyword_cooldown = int(input(Fore.CYAN + "⏳ Enter keyword detection cooldown for reply.txt (minutes): " + Style.RESET_ALL))

        max_delays = int(input(Fore.CYAN + "🔁 Enter number of delays: " + Style.RESET_ALL))
        delay_settings = []
        for i in range(max_delays):
            delay_after = int(input(Fore.CYAN + f"🔄 Enter number of messages before delay {i+1}: " + Style.RESET_ALL))
            delay_time = int(input(Fore.CYAN + f"⏳ Enter delay {i+1} time in seconds: " + Style.RESET_ALL))
            delay_settings.append((delay_after, delay_time))

        change_interval = input(Fore.CYAN + "⏳ Change interval after a specific delay? (y/n): " + Style.RESET_ALL).strip().lower()
        interval_changes = {}
        if change_interval == "y":
            num_changes = int(input(Fore.CYAN + "🔄 How many interval changes? " + Style.RESET_ALL))
            for _ in range(num_changes):
                after_delay = int(input(Fore.CYAN + "🕒 After which delay number? " + Style.RESET_ALL))
                new_min_interval = int(input(Fore.CYAN + "🕒 Enter new min interval (seconds): " + Style.RESET_ALL))
                new_max_interval = int(input(Fore.CYAN + "🕒 Enter new max interval (seconds): " + Style.RESET_ALL))
                interval_changes[after_delay] = (new_min_interval, new_max_interval)

        tokens_dict = dict(zip(bot_ids, [token for _, token, _, _ in tokens]))
        names_dict = dict(zip(bot_ids, [name for name, _, _, _ in tokens]))

        last_processed_id = get_latest_message_id(channel_id, tokens[0][1])
        if last_processed_id is None:
            return

        processed_messages = set()
        reply_indices = {}
        manual_messages = {}
        auto_message_ids = set()

        polling_thread = threading.Thread(
            target=poll_messages,
            args=(channel_id, bot_ids, tokens_dict, names_dict, reply_templates, keyword_replies, processed_messages, reply_indices, manual_messages, auto_message_ids, reply_delay_min, reply_delay_max, keyword_reply_delay_min, keyword_reply_delay_max, max_keyword_users, keyword_cooldown)
        )
        polling_thread.daemon = True
        polling_thread.start()

        if start_time_minutes > 0:
            countdown(start_time_minutes)

        log_message("info", "🤖 Starting automatic conversation...")

        last_message_per_sender = {}
        message_count = 0
        delay_count = 0

        for index, dialog in enumerate(dialog_list):
            try:
                text = dialog["text"]
                sender_index = dialog["sender"]
                reply_to = dialog.get("reply_to", None)

                if sender_index >= len(tokens):
                    log_message("error", f"⚠️ Sender index {sender_index} is out of bounds.")
                    return

                token_name, token, min_interval, max_interval = tokens[sender_index]
                message_reference = last_message_per_sender.get(reply_to) if reply_to is not None else None

                message_id = send_message(channel_id, token_name, token, text, message_reference)
                if message_id:
                    last_message_per_sender[sender_index] = message_id
                    auto_message_ids.add(message_id)

                custom_delay = dialog.get("delay", None)
                if custom_delay:
                    log_message("info", f"⏳ Custom delay from JSON detected: {custom_delay} seconds")
                    time.sleep(custom_delay)
                    log_message("info", "⏳ Resuming after custom delay...")
                    continue

                wait_time = random.uniform(min_interval, max_interval)
                log_message("info", f"⏳ Waiting {wait_time:.2f} seconds before the next message...")
                time.sleep(wait_time)

                message_count += 1

                if delay_count < max_delays and delay_count < len(delay_settings) and message_count >= delay_settings[delay_count][0]:
                    log_message("info", f"⏸️ Pausing for {delay_settings[delay_count][1]} seconds... ({delay_count + 1}/{max_delays})")
                    time.sleep(delay_settings[delay_count][1])
                    delay_count += 1

                if delay_count in interval_changes:
                    new_min_interval, new_max_interval = interval_changes[delay_count]
                    tokens[sender_index] = (token_name, token, new_min_interval, new_max_interval)
                    log_message("info", f"⏳ Interval changed to {new_min_interval}-{new_max_interval} seconds after delay {delay_count}/{max_delays}")

            except Exception as e:
                log_message("error", f"❗ An error occurred: {e}")
                return

        log_message("info", "🎉 Conversation completed.")

    except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
        log_message("error", f"❗ Error: {e}")
        return

if __name__ == "__main__":
    main()
