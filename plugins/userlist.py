# jsb.plugs.common/userlist.py
#
#

""" list all available users. """

## jsb imports

from jsb.utils.exception import handle_exception
from jsb.lib.commands import cmnds
from jsb.lib.examples import examples
from jsb.utils.pdod import Pdod
from jsb.lib.datadir import getdatadir
from jsb.lib.persistconfig import PersistConfig
from jsb.lib.threads import start_new_thread
from jsb.lib.fleet import fleet
from jsb.lib.persist import PlugPersist
from jsb.lib.threadloop import TimedLoop

from jsb.lib.persist import PlugPersist

## basic imports

import re, random
import os, time, datetime
import logging

cfg = PersistConfig()
cfg.define('watcher-interval', 5)
cfg.define('watcher-enabled', 0)
cfg.define('eta-timeout', 72000)

## defines

RE_ETA = re.compile(r'ETA (?P<item>\([^\)]+\)|\[[^\]]+\]|\w+)(?P<mod>\+\+|--)( |$)')

userpath = '/home/c-beam/users'
#usermap = eval(open("/home/mirror/.erawrim/usermap").read())
usermap = eval(open('%s/usermap' % cfg.get('datadir')).read())

weekdays = ['MO', 'DI', 'MI', 'DO', 'FR', 'SA', 'SO']


def getuser(ievent):
    if ievent.channel in usermap:
        return usermap[ievent.channel]
    elif ievent.fromm in usermap:
        return usermap[ievent.fromm]
    elif ievent.channel.find('c-base.org') > -1:
        return ievent.channel[:-11]
    elif ievent.fromm.find('c-base.org') > -1:
        return ievent.fromm[:-10]
    else:
        return 0

class EtaItem(PlugPersist):
     def __init__(self, name, default={}):
         PlugPersist.__init__(self, name)
         self.data.name = name
         self.data.etas = self.data.etas or {}
         self.data.etatimestamps = self.data.etatimestamps or {}
         self.data.etasubs = self.data.etasubs or []
         self.data.opensubs = self.data.opensubs or []

etaitem = EtaItem('eta')

class UserlistError(Exception): pass

class UserlistWatcher(TimedLoop):
    lastcount = -1
    lasteta = -1
    lastuserlist = []
    oldday = weekdays[datetime.datetime.now().weekday()]

    def handle(self):
        day = weekdays[datetime.datetime.now().weekday()]
        if day != self.oldday:
            self.oldday = day
            dayitem = LteItem(day)
            # convert LTEs to ETAs for current day
            for user in dayitem.data.ltes.keys():
                seteta(user, dayitem.data.ltes[user][0])
                try: bot = fleet.byname(self.name)
                except: pass
                if bot and bot.type == "sxmpp":
                    for etasub in etaitem.data.etasubs:
                        bot.say(etasub, 'ETA %s %s' % (user, dayitem.data.ltes[user][0]))
                del dayitem.data.ltes[user]
            # clear LTEs for current day
            dayitem.data.ltes = {}
            dayitem.save()   
        if not cfg.get('watcher-enabled'):
            raise UserlistError('watcher not enabled, use "!%s-cfg watcher-enabled 1" to enable' % os.path.basename(__file__)[:-3])
        try:
            # check if at least one user is logged in
            # or try to ping the switches
            users = userlist()
            usercount = len(users)
            if usercount != self.lastcount or self.lasteta != len(etaitem.data.etas):
                if self.lastcount == 0 and usercount > 0:
                    bot = 0
                    try: bot = fleet.byname(self.name)
                    except: pass
                    if bot and bot.type == "sxmpp":
                        for opensub in etaitem.data.opensubs:
                            bot.say(opensub, 'c3pO is awake')

                self.lastcount = usercount
                self.lasteta = len(etaitem.data.etas)

                logging.debug("Usercount: %s" % usercount)
                if usercount > 0:
                    #self.announce('open', 'chat')
                    # check if someone arrived who set an ETA
                    for user in users:
                        try: 
                            del etaitem.data.etas[user]
                            etaitem.save()
                        except: pass

                    # find out who just arrived
                    newusers = []
                    for user in userlist():
                        if user not in self.lastuserlist:
                            newusers.append(user)
                    #tell subscribers who has just arrived
                    for user in newusers:
                        logging.debug('%s has just arrived!' % user)
                    self.lastuserlist = userlist()
                #else:
                    #if len(etaitem.data.etas) > 0:
                        #self.announce('incoming', 'dnd')
                    #else:
                        #self.announce('closed', 'xa')

            # remove expired ETAs
            for user in etaitem.data.etas.keys():
                if time.time() > etaitem.data.etatimestamps[user]:
                    del etaitem.data.etas[user]
                    del etaitem.data.etatimestamps[user]
                    etaitem.save()

        except UserlistError:
            logging.error("watcher error")
            pass
        except KeyError:
            logging.error("watcher error")
            pass
       
        time.sleep(cfg.get('watcher-interval'))
  
    def announce(self, status, show):
        logging.info('announce(%s, %s)' % (status, show))
        print 'announce(%s, %s)' % (status, show)
        if not self.running or not cfg.get('watcher-enabled'):
            return
        for name in fleet.list():
            bot = 0
            try: bot = fleet.byname(self.name)
            except: pass
            if bot and bot.type == "sxmpp":
                print '%s[%s].setstatus(%s, %s)' % (bot.name, bot.type, status, show)
                bot.setstatus(status, show)

