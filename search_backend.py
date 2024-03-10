# -*- coding: utf-8 -*-
"""search_backend.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1iB5r9UKBQsbTvV9PRrp9fbFRpqXWCIuN
"""

#imports
import re
import numpy as np
import pickle
import nltk
import builtins

from nltk.corpus import stopwords
import json
from contextlib import closing
from nltk.stem import *
from collections import defaultdict, Counter
from inverted_index_gcp import *
import math
from google.cloud import storage
import sys
from collections import Counter, OrderedDict
import itertools
from itertools import islice, count, groupby
import pandas as pd
import os
import re
from operator import itemgetter
import nltk
from nltk.stem.porter import *
from nltk.corpus import stopwords
from time import time
from timeit import timeit
from pathlib import Path
import pickle
import pandas as pd
import numpy as np
from google.cloud import storage
import builtins
import math
from nltk import ngrams

from google.cloud import storage
client = storage.Client()
stemmer = PorterStemmer()

import os
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = 'task3mapreduce315537936-2e5ecd407dc5.json'

import hashlib
def _hash(s):
    return hashlib.blake2b(bytes(s, encoding='utf8'), digest_size=5).hexdigest()

nltk.download('stopwords')


class GCPHandler:
    def __init__(self, bucket_name):
        self.bucket_name = bucket_name
        self.client = storage.Client()

    def download_from_gcp(self, src_file_name, dest_file_name=None, folder=False):
        bucket = self.get_client()
        src_file_name = self.reformat_path(src_file_name, self.bucket_name)
        if folder:
            blobs = bucket.list_blobs()
            path = os.path.join(self.path_to_dataset_files_dir, "test_set")
            os.mkdir(path)
            for blob in blobs:
                file_name = blob.name
                if file_name.find(src_file_name) != -1 and not file_name.endswith(src_file_name + "/"):
                    dir = os.path.dirname(file_name)
                    full_dir = os.path.join(path, dir[len(src_file_name) + 1:])
                    if not os.path.exists(full_dir):
                        os.makedirs(full_dir)
                    dest = os.path.join(path , file_name[len(src_file_name) + 1:])
                    blob.download_to_filename(dest)
            return
        blob = bucket.blob(src_file_name)
        if dest_file_name:
            blob.download_to_filename(dest_file_name)
        else:
            blob.download_to_filename(src_file_name)

    def get_client(self):
        storage_client = storage.Client()
        bucket = storage_client.bucket(self.bucket_name)
        return bucket

    @staticmethod
    def reformat_path(path, bucket_name):
        start_index = path.find(bucket_name)
        if start_index == -1:
            return path
        return path[start_index + len(bucket_name) + 1:]

    def get_blob(self, blob_path):
        return self.get_client().blob(blob_path)

bucket_name = '315537936'  # Replace with your actual bucket name
gcp_handler = GCPHandler(bucket_name)

############################ loading indexes and dictionaries from bucket ############################
title_stem = pickle.loads(gcp_handler.get_blob('title_stem_only/title_stem_only_index.pkl').download_as_string())
body_stem = pickle.loads(gcp_handler.get_blob('text_stem/text_stem_index.pkl').download_as_string())
title_gram = pickle.loads(gcp_handler.get_blob('title2gram/title2gram_index.pkl').download_as_string())
pageviews = pickle.loads(gcp_handler.get_blob('pageviews.pkl').download_as_string())
pagerank = pickle.loads(gcp_handler.get_blob('pagerank.pkl').download_as_string())
idtitle = pickle.loads(gcp_handler.get_blob('doc_title_dict.pkl').download_as_string())


############################ end loading indexes and dictionaries from bucket ############################


TUPLE_SIZE = 6
stemmer = PorterStemmer()

english_stopwords = frozenset(stopwords.words('english'))
corpus_stopwords = ['category', 'references', 'also', 'links', 'extenal', 'see', 'thumb']
RE_WORD = re.compile(r"""[\#\@\w](['\-]?\w){2,24}""", re.UNICODE)

all_stopwords = english_stopwords.union(corpus_stopwords)

######################## Pre-Processing ###################################################################

def get_query_tokens(text, stemming=False):
    """
    Tokenizes the input query text and applies stemming (Optionally).
    Eventually, if we don't do stemming it will fit title_index & body_index.
    If we do stemming it will fit text with index_stemmed.

    Parameters:
        text (str): query to be tokenized.
        stemming (bool): If True, applies stemming. Default -  False.

    Returns:
        list: A list of tokens extracted from the input text.
    """
    tokens = [token.group() for token in RE_WORD.finditer(text.lower())]
    if stemming:
        tokens = [stemmer.stem(term) for term in tokens if term not in all_stopwords]
    else:
        tokens = [term for term in tokens if term not in all_stopwords]
    return tokens


