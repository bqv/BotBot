import re
import sys
import time
import socket
import sqlite3
import traceback

print("TheBotMeister.")

try:
    __import__('tty').setcbreak(sys.stdin.fileno())
except:
    pass

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(1800)
newline = "\r\n"
#host = "irc.awfulnet.org"
host = "192.168.1.65"
port = 4444

NAMERX = "^[\w-]+$"

dex = sqlite3.connect("dex.db")
dex.isolation_level = None
sql = dex.cursor()

def backup():
    with __import__('gzip').open(".%s.sql.gz" %(str(round(time.time()))), 'w') as f:
        for line in dex.iterdump():
            f.write(("%s\n" %(line)).encode('utf-8'))
        f.flush()

def send(line):
    sock.send((line+newline).encode('utf-8'))

def recv():
    data = sock.recv(4096).decode('utf-8')
    while data[-2:] != newline:
        data += sock.recv(1024).decode('utf-8')
    return data.split(newline)

def privmsg(dest, text):
    for line in text.split('\n'):
        send("%s %s :%s" %("PRIVMSG" if dest[0]=='#' else "NOTICE", dest, line))

def command(prefix, text, reply, caller):
    if text[0] == "init":
        sql.execute('''CREATE TABLE bots (
                bid INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL COLLATE NOCASE,
                owner TEXT NOT NULL COLLATE NOCASE,
                description TEXT NOT NULL)''')
        sql.execute('''CREATE TABLE commands (
                cid INTEGER PRIMARY KEY AUTOINCREMENT,
                bid INTEGER NOT NULL,
                name TEXT NOT NULL COLLATE NOCASE,
                prefix TEXT NOT NULL,
                description TEXT NOT NULL)''')
        reply("\x02Success\x02: Database Initialized")
    elif text[0] == "rquery":
        q = sql.execute(' '.join(text[1:]))
        reply("R"+str(q.rowcount))
        for r in q.fetchall():
            reply(str(r))
    elif text[0] == "ping":
        reply("Pong!")
    elif text[0] == "pong":
        reply("Ping!")
    elif text[0] == "bots":
        query = sql.execute("SELECT name FROM bots ORDER BY name")
        botlist = list([row[0] for row in query.fetchall()])
        if len(botlist) > 0:
            head = "\x02Registered bots (%d)\x02: "%(len(botlist))
            for sublist in [botlist[i:i+20] for i in range(0, len(botlist), 20)]:
                reply(head+(", ".join(sublist)))
                head = "\x02(cont.)\x02 "
        else:
            reply("\x02Registered bots (0)\x02: ")
    elif text[0] == "register":
        try:
            name = text[1]
            owner = text[2]
            desc = ' '.join([text[3],]+text[4:])
            if sql.execute("INSERT OR IGNORE INTO bots(name, owner, description) VALUES (?, ?, ?)", (name, owner, desc)).rowcount != 0:
                reply("\x02Success\x02: Bot '%s' Registered" %(name))
            else:
                reply("\x02NameError\x02: Bot '%s' already registered" %(name))
        except IndexError:
            reply("\x02TypeError\x02: register takes 3 (or more) arguments (%d given)" %(len(text)-1))
            reply(" --> register(TEXT bot, TEXT owner, TEXT description...)")
    elif text[0] == "rename":
        try:
            name = text[1]
            newname = text[2]
            if sql.execute("UPDATE bots SET name=? WHERE name=?", (newname,name)).rowcount != 0:
                reply("\x02Success\x02: Bot '%s' renamed to '%s'" %(name, newname))
            else:
                reply("\x02NameError\x02: No such bot '%s'" %(name))
        except IndexError:
            reply("\x02TypeError\x02: rename takes exactly 2 arguments (%d given)" %(len(text)-1))
            reply(" --> rename(TEXT oldname, TEXT newname)")
    elif text[0] == "reregister":
        try:
            name = text[1]
            owner = text[2]
            desc = ' '.join([text[3],]+text[4:])
            if sql.execute("UPDATE bots SET owner=?,description=? WHERE name=?", (owner, desc, name)).rowcount != 0:
                reply("\x02Success\x02: Bot '%s' updated" %(name))
            else:
                reply("\x02NameError\x02: No such bot '%s'" %(name))
        except IndexError:
            reply("\x02TypeError\x02: reregister takes exactly 3 arguments (%d given)" %(len(text)-1))
            reply(" --> reregister(TEXT bot, TEXT newowner, TEXT newdescription...)")
    elif text[0] == "unregister":
        try:
            name = text[1]
            c = sql.execute("DELETE FROM commands WHERE bid=(SELECT bid FROM bots WHERE name=?)", (name,)).rowcount
            if sql.execute("DELETE FROM bots WHERE name=?", (name,)).rowcount != 0:
                reply("\x02Success\x02: Bot '%s' and %d commands unregistered" %(name, c))
            else:
                reply("\x02NameError\x02: No such bot '%s'" %(name))
        except IndexError:
            reply("\x02TypeError\x02: unregister takes exactly 1 argument (%d given)" %(len(text)-1))
            reply(" --> unregister(TEXT bot)")
    elif text[0] == "describe":
        try:
            name = text[1]
            query = sql.execute("SELECT name, owner, description FROM bots WHERE name=?", (name,)).fetchone()
            if query != None:
                reply("\x02Name\x02: %s, \x02Owner\x02: %s, \x02Description\x02: %s" % tuple(query))
            else:
                reply("\x02NameError\x02: No such bot '%s'" %(name))
        except IndexError:
            reply("\x02TypeError\x02: describe takes exactly 1 argument (%d given)" %(len(text)-1))
            reply(" --> describe(TEXT bot)")
    elif text[0] == "prefixes" or text[0] == "prefixes":
        try:
            name = text[1]
            if sql.execute("SELECT count(bid) FROM bots WHERE name=?", (name,)).fetchone()[0] != 0:
                query = sql.execute("SELECT DISTINCT prefix FROM commands WHERE bid=(SELECT bid FROM bots WHERE name=?)", (name,))
                prefixes = list([row[0] for row in query.fetchall()])
                reply(("\x02Registered prefixes (%d)\x02: "%(len(prefixes)))+(" ".join(prefixes)))
            else:
                reply("\x02NameError\x02: No such bot '%s'" %(name))
        except IndexError:
            reply("\x02TypeError\x02: prefixes takes exactly 1 argument (%d given)" %(len(text)-1))
            reply(" --> prefixes(TEXT bot)")
    elif text[0] == "allprefixes":
        query = sql.execute("SELECT DISTINCT prefix FROM commands")
        prefixes = list([row[0] for row in query.fetchall()])
        reply(("\x02ALL used prefixes (%d)\x02: "%(len(prefixes)))+(" ".join(prefixes)))
    elif text[0] == "addcmd":
        try:
            name = text[1]
            command = text[2]
            pfx = text[3][:2]
            desc = ' '.join([text[4],]+text[5:])
            if sql.execute("SELECT count(bid) FROM bots WHERE name=?", (name,)).fetchone()[0] != 0:
                if sql.execute("SELECT count(*) FROM commands WHERE bid=(SELECT bid FROM bots WHERE name=?) AND name=? AND prefix=?", (name, command, pfx)).fetchone()[0] == 0:
                    sql.execute("INSERT INTO commands(bid, name, prefix, description) VALUES ((SELECT bid FROM bots WHERE name=?), ?, ?, ?)", (name, command, pfx, desc))
                    reply("\x02Success\x02: Command '%s%s' Added" %(pfx, command))
                else:
                    reply("\x02NameError\x02: Command '%s%s' already registered for %s" %(pfx, command, name))
            else:
                reply("\x02NameError\x02: No such bot '%s'" %(name))
        except IndexError:
            reply("\x02TypeError\x02: addcmd takes 4 (or more) arguments (%d given)" %(len(text)-1))
            reply(" --> addcmd(TEXT bot, TEXT command, TEXT prefix, TEXT description...)")
    elif text[0] == "allcmds" or text[0] == "commands" or text[0] == "allcmd":
        query = sql.execute("SELECT DISTINCT prefix||name FROM commands ORDER BY name")
        commands = list([row[0] for row in query.fetchall()])
        if len(commands) > 0:
            head = "\x02ALL registered commands (%d)\x02: "%(len(commands))
            for sublist in [commands[i:i+20] for i in range(0, len(commands), 20)]:
                reply(head+(", ".join(sublist)))
                head = "\x02(cont.)\x02 "
        else:
            reply("\x02ALL registered commands (0)\x02: ")
    elif text[0] == "listcmds" or text[0] == "listcmd":
        try:
            name = text[1]
            if sql.execute("SELECT count(bid) FROM bots WHERE name=?", (name,)).fetchone()[0] != 0:
                query = sql.execute("SELECT prefix||name FROM commands WHERE bid=(SELECT bid FROM bots WHERE name=?) ORDER BY name", (name,))
                commands = list([row[0] for row in query.fetchall()])
                if len(commands) > 0:
                    head = "\x02Registered commands (%d)\x02: "%(len(commands))
                    for sublist in [commands[i:i+20] for i in range(0, len(commands), 20)]:
                        reply(head+(", ".join(sublist)))
                        head = "\x02(cont.)\x02 "
                else:
                    reply("\x02Registered commands (0)\x02: ")
            else:
                reply("\x02NameError\x02: No such bot '%s'" %(name))
        except IndexError:
            reply("\x02TypeError\x02: listcmds takes exactly 1 argument (%d given)" %(len(text)-1))
            reply(" --> listcmds(TEXT bot)")
    elif text[0] == "delcmd":
        try:
            name = text[1]
            command = text[2]
            pfx = text[3][:2]
            if sql.execute("SELECT count(bid) FROM bots WHERE name=?", (name,)).fetchone()[0] != 0:
                if sql.execute("DELETE FROM commands WHERE bid=(SELECT bid FROM bots WHERE name=?) AND name=? AND prefix=?", (name, command, pfx)).rowcount != 0:
                    reply("\x02Success\x02: Command '%s%s' Deleted" %(pfx, command))
                else:
                    reply("\x02NameError\x02: No such command '%s%s'" %(pfx, command))
            else:
                reply("\x02NameError\x02: No such bot '%s'" %(name))
        except IndexError:
            reply("\x02TypeError\x02: delcmd takes exactly 3 arguments (%d given)" %(len(text)-1))
            reply(" --> delcmd(TEXT bot, TEXT command, TEXT prefix)")
    elif text[0] == "setcmd":
        try:
            name = text[1]
            command = text[2]
            pfx = text[3][:2]
            desc = ' '.join([text[4],]+text[5:])
            if sql.execute("SELECT count(bid) FROM bots WHERE name=?", (name,)).fetchone()[0] != 0:
                if sql.execute("UPDATE commands SET description=? WHERE bid=(SELECT bid FROM bots WHERE name=?) AND name=? AND prefix=?", (desc, name, command, pfx)).rowcount != 0:
                    reply("\x02Success\x02: Command '%s%s' Updated" %(pfx, command))
                else:
                    reply("\x02NameError\x02: No such command '%s%s'" %(pfx, command))
            else:
                reply("\x02NameError\x02: No such bot '%s'" %(name))
        except IndexError:
            reply("\x02TypeError\x02: setcmd takes 4 (or more) arguments (%d given)" %(len(text)-1))
            reply(" --> setcmd(TEXT bot, TEXT command, TEXT prefix, TEXT description...)")
    elif text[0] == "helpcmd" or (text[0] == "help" and len(text) > 1 and text[1].lower() != "botbot"):
        if len(text) <= 4:
            if len(text) == 2:
                command = text[1]
                commands = sql.execute("SELECT prefix||name, description FROM commands WHERE prefix||name=?", (command,)).fetchall()
            elif len(text) == 3:
                name = text[1]
                command = text[2]
                commands = sql.execute("SELECT prefix||name, description FROM commands WHERE bid=(SELECT bid FROM bots WHERE name=?) AND prefix||name=?", (name, command)).fetchall()
            elif len(text) == 4:
                name = text[1]
                command = text[2]
                pfx = text[3][:2]
                commands = sql.execute("SELECT prefix||name, description FROM commands WHERE bid=(SELECT bid FROM bots WHERE name=?) AND name=? AND prefix=?", (name, command, pfx)).fetchall()
            if len(commands) == 0:
                reply("\x02NameError\x02: No such command '%s'" %(command))
            elif len(commands) == 1:
                reply("\x02Command\x02: %s, \x02Description\x02: %s" % tuple(commands[0]))
            else:
                reply("\x02NameError\x02: Ambiguous command name '%s'. Matches: %s" %(command, ', '.join([row[0] for row in commands])))
        else:
            reply("\x02TypeError\x02: helpcmd takes exactly 3 argument (%d given)" %(len(text)-1))
            reply(" --> helpcmd(TEXT bot, TEXT command, TEXT prefix)")
    elif text[0] == "help":
        reply("\x02BotDex commands\x02: See @describe BotBot, !listcmds BotBot and @helpcmd BotBot <command> <prefix>")