#watcher = ''
watcher = UserlistWatcher('default-sxmpp', cfg.get('watcher-interval'))

#watcher = UserlistWatcher()
#if not watcher.data:
#    watcher = UserlistWatcher()

def init():
    print "init"
    watcher.start()
    return 1 
#    if cfg.get('watcher-enabled'):
#        watcher = UserlistWatcher('ulwatcher', 5)
#        watcher.start()
#    return 1

def shutdown():
    print "shutdown"
    #if watcher.running:
    watcher.stop()
    return 1

def userlist():
    return os.listdir(userpath)

## userlist command

def handle_userlist(bot, ievent):
    """list all user that have logged in on the mirror."""
    users = userlist()
    reply = ''
    if len(users) > 0 or len(etaitem.data.etas) > 0:
        if len(users) > 0:
            reply += 'available: ' + ', '.join(users) + '\n' 
        if len(etaitem.data.etas) > 0:
            etalist = []
            for key in etaitem.data.etas.keys():
                etalist += ['%s [%s]' % (key, etaitem.data.etas[key])]
            reply += 'ETA: ' + ', '.join(etalist) + '\n'
    else:
        reply = "No one there"
    ievent.reply(reply)

def handle_userlist_login(bot, ievent):
    user = getuser(ievent)
    if not user: return ievent.reply('I cannot figure out your nickname, sorry')
    try:
        result = os.system('touch %s/%s' % (userpath, user))
        if result == 0:
            ievent.reply('Danke dass du dich angemeldet hast! :)')
        else: 
            ievent.reply('Du konntest nicht manuell angemeldet werden, ich weiss nicht warum.')
    except UserlistError, e:
        ievent.reply(str(s))

def handle_userlist_logout(bot, ievent):
    user = getuser(ievent)
    print user
    if not user: return ievent.reply('I cannot figure out your nickname, sorry')
    try:
        result = os.remove('%s/%s' % (userpath, user))
        ievent.reply('Danke dass du dich abgemeldet hast! :)')
        #ievent.reply('Du konntest nicht manuell abgemeldet werden, ich weiss nicht warum.')
    except UserlistError, e:
        ievent.reply(str(s))

def handle_userlist_subeta(bot, ievent):
    try:
        if ievent.channel not in etaitem.data.etasubs:
            etaitem.data.etasubs.append(ievent.channel)
            etaitem.save()
        ievent.reply('thank you for your subscription for eta notifications')
    except UserlistError, e:
        ievent.reply(str(s))

def handle_userlist_unsubeta(bot, ievent):
    try:
        if ievent.channel in etaitem.data.etasubs:
            print 'remove %s from %s' % (ievent.channel, str(etaitem.data.etasubs))
            etaitem.data.etasubs.remove(ievent.channel)
            etaitem.save()
        ievent.reply('you have been unsubscribed from eta notifications')
    except UserlistError, e:
        ievent.reply(str(s))
   
