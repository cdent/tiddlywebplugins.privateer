"""
Public access to private things via unguessable URIs.

Maintain a mapping between uuids and a proper URI + user.

Access the URI as that user.
"""

import simplejson
import urlparse
import uuid

from tiddlyweb.control import filter_tiddlers
from tiddlyweb.model.bag import Bag
from tiddlyweb.model.tiddler import Tiddler
from tiddlyweb.model.user import User
from tiddlyweb.store import StoreError
from tiddlyweb.web.http import HTTP404, HTTP400, HTTP302
from tiddlyweb.web.query import Query
from tiddlyweb.web.negotiate import Negotiate
from tiddlyweb.web.util import server_base_url

from tiddlywebplugins.utils import require_any_user, ensure_bag

MAPPING_BAG = 'PRIVATEER'
POLICY = dict(read=['NONE'], write=['NONE'], create=['NONE'],
        manage=['NONE'], accept=['NONE'])


def init(config):
    if 'selector' in config:
        config['selector'].add('/_/{identifier:segment}',
                GET=map_to_private, DELETE=delete_mapping)
        config['selector'].add('/_', GET=mapping_list,
                POST=make_mapping)


@require_any_user()
def delete_mapping(environ, start_response):
    identifier = environ['wsgiorg.routing_args'][1]['identifier']
    current_user = environ['tiddlyweb.usersign']['name']
    store = environ['tiddlyweb.store']
    try:
        tiddler = Tiddler(identifier, MAPPING_BAG)
        tiddler = store.get(tiddler)
        tiddler_user = tiddler.fields['user']
        if current_user != tiddler_user:
            raise HTTP404('resource unavailable') # obscure user mismatch
        store.delete(tiddler)
    except StoreError, exc:
        raise HTTP404('resource not found')

    start_response('204 No Content', [])
    return []


@require_any_user()
def make_mapping(environ, start_response):
    uri = None
    try:
        type = environ['tiddlyweb.type']
    except KeyError:
        type = None
    if type == 'application/json':
        try:
            length = environ['CONTENT_LENGTH']
            content = environ['wsgi.input'].read(int(length))
            data = simplejson.loads(content)
            uri = data['uri']
        except (KeyError, IOError, simplejson.JSONDecodeError), exc:
            raise HTTP400('Unable to parse input: %s' % exc)
    else:
        try:
            uri = environ['tiddlyweb.query']['uri'][0]
        except (KeyError, IndexError), exc:
            raise HTTP400('Unable to parse input: %s' % exc)

    if uri:
        uuid = _make_mapping_tiddler(environ, uri)
    else:
        raise HTTP400('No uri for mapping provided')

    start_response('201 Created', [
        ('Location', _mapping_uri(environ, uuid))])
    return []


@require_any_user()
def mapping_list(environ, start_response):
    current_user = environ['tiddlyweb.usersign']['name']
    store = environ['tiddlyweb.store']
    try:
        bag = Bag(MAPPING_BAG)
        tiddlers = filter_tiddlers(store.list_bag_tiddlers(bag),
                'select=user:%s' % current_user, environ=environ)
        results = {}
        for tiddler in tiddlers:
            store.get(tiddler)
            results[_mapping_uri(environ, tiddler.title)] = tiddler.fields['uri']
    except StoreError, exc:
        raise HTTP404('Unable to list mappings: %s' % exc)

    output = simplejson.dumps(results)

    start_response('200 OK', [
        ('Content-Type', 'application/json')])
    return [output]


def map_to_private(environ, start_response):
    identifier = environ['wsgiorg.routing_args'][1]['identifier']
    host, target_uri, user = _map_to_uri(environ, identifier)
    environ['tiddlyweb.usersign'] = _proxy_user(environ, user)
    try:
        target_uri, query_string = target_uri.split('?', 1)
        environ['QUERY_STRING'] = query_string.encode('utf-8')
    except ValueError: # no ?
        pass
    if host:
        environ['HTTP_HOST'] = host.encode('utf-8')
    environ['PATH_INFO'] = target_uri.encode('utf-8')
    # reparse the query string into tiddlyweb.query and filters
    Query(None).extract_query(environ)
    Negotiate(None).figure_type(environ)
    return environ['tiddlyweb.config']['selector'](environ, start_response)


def _make_mapping_tiddler(environ, uri):
    store = environ['tiddlyweb.store']
    try:
        mapping_bag = ensure_bag(MAPPING_BAG, store, policy_dict=POLICY)
        title_uuid = '%s' % uuid.uuid4()
        tiddler = Tiddler(title_uuid, MAPPING_BAG)
        tiddler.fields['uri'] = uri
        tiddler.fields['user'] = environ['tiddlyweb.usersign']['name']
        store.put(tiddler)
    except StoreError, exc:
        raise HTTP400('Unable to create mapping: %s' % exc)
    return title_uuid

def _map_to_uri(environ, identifier):
    store = environ['tiddlyweb.store']
    try:
        tiddler = Tiddler(identifier, MAPPING_BAG)
        tiddler = store.get(tiddler)
        uri = tiddler.fields['uri']
        user = tiddler.fields['user']
        scheme, netloc, path, params, query, fragment = urlparse.urlparse(uri)
        host = urlparse.urlunparse((scheme, netloc, '', '', '', ''))
        path = urlparse.urlunparse(('', '', path, params, query, fragment))
        return host, path, user
    except (StoreError, KeyError), exc:
        raise HTTP404('valid mapping not found: %s' % exc)


def _mapping_uri(environ, identifier):
    location = '%s/_/%s' % (server_base_url(environ), identifier)
    return location


def _proxy_user(environ, username):
    store = environ['tiddlyweb.store']
    try:
        user = User(username)
        user = store.get(user)
        return {'name': user.usersign, 'roles': user.list_roles()}
    except StoreError, exc:
        raise HTTP400('invalid mapping: %s' % exc)
