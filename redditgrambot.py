import json
import logging
import os
import random
import re
from typing import Union

import praw
import youtube_dl
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    Filters,
    MessageHandler,
    Updater,
)
from telegram.utils.helpers import escape_markdown

# Load config
with open("config.json") as config_file:
    CONFIGURATION = json.load(config_file)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# Globals
logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.reddit.com/search?q=url:{}"
SUBREDDIT_URL = "https://www.reddit.com/r/{}"

START_MESSAGE = "Hi! I'm a bot to help improve Reddit sharing and access on Telegram.\n\
                 Check out my commands to see what I can do.\n\
                 Add me on a group to help you find discussions about links sent by your friends."

HELP_MESSAGE = "Help!"

# Praw instance
reddit = praw.Reddit(
    client_id=CONFIGURATION["client_id"],
    client_secret=CONFIGURATION["client_secret"],
    user_agent=CONFIGURATION["user_agent"],
)

re_links = r"(?s)(https?:\/\/(?:www\.)?(?:i\.)?(?:imgur|gfycat|redd|streamable)\.(?:com|it)\/(?:gallery/)?(?:a\/[a-zA-Z0-9]+|(?:[a-zA-Z0-9_-]+)\.?(?:gifv|webm|mp4|png|jpg|gif|jpeg)?))"  # noqa: E501
re_subreddit = r"(?:^|\W)(?:\/r\/([a-zA-Z0-9_]+))"
v_reddit_links = r"(https?:\/\/(?:www\.)?(?:v\.)?(?:redd.it)\/(?:.*?))(?:\s|$)"
comments_id = r"(https:\/\/(?:www\.|old\.)?reddit.com\/r\/(?:.*?)\/comments\/(.*?)\/.*)"


