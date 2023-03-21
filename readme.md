# TF/IDF search engine

TF/IDF searcher in Python using Redis zsets as a store. 

utilized resources: 
https://gist.github.com/josiahcarlson/464760 + https://tartarus.org/martin/PorterStemmer/

to do:
- implement cleaner Redis access
- implement flags in search:
    -> -term to exclude a term from results
    -> "term" to ensure term is exactly matched in all results 
- consider more content cleaning - is it worth using a metaphone algorithm in addition to the porter stemmer?
- implement formal unit test with real text
- allow for flags to be set that force the results to have URLs, emails, etc