def handle_userlist_subopen(bot, ievent):
    try:
        if ievent.channel not in etaitem.data.opensubs:
            etaitem.data.opensubs.append(ievent.channel)
            etaitem.save()
        ievent.reply('thank you for your opening notification subscription')
    except UserlistError, e:
        ievent.reply(str(s))

def handle_userlist_unsubopen(bot, ievent):
    try:
        if ievent.channel in etaitem.data.opensubs:
            print 'remove %s from %s' % (ievent.channel, str(etaitem.data.opensubs))
            etaitem.data.opensubs.remove(ievent.channel)
            etaitem.save()
        ievent.reply('you have been unsubscribed from opening notifications')
    except UserlistError, e:
        ievent.reply(str(s))
    
def handle_userlist_lssub(bot, ievent):
    try:
        ievent.reply('ATT-Subbscribers: %s\nOpening Subscribers: %s\nETA-Subscribers: %s' % (str(etaitem.data.subscribers), str(etaitem.data.opensubs), str(etaitem.data.etasubs)))
    except UserlistError, e:
        ievent.reply(str(s))

def handle_userlist_lseta(bot, ievent):
    try:
        if len(etaitem.data.etas) > 0:
            etalist = []
            for key in etaitem.data.etas.keys():
                etalist += ['%s [%s]' % (key, etaitem.data.etas[key])]
            ievent.reply('ETA: %s' % ', '.join(etalist))
    except UserlistError, e:
        ievent.reply(str(s))

def seteta(user, eta):
    if eta == '0':
        del etaitem.data.etas[user]
    else:
        etaitem.data.etas[user] = eta
        etaitem.data.etatimestamps[user] = time.time() + cfg.get('eta-timeout')
    etaitem.save()


def handle_userlist_eta(bot, ievent):
    eta = 0
    if ievent.args[0].upper() in weekdays:
        return handle_lte(bot, ievent)
    if ievent.args[0] in ('gleich', 'bald'):
        foo = datetime.datetime.now() + datetime.timedelta(minutes=30)
        print foo
        eta = int(foo.strftime("%H%M"))
    else:
        eta = ievent.rest
        
        #try:    eta = int(ievent.args[0])
        #except: return ievent.reply('Please set your ETA like this: !eta 1800')
    user = getuser(ievent)
    if not user: return ievent.reply('I cannot figure out your nickname, sorry')
    seteta(user, eta)
    try:
        for etasub in etaitem.data.etasubs:
            bot.say(etasub, 'ETA %s %s' % (user, eta))
        #ievent.reply('Set eta for %s to %d' % (user, eta))
        ievent.reply('Danke dass Du bescheid sagst :)')
 
    except UserlistError, e:
        ievent.reply(str(s))

def handle_userlist_watch_start(bot, ievent):
    if not cfg.get('watcher-enabled'):
        ievent.reply('watcher not enabled, use "!%s-cfg watcher-enabled 1" to enable and reload the plugin' % os.path.basename(__file__)[:-3])
        return
    watcher.add(bot, ievent)
    ievent.reply('ok')

def handle_userlist_watch_stop(bot, ievent):
    if not cfg.get('watcher-enabled'):
        ievent.reply('watcher not enabled, use "!%s-cfg watcher-enabled 1" to enable and reload the plugin' % os.path.basename(__file__)[:-3])
        return
    watcher.remove(bot, ievent)
    ievent.reply('ok')

def handle_userlist_watch_list(bot, ievent):
    if not cfg.get('watcher-enabled'):
        ievent.reply('watcher not enabled, use "!%s-cfg watcher-enabled 1" to enable and reload the plugin' % os.path.basename(__file__)[:-3])
        return
    result = []
    for name in sorted(watcher.data.keys()):
        if watcher.data[name]:
            result.append('on %s:' % name)
        for channel in sorted(watcher.data[name].keys()):
            result.append(channel)
    if result:
        ievent.reply(' '.join(result))
    else:
        ievent.reply('no watchers running')