def start(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /start is issued."""
    update.message.reply_text(START_MESSAGE)


def help(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /help is issued."""
    update.message.reply_text(HELP_MESSAGE)


def search_post(update: Update, url: str) -> None:
    """Search link on reddit."""
    submissions = [
        s
        for s in reddit.subreddit("all").search(query="url:{}".format(url), sort="top")
    ]
    len_sub = len(submissions)
    if len_sub < 2 and url.endswith("mp4"):
        # Sometimes an app shares a gifv link with mp4 extension, I don't know why this happens.
        # A quick fix is try to search for the gifv version of the video
        url = url.replace("mp4", "gifv")
        submissions = [
            s
            for s in reddit.subreddit("all").search(
                query="url:{}".format(url), sort="top"
            )
        ] + submissions
        len_sub = len(submissions)
    if len_sub:
        reply = "I found {} {} with this [url]({})\n".format(
            len_sub, "posts" if len_sub > 1 else "post", url
        )
        for sub in submissions[:3]:
            sub_url = SUBREDDIT_URL.format(sub.subreddit)
            striped_title = re.sub(r"[\[\](){}]", "", sub.title)
            reply += "{}⇳ [{}]({}) (on [/r/{}]({}))\n".format(
                sub.ups, striped_title, sub.shortlink, sub.subreddit, sub_url
            )
        if len_sub > 3:
            reply += "\nShowing at most the three most upvoted:\n"
            reply += "You can see all posts in this [link]({})".format(
                SEARCH_URL.format(url)
            )
        update.message.reply_text(
            text=reply, parse_mode="Markdown", disable_web_page_preview=True
        )


def random_post(update: Update, context: CallbackContext, more: dict = None) -> None:
    """Send a random post from a subreddit"""
    if more:
        subreddit = more["subreddit"]
    else:
        subreddit = update.message.text.split(" ")[1]

    try:
        post = reddit.subreddit(subreddit).random()
    except praw.exceptions.ClientException:
        # Know reddit bug, see: https://github.com/praw-dev/praw/issues/885
        # So we use our own random with blackjack and hookers
        post = random.choice([p for p in reddit.subreddit(subreddit).hot(limit=25)])

    if not post:
        update.message.reply_test("Invalid subreddit {}".format(subreddit))

    keyboard = [
        [
            InlineKeyboardButton("More", callback_data=subreddit),
            InlineKeyboardButton("Open post", url=post.shortlink),
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    title = escape_markdown(post.title)
    url = escape_markdown(post.url)
    selftext = escape_markdown(post.selftext)
    reply_text = "*{}*\n{}\nRandom post from [/r/{}]({})".format(
        title,
        url if not selftext else selftext + "\n",
        subreddit,
        SUBREDDIT_URL.format(subreddit),
    )

    if more:
        reply_text += " requested by {}".format(more["username"])
        context.bot.send_message(
            text=reply_text,
            chat_id=more["chat_id"],
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )
    else:
        update.message.reply_text(
            text=reply_text, reply_markup=reply_markup, parse_mode="Markdown"
        )


def more_button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query

    random_post(
        update,
        context,
        {
            "subreddit": query.data,
            "chat_id": query.message.chat_id,
            "username": query.from_user.username,
        },
    )


def peek_subreddit(update: Update, subreddit: str) -> None:
    """Show current hot posts of subreddit."""
    reply = "Here's a sneak peek of [/r/{}]({}):\n".format(
        subreddit, SUBREDDIT_URL.format(subreddit)
    )
    for post in reddit.subreddit(subreddit).hot(limit=5):
        striped_title = re.sub(r"[\[\](){}]", "", post.title)
        striped_title = (
            striped_title[:40] + "..." if len(striped_title) > 40 else striped_title
        )
        reply += "- [{}]({})\n".format(striped_title, post.shortlink)

    update.message.reply_text(
        text=reply, parse_mode="Markdown", disable_web_page_preview=True
    )


def get_vreddit_url(text: str) -> Union[str, None]:
    match = re.search(v_reddit_links, text)
    if match:
        return match.group(1)
    match = re.search(comments_id, text)
    if match:
        submission = reddit.submission(match.group(2))
        if hasattr(submission, "crosspost_parent") and submission.crosspost_parent:
            submission = reddit.submission(submission.crosspost_parent.split("_")[1])
        if submission.is_video:
            return submission.url


def send_video(update: Update, url: str) -> None:
    filename = "/tmp/%s%s.mp4" % (update.message.chat.id, update.message.message_id)
    ydl_opts = {"outtmpl": filename}
    try:
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except:
        update.message.reply_text("Failed to download video.")
        return

    with open(filename, "rb") as video:
        update.message.reply_video(video=video, timeout=99999)
    os.remove(filename)


def message_handler(update: Update, context: CallbackContext) -> None:
    if not update.message:
        return
    v_reddit = get_vreddit_url(update.message.text)
    if v_reddit:
        send_video(update, v_reddit)

    matches = re.findall(re_links, update.message.text)
    if matches:
        search_post(update, matches[0])
        return

    matches = re.findall(re_subreddit, update.message.text)
    if matches:
        peek_subreddit(update, matches[0])
        return


def error(update: Update, context: CallbackContext) -> None:
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)


def main() -> None:
    """Start the bot."""
    # Create the EventHandler and pass it your bot's token.
    updater = Updater(CONFIGURATION["telegram_token"])

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # Add command handlers
    dp.add_handler(CommandHandler("start", start, run_async=True))
    dp.add_handler(CommandHandler("help", help, run_async=True))
    dp.add_handler(CommandHandler("r", random_post, run_async=True))

    # Add message handlers
    dp.add_handler(MessageHandler(Filters.text, message_handler, run_async=True))
    dp.add_handler(
        MessageHandler(Filters.regex("/r/.*"), message_handler, run_async=True)
    )  # hack to get messages starting with /

    # Add inline button handlers
    dp.add_handler(CallbackQueryHandler(more_button, run_async=True))

    # Add error handler
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == "__main__":
    main()
