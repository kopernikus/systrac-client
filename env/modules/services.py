import os
from os.path import join as joinpath
from subprocess import Popen, PIPE
from config import Option, ExtensionOption
from core import implements, Component, ExtensionPoint,\
        SysTracError, Interface

import cherrypy as cp

from base import ISystemModule



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


            
class SysVServiceModule(Component):
    implements(IServiceManager)
    
    def __init__(self):
        self.basedir = '/etc/init.d'
        self.blacklist = [
            'skeleton', 'rc', 'rcS','pppd-dns'
            'open-vm-tools.dpkg-old', 'README',
            'anacron', 'acpi-support', 'alsa-utils',
            'apmd', 'apport', 'binfmt-support',
            'brltty', 'console-setup', 'dkms_autoinstaller',
            'dns-clean', 'gdm', 'halt', 'hotkey-setup', 
            'keyboard-setup', 'killprocs', 'laptop-mode',
            'linux-restricted-modules-common',
            'module-init-tools', 'mountoverflowtmp',
            'networking', 'ondemand', 'open-vm-tools',
            'pulseaudio', 'procps', 'rc', 'rc.local',
            'readahead', 'readahead-desktop', 'reboot',
            'rmnologin', 'screen-cleanup', 'sendsigs',
            'single', 'stop-bootlogd', 'stop-bootlogd-single',
            'stop-readahead', 'system-tools-backends', 'udev',
            'udev-finish', 'wpa-ifupdown']
    
        self.answer = {
                'status':None,
                'result': None,
                'errors':[]}
                
    @classmethod
    def supported_plattform(cls):
        yield ('linux', 'ubuntu', '9.04')
        yield ('linux', 'debian', '5.0')
      
    def index(self):
        return self.json.dumps(
            {'methods':['list', 'start', 'stop', 'restart', 'status']})
 

    def list(self):
        raw =  [e for e in os.listdir('/etc/init.d')
                if not e.endswith('.sh')]
        srv = [e for e in raw if e not in self.blacklist]
        return self.json.dumps({'services': srv, 'errors': []})

 
    def start(self, name):
        if os.path.isfile(joinpath(self.basedir, name)):
            return self.json.dumps({
                'service': name,
                'status':'started',
                'result': 'success',
                'errors':[]})
        return self.json.dumps({'result':'fail', 'errors':['NOTFOUND']})
        
    def status(self, name):
        cmd = joinpath(self.basedir, name)
        if os.path.isfile(cmd):
            p = Popen(cmd+' status', stderr=PIPE, stdout=PIPE, shell=True)
            ret = p.wait()
            res = p.stdout.read()
            err = p.stderr.read()
            return self.json.dumps({
                'service': name,
                'status':ret,
                'result': res,
                'errors':[err]})
        return self.json.dumps({'result':'fail', 'errors':['NOTFOUND']})
        
    def stop(self, name):
        if os.path.isfile(joinpath(self.basedir, name)):
            return self.json.dumps({
                'service': name,
                'status':'sucess',
                'result': 'stopped',
                'errors':[]})
        else:
            return self.json.dumps({
                'status':'fail',
                'result': 'unknown',
                'errors':['NOTFOUND']})
    
    def restart(self, name):
        if os.path.isfile(joinpath(self.basedir, name)):
            return self.json.dumps({
                'status':'success',
                'result': 'started',
                'errors':[]})

class UpstartServiceModule(Component):
    implements(IServiceManager)
    
    def __init__(self):
        self.answer = {
                'status':None,
                'result': None,
                'errors':[]}
                
    @classmethod
    def supported_plattform(cls):
        yield ('linux', 'ubuntu', '10.04')
        
    def description(self):
        return "Service management with Upstart"
        
    def start(self, service):
        pass
      
    def stop(self, service):
        pass
      
    def restart(self, service):
        pass
      
    def list(self):
        pass
      
    def status(self, service):
        pass

class ServiceModule(Component):
    implements(ISystemModule)
    
    children = ExtensionPoint(IServiceManager)
    #default service manager
    default_manager = ExtensionOption('systrac', 'default_service_manager', 
                              IServiceManager)
  
    def __init__(self):
        self.log.debug("Got IServiceManager providers %s" % self.children)
        
    #FIXME: collect all platforms from self.children
    @classmethod
    def supported_plattform(cls):
        yield ('linux', 'ubuntu', '9.04')
        yield ('linux', 'debian', '5.0')
        
    def description(self):
        return "Service management"
        
    def get_path(self):
        return 'services'
        
    @cp.expose
    @cp.tools.set_content_type()
    def start(self, name):
        return self.default_manager.start(name)
  
    @cp.expose
    @cp.tools.set_content_type()
    def stop(self, name):
        return self.default_manager.start(name)
    
    @cp.expose
    @cp.tools.set_content_type()
    def restart(self, name):
        return self.default_manager.start(name)
        
    @cp.expose
    @cp.tools.set_content_type()
    def status(self, name):
        return self.default_manager.status(name)
    
    @cp.expose
    @cp.tools.set_content_type()
    def list(self):
        return self.default_manager.list()
    
    @cp.expose
    @cp.tools.set_content_type()
    def index(self):
        return self.json.dumps(
            {'methods':['list', 'start', 'stop', 'restart', 'status']})
