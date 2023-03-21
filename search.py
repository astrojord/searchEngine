import re
import math
import collections
import redis
import os
from .porter import PorterStemmer

NOT_WORDS = re.compile("[^a-z0-9' ]")

# http://www.textfixer.com/resources/common-english-words.txt
STOP_WORDS = ["a","able","about","across","after","all","almost","also","am","among","an","and","any","are","as","at",
              "be","because","been","but","by","can","cannot","could","dear","did","do","does","either","else","ever","every",
              "for","from","get","got","had","has","have","he","her","hers","him","his","how","however",
              "i","if","in","into","is","it","its","just","least","let","like","likely","may","me","might","most","must","my",
              "neither","no","nor","not","of","off","often","on","only","or","other","our","own","rather",
              "said","say","says","she","should","since","so","some",
              "than","that","the","their","them","then","there","these","they","this","tis","to","too","twas","us",
              "wants","was","we","were","what","when","where","which","while","who","whom","why","will","with","would","yet","you","your"]

class Searcher():
    def __init__(self, prefix):
        self.prefix = prefix.lower().rstrip(':') + ':'
        self.connection = redis.Redis(host='localhost', port=6379, db=0) # TODO

    @staticmethod
    def get_content_keys(content, add = True):
        # clean content and remove single characters
        words = NOT_WORDS.sub(' ', content.lower().split())
        words = [words.strip("'") for word in words]
        words = [w for w in words if w not in STOP_WORDS and len(w) > 1]

        # apply Porter stemmer 
        # https://tartarus.org/martin/PorterStemmer/
        words = [PorterStemmer.stem(w, 0, len(w)-1) for w in words]

        if not add:
            return words
        
        # calculate TF
        counts = collections.defaultdict(float)
        for w in words:
            counts[w] += 1
        tf = dict((w, count / len(words)) for w, count in counts.iteritems())
        return tf

    def handle_content(self, id, content, add = True):
        # add TFs to zset
        # if bool add param is false, remove from zset instead
        keys = self.get_content_keys(content)
        p = self.connection.pipeline(False)

        if add:
            p.sadd(self.prefix + 'indexed:', id)
            for k, v in keys.iteritems():
                p.zadd(self.prefix+k, id, v)
        else:
            p.srem(self.prefix + 'indexed', id)
            for k in keys:
                p.zrem(self.prefix+k, id)

        p.execute()
        return len(keys)
    
    def add_index(self, id, content):
        return self.handle_content(id, content)
    
    def rem_index(self, id, content):
        return self.handle_content(id, content, add = False)

    def search(self, query, offset = 0, count = 10):
        # get term keys
        keys = [self.prefix + key for key in self.get_content_keys(query, False)]
        if not keys:
            return [], 0
        
        total_docs = max(self.connection.scard(self.prefix + "indexed:"), 1)

        # get TF
        p = self.connection.pipeline(False)
        for k in keys:
            p.zcard(k)
        sizes = p.execute()

        # calculate IDF
        def idf(count):
            if not count:
                return 0
            return max(math.log(total_docs / count, 2), 0)
        idfs = map(idf, sizes)

        # make dict of weights
        weights = dict((key, idf_value) for key, size, idf_value in zip(keys, sizes, idfs))
        if not weights:
            return [], 0
        
        temp_key = self.prefix + "temp:" + os.urandom(8).encode('hex') # use this for getting the results then delete it
        try:
            known = self.connection.zunionstore(temp_key, weights) # multiply using the weights we found
            ids = self.connection.zrevrange(temp_key, offset, offset+count-1, withscores = True)
        finally: 
            self.connection.delete(temp_key)
        return ids, known

def test():
    s = Searcher('test')
    s.connection.delete(*s.connection.keys('test:*'))

    s.add_index(1, "hello world")
    s.add_index(2, "this is a test, hello")

    print(f"search for \"hello\": {s.search('hello')}")
    print(f"search for \"this\": {s.search('this')}")
    print(f"search for \"world\": {s.search('world')}")

if __name__ == "__main__":
    test()