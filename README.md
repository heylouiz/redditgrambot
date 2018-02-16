# redditgrambot

A bot to help improve Reddit sharing and access on Telegram.

## How to run:

Before jumping into the code you'll need to create a Telegram bot and a Reddit Script Application.

Create Reddit script application:
http://praw.readthedocs.io/en/latest/getting_started/authentication.html#script-application

Create Telegram bot:
https://core.telegram.org/bots#6-botfather

### Dependencies (Only works in Python3)

Create a virtualenv (Optional):
```
mkdir ~/virtualenv
virtualenv -p python3 ~/virtualenv
source ~/virtualenv/bin/activate
```
Install the requirements (use sudo if you are not using a virtualenv):

```pip install -r requirements.txt```

### Running

After all the requirements are installed edit *config.json* file with your BOT's Token as well Reddit client information.

To run the bot simply execute this command:
```python redditgrambot.py```
