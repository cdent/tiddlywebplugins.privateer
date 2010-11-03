
import shutil

from wsgi_intercept import httplib2_intercept
import wsgi_intercept
import httplib2

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
    store.put(user)

    bag = Bag('ho')
    bag.policy.read = ['cdent']
    store.put(bag)
    tiddler = Tiddler('junk', 'ho')
    tiddler.text = 'i am unique'
    store.put(tiddler)


def test_basic_tiddler():
    response, content = http.request(
            'http://0.0.0.0:8080/bags/ho/tiddlers/junk.txt')
    assert response['status'] == '401'

    response, content = http.request(
            'http://0.0.0.0:8080/_/123456789')
    assert response['status'] == '200', content
    assert 'i am unique' in content

    response, content = http.request('http://0.0.0.0:8080/_/123456789',
            method='PUT')
    assert response['status'] == '405'

    response, content = http.request('http://0.0.0.0:8080/_/nonono')
    assert response['status'] == '404'


def test_with_query():
    response, content = http.request('http://0.0.0.0:8080/_/query')
    assert response['status'] == '200'
    print content
    assert 'junk' in content
