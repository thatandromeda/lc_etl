import gensim

model = gensim.models.Doc2Vec.load("path/to/model")

# Get key for first indexed document
key = model.dv.index_to_key[0]

model.dv.most_similar(key)
