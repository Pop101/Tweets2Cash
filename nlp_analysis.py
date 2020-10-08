from lemon import Lemon
from Levenshtein import distance
import nltk

# silently grab all nltk dependencies
nltk.download('averaged_perceptron_tagger', quiet=True)
nltk.download('wordnet', quiet=True)
nltk.download('vader_lexicon',quiet=True)
nltk.download('stopwords',quiet=True)

from requests.exceptions import HTTPError
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from nltk.corpus import wordnet, stopwords

lemmatizer = nltk.WordNetLemmatizer(); next(wordnet.words()) # I have no idea why next(wordnet.words()) fixes threading, but it does.
stemmer = nltk.stem.porter.PorterStemmer()
stop_words = set(stopwords.words('english'))

class TextToTradeables:
    sia = SentimentIntensityAnalyzer()

    @staticmethod
    def process_text(text, search_for:str='stock', similarity_cutoff:int=1.4, min_noun_length:int=4):
        text = str(text)

        companies = list()
        entities = TextToTradeables.get_noun_phrases(text)
        for entity in entities:
            if min_noun_length > 0 and len(str(entity).replace(' ','')) < min_noun_length: continue
            
            ds = TextToTradeables.deep_search(str(entity), search_for=search_for)
            if ds[0] != None and ds[1] < similarity_cutoff: companies.append(ds)
        
        return companies
    
    @staticmethod
    def get_noun_phrases(text):
        sentence_re = r'(?:(?:[A-Z])(?:.[A-Z])+.?)|(?:\w+(?:-\w+)*)|(?:\$?\d+(?:.\d+)?%?)|(?:...|)(?:[][.,;"\'?():-_`])'
        grammar = r"""
            NBAR:
                {<NN.*|JJ>*<NN.*>}  # Nouns and Adjectives, terminated with Nouns
                
            NP:
                {<NBAR><IN><NBAR>}  # Above, connected with in/of/etc...
                {<NBAR>}
        """
        chunker = nltk.RegexpParser(grammar)

        def leaves(tree):
            for subtree in tree.subtrees(filter = lambda t: t.label()=='NP'):
                yield subtree.leaves()

        def normalise(word):
            word = word.lower()
            #word = lemmatizer.lemmatize(word)
            return word

        def get_terms(tree):
            for leaf in leaves(tree):
                term = [ normalise(w) for w,t in leaf ]
                yield term

        def get_phrases(text):
            toks = nltk.regexp_tokenize(text, sentence_re)
            postoks = nltk.tag.pos_tag(toks)
            tree = chunker.parse(postoks)
            
            terms = get_terms(tree)
            phrases = [" ".join(term) for term in terms]
            return phrases
        return get_phrases(text)

    @staticmethod
    def deep_search(query:str, search_for='stock'):
        if query == None or len(query) <= 0: return None, None
        try: tradeable = Lemon.search_for_tradeable(query, search_type='name', search_for=search_for)
        except HTTPError: tradeable = None
        while tradeable == None and ' ' in query and len(query) > 1:
            query = query[query.find(' ')+1:]
            try:
                tradeable = Lemon.search_for_tradeable(query, search_type='name', search_for=search_for)
            except HTTPError:
                return None, None

        if tradeable == None: return None, None
        return tradeable, distance(tradeable.name.lower(), query.lower())/len(query)
    
    @staticmethod
    def get_sentiment(text:str):
        return TextToTradeables.sia.polarity_scores(str(text))['compound']
    
    @staticmethod
    def remove_stopwords(text:str):
        return ' '.join(filter(lambda w: w not in stop_words, text.split(' ')))

from threading import Timer
import time
# we cannot force threading.Timer to execute early, so we must wrap
# I had no idea where to put this. It messes up the elegance of main.py, so just deal with it here.
class StoppableTimer:
    def __init__(self, interval, function, args:list=list(), kwargs:dict=dict()):
        self.function = function; self.args = args; self.kwargs = kwargs
        self.started = time.time()
        self.thread = Timer(interval, self.execute)
        self.thread.start()
    def is_alive(self):
        if not self.thread: return False
        return self.thread.is_alive()
    def execute(self):
        if self.is_alive(): self.thread.cancel()
        self.function(*self.args, **self.kwargs)
    def cancel(self):
        if self.is_alive(): self.thread.cancel()
        

if __name__ == "__main__":
    txts = ["Good Apple Inc. will do terrible today. Absolutely horrendous. Daimler will do fine. asdfa will fail"]
    txts.append("Biden has repeatedly failed to answer legitimate questions that American voters should know the answers to before voting while Trump takes every interview in the world. Chris Wallace had the opportunity tonight to get more information to the American voter on Biden and he failed")
    txts.append("RT @realDonaldTrump: Last night I did what the corrupt media has refused to do: I held Joe Biden Accountable for his 47 years of lies, 47 y...")

    # manually run the text analysis for more transparency
    for txt in txts:
        possible_companies = TextToTradeables.get_noun_phrases(txt)
        print('Entities in "{0}":\n{1}'.format(txt, possible_companies))
        for comp in possible_companies:
            ds = TextToTradeables.deep_search(comp)

            if ds[0] != None and ds[1] < 1.4:
                print('Found stock:')
                print('\t{0}'.format(ds))
                print('\t{0}'.format(ds[0].name))
                print('\t{0}'.format(ds[0].type))
        print('Opinion on these stocks: {0}'.format(TextToTradeables.sia.polarity_scores(txt)['compound']))