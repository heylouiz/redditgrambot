#!/usr/bin/env python
# -*- coding: utf-8 -*-
import praw
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, RegexHandler, Filters, CallbackQueryHandler
from telegram.ext.dispatcher import run_async
from telegram.utils.helpers import escape_markdown
import logging
import re
import random
import json

# Load config
with open('config.json') as config_file:
    CONFIGURATION = json.load(config_file)

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

# Globals
logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.reddit.com/search?q=url:{}"
SUBREDDIT_URL = "https://www.reddit.com/r/{}"

START_MESSAGE = "Hi! I'm a bot to help improve Reddit sharing and access on Telegram.\n\
                 Check out my commands to see what I can do.\n\
                 Add me on a group to help you find discussions about links sent by your friends."

HELP_MESSAGE = "Help!"

# Praw instance
reddit = praw.Reddit(client_id=CONFIGURATION["client_id"],
                     client_secret=CONFIGURATION["client_secret"],
                     user_agent=CONFIGURATION["user_agent"])

# Regexes TODO: Match on multiple lines, currently only matching if the string is on the first line
re_links = r"(https?:\/\/(?:www\.)?(?:i\.)?(?:imgur|gfycat|redd|streamable)\.(?:com|it)\/(?:gallery/)?(?:a\/[a-zA-Z0-9]+|(?:[a-zA-Z0-9_-]+)\.?(?:gifv|webm|mp4|png|jpg|gif|jpeg)?))"
re_subreddit = r"(?:^|\W)(?:\/r\/([a-zA-Z0-9]+))"

# Command functions
def start(bot, update):
    """Send a message when the command /start is issued."""
    update.message.reply_text(START_MESSAGE)


def help(bot, update):
    """Send a message when the command /help is issued."""
    update.message.reply_text(HELP_MESSAGE)


def search_post(bot, update, url):
    """Search link on reddit."""
    submissions = [s for s in reddit.subreddit('all').search(query='url:{}'.format(url), sort="top")]
    len_sub = len(submissions)
    if len_sub < 2 and url.endswith("mp4"):
        # Sometimes an app shares a gifv link with mp4 extension, I don't know why this happens.
        # A quick fix is try to search for the gifv version of the video
        url = url.replace("mp4", "gifv")
        submissions = [s for s in reddit.subreddit('all').search(query='url:{}'.format(url), sort="top")] + submissions
        len_sub = len(submissions)
    if len_sub:
        reply = "I found {} {} with this [url]({})\n".format(len_sub, "posts" if len_sub > 1 else "post", url)
        for sub in submissions[:3]:
            sub_url = SUBREDDIT_URL.format(sub.subreddit)
            striped_title = re.sub("[\[\](){}]","", sub.title)
            reply += "{}⇳ [{}]({}) (on [/r/{}]({}))\n".format(sub.ups, striped_title,
                                                              sub.shortlink, sub.subreddit, sub_url)
        if len_sub > 3:
            reply += "\nShowing at most the three most upvoted:\n"
            reply += "You can see all posts in this [link]({})".format(SEARCH_URL.format(url))
        update.message.reply_text(text=reply, parse_mode="Markdown", disable_web_page_preview=True)

@run_async
def random_post(bot, update, more=None):
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

    keyboard = [[InlineKeyboardButton("More", callback_data=subreddit),
                 InlineKeyboardButton("Open post", url=post.shortlink)]]

    reply_markup = InlineKeyboardMarkup(keyboard)

    title = escape_markdown(post.title)
    url = escape_markdown(post.url)
    selftext = escape_markdown(post.selftext)
    reply_text = "*{}*\n{}\nRandom post from [/r/{}]({})".format(title, url if not selftext else selftext + "\n",
                                                                 subreddit, SUBREDDIT_URL.format(subreddit))

    if more:
        reply_text += " requested by {}".format(more["username"])
        bot.send_message(text=reply_text, chat_id=more["chat_id"], reply_markup=reply_markup, parse_mode="Markdown")
    else:
        update.message.reply_text(text=reply_text, reply_markup=reply_markup, parse_mode="Markdown")

@run_async
def more_button(bot, update):
    query = update.callback_query

    random_post(bot, update, {"subreddit": query.data,
                              "chat_id": query.message.chat_id,
                              "username": query.from_user.username})

def peek_subreddit(bot, update, subreddit):
    """Show current hot posts of subreddit."""
    reply = "Here's a sneak peek of [/r/{}]({}):\n".format(subreddit, SUBREDDIT_URL.format(subreddit))
    for post in reddit.subreddit(subreddit).hot(limit=5):
        striped_title = re.sub("[\[\](){}]","", post.title)
        striped_title = striped_title[:40] + "..." if len(striped_title) > 40 else striped_title
        reply += "- [{}]({})\n".format(striped_title, post.shortlink)

    update.message.reply_text(text=reply, parse_mode="Markdown", disable_web_page_preview=True)

@run_async
def message_handler(bot, update):
    matches = re.findall(re_links, update.message.text)
    if matches:
        search_post(bot, update, matches[0])
        return

    matches = re.findall(re_subreddit, update.message.text)
    if matches:
        peek_subreddit(bot, update, matches[0])
        return

def error(bot, update, error):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, error)


def main():
    """Start the bot."""
    # Create the EventHandler and pass it your bot's token.
    updater = Updater(CONFIGURATION["telegram_token"])

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # Add command handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help))
    dp.add_handler(CommandHandler("r", random_post))

    # Add message handlers
    dp.add_handler(MessageHandler(Filters.text, message_handler))
    dp.add_handler(RegexHandler("/r/.*", message_handler)) # hack to get messages starting with /

    # Add inline button handlers
    dp.add_handler(CallbackQueryHandler(more_button))

    # Add error handler
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
