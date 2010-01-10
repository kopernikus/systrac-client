# -*- coding: utf-8 -*-
#
# Copyright (C) 2009 Paul Kölle
# All rights reserved.

import sys, os
sys.path.insert(0, os.path.abspath('lib'))
sys.path.insert(0, os.path.abspath('env/modules'))

from core import Dispatcher
from env import Environment

if __name__ == '__main__':
    path = os.path.abspath('env')
    env = Environment(path)
    srv = env[Dispatcher]
    print env.components
    print env.log
    print env.config
    srv('0.0.0.0', 1111)
