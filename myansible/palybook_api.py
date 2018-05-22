import sys
import json
from collections import namedtuple
from ansible.parsing.dataloader import DataLoader
from ansible.vars.manager import VariableManager
from ansible.inventory.manager import InventoryManager
from ansible.executor.playbook_executor import PlaybookExecutor
from ansible.playbook.play import Play
from ansible import constants as C
from ansible.plugins.callback import CallbackBase
from ansible.executor.task_queue_manager import TaskQueueManager
import logging


def Playbook_Run(host, playbook_path,args=None):
    loader = DataLoader()
    inventory = InventoryManager(loader=loader, sources=host)
    variable_manager = VariableManager(loader=loader, inventory=inventory)
    #json参数列表
    variable_manager.extra_vars={"cmd":args}
    Options = namedtuple('Options',
                         ['listtags', 'listtasks', 'listhosts', 'syntax', 'connection', 'module_path', 'forks',
                          'remote_user', 'private_key_file', 'ssh_common_args', 'ssh_extra_args', 'sftp_extra_args',
                          'scp_extra_args', 'become', 'become_method', 'become_user', 'verbosity', 'check', 'diff'])
    options = Options(listtags=False, listtasks=False, listhosts=False, syntax=False, connection='smart',
                      module_path=None, forks=100, remote_user='root', private_key_file=None, ssh_common_args=None,
                      ssh_extra_args=None, sftp_extra_args=None, scp_extra_args=None, become=True, become_method=None,
                      become_user='root', verbosity=None, check=False, diff=False)
    passwords = {}
    pbex = PlaybookExecutor(playbooks=[playbook_path], inventory=inventory, variable_manager=variable_manager,
                            loader=loader, options=options, passwords=passwords)
    result = pbex.run()
    return result