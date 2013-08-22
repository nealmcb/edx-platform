from __future__ import absolute_import

import logging

import pymongo

from track.backends.base import BaseBackend


log = logging.getLogger('track.backends.mongo')


class MongoBackend(BaseBackend):
    def __init__(self, **options):
        super(MongoBackend, self).__init__(**options)

        uri = _make_mongodb_uri(options)
        db_name = options.pop('database', 'track')
        collection_name = options.pop('collection', 'events')

        # By default disable write acknoledgements
        write_concern = options.pop('w', 0)

        self.client = pymongo.MongoClient(host=uri, w=write_concern, **options)
        self.collection = self.client[db_name][collection_name]

        self._create_indexes()

    def _create_indexes(self):
        self.collection.create_index('event_type')
        self.collection.create_index([('time', pymongo.DESCENDING)])

    def send(self, event):
        self.collection.insert(event)


def _make_mongodb_uri(options):
    """
    Make a MongoDB URI from options

    Returns the joined URI and removes the used keys from `options`.
    """

    host = options.pop('host', 'localhost')
    port = options.pop('port', 27017)
    user = options.pop('user', '')
    password = options.pop('password', '')

    uri = 'mongodb://'
    if user or password:
        uri += '{user}:{password}@'.format(user=user, password=password)
    uri += '{host}:{port}'.format(host=host, port=port)

    return uri
