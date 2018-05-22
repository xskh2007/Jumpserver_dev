#coding:utf8

import os
import json
from collections import namedtuple
from ansible.inventory import Inventory
from ansible.vars import VariableManager
from ansible.parsing.dataloader import DataLoader
from ansible.executor.playbook_executor import PlaybookExecutor
from ansible.plugins.callback import CallbackBase
from ansible.errors import AnsibleParserError


class mycallback(CallbackBase):

    def __init__(self, *args):
        super(mycallback, self).__init__(display=None)
        self.status_ok = json.dumps({})
        self.status_fail = json.dumps({})
        self.status_unreachable = json.dumps({})
        self.status_playbook = ''
        self.status_no_hosts = False
        self.host_ok = {}
        self.host_failed = {}
        self.host_unreachable = {}

    def v2_runner_on_ok(self, result):
        host = result._host.get_name()
        self.runner_on_ok(host, result._result)
        self.host_ok[host] = result

    def v2_runner_on_failed(self, result, ignore_errors=False):
        host = result._host.get_name()
        self.runner_on_failed(host, result._result, ignore_errors)
        self.host_failed[host] = result

    def v2_runner_on_unreachable(self, result):
        host = result._host.get_name()
        self.runner_on_unreachable(host, result._result)
        self.host_unreachable[host] = result

    def v2_playbook_on_no_hosts_matched(self):
        self.playbook_on_no_hosts_matched()
        self.status_no_hosts = True

    def v2_playbook_on_play_start(self, play):
        self.playbook_on_play_start(play.name)
        self.playbook_path = play.name


class ansible_playbook():

    # 初始化各项参数,根据需求修改
    def __init__(self, playbook,
                 host_list='/etc/ansible/inventory',
                 ansible_cfg=None,
                 passwords={}):
        self.playbook_path = playbook
        self.passwords = passwords
        Options = namedtuple('Options',
                            ['connection',
                            'remote_user',
                            'ask_sudo_pass',
                            'verbosity',
                            'ack_pass',
                            'module_path',
                            'forks',
                            'become',
                            'become_method',
                            'become_user',
                            'check',
                            'listhosts',
                            'listtasks',
                            'listtags',
                            'syntax',
                            'sudo_user',
                            'sudo'])
        self.options = Options(connection='ssh',
                            remote_user='root',
                            ack_pass=None,
                            sudo_user='root',
                            forks=20,
                            sudo='no',
                            ask_sudo_pass=False,
                            verbosity=5,
                            module_path=None,
                            become=False,
                            become_method='sudo',
                            become_user='root',
                            check=None,
                            listhosts=None,
                            listtasks=None,
                            listtags=None,
                            syntax=None)
        if ansible_cfg != None:
            os.environ["ANSIBLE_CONFIG"] = ansible_cfg
        self.variable_manager = VariableManager()
        self.loader = DataLoader()
        self.inventory = Inventory(loader=self.loader, variable_manager=self.variable_manager, host_list=host_list)

    # 定义运行的方法和返回值
    def run(self):
        #判断playbook是否存在
        if not os.path.exists(self.playbook_path):
            code = 1000
            results = {'playbook': self.playbook_path, 'msg': self.playbook_path + ' playbook is not exist',
                       'flag': False}
        pbex = PlaybookExecutor(playbooks=[self.playbook_path],
                                inventory=self.inventory,
                                variable_manager=self.variable_manager,
                                loader=self.loader,
                                options=self.options,
                                passwords=self.passwords)
        self.results_callback = mycallback()
        pbex._tqm._stdout_callback = self.results_callback

        try:
            code = pbex.run()
        except AnsibleParserError:
            code = 1001
            results = {'playbook': self.playbook_path, 'msg': self.playbook_path + ' playbook have syntax error',
                       'flag': False}
            return code, results
        if self.results_callback.status_no_hosts:
            code = 1002
            results = {'playbook': self.playbook_path, 'msg': self.results_callback.status_no_hosts, 'flag': False,
                       'executed': False}
            return code, results

    def get_result(self):
        self.result_all = {'success': {}, 'fail': {}, 'unreachable': {}}

        for host, result in self.results_callback.host_ok.items():
            self.result_all['success'][host] = result._result

        for host, result in self.results_callback.host_failed.items():
            self.result_all['failed'][host] = result._result['msg']

        for host, result in self.results_callback.host_unreachable.items():
            self.result_all['unreachable'][host] = result._result['msg']

        for i ,a in self.result_all.items():
            print (i,a)



if __name__ == '__main__':
    play_book = ansible_playbook(playbook='/etc/ansible/playbook/test.yml')
    play_book.run()
    play_book.get_result()
