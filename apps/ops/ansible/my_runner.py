# ~*~ coding: utf-8 ~*~

import os
from collections import namedtuple
from ansible.executor.task_queue_manager import TaskQueueManager
from ansible.vars.manager import VariableManager
from ansible.parsing.dataloader import DataLoader
from ansible.executor.playbook_executor import PlaybookExecutor
from ansible.playbook.play import Play
import ansible.constants as C

from .callback import AdHocResultCallback, PlaybookResultCallBack, \
    CommandResultCallback
from common.utils import get_logger
from .exceptions import AnsibleError


__all__ = ["AdHocRunner"]
C.HOST_KEY_CHECKING = False
logger = get_logger(__name__)


Options = namedtuple('Options', [
    'listtags', 'listtasks', 'listhosts', 'syntax', 'connection',
    'module_path', 'forks', 'remote_user', 'private_key_file', 'timeout',
    'ssh_common_args', 'ssh_extra_args', 'sftp_extra_args',
    'scp_extra_args', 'become', 'become_method', 'become_user',
    'verbosity', 'check', 'extra_vars', 'playbook_path', 'passwords',
    'diff', 'gathering', 'remote_tmp',
])


def get_default_options():
    options = Options(
        listtags=False,
        listtasks=False,
        listhosts=False,
        syntax=False,
        timeout=60,
        connection='ssh',
        module_path='',
        forks=10,
        remote_user='root',
        private_key_file=None,
        ssh_common_args="",
        ssh_extra_args="",
        sftp_extra_args="",
        scp_extra_args="",
        become=None,
        become_method=None,
        become_user=None,
        verbosity=None,
        extra_vars=[],
        check=False,
        playbook_path='/etc/ansible/',
        passwords=None,
        diff=False,
        gathering='implicit',
        remote_tmp='/tmp/.ansible'
    )
    return options




class CopyAdHocRunner:
    """
    ADHoc Runner接口
    """
    results_callback_class = AdHocResultCallback
    loader_class = DataLoader
    variable_manager_class = VariableManager
    options = get_default_options()
    default_options = get_default_options()

    def __init__(self, inventory, options=None):
        if options:
            self.options = options
        self.inventory = inventory
        self.loader = DataLoader()
        self.variable_manager = VariableManager(
            loader=self.loader, inventory=self.inventory
        )

    def set_option(self, k, v):
        kwargs = {k: v}
        self.options = self.options._replace(**kwargs)

    def run(self, tasks, pattern, play_name='Ansible Ad-hoc', gather_facts='no'):
        """
        :param tasks: [{'action': {'module': 'shell', 'args': 'ls'}, ...}, ]
        :param pattern: all, *, or others
        :param play_name: The play name
        :return:
        """
        results_callback = self.results_callback_class()


        play_source = dict(
            name=play_name,
            hosts=pattern,
            gather_facts=gather_facts,
            tasks=tasks
        )

        play = Play().load(
            play_source,
            variable_manager=self.variable_manager,
            loader=self.loader,
        )

        tqm = TaskQueueManager(
            inventory=self.inventory,
            variable_manager=self.variable_manager,
            loader=self.loader,
            options=self.options,
            stdout_callback=results_callback,
            passwords=self.options.passwords,
        )
        logger.debug("Get inventory matched hosts: {}".format(
            self.inventory.get_matched_hosts(pattern)
        ))

        try:
            tqm.run(play)
            return results_callback
        except Exception as e:
            raise AnsibleError(e)
        finally:
            tqm.cleanup()
            self.loader.cleanup_all_tmp_files()




class CopyRunner(CopyAdHocRunner):
    results_callback_class = CommandResultCallback
    modules_choices = ('shell', 'raw', 'command', 'script')

    def execute(self, cmd, pattern, module=None):
        if module and module not in self.modules_choices:
            raise AnsibleError("Module should in {}".format(self.modules_choices))
        else:
            module = "shell"

        tasks = [
            {"action": {"module": module, "args": cmd}}
        ]
        hosts = self.inventory.get_hosts(pattern=pattern)
        name = "Run command {} on {}".format(cmd, ", ".join([host.name for host in hosts]))
        return self.run(tasks, pattern, play_name=name)

    def mycopy(self, cmd, pattern, module='copy'):
        # print(cmd,111)
        # src = '/tmp/test.py'
        # dest = '/tmp/'
        # cmd="src=%s  dest=%s"%(src, dest)
        # print(cmd,222)

        tasks = [
            {"action": {"module": module, "args":cmd}}
        ]
        hosts = self.inventory.get_hosts(pattern=pattern)
        name = "Run command {} on {}".format(cmd, ", ".join([host.name for host in hosts]))
        return self.run(tasks, pattern, play_name=name)

