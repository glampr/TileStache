""" A stylish alternative for caching your tiles.


"""

import re

from cgi import parse_qs
from sys import stderr, stdout
from ModestMaps.Core import Coordinate
from StringIO import StringIO
from os.path import realpath, dirname, join as pathjoin
from os import environ

import Caches
import Geography

try:
    from json import load as loadjson
    from json import dumps as dumpjsons
except ImportError:
    from simplejson import load as loadjson
    from simplejson import dumps as dumpjsons

class Configuration:
    """ A complete site configuration, with a collection of Layer objects.
    """
    def __init__(self):
        self.layers = {}

class Layer:
    """ A Layer, with its own provider and projection.
    """
    def __init__(self, config, provider, projection):
        self.config = config
        self.provider = provider
        self.projection = Geography.getProjectionByName(projection)

    def render(self, coord):
        """ Render an image for a coordinate, return a PIL Image instance.
        """
        srs = self.projection.srs
        xmin, ymin, xmax, ymax = self.envelope(coord)
        
        img = self.provider.renderEnvelope(256, 256, srs, xmin, ymin, xmax, ymax)
        
        assert hasattr(img, 'size') and hasattr(img, 'save'), \
               'Return value of provider.renderEnvelope() must look like an image.'
        
        return img

    def envelope(self, coord):
        """ Projected rendering envelope (xmin, ymin, xmax, ymax) for a Coordinate.
        """
        ul = self.projection.coordinateProj(coord)
        lr = self.projection.coordinateProj(coord.down().right())
        
        return min(ul.x, lr.x), min(ul.y, lr.y), max(ul.x, lr.x), max(ul.y, lr.y)

def parseConfigfile(configpath):
    """ Parse a configuration file path and return a Configuration object.
    """
    raw = loadjson(open(configpath, 'r'))
    
    config = Configuration()
    
    cache = raw.get('cache', {})
    
    if cache['type'] == 'Disk':
        cachepath = realpath(pathjoin(dirname(configpath), cache['path']))
        cache = Caches.Disk(cachepath)
    
    for (name, layer) in raw.get('layers', {}).items():
        projection = layer.get('projection', '')
        
        provider = layer['provider']
        classpath = provider['class'].split('.')

        module = __import__( '.'.join(classpath[:-1]) )
        _class = getattr(module, classpath[-1])
        kwargs = provider.get('kwargs', {})
        provider = _class(**kwargs)
    
        config.layers[name] = Layer(config, provider, projection)

    return config

def getTypeByExtension(extension):
    """ Get mime-type and PIL format by file extension.
    """
    if extension.lower() == 'png':
        return 'image/png', 'PNG'

    elif extension.lower() == 'jpg':
        return 'image/jpeg', 'JPEG'

    else:
        raise Exception('Unknown extension: "%s"' % extension)

def handleRequest(layer, coord, extension, query):
    """ Get a type string and image binary for a given request layer, coordinate, file extension, and query string.
    """
    mimetype, format = getTypeByExtension(extension)
    
    out = StringIO()
    img = layer.render(coord)
    img.save(out, format)
    
    return mimetype, out.getvalue()

# regular expression for PATH_INFO
pathinfo_pat = re.compile(r'^/(?P<l>.+)/(?P<z>\d+)/(?P<x>\d+)/(?P<y>\d+)\.(?P<e>\w+)$')

def cgiHandler(debug=False):
    """ 
    """
    if debug:
        import cgitb
        cgitb.enable()
    
    path = pathinfo_pat.match(environ['PATH_INFO'])
    layer, row, column, zoom, extension = [path.group(p) for p in 'lyxze']
    config = parseConfigfile('tilestache.cfg')
    
    coord = Coordinate(int(row), int(column), int(zoom))
    query = parse_qs(environ['QUERY_STRING'])
    layer = config.layers[layer]
    
    mimetype, content = handleRequest(layer, coord, extension, query)
    
    print >> stdout, 'Content-Length: %d' % len(content)
    print >> stdout, 'Content-Type: %s\n' % mimetype
    print >> stdout, content
