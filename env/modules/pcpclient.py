# -*- coding: utf-8 -*-
#
# Copyright (C) 2009 Paul Kölle
# All rights reserved.

from subprocess import Popen, PIPE

from core import *
from interfaces import IMonitoringModule
from lib.util import nodes

pcp_error = False
have_pcp = True
try:
    import pcpi
    from pcpi import *
except ImportError, e:
    have_pcp = False
    pcp_error = e

class PCPProxy(Component):
    implements(IMonitoringModule)

    @classmethod
    def supported_plattform(cls, p, f, r):
        """check plattform, flavour, release"""
        #FIXME check for running pmcd (open socket on localhost)
        return os.path.exists('/usr/bin/pminfo')

        #if not have_pcp:
        #    print "Failed to load PCP library. PCP not installed (%s)" % pcp_error
        #    return False
        #return True

    def metrics(self, NS='.'):
        """return a list/tree of metrics starting at 'NS' """
        ret, out, err = self._run_cmd("/usr/bin/pminfo mem")
        if ret != 0:
            raise SysTracError("Error running pminfo -> %s" % err)
        lines = [l.strip() for l in out.split('\n')]
        root = nodes.Node(None, "pcp")
        for line in lines:
            _create_nodes(root, line)

        out = [node.position for node in nodes.Node._instances]
        #for node in nodes.Node._instances:
        #    if node.children:
        #        print "Node %s has %d children" % (node.position, len(node.children))
        return {'status':0, 'response':[out], 'errors':[]}

    def values(self, *metric):
        """get current values for each metric in *metrics"""
        pass

    def _run_cmd(self, cmd):
        #print "command passed to Popen: %s" % cmd+' '+action
        p = Popen(cmd, stderr=PIPE, stdout=PIPE, shell=True)
        out, err = p.communicate()
        if p.returncode != 0:
            return p.returncode, None, err+out
        return p.returncode, out or None, err or None


def _create_nodes(parent, line):
    parts = line.split('.', 1)
    if len(parts) == 1:
        parent.appendNode(parts[0])
        return

    current =  nodes.Node.findNode(parent.position+'.'+parts[0])
    if not current:
        current = parent.appendNode(parts[0])

    _create_nodes(current, parts[1])