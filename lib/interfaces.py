# -*- coding: utf-8 -*-
#
# Copyright (C) 2009 Paul Kölle
# All rights reserved.

from core import Interface

class IBaseModule(Interface):
    def get_path():
        """return the PATH the provider claims ownership for"""
        pass

    def index(*args, **kwargs):
        """the default handler"""
        pass

class ISystemModule(Interface):
    """A module for handling system tasks or providing
    system related information accessible under the /system namespace"""

    def description():
        """return a string describing the module"""

    def get_path():
        """the url path below /system"""

class IConfigModule(Interface):
    """access to /etc"""

    def description():
        """return a string describing the module"""

    def get_path():
        """the url path"""
        
class IMonitoringModule(Interface):
    """Implementors provide one or more (performance) metrics."""

    def description():
        """return a string describing the module"""

    def metrics():
      """return a list of metrics"""

    def values( *metrics):
      """return a dict of list for all instances
         for all metrics in the *metrics list:
      So if you have io-statistics for two disks the result
      might look like:
      {"sda":[0.1, 0.4, 1.1], "sdb":[0.3, 2.0, 2.1]}
      """

class IPackageManager(Interface):
    def search(pkgname):
      "search for package"

    def install(pkgname):
        """install/update a package"""

    def remove(pkgname):
      """uninstall package"""

    def update():
        """update the package database"""

    def upgrade():
        """perform system upgrade"""

    def updates():
        """list packages with new versions"""

    def info(pkgname):
        """detailed info for package 'name'"""


class IProcessInfo(Interface):
    def info(pid):
        "return a json dict with process information"

    def list():
        "return a list of running processes"

    def kill(pid):
        """kill process by pid"""

        
class IServiceManager(Interface):
    def start(name):
        """start a service"""

    def restart(name):
        """restart a service"""

    def stop(name):
        """stop a service"""

    def list():
        """list available services"""

    def status():
        """return service status"""