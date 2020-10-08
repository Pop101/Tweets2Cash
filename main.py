# Try to download and import lemon.
import dl_lemon
try: from lemon import Lemon, Account, HeldTradeable
except ImportError: raise Exception('Could not find or download lemon.py! Please download it from https://github.com/Pop101/Lemon/blob/master/lemon.py manually.')

# Regular Imports
from twitter import Twitter
from nlp_analysis import TextToTradeables, StoppableTimer
from datetime import datetime
from requests.exceptions import HTTPError
import os

import yaml
try: from yaml import CLoader as Loader
except ImportError: from yaml import Loader


KEY_FILE = './config.yml'

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
            config['weighted'] = yml['weighted-factor']
            config['users'] = [str(usr) for usr in yml['user-ids']]
            config['denylist'] = [str(usr).lower().strip() for usr in yml['denylist']]
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
    # re-prune the stock list
    stocks = list(filter(lambda stock: stock[1]*len(stock[0].name) <= config['weighted'], stocks))

    # search twitter cashtags ($STOCK)
    cashtags = [(Lemon.search_for_tradeable(Twitter.cashtag_to_stock(q)), 0) for q in Twitter.get_tweet_cashtags(tweet)]
    cashtags = list(filter(lambda x: x != None and x[0] != None, cashtags))
    stocks.extend(cashtags)

    if config['verbose'] and len(cashtags) > 0:
        print('Cashtag IO: i:{0}, o:{1}'.format(Twitter.get_tweet_cashtags(tweet), [q[0].name for q in cashtags]))
    
    if len(stocks) <= 0 or sent == 0: return

    if config['verbose']:
        to_print = '"{0}":\n'.format(txt)
        to_print += '\t{0} these stocks with a sentiment of {1}:\n'.format('Buying' if sent > 0 else 'Selling', sent)
        for stock in stocks:
            to_print += '\t\t{0} at ${1} (sim: {2}, w_sim: {3})\n'.format(stock[0].name, stock[0].get_cost(), stock[1], stock[1]*len(stock[0].name))
        print(to_print)
    
    # remove like stocks and listed stocks
    found_tradeables, unique_stocks = list(), list()
    for stock in stocks: 
        if stock[0].isin not in found_tradeables and str(stock[0].name).lower().strip() not in config['denylist']:
            found_tradeables.append(stock[0].isin)
            unique_stocks.append(stock)
    stocks = unique_stocks
    del found_tradeables, unique_stocks

    # trade the stocks based on sentiment
    for stock in stocks:
        if sent > 0: result, code = bull(account, stock[0])
        if sent < 0: result, code = bear(account, stock[0])
        
        if not result: print('Error handling stock {0}: "{1}"'.format(stock[0].name, code))
        elif config['verbose']: print('{0} on {1}'.format(code,stock[0].name))

# we must keep a list of scheduled trades in case of program stop 
scheduled_trades = list()

def bull(account:Account, tradeable):
    """
    Buy now, sell at close
    """
    try: quantity = int(config['limit']/tradeable.get_cost())
    except ZeroDivisionError: quantity = 1
    if quantity <= 0: return (False, 'Price higher than set limit') # can't trade fractions kid

    time_to_close = (Lemon.next_market_closing()-datetime.now().astimezone()).total_seconds()
    if time_to_close < config['limit-time']: return (False, 'Too close to closing time!'  if time_to_close > 0 else 'Market Closed') # don't go for profit 1 hr before close

    time_to_open = (Lemon.next_market_availability()-datetime.now().astimezone()).total_seconds()
    if time_to_open > config['limit-time']: return (False, 'Too far from opening time.') # don't try more than 1 hour before market start

    # buy
    try: account.create_buy_order(tradeable, quantity=quantity)
    except HTTPError as e: return (False, 'HTTPError when creating buy order for {0}: {1} {2}'.format(tradeable.name, e.errno, e.strerror))
    
    def sell_later():
        if config['nuke']: quantity = int(HeldTradeable(tradeable.isin, account).get_amount())
        try: account.create_sell_order(tradeable, quantity=quantity, handle_errors=True)
        except HTTPError as e: 
            if config['verbose']: print('HTTPError when creating sell order for {0} after buying: {1} {2}'.format(tradeable.name, e.errno, e.strerror))
    
    timer = StoppableTimer(time_to_close-config['limit-time'], sell_later)
    scheduled_trades.append(timer)
    return (True, 'Executing bullish strategy with a quantity of {0}'.format(quantity))

def bear(account:Account, tradeable):
    """
    Sell now (if any are held), buy at close
    """
    try: quantity = int(config['limit']/tradeable.get_cost())
    except ZeroDivisionError: quantity = 1
    if quantity <= 0: return (False, 'Price higher than set limit') # can't trade fractions kid

    time_to_close = (Lemon.next_market_closing()-datetime.now().astimezone()).total_seconds()
    if time_to_close < config['limit-time']: return (False, 'Too close to closing time!' if time_to_close > 0 else 'Market Closed') # don't go for profit 1 hr before close

    time_to_open = (Lemon.next_market_availability()-datetime.now().astimezone()).total_seconds()
    if time_to_open > config['limit-time']: return (False, 'Too far from opening time.') # don't try more than 1 hour before market start

    # sell
    held_quantity = HeldTradeable(tradeable.isin, account).get_amount()
    sell_quantity = min(quantity, held_quantity) if not config['nuke'] else held_quantity
    try: account.create_sell_order(tradeable, quantity=sell_quantity)
    except HTTPError as e: return(False, 'HTTPError when creating sell order for {0}: {1} {2}'.format(tradeable.name, e.errno, e.strerror))
    
    def buy_later():
        try: account.create_buy_order(tradeable, quantity=quantity)
        except ValueError:
            if config['verbose']: print('Error buying {0} {1} after selling short'.format(tradeable.name, quantity))
        except HTTPError as e: 
            if config['verbose']: print('HTTPError buying {0} after selling short: {1} {2}'.format(tradeable.name, e.errno, e.strerror))
    
    timer = StoppableTimer(time_to_close-config['limit-time'], buy_later)
    scheduled_trades.append(timer)
    return (True, 'Executing bearish strategy with a quantity of {0}'.format(quantity))

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
        twtr.close_stream()
    finally:
        print('Stream closed!')
        # On exit, attempt to cancel all outgoing orders
        for order in account.get_orders():
            order.delete()
            
        # On exit, attempt to execute all queued orders
        for task in scheduled_trades:
            try: task.execute()
            except: task.cancel()

        # Get and print out the change in funds if verbose
        if config['verbose']:
            funds = account.get_funds()
            print('Funds gained: {0} ({1}%)'.format(funds-initial_funds, ['', '+'][funds-initial_funds > 0] + str((funds-initial_funds)/initial_funds)))