def get_tokens_ngrams(text,stemming=False):
    """
    Returns tokens of the input *query* with n-gram, suitable for main search.

    Parameters:
        text (list): The input - The query. Can be after stem or not.
        stemming (bool): If True, applies stemming. Default -  False.


    Returns:
        list: A list of tokens including n-gram generated from the input text.
    """
    ngrams_tokens = []
    # Re-check to not include stop-words
    tokens = [token.group() for token in RE_WORD.finditer(text.lower())]
    if stemming:
        tokens = [stemmer.stem(term) for term in tokens if term not in all_stopwords]
    else:
        tokens = [term for term in tokens if term not in all_stopwords]
    bigram = list(ngrams(tokens, 2))
    ngrams_tokens += [' '.join(b) for b in bigram]

    return ngrams_tokens

def get_candidate_documents(query, index):
    """
    Returns relevant documents for the given query along with their term frequencies.
    Returns a set of all unique relevant documents their corresponding (token:{(doc_id,tf)...}).
    The tuple (doc_id,tf) is extracted from the index function 'read_a_posting_list'
    when recieving a specific token.

    Parameters:
        query_to_search (list): A list of tokens extracted from user's query.
        index: The inverted index containing relevant information.


    Returns:
        set: A set of unique relevant document IDs.
        dict: A dictionary of candidates where each key is a term and its value is a dictionary
              containing relevant document IDs and their corresponding term frequencies. Contains all words and relevant
              docs.
              Example structure:
              {
                  'term1': {'doc_id1': term_frequency1, 'doc_id2': term_frequency2, ...},
                  'term2': {'doc_id3': term_frequency3, 'doc_id4': term_frequency4, ...},
                  ...
              }
    """
    candidates_docs, candidates = {}, set()
    for w in np.unique(query):
        # cheaks if word in inverted index df which is {token:df}
        df = index.df
        if w in df:
            # Extracting (doc_id,tf) for specific token
            p = index.read_a_posting_list(".",w,"315537936")
            only_docs = [x[0] for x in p]
            candidates_docs.update({w: dict(p)})
            candidates.update(only_docs)
    return candidates, candidates_docs


def get_top_n_scored_docs(score_dict, N=500):
    """
    Sorts the best documents by their scores.
    The score will be defined later by linear combination of many scores.

    Parameters:
        sim_dict (dict): A dictionary {doc_id: scores}.
    Returns:
        list: The best N documents sorted in descending order by their scores.
              Default N is after a lot of trials. N=100 is the minimum possible.
    """
    return sorted([(doc_id, score) for doc_id, score in score_dict.items()], key=lambda x: x[1], reverse=True)[:N]

###################################################################################################################


###################  Search title and / or anchor index ################################################

def get_title_anchor_score(query, term_dict):
    """
    When we look at a certain index,
    the frequency of a certain word in relation to the size of the index is very low.
    Calculating a weighted score like tf-idf or CosSim will not give an accurate measure and can lead to bias calculation.
    Therefore, counting the total frequency that a certain word appears in a certain document is more reasonable.
    The more times a certain word appears in the title/ anchor of a document,
    the higher the score and the more relevant it will be for this specific query.
    This function calculates unique tokens from the query that appear in a document.

    Parameters:
        query (list): A list of tokens representing the query.
        term_dict (dict): A dictionary where keys are terms from the query and values are dictionaries
            containing relevant document IDs and their corresponding term frequencies.

    Returns:
        dict: A dictionary where keys are document IDs and values are scores based on how many unique words
              appear in each document -- > {doc_id:score}
    """
    dict_to_return = {}
    for w in term_dict.keys():
        for doc in term_dict[w].keys():
            dict_to_return[doc] = dict_to_return.get(doc, 0) + 1
    return dict_to_return


def search_for_title_anchor(query, index):
    """
    Returns the best documents for title and anchor.
    The documents are sorted by their score which is calculated above.

    Parameters:
        query (list): A list of tokens representing the query.
        index (dict): The inverted index containing information about terms and their corresponding documents.

    Returns:
        list: A list of tuples containing document IDs and their corresponding titles, sorted by score.
        dict: A dictionary where {doc_id:score}, helpful for the main search.
    """
    rel_docs, candidates_dict = get_candidate_documents(query, index)
    rr = get_title_anchor_score(query, candidates_dict)
    # N is after lots of expirements
    id_score = get_top_n_scored_docs(rr, N=100000000)
    res = [i[0] for i in id_score]
    return [(j, idtitle[j]) for j in res if j in idtitle], rr


########################  Search body index   ######################################################

