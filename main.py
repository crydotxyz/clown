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
    """Prints a message with color and logs it to a file"""
    current_time = get_current_time()
    full_message = f"[{current_time}] {message}"

    colors = {
        "info": Fore.GREEN,
        "warning": Fore.YELLOW,
        "error": Fore.RED
    }

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
    """Displays a banner using pyfiglet"""
    banner = pyfiglet.figlet_format("CLOWN BOT")
    print(Fore.CYAN + banner)

def format_time(remaining_seconds):
    """Formats time into hours, minutes, and seconds"""
    formatted_time = str(timedelta(seconds=remaining_seconds))
    return formatted_time

def display_progress_bar(progress, total):
    """Creates a progress bar with a length of 30 characters"""
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
    """Gets the user ID from the token"""
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
    """Loads templates from a file with support for multiple keywords separated by |"""
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

def get_reply(message, reply_templates, reply_indices, used_keywords):
    """Gets a reply based on message content, using sequential replies and avoiding used keywords"""
    available_keys = [key for key in reply_templates if key in message.lower() and key not in used_keywords]
    if not available_keys:
        return None, None

    selected_key = available_keys[0]
    responses = reply_templates[selected_key]
    if not responses:
        return None, None

    index = reply_indices.get(selected_key, 0)
    reply = responses[index]
    reply_indices[selected_key] = (index + 1) % len(responses)

    return reply, selected_key

def should_respond(data, bot_ids, processed_messages, manual_messages, auto_message_ids):
    """Determines which bots should respond (returns a list of bot_ids)"""
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

def respond_to_message(channel_id, token_name, token, message_content, reply_text, message_reference, bot_id, manual_messages, auto_message_ids):
    """Function to send a response in a separate thread with manual message check"""
    reply_delay = random.uniform(15, 60)
    log_message("info", f"⏳ [{token_name}] Waiting {reply_delay:.2f} seconds before replying...")

    # Check for manual messages before delay for quick cancellation
    if bot_id in manual_messages and manual_messages[bot_id] > message_reference and manual_messages[bot_id] not in auto_message_ids:
        log_message("info", f"🚫 [{token_name}] Automatic message canceled due to a more recent manual message.")
        return

    time.sleep(reply_delay)
    
    # Check again after delay to ensure no new manual messages during delay
    if bot_id in manual_messages and manual_messages[bot_id] > message_reference and manual_messages[bot_id] not in auto_message_ids:
        log_message("info", f"🚫 [{token_name}] Automatic message canceled due to a more recent manual message.")
        return

    message_id = send_message(channel_id, token_name, token, reply_text, message_reference)
    if message_id:
        auto_message_ids.add(message_id)

def poll_messages(channel_id, bot_ids, tokens_dict, names_dict, reply_templates, processed_messages, reply_indices, manual_messages, auto_message_ids):
    """Polls new messages and processes replies/mentions for multiple bots"""
    global last_processed_id
    while True:
        try:
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

                        # Detect manual messages and mark as processed
                        if author_id in bot_ids and message_id not in auto_message_ids:
                            manual_messages[author_id] = message_id
                            log_message("info", f"📝 Manual message detected from bot {author_id}: '{message['content']}' (Message ID: {message_id})")
                            processed_messages.add(message_id)  # Add to processed_messages to prevent duplication

                        bot_ids_to_respond = should_respond(message, bot_ids, processed_messages, manual_messages, auto_message_ids)
                        if bot_ids_to_respond:
                            author = message["author"]["username"]
                            content = message["content"]
                            log_message("info", f"🔔 Message from {author}: '{content}'")

                            used_keywords = set()
                            for bot_id in bot_ids_to_respond:
                                token = tokens_dict[bot_id]
                                token_name = names_dict[bot_id]
                                reply_text, selected_key = get_reply(message["content"], reply_templates, reply_indices, used_keywords)
                                if reply_text and selected_key:
                                    used_keywords.add(selected_key)
                                    thread = threading.Thread(
                                        target=respond_to_message,
                                        args=(channel_id, token_name, token, message["content"], reply_text, message["id"], bot_id, manual_messages, auto_message_ids)
                                    )
                                    thread.start()
                                else:
                                    log_message("warning", f"❌ [{token_name}] No matching template or keyword already used.")
                        last_processed_id = message["id"]
            else:
                log_message("warning", f"⚠️ Failed to fetch messages: {response.status_code}")
        except Exception as e:
            log_message("error", f"❗ Error in polling: {e}")
        time.sleep(5)

def get_latest_message_id(channel_id, token):
    """Fetches the latest message ID in the channel"""
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
            args=(channel_id, bot_ids, tokens_dict, names_dict, reply_templates, processed_messages, reply_indices, manual_messages, auto_message_ids)
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
