# Try to download and import lemon.
import dl_lemon
try: from lemon import Lemon, Account, HeldTradeable
except ImportError: raise ImportError('Could not find or download lemon.py! Please download it from https://github.com/Pop101/Lemon/blob/master/lemon.py manually.')

# Regular Imports
from twitter import Twitter
from nlp_analysis import TextToTradeables, StoppableTimer
from datetime import datetime
import os

import yaml
try: from yaml import CLoader as Loader
except ImportError: from yaml import Loader


KEY_FILE = './config-actual.yml'

# Load all the keys and config options we need
def load_config(path='./config.yml'):
    assert os.path.exists(path), "Config does not exist!"
    with open(path) as file:
        yml = yaml.load(file.read(), Loader=Loader)
        config = dict()
        try: 
            config['twitter'] = (yml['twitter']['consumer-key'], yml['twitter']['consumer-secret'], yml['twitter']['app-token'], yml['twitter']['app-secret'])
            config['lemon'] = 'TOKEN {0}'.format(yml['lemon']) if 'TOKEN' not in yml['lemon'] else yml['lemon']
            config['account-name'] = yml['lemon-account-name']
            config['verbose'] = yml['verbose']
            config['limit'] = yml['transaction-limit']
            config['limit-time'] = yml['limit-time']
            config['nuke'] = yml['sell-all-mode']
            config['match'] = yml['match-factor']
            config['users'] = [str(usr) for usr in yml['user-ids']]
        except KeyError: 
            print('Error in config')
            quit(1)
        del yml
    assert '<KEY>' not in repr(config), 'Please add your keys to the config!'
    return config

def on_tweet_recieved(account:Account, tweet):
    txt = Twitter.get_tweet_text(tweet)

    # get tweet sentiment
    sent = TextToTradeables.get_sentiment(txt)

    # search body with nlp
    stocks = TextToTradeables.process_text(txt, similarity_cutoff=config['match'], min_noun_length=4)

    # search twitter cashtags ($STOCK)
    cashtags = [(TextToTradeables.deep_search(Twitter.cashtag_to_stock(q)), 0) for q in Twitter.get_tweet_cashtags(tweet)]
    print('i:{0}, o:{1}'.format(Twitter.get_tweet_cashtags(tweet), [q[0].name for q in cashtags]))
    
    if len(stocks) <= 0 or sent == 0: return

    if config['verbose']:
        to_print = '"{0}":\n'.format(txt)
        to_print += '\t{0} these stocks with a sentiment of {1}:\n'.format('Buy' if sent > 0 else 'Sell', sent)
        for stock in stocks:
            to_print += '\t\t{0} at ${1} (sim: {2}, w_sim: {3})\n'.format(stock[0].name, stock[0].get_cost(), stock[1], stock[1]*len(stock[0].name))
        print(to_print)
    
    # trade the stocks based on sentiment
    for stock in stocks:
        if sent > 0: bull(account, stock[0])
        if sent < 0: bear(account, stock[0])

# we must keep a list of scheduled trades in case of program stop 
scheduled_trades = list()

def bull(account:Account, tradeable):
    """
    Buy now, sell at close
    """
    quantity = int(config['limit']/tradeable.get_cost())
    if quantity <= 0: return # can't trade fractions kid

    time_to_close = (Lemon.next_market_closing()-datetime.datetime.now()).total_seconds()
    if time_to_close < config['limit-time']: return # don't go for profit 1 hr before close

    account.create_buy_order(tradeable, quantity=quantity)
    
    def sell_later():
        if config['nuke']: quantity = int(HeldTradeable(tradeable.isin, account).get_amount())
        account.create_sell_order(tradeable, quantity=quantity)
    
    timer = StoppableTimer(time_to_close-config['limit-time'], sell_later)
    scheduled_trades.append(timer)

def bear(account:Account, tradeable):
    """
    Sell now (if any are held), buy at close
    """
    quantity = int(config['limit']/tradeable.get_cost())
    if quantity <= 0: return # can't trade fractions kid

    time_to_close = (Lemon.next_market_closing()-datetime.datetime.now()).total_seconds()
    if time_to_close < config['limit-time']: return # don't go for profit 1 hr before close

    sell_quantity = quantity if not config['nuke'] else int(HeldTradeable(tradeable.isin, account).get_amount())
    account.create_sell_order(tradeable, quantity=sell_quantity)
    
    def buy_later():
        account.create_buy_order(tradeable, quantity=quantity)
    
    timer = StoppableTimer(time_to_close-config['limit-time'], buy_later)
    scheduled_trades.append(timer)

if __name__ == '__main__':
    config = load_config(KEY_FILE)

    # load up our lemon.markets account
    account = Lemon.select_account(config['lemon'], config['account-name'])
    initial_funds = account.get_funds()
    print('Available funds in account "{0}": ${1}'.format(config['account-name'],initial_funds))
    
    # instanciate twitter and set callback
    twtr = Twitter(*config['twitter'])
    twtr.callback = lambda tweet: on_tweet_recieved(account, tweet)
    
    # start the stream and hope for the best!
    try:
        if config['verbose']: print('Opening Stream! Use Control-C to stop!')
        twtr.open_stream(users=config['users'], is_async=False, restrict=True, verbose=config['verbose'])
    except (OSError, SystemError, KeyboardInterrupt):
        if config['verbose']: print('Attempting to stop gracefully.')
    finally:
        # On exit, attempt to execute all queued orders
        twtr.close_stream()
        for task in scheduled_trades:
            try: task.execute()
            except: task.cancel()

        # Get and print out the change in funds if verbose
        if config['verbose']:
            funds = account.get_funds()
            print('Funds gained: {0} ({1}%)'.format(funds-initial_funds, ['', '+'][funds-initial_funds > 0] + str((funds-initial_funds)/initial_funds)))