#!/usr/bin/env python
from pprint import pprint
from pathlib import Path
import json
from zoneinfo import ZoneInfo
from datetime import datetime
from telegram.client import Telegram

tg = Telegram(
    api_id="29239236",
    api_hash="d6e255d06566781689cbd78258de91b0",
    phone="+79617543655",
    database_encryption_key="mydatabasesosecure",
    files_directory="./tdlib_files/",
)
tg.login()


def get_cached_messages(chat_id):
    chat_messages = []

    chat_messages_path = Path(f"messages/{chat_id}.json")
    if chat_messages_path.is_file():
        with open(Path(f"messages/{chat_id}.json")) as file:
            chat_messages = json.loads(file.read())
    else:
        write_messages_to_cache(chat_id, chat_messages)
    return chat_messages


def write_messages_to_cache(chat_id, messages):
    Path("messages").mkdir(parents=True, exist_ok=True)

    with open(Path(f"messages/{chat_id}.json"), "w") as file:
        file.write(json.dumps(messages, indent=2, ensure_ascii=False))


def find_chat_ids(*chat_names: str) -> None:
    result_get_chats = tg.get_chats(limit=1000)
    result_get_chats.wait()

    chat_ids = result_get_chats.update["chat_ids"]

    for chat_id in chat_ids:
        result_get_chat = tg.get_chat(chat_id)
        result_get_chat.wait()

        chat = result_get_chat.update

        for chat_name in chat_names:
            if chat_name.lower() in chat["title"].lower():
                print(f'# chat_id = {chat["id"]}  # {chat["title"]}')


# find_chat_ids("Вадим & 404, Вова", "Дикие Псы")

users = {}


def get_user_full_name(user_id) -> str:
    if user_id not in users:
        result_get_user = tg.get_user(user_id)
        result_get_user.wait()
        user = result_get_user.update
    else:
        user = users[user_id]

    full_name = []

    if user["first_name"]:
        full_name.append(user["first_name"])

    if user["last_name"]:
        full_name.append(user["last_name"])

    if user["username"]:
        full_name.append(f'@{user["username"]}')

    return " ".join(full_name) or "noname"


def localize(date_time):
    return date_time.astimezone(ZoneInfo("Asia/Yekaterinburg")).isoformat().split("T")[0]


def print_formated_date(func) -> str:
    def wrapper(message):
        date = localize(datetime.fromtimestamp(message["date"]))
        message["date"] = date
        print(date, end=" ")
        return func(message)

    return wrapper


def start_member(user_id, start):
    user_members = [m for m in members if m["user_id"] == user_id]
    if user_members:
        last_member = user_members[-1]
        if last_member["end"] in (start, None):
            last_member["end"] = None
            user_members[-1] = last_member
            return
    members.append(dict(user_id=user_id, start=start, end=None))


def end_member(user_id, end):
    user_members = [m for m in members if m["user_id"] == user_id]

    # assert user_members, f"Не был ранее добавен {locals()}"
    if not user_members:
        user_members = [dict(user_id=user_id, start="2017-07-27", end=None)]

    last_member = user_members[-1]

    assert not last_member["end"], f"Уже завершен {locals()}"

    if last_member["start"] == end:
        del user_members[-1]
    else:
        last_member["end"] = end
        user_members[-1] = last_member


@print_formated_date
def parse_message_basic_group_chat_create(message):
    content = message["content"]
    print("Создан чат:", content["title"])
    print("С пользователями:", ", ".join([get_user_full_name(user_id) for user_id in content["member_user_ids"]]))
    for user_id in content["member_user_ids"]:
        start_member(user_id, start=message["date"])


@print_formated_date
def parse_message_chat_add_members(message):
    content = message["content"]
    print("Добавлены пользователи:", ", ".join([get_user_full_name(user_id) for user_id in content["member_user_ids"]]))
    for user_id in content["member_user_ids"]:
        start_member(user_id, start=message["date"])


@print_formated_date
def parse_message_chat_join_by_link(message):
    print("Вступил по ссылке:", get_user_full_name(message["sender_id"]["user_id"]))
    start_member(message["sender_id"]["user_id"], start=message["date"])


@print_formated_date
def parse_message_chat_delete_member(message):
    content = message["content"]
    print("Удален пользователь:", get_user_full_name(content["user_id"]))
    end_member(content["user_id"], end=message["date"])


@print_formated_date
def parse_message_chat_change_title(message):
    content = message["content"]
    print("Новое название:", content["title"])


PARSERS_BY_TYPE = {
    "messageBasicGroupChatCreate": parse_message_basic_group_chat_create,
    "messageChatAddMembers": parse_message_chat_add_members,
    "messageChatJoinByLink": parse_message_chat_join_by_link,
    "messageChatDeleteMember": parse_message_chat_delete_member,
    "messageChatChangeTitle": parse_message_chat_change_title,
    # "messageUnsupported": lambda m: pprint(m),
}
AVAILABLE_TYPES = list(PARSERS_BY_TYPE.keys())

# chat_id = -1001615963537  # Дикие Псы
# chat_id = -1001993194902  # Вадим & 404, Вова
chat_id = -1001135165196  # Дикие псы (просто другие)
old_chat_id = chat_id

members = []

cached_messages = get_cached_messages(chat_id)

if cached_messages:
    all_messages = cached_messages[:]
    from_message_id = cached_messages[-1]["id"]
    old_chat_id = cached_messages[-1]["chat_id"]
else:
    all_messages = []
    from_message_id = 0

has_messages = True

while has_messages:
    result = tg.get_chat_history(chat_id=old_chat_id, limit=100, from_message_id=from_message_id)
    result.wait()
    messages = result.update["messages"]
    if not messages:
        last_message = all_messages[-1]["content"]

        if last_message["@type"] == "messageChatUpgradeFrom":
            result_create_basic_group_chat = tg.create_basic_group_chat(last_message["basic_group_id"])
            result_create_basic_group_chat.wait()
            basic_group_chat = result_create_basic_group_chat.update

            from_message_id = 0
            old_chat_id = basic_group_chat["id"]
        else:
            has_messages = False
        continue
    all_messages += messages
    write_messages_to_cache(chat_id, all_messages)
    print("Загружено сообщений:", len(all_messages))
    from_message_id = messages[-1]["id"]


filtered_messages = [m for m in all_messages if m["content"]["@type"] in AVAILABLE_TYPES][::-1]
# pprint(set([m["content"]["@type"] for m in all_messages]))

for message in filtered_messages:
    PARSERS_BY_TYPE[message["content"]["@type"]](message)

today = localize(datetime.now())

for member in members:
    print(
        f"    {get_user_full_name(member['user_id']):<40}",
        f":{('' if member['end'] else 'active'):<6}, {member['start']}, {member['end'] if member['end'] else today}",
    )

tg.stop()
