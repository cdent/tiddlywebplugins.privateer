"""
Public access to private things via unguessable URIs.

Maintain a mapping between uuids and a proper URI + user.

Access the URI as that user.
"""

from tiddlyweb.web.http import HTTP404
from tiddlyweb.web.query import Query

MAP = {
        '123456789': ('/bags/ho/tiddlers/junk', 'cdent'),
        'query': ('/bags/ho/tiddlers?select=title:junk', 'cdent'),
        }

def map_to_private(environ, start_response):
    identifier = environ['wsgiorg.routing_args'][1]['identifier']
    target_uri, user = _map_to_uri(identifier)
    print target_uri, user
    environ['tiddlyweb.usersign'] = _proxy_user(environ, user)
    try:
        target_uri, query_string = target_uri.split('?', 1)
        environ['QUERY_STRING'] = query_string
    except ValueError: # no ?
        pass
    environ['PATH_INFO'] = target_uri
    # reparse the query string into tiddlyweb.query and filters
    Query(None).extract_query(environ)
    return environ['tiddlyweb.config']['selector'](environ, start_response)


def init(config):
    if 'selector' in config:
        config['selector'].add('/_/{identifier:segment}',
                GET=map_to_private)


def _map_to_uri(identifier):
    try:
        return MAP[identifier]
    except KeyError:
        raise HTTP404('mapping not found')


def _proxy_user(environ, username):
    return {'name': username, 'roles': []}
