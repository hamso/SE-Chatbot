#!/usr/bin/env python

import chatexchange.client
import chatexchange.events
import getpass
import re
from GetAssociatedWord import GetAssociatedWord
from SecretSpells import *
from HTMLParser import HTMLParser
import thread
import time
import random
import math
from bs4 import BeautifulSoup
import requests
import urllib
import json
import logging
import logging.handlers

class WordAssociationBot:

    room = None
    client = None
    commands = {}
    owner_commands = {}
    owner_id = 229438 # change this into your ID
    owner_name = "ProgramFOX" # change this into your name
    enabled = True
    running = True
    waiting_time = -1
    current_word_to_reply = ""
    translation_languages = [ "auto", "en", "fr", "nl", "de", "he", "ru", "el", "pt", "es", "fi", "af", "sq", "ar", "hy", "az", "eu", "be", "bn", "bs", "bg", "ca", "ceb", "zh-CN", "hr", "cs", "da",
                              "eo", "et", "tl", "gl", "ka", "gu", "ht", "ha", "hi", "hmn", "hu", "is", "ig", "id", "ga", "it", "ja", "jw", "kn", "km", "ko", "lo", "la", "lv", "lt", "mk", "ms"
                              "mt", "mi", "mr", "mn", "ne", "no", "fa", "pl", "pa", "ro", "sr", "sk", "sl", "so", "sw", "sv", "ta", "te", "th", "tr", "uk", "ur", "vi", "cy", "yi", "yo", "zu" ]
    end_lang = None
    translation_chain_going_on = False
    spellManager = SecretSpells()
    
    def main(self):
        self.setup_logging()
        self.commands = { 
            'time': self.command_time,
            'viewspells': self.command_viewspells,
            'translationchain': self.command_translationchain
        }
        self.owner_commands = {
            'stop': self.command_stop,
            'disable': self.command_disable,
            'enable': self.command_enable,
            'award': self.command_award,
            'emptyqueue': self.command_emptyqueue      
        }
        self.spellManager.init()
        site = raw_input("Site: ")
        room_number = int(raw_input("Room number: "))
        email = raw_input("Email address: ")
        password = getpass.getpass("Password: ")
        
        f = open("config.txt", "r")
        self.waiting_time = int(f.read());
        f.close()

        self.client = chatexchange.client.Client(site)
        self.client.login(email, password)
        
        self.spellManager.c = self.client
    
        self.room = self.client.get_room(room_number)
        self.room.join()
        self.room.watch(self.on_event)
            
        thread.start_new_thread(self.scheduled_empty_queue, ())
        
        while self.running:
            inputted = raw_input("<< ")
            if inputted.startswith("$") and len(inputted) > 2:
                command_in = inputted[2:]
                command_out = self.command(command_in, None, None)
                if command_out != False and command_out is not None:
                    print command_out
                if inputted[1] == "+":
                    self.room.send_message("%s" % command_out)
                    
    
    def setup_logging(self):
        logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO)
        logger.setLevel(logging.DEBUG)

        # In addition to the basic stderr logging configured globally
        # above, we'll use a log file for chatexchange.client.
        wrapper_logger = logging.getLogger('chatexchange.client')
        wrapper_handler = logging.handlers.TimedRotatingFileHandler(
           filename='client.log',
            when='midnight', delay=True, utc=True, backupCount=7,
        )
        wrapper_handler.setFormatter(logging.Formatter(
            "%(asctime)s: %(levelname)s: %(threadName)s: %(message)s"
        ))
        wrapper_logger.addHandler(wrapper_handler)
                    
    def scheduled_empty_queue(self):
        while self.running:
            time.sleep(15 * 60)
            awarded = self.spellManager.empty_queue()
            for s in awarded:
                if self.room is not None:
                    self.room.send_message(s)
                else:
                    print s
            
    def reply_word(self, word, message, wait, orig_word):
        if wait and self.waiting_time > 0:
            time.sleep(self.waiting_time)
        if word == self.current_word_to_reply:
            if word is not None:
                message.reply(word);
            else:
                self.room.send_message("No associated word found for %s" % orig_word)

    def on_event(self, event, client):
        should_return = False
        if not self.enabled:
            should_return = True
        if (not self.enabled) and event.user.id == self.owner_id and event.message.content.startswith("&gt;&gt;"):
            should_return = False
        if not self.running:
            should_return = True
        if not isinstance(event, chatexchange.events.MessagePosted):
            should_return = True
        if should_return:
            return
        
        message = event.message

        if event.user.id == self.client.get_me().id:
            return
        
        h = HTMLParser()
        content = h.unescape(message.content)
        content = re.sub("\(.+?\)", "", content)
        content = re.sub("\s+", " ", content)
        content = content.strip()
        parts = content.split(" ")
        if (not parts[0].startswith(">>")) and (len(parts) != 2 or not parts[0].startswith("@")) and (event.user.id != -2):
            return
        
        if parts[0].startswith(">>"):
            cmd_args = content[2:]
            if (not cmd_args.startswith("translat")) and re.compile("[^a-zA-Z0-9 -]").search(cmd_args):
                message.reply("Command contains invalid characters")
            else:
                output = self.command(cmd_args, message, event)
                if output != False and output is not None:
                    if len(output) > 500:
                        message.reply("Output would be longer than 500 characters (the limit), so only the first 500 characters are posted now.")
                        self.room.send_message(output[:500])
                    else:
                        message.reply(output)
        elif parts[0].startswith("@"):
            c = parts[1]
            if re.compile("[^a-zA-Z0-9-]").search(c):
                return
            word_to_reply = GetAssociatedWord(c)
            self.current_word_to_reply = word_to_reply
            thread.start_new_thread(self.reply_word, (word_to_reply, message, True, c))
    

    def command(self, cmd, msg, event):
        cmd_args = cmd.split(' ')
        cmd_name = cmd_args[0]
        args = cmd_args[1:]
        if cmd_name == "translationchain":
            to_translate = " ".join(args[3:])
            args = args[:3]
            args.append(to_translate)
        if cmd_name in self.commands:
            return self.commands[cmd_name](args, msg, event)

        elif cmd_name in self.owner_commands:
            if msg is None or event.user.id == self.owner_id:
                return self.owner_commands[cmd_name](args, msg, event)
            else:
                return "You don't have the privilege to execute this command"
        else:
            return "Command not found"
    
    def command_time(self, args, msg, event):
        if len(args) > 0:
            try:
                new_time = int(args[0])
                if new_time > -1:
                    self.waiting_time = new_time
                    f = open("config.txt", "w")
                    f.write(str(self.waiting_time))
                    f.close()
                    return "Waiting time set to %s %s." % (args[0], ("seconds" if new_time != 1 else "second"))
                else:
                    return "Given argument has to be a positive integer."
            except ValueError:
                return "Given argument is not a valid integer."
        else:
            return "Command does not have enough arguments."
                
    def command_stop(self, args, msg, event):
        self.enabled = False
        self.running = False
        if msg is not None:
            msg.reply("Bot terminated.")
        self.client.logout()
        return False
        
    def command_disable(self, args, msg, event):
        self.enabled = False
        return "Bot disabled, run >>enable to enable it again."
        
    def command_enable(self, args, msg, event):
        self.enabled = True
        return "Bot enabled."
    
    def command_award(self, args, msg, event):
        spell_id = -1
        user_id = -1
        add_to_queue = False
        if len(args) < 3:
            return "Not enough arguments."
        try:
            spell_id = int(args[0])
            user_id = int(args[1])
        except ValueError:
            return "Not a valid id."
        if args[2] == "-n":
            add_to_queue = False
        elif args[2] == "-q":
            add_to_queue = True
        else:
            return "Invalid arguments."
        return self.spellManager.award(spell_id, user_id, add_to_queue)
        
    def command_viewspells(self, args, msg, event):
        if len(args) < 1:
            return "Not enough arguments."
        user_id = -1
        try:
            user_id = int(args[0])
        except ValueError:
            return "Invalid arguments."
        return self.spellManager.view_spells(user_id)
    
    def command_emptyqueue(self, args, msg, event):
        awarded = self.spellManager.empty_queue()
        for s in awarded:
            if self.room is not None:
                self.room.send_message(s)
            else:
                print s

    def command_translationchain(self, args, msg, event):
        translation_count = -1
        if len(args) < 4:
            return "Not enough arguments."
        try:
            translation_count = int(args[0])
        except ValueError:
            return "Invalid arguments."
        if translation_count < 1:
            return "Invalid arguments."
        if not self.translation_chain_going_on:
            if not args[1] in self.translation_languages or not args[2] in self.translation_languages:
                return "Language not in list. If the language is supported, ping ProgramFOX and he will add it."
            self.translation_chain_going_on = True
            thread.start_new_thread(self.translationchain, (args[3], args[1], args[2], translation_count))
            return "Translation chain started. Translation made by [Google Translate](https://translate.google.com). It might take some time before messages in the chain are posted due to rate limiting."
        else:
            return "There is already a translation chain going on."

    def translationchain(self, text, start_lang, end_lang, translation_count):
        i = 0
        curr_lang = start_lang
        next_lang = None
        curr_text = text
        choices = list(self.translation_languages)
        choices.remove(end_lang)
        while i < translation_count - 1:
            if next_lang is not None:
                curr_lang = next_lang
            while True:
                next_lang = random.choice(choices)
                if next_lang != curr_lang:
                    break
            result = self.translate(curr_text, curr_lang, next_lang)
            curr_text = result
            self.room.send_message("Translate %s-%s: %s" % (curr_lang, next_lang, result))
            i += 1
        final_result = self.translate(curr_text, next_lang, end_lang)
        self.room.send_message("Final translation result (%s-%s): %s" % (next_lang, end_lang, final_result))
        self.translation_chain_going_on = False
    
    def translate(self, text, start_lang, end_lang):
        translate_url = "https://translate.google.com/translate_a/single?client=t&sl=%s&tl=%s&hl=en&dt=bd&dt=ex&dt=ld&dt=md&dt=qc&dt=rw&dt=rm&dt=ss&dt=t&dt=at&dt=sw&ie=UTF-8&oe=UTF-8&prev=btn&srcrom=1&ssel=0&tsel=0&q=%s" % (start_lang, end_lang, urllib.quote_plus(text.encode("utf-8")))
        r = requests.get(translate_url)
        unparsed_json = r.text.split("],[\"\",,", 1)[0].split("]],,", 1)[0][3:]
        #print unparsed_json
        #parsed_json = json.loads(unparsed_json)
        #result_parts = []
        #for json_arr in parsed_json:
        #    result_parts.append(json_arr[0])
        #return " ".join(result_parts)
        return self.parse(unparsed_json)
    
    def parse(self, json):
        is_open = False
        is_backslash = False
        is_translation = True
        all_str = []
        curr_str = []
        for c in json:
            if c != '"' and not is_open:
                continue
            elif c == '"' and not is_open:
                is_open = True
            elif c == '\\':
                is_backslash = not is_backslash
                if is_translation:
                    curr_str.append(c)
            elif c == '"' and is_open and not is_backslash:
                is_open = False
                if is_translation:
                    s = "".join(curr_str).replace("\\\\", "\\").replace("\\\"", "\"")
                    all_str.append(s)
                curr_str = []
                is_backslash = False
                is_translation = not is_translation
            else:
                is_backslash = False
                if is_translation:
                    curr_str.append(c)
        return " ".join(all_str)
            

if __name__ == '__main__':
    bot = WordAssociationBot()
    bot.main()