def cos_sim_calculation(query_tokens, index, docs, candidates_dict):
    """
    Calculates TF-IDF and cosine similarity for body index.
    NOTICE - the calculation is ONLY for the relevant documents from the candidates.
    NOT FOR EVERY DOCUMENT!!!

    Parameters:
        query_tokens (list): A list of tokens representing the query.
        index: The inverted index containing significant information.
        candidate_dict (dict): A dictionary which: {term: {doc_id: tf}}.

    Returns:
        dict: A dictionary where {doc_id: score (cosSim)}.
    """
    # get size of query
    n = len(query_tokens)
    query_vector = np.ones(n)
    doc_score = defaultdict(int)

    for doc in docs:
        tf_ids_score = np.empty(n)
        for i, word in enumerate(query_tokens):
            # Only relevant docs of query
            if (word in index.df) and (doc in candidates_dict[word]):
                tf_term = (candidates_dict[word][doc] / index.document_length[doc])
                # CORPUS_SIZE = 6348910
                idf_term = math.log2(6348910 / index.df[word])
                tf_ids_score[i] = tf_term * idf_term
            else:
                tf_ids_score[i] = 0

        inner_product = np.dot(tf_ids_score, query_vector)
        size_q = np.linalg.norm(query_vector)
        # Cosine Similarity calculation for each candidate document
        doc_score[doc] = inner_product / (size_q * index.normalized_length[doc])

    return doc_score


def search_body(index, query):
    """
    Returns the best documents for body.
    The documents are sorted by their score which is calculated above.
    Parameters: query: list of tokens
                index: inverted index
    Returns: [(doc_id,title)...], {doc_id: cosine similarity score}
             The dictionary will be helpful for the main search.
    """
    rel_docs, candidates_dict = get_candidate_documents(query, index)
    cos_sim_dict = cos_sim_calculation(query, index, rel_docs, candidates_dict)
    # We will return first 100 because this is what requested
    top_n = get_top_n_scored_docs(cos_sim_dict, 100)
    res = [i[0] for i in top_n]
    return [(j, idtitle[j]) for j in res], cos_sim_dict



########################  Class for improving body index search #########################################


class BM25_index:
    """
    BM25 is a sub-linear transformation of TF-IDF calculation.
    It helps us avoid dominance by one term,
    creating an upper bound.
    It normalizes document length.
    BM25 has two empirical parameters. By tuning them, we can even improve it more.
    b - punishes long documents, k1 - allows for control over the saturation effect.
    We defined k1=1.5, b=0.75 after searching for the most effective values for tuning.
    """

    def __init__(self, index, k1=1.5, b=0.75):
        self.b = b
        self.k1 = k1
        self.index = index
        # CORPUS_SIZE
        self.N = len(index.document_length)
        # Average document length
        self.avg_doc_len = builtins.sum(index.document_length.values()) / self.N

    def calc_idf(self, list_of_tokens):
        idf = {}
        for term in list_of_tokens:
            if term in self.index.df:
                n_ti = self.index.df[term]
                # FORMULA
                idf[term] = math.log(1 + (self.N - n_ti + 0.5) / (n_ti + 0.5))
            else:
                pass
        return idf

    def _score(self, query, doc_id, candidate_dict):
        score = 0.0
        doc_len = self.index.document_length[doc_id]
        for term in query:
            if term in self.index.df:
                # (doc_id, tf) for each term
                term_frequencies = candidate_dict[term]
                if doc_id in term_frequencies:
                    freq = term_frequencies[doc_id]
                    # FORMULA
                    numerator = self.idf[term] * freq * (self.k1 + 1)
                    denominator = freq + self.k1 * (1 - self.b + self.b * doc_len / self.avg_doc_len)
                    score += (numerator / denominator)
        return score

    def search(self, q, N=10000):
        # q is the extracted tokens list
        candidates, candidates_dict = get_candidate_documents(q, self.index)
        self.idf = self.calc_idf(q)
        temp_dict = {k: self._score(q, k, candidates_dict) for k in candidates}
        # highest_N_score is a list of tuples where [(docID, score)...]
        highest_n_score = get_top_n_scored_docs(temp_dict, N)
        return highest_n_score

#######################################################################################################


################################# Helper for main search ############################################
def find_minmax(scores_list):
    """
    Returns the minimum and maximum values in a given list.
    Helps us to scale the score from every score in the main search
    Parameter:
        lst (list of floats): A list of floats.
    Returns:
        tuple: A tuple containing the minimum and maximum numbers from the list.
    """
    if len(scores_list) == 0: return 0, 1
    min_v, max_v = np.min(scores_list), np.max(scores_list)
    if max_v == 0.0:
        max_v = 1
    return min_v, max_v

  #######################################################################################################


#####################      THE MAIN SEARCH   ##################################################\

