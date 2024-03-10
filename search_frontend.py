# -*- coding: utf-8 -*-


from flask import Flask, request, jsonify
from search_backend import search_title_backend, search_body_backend, final_search, search_anchor_backend



class MyFlaskApp(Flask):
    def run(self, host=None, port=None, debug=None, **options):
        super(MyFlaskApp, self).run(host=host, port=port, debug=debug, **options)


app = MyFlaskApp(__name__)
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False


@app.route("/search")

def search():
    '''
    Fetches up to 100 search results based on the provided query. This function allows flexibility
    in choosing the search engine and implementing various retrieval techniques such as stemming,
    stopword removal, PageRank, and query expansion, within the project's requirements regarding
    efficiency and quality.

    Usage:
        To perform a search, navigate to a URL like:
        http://YOUR_SERVER_DOMAIN/search?query=hello+world
        where YOUR_SERVER_DOMAIN is your server's domain (e.g., XXXX-XX-XX-XX-XX.ngrok.io if using ngrok on Colab
        or your external IP on GCP).

    Parameters:
        query (str): The search query string.

    Returns:
        list: A list of up to 100 search results, ordered from best to worst. Each element is a tuple
        containing the wiki_id and title of the search result.
    '''
    res = []
    query = request.args.get('query', '')
    if len(query) == 0:
        return jsonify(res)
    res = final_search(query)
    return jsonify(res)


@app.route("/search_body")
def search_body():
    '''
    Retrieves up to 100 search results for the given query using TF-IDF and cosine similarity
    calculated based on the body of articles only. This function utilizes the staff-provided tokenizer
    from Assignment 3 (GCP part) for tokenization and removes stopwords.

    Usage:
        To perform a search, navigate to a URL like:
        http://YOUR_SERVER_DOMAIN/search_body?query=hello+world
        where YOUR_SERVER_DOMAIN is your server's domain (e.g., XXXX-XX-XX-XX-XX.ngrok.io if using ngrok on Colab
        or your external IP on GCP).

    Parameters:
        query (str): The search query string.

    Returns:
        list: A list of up to 100 search results, ordered from best to worst. Each element is a tuple
        containing the wiki_id and title of the search result.
    '''
    res = []
    query = request.args.get('query', '')
    if len(query) == 0:
        return jsonify(res)
    res = search_body_backend(query)
    return jsonify(res)


@app.route("/search_title")
def search_title():
    '''
    Retrieves all search results containing a query word in the title of articles, ordered
    in descending order of the number of distinct query words that appear in the title. This
    function does not utilize stemming and uses the staff-provided tokenizer from Assignment 3
    (GCP part) for tokenization and stopwords removal. For example, a document with a title
    that matches two distinct query words will be ranked before a document with a title that
    matches only one distinct query word, regardless of the number of times the term appeared
    in the title (or query).

    Usage:
        To test this function, navigate to a URL like:
        http://YOUR_SERVER_DOMAIN/search_title?query=hello+world
        where YOUR_SERVER_DOMAIN is your server's domain (e.g., XXXX-XX-XX-XX-XX.ngrok.io if using ngrok on Colab
        or your external IP on GCP).

    Parameters:
        query (str): The search query string.

    Returns:
        list: A list of all search results, ordered from best to worst. Each element is a tuple
        containing the wiki_id and title of the search result.
    '''
    res = []
    query = request.args.get('query', '')
    if len(query) == 0:
        return jsonify(res)
    res = search_title_backend(query)
    return jsonify(res)


@app.route("/search_anchor")
def search_anchor():
    '''
    Retrieves all search results containing a query word in the anchor text of articles, ordered
    in descending order of the number of query words that appear in anchor text linking to the page.
    This function does not utilize stemming and uses the staff-provided tokenizer from Assignment 3
    (GCP part) for tokenization and stopwords removal. For example, a document with anchor text that
    matches two distinct query words will be ranked before a document with anchor text that matches
    only one distinct query word, regardless of the number of times the term appeared in the anchor
    text (or query).

    Usage:
        To test this function, navigate to a URL like:
        http://YOUR_SERVER_DOMAIN/search_anchor?query=hello+world
        where YOUR_SERVER_DOMAIN is your server's domain (e.g., XXXX-XX-XX-XX-XX.ngrok.io if using ngrok on Colab
        or your external IP on GCP).

    Parameters:
        query (str): The search query string.

    Returns:
        list: A list of all search results, ordered from best to worst. Each element is a tuple
        containing the wiki_id and title of the search result.
    '''
    res = []
    query = request.args.get('query', '')
    if len(query) == 0:
        return jsonify(res)
    res = search_anchor_backend(query)
    return jsonify(res)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)