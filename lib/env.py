# -*- coding: utf-8 -*-
#
# Copyright (C) 2003-2009 Edgewall Software
# Copyright (C) 2003-2007 Jonas Borgström <jonas@edgewall.com>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://trac.edgewall.org/wiki/TracLicense.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://trac.edgewall.org/log/.
#
# Author: Jonas Borgström <jonas@edgewall.com>

import os.path
try:
    import threading
except ImportError:
    import dummy_threading as threading
import setuptools
import sys
from urlparse import urlsplit

try:
    import json
except ImportError:
    try: 
        import simplejson as json
    except ImportError:
        raise SysTracError("no usable json module found")

import core
from config import *
from core import Component, ComponentManager, implements, Interface, \
                      ExtensionPoint, SysTracError
from util import arity, copytree, get_pkginfo, makedirs
from util.text import exception_to_unicode, printerr, printout

import cherrypy as cp

__all__ = ['Environment', 'open_environment']


class Environment(Component, ComponentManager):
    """Trac stores project information in a Trac environment."""
    
    log_type = Option('logging', 'log_type', 'none',
        """Logging facility to use.
        
        Should be one of (`none`, `file`, `stderr`, `syslog`, `winlog`).""")

    log_file = Option('logging', 'log_file', 'systrac.log',
        """If `log_type` is `file`, this should be a path to the log-file.""")

    log_level = Option('logging', 'log_level', 'DEBUG',
        """Level of verbosity in log.
        
        Should be one of (`CRITICAL`, `ERROR`, `WARN`, `INFO`, `DEBUG`).""")

    log_format = Option('logging', 'log_format', None,
        """Custom logging format.

        If nothing is set, the following will be used:
        
        Trac[$(module)s] $(levelname)s: $(message)s

        In addition to regular key names supported by the Python logger library
        library (see http://docs.python.org/lib/node422.html), one could use:
         - $(path)s     the path for the current environment
         - $(basename)s the last path component of the current environment
         - $(project)s  the project name

         Note the usage of `$(...)s` instead of `%(...)s` as the latter form
         would be interpreted by the ConfigParser itself.

         Example:
         ($(thread)d) Trac[$(basename)s:$(module)s] $(levelname)s: $(message)s""")
         
    platform = Option('systrac', 'platform', None,
            """the platform name. One of 'linux', 'solaris', 'bsd', 'windows'""")

    flavour = Option('systrac', 'flavour', None,
            """the platform variant, for linux this is usually the name of
            the distribution i.e 'debian', 'ubuntu', 'suse', 'redhat'""")
        
    release = Option('systrac', 'release', None,
            """the release as a numerical value""")
            
    default_content_type = Option('systrac', 'default_content_type', 'application/json',
            """The default content type for the set_content_type Tool""")
            
    def __init__(self, path, create=False, options=[]):
        """Initialize the Trac environment.
        
        @param path:   the absolute path to the Trac environment
        @param create: if `True`, the environment is created and populated with
                       default data; otherwise, the environment is expected to
                       already exist.
        @param options: A list of `(section, name, value)` tuples that define
                        configuration options
        """
        ComponentManager.__init__(self)

        self.path = path
        self.setup_config(load_defaults=create)
        self.setup_log()

        from core import  __version__ as VERSION
        self.systeminfo = [
            ('SysTrac', get_pkginfo(core).get('version', VERSION)),
            ('Python', sys.version),
            ('setuptools', setuptools.__version__),
            ]

        #setup the set_content_type Tool before loading any pagehandlers
        def set_content_type(ct=None):
            if cp.response.status == 404: 
                return # probably all but 2xx unless errors are convertet to json too
            if ct:
                cp.response.headers['Content-Type'] = ct
            else:
                cp.response.headers['Content-Type'] = self.default_content_type
        cp.tools.set_content_type = cp.Tool('before_finalize', set_content_type)
        
        from loader import load_components
        #FIXME: remove hardcoded string, reenable config
        plugins_dir = os.path.abspath('../modules')
        load_components(self, plugins_dir and (plugins_dir,))


    def get_platform(self):
        return (self.platform, self.flavour, self.release)
        
    def component_activated(self, component):
        """Initialize additional member variables for components.
        
        Every component activated through the `Environment` object gets three
        member variables: `env` (the environment object), `config` (the
        environment configuration) and `log` (a logger object)."""
        component.env = self
        component.config = self.config
        component.log = self.log
        
        #add a reference to the json module for convenience
        component.json = json
        component.default_content_type = self.default_content_type
        
    def is_component_enabled(self, cls):
        """FIXME: make comparison case insensitive"""
        whitelist = ['Dispatcher']
        if cls.__name__ in whitelist: return True
        
        p = self.config.get('systrac', 'platform')
        f = self.config.get('systrac', 'flavour')
        r = self.config.get('systrac', 'release')
        self.log.info("My platform: %s (%s, version: %s)\n" % (p, f, r))
        try:
            print "Checking supported_platform on %s" % cls.__name__
            return cls.supported_plattform(p, f, r)
        except NotImplementedError, e:
            self.log.warn("%s Does not support the platform (%s, %s, %s) for this host.\n" % (
                        cls.__name__, p, f, r))
            return False

    def setup_config(self, load_defaults=False):
        """Load the configuration file."""
        self.config = Configuration(os.path.join(self.path, 'conf', 'systrac.ini'))
        if load_defaults:
            for section, default_options in self.config.defaults().items():
                for name, value in default_options.items():
                    if self.config.parent and name in self.config.parent[section]:
                        value = None
                    self.config.set(section, name, value)

    def get_log_dir(self):
        """Return absolute path to the log directory."""
        return os.path.join(self.path, 'log')

    def setup_log(self):
        """Initialize the logging sub-system."""
        from log import logger_factory
        logtype = self.log_type
        logfile = self.log_file
        if logtype == 'file' and not os.path.isabs(logfile):
            logfile = os.path.join(self.get_log_dir(), logfile)
        format = self.log_format
        if format:
            format = format.replace('$(', '%(') \
                     .replace('%(path)s', self.path) \
                     .replace('%(basename)s', os.path.basename(self.path))
        self.log = logger_factory(logtype, logfile, self.log_level, self.path,
                                  format=format)

 