cmnds.add('ul', handle_userlist, ['GUEST'])
cmnds.add('who', handle_userlist, ['GUEST'])
cmnds.add('ul-logout', handle_userlist_logout, ['GUEST'])
cmnds.add('logout', handle_userlist_logout, ['GUEST'])
cmnds.add('ul-login', handle_userlist_login, ['GUEST'])
cmnds.add('login', handle_userlist_login, ['GUEST'])
cmnds.add('ul-eta', handle_userlist_eta, ['GUEST'])
cmnds.add('eta', handle_userlist_eta, ['GUEST'])
cmnds.add('ul-subeta', handle_userlist_subeta, ['GUEST'])
cmnds.add('ul-unsubeta', handle_userlist_unsubeta, ['GUEST'])
cmnds.add('ul-subopen', handle_userlist_subopen, ['GUEST'])
cmnds.add('ul-unsubopen', handle_userlist_unsubopen, ['GUEST'])
cmnds.add('ul-subscribe', handle_userlist_subeta, ['GUEST'])
cmnds.add('ul-unsubscribe', handle_userlist_unsubeta, ['GUEST'])
cmnds.add('ul-lssub', handle_userlist_lssub, ['ULADM'])
cmnds.add('userlist', handle_userlist, ['GUEST'])
examples.add('userlist', 'list all user that have logged in on the mirror.', 'userlist')

cmnds.add('userlist-watch-start', handle_userlist_watch_start, 'ULADM')
cmnds.add('userlist-watch-stop',  handle_userlist_watch_stop, 'ULADM')
cmnds.add('userlist-watch-list',  handle_userlist_watch_list, 'ULADM')


# MO 1900 2300
class LteItem(PlugPersist):
    def __init__(self, name, default={}):
         PlugPersist.__init__(self, name)
         self.data.name = name
         self.data.ltes = self.data.ltes or {}

def handle_lte(bot, ievent):
    user = getuser(ievent)
    if not user: return ievent.reply('I cannot figure out your nickname, sorry')
    item = LteItem(user)
    args = ievent.rest.upper().split(' ')

    lteusers = PlugPersist('lteusers')
    if not lteusers.data: lteusers.data = {}
    if len(ievent.args) == 3:
        (day, start, end) = args
        if args[0] not in ('MO', 'DI', 'MI', 'DO', 'FR', 'SA', 'SO'): 
            #, 'MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU'):
            return ievent.reply('Please enter your LTE like this: !lte MO 1900 2200')
        item.data.ltes[args[0]] = args
        item.save()
        dayitem = LteItem(args[0])
        dayitem.data.ltes[user] = args[1:]
        dayitem.save()
        lteusers.data[user] = time.time()
        lteusers.save()
        ievent.reply('Thanks, your LTE has been saved.')
    elif len(ievent.args) == 2:
        if args[1] == '0':
            dayitem = LteItem(args[0])
            if user in dayitem.data.ltes.keys():
                del dayitem.data.ltes[user]            
                dayitem.save()
                ievent.reply('Thanks, your LTE for %s has been deleted.' % args[0])
            else:
                ievent.reply('You have no LTE set for %s.' % args[0])
    elif len(ievent.args) == 1:
        if args[0] in ('MO', 'DI', 'MI', 'DO', 'FR', 'SA', 'SO'):
            dayitem = LteItem(args[0])
            if len(dayitem.data.ltes.keys()) > 0:
                reply = 'LTEs for %s: \n' % args[0]
                for user in dayitem.data.ltes.keys():
                    reply += '%s [%s]\n' % (user, '-'.join(dayitem.data.ltes[user]))
                ievent.reply(reply)
        else:
            ievent.reply('Unknown day')
    elif len(ievent.args) == 0:
        reply = ''
        for day in weekdays:
            dayitem = LteItem(day)
            if len(dayitem.data.ltes.keys()) > 0:
                reply += '%s: %s\n' % (day, ', '.join(dayitem.data.ltes.keys()))
        ievent.reply(reply)
    else:
        ievent.reply(str(len(ievent.rest.split(' '))))

cmnds.add('lte', handle_lte, ['GUEST'])