if sock.connect_ex((host, port)) == 0:
    #send("NICK BotBot")
    send("NICK TobTob")
    send("USER BotMeister * * *")
    send("PASS bot/awfulnet:sadaharu")
    while dex:
        try:
            for line in recv():
                if not line: continue
                else:
                    sys.stdout.buffer.write((line+'\n').encode('utf-8'))
                    sys.stdout.flush()
                    line = line.split()

                if line[0] == "PING":
                    send("PONG "+line[1])
                elif line[1] == "001":
                    #send("PRIVMSG NickServ :identify %s" %(input()))
                    send("JOIN #bots,#test")
                    send("JOIN #lgbteens,#programming,#teenagers")
                elif line[1] == "INVITE":
                    send("JOIN %s" %(line[3]))
                elif line[1] == "PRIVMSG":
                    msg = ' '.join(line[3:]).lstrip(':').strip()

                    if msg[0] == '!' or msg[0] == '@' or line[2][0] != '#':
                        if line[2][0] != '#': # Hack for serv-like PM responses
                            respond = lambda text: privmsg(line[0].split('!')[0][1:], text)
                            msg = '#'+msg
                        elif msg[0] == '@' and line[2].lower() != "#teenagers": # as per keve
                            respond = lambda text: privmsg(line[2], text)
                        else:#if msg[0] == '!':
                            respond = lambda text: privmsg(line[0].split('!')[0][1:], text)

                        sql.execute("SAVEPOINT last")
                        try:
                            command(msg[0], msg[1:].split(), respond, line[0].split('!')[0][1:])
                        except sqlite3.Error as e:
                            print("An error occurred: "+e.args[0])
                            traceback.print_exc()
                            privmsg(line[2], "An error occurred: "+e.args[0])
                            sql.execute("ROLLBACK TO SAVEPOINT last")
                        sql.execute("RELEASE SAVEPOINT last")
        except KeyboardInterrupt:
            try:
                dex.commit()
                backup()
                print("Technified.")
                time.sleep(5) # Waiting for confirmation...
                print("ReMeistered.")
            except KeyboardInterrupt:
                break
        except socket.error as e:
            print("Socket Error: %s" %(e))
            break
        except Exception:
            traceback.print_exc()

sock.close()
dex.commit()
dex.close()

print("RetsiemTobEht.")
