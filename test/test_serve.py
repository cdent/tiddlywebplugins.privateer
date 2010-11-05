
import shutil

from base64 import b64encode
from wsgi_intercept import httplib2_intercept
import wsgi_intercept
import httplib2

from urllib import urlencode
from simplejson import dumps, loads

from tiddlyweb.config import config
from tiddlyweb.web import serve
from tiddlywebplugins.utils import get_store

from tiddlyweb.model.bag import Bag
from tiddlyweb.model.tiddler import Tiddler
from tiddlyweb.model.user import User

def setup_module(module):
    try:
        shutil.rmtree('store')
    except:
        pass

    def app():
        return serve.load_app()
    httplib2_intercept.install()
    wsgi_intercept.add_wsgi_intercept('0.0.0.0', 8080, app)

    module.store = get_store(config)
    module.http = httplib2.Http()
    user = User('cdent')
    user.set_password('cowpoo')
    store.put(user)

    module.authorization = b64encode('cdent:cowpoo')

    user = User('fnd')
    user.set_password('whitespace')
    store.put(user)

    module.other_auth = b64encode('fnd:whitespace')

    bag = Bag('ho')
    bag.policy.read = ['cdent']
    store.put(bag)
    tiddler = Tiddler('junk', 'ho')
    tiddler.text = 'i am unique'
    store.put(tiddler)

    bag = Bag('cars')
    bag.policy.read = ['fnd']
    store.put(bag)
    tiddler = Tiddler('mazda', 'cars')
    tiddler.text = 'funky green'
    store.put(tiddler)


def test_basic_tiddler():
    response, content = http.request(
            'http://0.0.0.0:8080/bags/ho/tiddlers/junk.txt')
    assert response['status'] == '401'

    location = _make_mapping('http://0.0.0.0:8080/bags/ho/tiddlers/junk.txt',
            authorization)
    assert 'http://0.0.0.0:8080/_/' in location

    response, content = http.request(location)
    assert response['status'] == '200', content
    assert 'i am unique' in content

    response, content = http.request(location, method='PUT')
    assert response['status'] == '405'

    response, content = http.request('http://0.0.0.0:8080/_/nonono')
    assert response['status'] == '404'

    response, content = http.request(location, method='DELETE')
    assert response['status'] == '403', content

    response, content = http.request(location, method='DELETE',
            headers={'Authorization': 'Basic %s' % other_auth})
    assert response['status'] == '404', content

    response, content = http.request(location, method='DELETE',
            headers={'Authorization': 'Basic %s' % authorization})
    assert response['status'] == '204', content

    response, content = http.request(location)
    assert response['status'] == '404', content


def test_with_query():
    location = _make_mapping(
            'http://0.0.0.0:8080/bags/ho/tiddlers?select=title:junk',
            authorization)
    assert 'http://0.0.0.0:8080/_/' in location

    response, content = http.request(location)
    assert response['status'] == '200'
    assert 'junk' in content


def test_lister():
    location_c_one = _make_mapping('http://0.0.0.0:8080/bags/ho/tiddlers/junk',
            authorization)
    location_c_two = _make_mapping(
            'http://0.0.0.0:8080/bags/ho/tiddlers/junk.txt',
            authorization)

    location_f_one = _make_mapping(
            'http://0.0.0.0:8080/bags/cars/tiddlers/mazda',
            other_auth)
    location_f_one = _make_mapping(
            'http://0.0.0.0:8080/bags/cars/tiddlers/mazda.txt',
            other_auth)

    response, content= http.request('http://0.0.0.0:8080/_')
    assert response['status'] == '401'

    response, content = http.request('http://0.0.0.0:8080/_',
            headers={'Authorization': 'Basic %s' % authorization})
    assert response['status'] == '200'
    assert 'mazda' not in content
    info = loads(content)
    assert len(info) == 3 # the select query is still in there

    response, content = http.request('http://0.0.0.0:8080/_',
            headers={'Authorization': 'Basic %s' % other_auth})
    assert response['status'] == '200'
    assert 'junk' not in content
    info = loads(content)
    assert len(info) == 2


def _make_mapping(uri, authorization):
    post_data = {'uri': uri}
    post_body = dumps(post_data)
    response, content = http.request('http://0.0.0.0:8080/_',
            method='POST',
            headers={'Content-type': 'application/json',
                'Authorization': 'Basic %s' % authorization},
            body=post_body)
    assert response['status'] == '201', content
    return response['location']
