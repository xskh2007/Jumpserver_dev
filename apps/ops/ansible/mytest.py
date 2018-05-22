# -*- coding: utf-8 -*-
#

import unittest
import sys

sys.path.insert(0, "../..")

from ops.ansible.runner import CopyAdHocRunner, CopyRunner
from ops.ansible.inventory import BaseInventory




host_data = [
    {
        "hostname": "testserver",
        "ip": "192.168.1.152",
        "port": 22,
        "username": "root",
        "password": "zzjr#2015",
    },
    {
        "hostname": "testserver2",
        "ip": "192.168.2.220",
        "port": 22,
        "username": "root",
        "password": "zzjr#2015",
    },
]
inventory = BaseInventory(host_data)
runner = CopyRunner(inventory)

cmd="src=/tmp/test2.py dest=/tmp/"
res = runner.mycopy(cmd, 'all')
print(res.results_command)