def search(query, idx_title, idx_body, idx_title_ngram):
    """
    The main search function,
    This function calculates the best documents with the highest scores by:
    their body (stemmed)
    title
    title with n-gram
    page rank
    page views

    All the relevant docs are extracted after applying BM25 search on body index.
    Assuming it predicts the best candidates docs. N is also after lots of experiments.
    All the scores for relevant docs are first scaled by min max scaler.
    Then we give every score a ceratin weight in the final score calculation.
    The weights are after lots of expereiments to find the best combinaton.

    Paramters:
        query : The query as a string.
        idx_title_stem : Inverted index on title.
        idx_title_ngram : Inverted index on title with stemming.
        idx_body_stem : Inverted index on anchor.

    Returns:
        list: A list of tuples containing document IDs and their corresponding titles.
              The list includes the documents that received the highest scores based on various metrics
              while using weights- {doc_id:title}
    """

    # Tokens regular
    query_tokens = get_query_tokens(query)
    # Tokens with stem
    query_stem = get_query_tokens(query,True)
    # Tokens with n-gram
    #query_ngram = get_tokens_ngrams(query)
    # Tokens with n-gram and stem
    #query_ngram_stem = get_tokens_ngrams(query,True)

    # Search with bm25
    bm25 = BM25_index(idx_body)
    bm25_cand = bm25.search(query_tokens, 5000)


    cadndiate_scores = {}

    #INITIALIZE
    bm25_lst_scores = np.zeros(len(bm25_cand))
    top_titles_scores = np.zeros(len(bm25_cand))
    top_title_n_gram_scores = np.zeros(len(bm25_cand))
    page_rank_scores = np.zeros(len(bm25_cand))
    page_views_scores = np.zeros(len(bm25_cand))

    for i, c in enumerate(bm25_cand):
        bm25_lst_scores[i] = c[1]
        cadndiate_scores[c[0]] = [c[1], 0, 0, 0, 0]

    # search on title and anchor -> {doc_id:score}
    title_sim = search_for_title_anchor(query_stem, idx_title)[1]
    title_ngram_sim = search_for_title_anchor(query_tokens, idx_title_ngram)[1]

    top_title = get_top_n_scored_docs(title_sim, 5000)
    top_title_ngram = get_top_n_scored_docs(title_ngram_sim, 5000)


    for i, c in enumerate(top_title):
        if c[0] in cadndiate_scores:
            top_titles_scores[i] = c[1]
            cadndiate_scores[c[0]][1] = c[1]

    for i, c in enumerate(top_title_ngram):
        if c[0] in cadndiate_scores:
            top_title_n_gram_scores[i] = c[1]
            cadndiate_scores[c[0]][2] = c[1]

    for i, c in enumerate(cadndiate_scores):
        if c in pagerank:
            page_rank_scores[i] = pagerank[c]
            cadndiate_scores[c][3] = pagerank[c]
        if c in pageviews:
            page_views_scores[i] = pageviews[c]
            cadndiate_scores[c][4] = pageviews[c]

    # find min max values for normalize
    minimum_bm25, maximum_bm25 = find_minmax(bm25_lst_scores)
    minimum_title, maximum_title = find_minmax(top_titles_scores)
    minimum_ngram, maximum_ngram = find_minmax(top_title_n_gram_scores)
    minimum_prank, maximum_prank = find_minmax(page_rank_scores)
    minimum_pv, maximum_pv = find_minmax(page_views_scores)

    for k in cadndiate_scores:
        agg_score = 0
        # MIN MAX SCALER
        cadndiate_scores[k][0] = (cadndiate_scores[k][0] - minimum_bm25) / (maximum_bm25 - minimum_bm25) * 3
        cadndiate_scores[k][1] = (cadndiate_scores[k][1] - minimum_title) / (maximum_title - minimum_title) * 1
        cadndiate_scores[k][2] = (cadndiate_scores[k][2] - minimum_ngram) / (maximum_ngram - minimum_ngram) * 1
        cadndiate_scores[k][3] = (cadndiate_scores[k][3] - minimum_prank) / (maximum_prank - minimum_prank) * 1
        cadndiate_scores[k][4] = (cadndiate_scores[k][4] - minimum_pv) / (maximum_pv - minimum_pv) * 1

        # get aggregated score for each document
        for i in cadndiate_scores[k]:
          agg_score += i
          cadndiate_scores[k] = agg_score

    #REQUESTED TOP 50
    result = get_top_n_scored_docs(cadndiate_scores, 50)
    res = [i[0] for i in result]
    res = [(str(j), idtitle[j]) for j in res]

    return res


def final_search(query):
    """
    Calls to the final search.
    """
    return search(query, title_stem, body_stem, title_gram)

