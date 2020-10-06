import json, os
import tweepy
from concurrent.futures import ThreadPoolExecutor
from inspect import signature
import sys, traceback, requests
from unicodedata import normalize

class Twitter:
    def __init__(self, consumer_key, consumer_secret, app_token, app_secret):
        assert consumer_key, 'No consumer key'
        assert consumer_secret, 'No consumer secret'
        assert app_token, 'No app token'
        assert app_secret, 'No app secret'

        self.auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
        self.auth.set_access_token(app_token, app_secret)
        self.api = tweepy.API(self.auth)
        self.stream = None
    
    def stream_open(self):
        return self.stream
    
    def open_stream(self, is_async:bool=True, users=['25073877'], restrict=True, verbose=True):
        if not self.stream_open():
            self.stream_listener = CallbackStreamListener(self.callback, swallow_errors=not verbose, filter_users=(users if restrict else list()))
            self.stream = tweepy.Stream(auth=self.api.auth, listener=self.stream_listener)
            self.stream.filter(follow=users, is_async=is_async)

    def callback(self, tweet_json):
        pass

    def close_stream(self):
        if self.stream_open():
            self.stream_listener.close()
            self.stream.disconnect()
            self.stream = None
    @staticmethod
    def get_tweet_text(tweet_json):
        # https://github.com/tweepy/tweepy/issues/878#issuecomment-424216624
        # Try for extended text of original tweet, if RT'd (streamer)
        try: text = tweet_json['retweeted_status']['extended_tweet']['full_text']
        except: 
            # Try for extended text of an original tweet, if RT'd (REST API)
            try: text = tweet_json['retweeted_status']['full_text']
            except:
                # Try for extended text of an original tweet (streamer)
                try: text = tweet_json['extended_tweet']['full_text']
                except:
                    # Try for extended text of an original tweet (REST API)
                    try: text = tweet_json['full_text']
                    except:
                        # Try for basic text of original tweet if RT'd 
                        try: text = tweet_json['retweeted_status']['text']
                        except:
                            # Try for basic text of an original tweet
                            try: text = tweet_json['text']
                            except: text = ''
        text = normalize('NFKD',text).encode('ascii',errors='ignore').decode('ascii', errors='ignore').replace('\n',' ').replace('\r','')
        
        # remove trailing ellipses
        if text.endswith('...'):
            if ' ' in text: text = text[0:text.rfind(' ')]
            else: text = text.strip('...')
        return text
    
    @staticmethod
    def get_tweet_hashtags(tweet_json):
        tags = tweet_json['entities']['hashtags']
        return [tag['text'] for tag in tags]
    
    @staticmethod
    def get_tweet_cashtags(tweet_json):
        tags = tweet_json['entities']['symbols']
        return [str(tag['text']).upper() for tag in tags]
    
    @staticmethod
    def cashtag_to_stock(symbol:str):
        # necessary because German symbols are significantly different from NYSE symbols
        # https://stackoverflow.com/questions/38967533/retrieve-company-name-with-ticker-symbol-input-yahoo-or-google-api
        url = "http://d.yimg.com/autoc.finance.yahoo.com/autoc?query={}&region=1&lang=en".format(symbol)

        result = requests.get(url).json()

        for x in result['ResultSet']['Result']:
            if x['symbol'] == symbol:
                return x['name']

    @staticmethod
    def load_from_file(path='./keys.json'):
        if not os.path.exists(path): 
            return (None, ) * 4

        with open(path, 'r') as file:
            keys = json.loads(file.read())
            return keys['consumer-key'], keys['consumer-secret'], keys['app-token'], keys['app-secret']

class CallbackStreamListener(tweepy.StreamListener):
    def __init__(self, callback, swallow_errors:bool=False, num_threads:int=5, filter_users:list=[]):
        assert callable(callback) and len(signature(callback).parameters) == 1, 'Callback must be a callable that supports 1 arguement'
        self.executor = ThreadPoolExecutorStackTraced(num_threads) if not swallow_errors else ThreadPoolExecutor(num_threads)
        self.callback = callback
        self.filter = filter_users
        super().__init__()

    def on_data(self, data):
        self.executor.submit(self.handle_data, data)

    def on_error(self, status_code):
        if status_code == 420: # If we disconnect from the stream, kill ourselves
            self.close()
            return False
        if status_code == 401:
            raise ValueError('Authorization invalid! Check your keys!')
    
    def handle_data(self, data):
        try:
            tweet = json.loads(data)
            tweet['text'] # simply call to check for malformed tweet
        except (KeyError, ValueError): return

        try: user = tweet['user']['id_str'].lower()
        except KeyError: return
        
        if len(self.filter) <= 0 or user in self.filter:
            self.callback(tweet)

    def close(self):
        self.executor.shutdown(wait=True)

# Adapted from https://stackoverflow.com/questions/19309514/getting-original-line-number-for-exception-in-concurrent-futures/24457608#24457608
class ThreadPoolExecutorStackTraced(ThreadPoolExecutor):
    def submit(self, fn, *args, **kwargs):
        """Submits the wrapped function instead of `fn`"""
        return super(ThreadPoolExecutorStackTraced, self).submit(
            self._function_wrapper, fn, *args, **kwargs)

    def _function_wrapper(self, fn, *args, **kwargs):
        """Wraps `fn` in order to preserve the traceback of any kind of
        raised exception
        """
        try:
            return fn(*args, **kwargs)
        except Exception:
            traceback.print_exc()


if __name__ == "__main__":
    twtr = Twitter(*Twitter.load_from_file(path='keys-actual.json'))
    twtr.callback = lambda dat: print('\n\n{0}\n\n'.format(dat))
    try:
        twtr.open_stream(is_async=False,)
    except (KeyboardInterrupt, SystemExit):
        print('Closing stream')
        twtr.close_stream()

