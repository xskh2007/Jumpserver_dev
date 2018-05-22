# ~*~ coding: utf-8 ~*~
import json
from collections import Mapping,namedtuple
from ansible import constants as C
from ansible.inventory.host import Host
from ansible.vars.manager import VariableManager
from ansible.inventory.manager import InventoryManager
from ansible.parsing.dataloader import DataLoader
from ansible.errors import AnsibleError, AnsibleParserError
from ansible.playbook.play import Play
from ansible.executor.task_queue_manager import TaskQueueManager
from ansible.plugins.callback import CallbackBase
from ansible.executor.playbook_executor import PlaybookExecutor
from ansible.utils.vars import load_extra_vars
from ansible.utils.vars import load_options_vars


class HostInventory(Host):
    def __init__(self, host_data):
        self.host_data = host_data
        hostname = host_data.get('hostname') or host_data.get('ip')
        port = host_data.get('port') or 22
        super(HostInventory,self).__init__(hostname, port)
        self.__set_required_variables()
        self.__set_extra_variables()

    def __set_required_variables(self):
        host_data = self.host_data
        self.set_variable('ansible_host', host_data['ip'])
        self.set_variable('ansible_port', host_data['port'])

        if host_data.get('username'):
            self.set_variable('ansible_user', host_data['username'])

        if host_data.get('password'):
            self.set_variable('ansible_ssh_pass', host_data['password'])
        if host_data.get('private_key'):
            self.set_variable('ansible_ssh_private_key_file', host_data['private_key'])

        become = host_data.get("become", False)
        if become:
            self.set_variable("ansible_become", True)
            self.set_variable("ansible_become_method", become.get('method', 'sudo'))
            self.set_variable("ansible_become_user", become.get('user', 'root'))
            self.set_variable("ansible_become_pass", become.get('pass', ''))
        else:
            self.set_variable("ansible_become", False)

    def __set_extra_variables(self):
        for k, v in self.host_data.get('vars', {}).items():
            self.set_variable(k, v)

    def __repr__(self):
        return self.name


class MyInventory(InventoryManager):

    def __init__(self, resource=None):
        self.resource = resource
        self.loader = DataLoader()
        self.variable_manager = VariableManager()
        super(MyInventory,self).__init__(self.loader)

    def get_groups(self):
        return self._inventory.groups

    def get_group(self, name):
        return self._inventory.groups.get(name, None)

    def parse_sources(self, cache=False):
        group_all = self.get_group('all')
        ungrouped = self.get_group('ungrouped')
        if isinstance(resource, list):
            for host_data in self.resource:
                host = HostInventory(host_data=host_data)
                self.hosts[host_data['hostname']] = host
                groups_data = host_data.get('groups')
                if groups_data:
                    for group_name in groups_data:
                        group = self.get_group(group_name)
                        if group is None:
                            self.add_group(group_name)
                            group = self.get_group(group_name)
                        group.add_host(host)
                else:
                    ungrouped.add_host(host)
                group_all.add_host(host)
                
        elif isinstance(resource, dict):
            for k,v in self.resource.items():
                group = self.get_group(k)
                if group is None:
                    self.add_group(k)  
                    group = self.get_group(k)   

                if 'hosts' in v:
                    if not isinstance(v['hosts'], list):
                        raise AnsibleError("You defined a group '%s' with bad data for the host list:\n %s" % (group, v))
                    for host_data in v['hosts']:
                        host = HostInventory(host_data=host_data)
                        self.hosts[host_data['hostname']] = host
                        group.add_host(host)   
                                        
                if 'vars' in v:
                    if not isinstance(v['vars'], dict):
                        raise AnsibleError("You defined a group '%s' with bad data for variables:\n %s" % (group, v))
        
                    for x, y in v['vars'].items():
                        self._inventory.groups[k].set_variable( x, y)
                                          

    def get_matched_hosts(self, pattern):
        return self.get_hosts(pattern)

class ModelResultsCollector(CallbackBase):  
  
    def __init__(self, *args, **kwargs):  
        super(ModelResultsCollector, self).__init__(*args, **kwargs)  
        self.host_ok = {}  
        self.host_unreachable = {}  
        self.host_failed = {}  
  
    def v2_runner_on_unreachable(self, result):  
        self.host_unreachable[result._host.get_name()] = result 
  
    def v2_runner_on_ok(self, result,  *args, **kwargs):  
        self.host_ok[result._host.get_name()] = result  

  
    def v2_runner_on_failed(self, result,  *args, **kwargs):  
        self.host_failed[result._host.get_name()] = result  

        

class PlayBookResultsCollector(CallbackBase):  
    CALLBACK_VERSION = 2.0    
    def __init__(self, *args, **kwargs):  
        super(PlayBookResultsCollector, self).__init__(*args, **kwargs)  
        self.task_ok = {}  
        self.task_skipped = {}  
        self.task_failed = {}  
        self.task_status = {} 
        self.task_unreachable = {}
        self.task_changed = {}

    def v2_runner_on_ok(self, result, *args, **kwargs):
        self.task_ok[result._host.get_name()]  = result

    def v2_runner_on_failed(self, result, *args, **kwargs):
        self.task_failed[result._host.get_name()] = result

    def v2_runner_on_unreachable(self, result):
        self.task_unreachable[result._host.get_name()] = result

    def v2_runner_on_skipped(self, result):
        self.task_ok[result._host.get_name()]  = result

    def v2_runner_on_changed(self, result):
        self.task_changed[result._host.get_name()] = result

    def v2_playbook_on_stats(self, stats):
        hosts = sorted(stats.processed.keys())
        for h in hosts:
            t = stats.summarize(h)
            self.task_status[h] = {
                                       "ok":t['ok'],
                                       "changed" : t['changed'],
                                       "unreachable":t['unreachable'],
                                       "skipped":t['skipped'],
                                       "failed":t['failures']
                                   }
        


class ANSRunner(object):  
    

    
    def __init__(
        self,
        hosts=C.DEFAULT_HOST_LIST,
        module_name=C.DEFAULT_MODULE_NAME,   
        module_args=C.DEFAULT_MODULE_ARGS,    
        forks=C.DEFAULT_FORKS,               
        timeout=C.DEFAULT_TIMEOUT,            
        pattern="all",                       
        remote_user=C.DEFAULT_REMOTE_USER,   
        module_path=None,
        connection_type="smart",
        become=None,
        become_method=None,
        become_user=None,
        check=False,
        passwords=None,
        extra_vars = None,
        private_key_file=None,
        listtags=False,
        listtasks=False,
        listhosts=False,
        ssh_common_args=None,
        ssh_extra_args=None,
        sftp_extra_args=None,
        scp_extra_args=None,
        verbosity=None,
        syntax=False,        
        redisKey=None,
        logId=None
    ):
        self.Options = namedtuple("Options", [
                                                'listtags', 'listtasks', 'listhosts', 'syntax', 'connection',
                                                'module_path', 'forks', 'remote_user', 'private_key_file', 'timeout',
                                                'ssh_common_args', 'ssh_extra_args', 'sftp_extra_args', 'scp_extra_args',
                                                'become', 'become_method', 'become_user', 'verbosity', 'check',
                                                'extra_vars', 'diff'
                                                ]
                                            )
        self.results_raw = {} 
        self.pattern = pattern
        self.module_name = module_name
        self.module_args = module_args
        self.gather_facts = 'no'
        self.options = self.Options(
            listtags=listtags,
            listtasks=listtasks,
            listhosts=listhosts,
            syntax=syntax,
            timeout=timeout,
            connection=connection_type,
            module_path=module_path,
            forks=forks,
            remote_user=remote_user,
            private_key_file=private_key_file,
            ssh_common_args=ssh_common_args or "",
            ssh_extra_args=ssh_extra_args or "",
            sftp_extra_args=sftp_extra_args,
            scp_extra_args=scp_extra_args,
            become=become,
            become_method=become_method,
            become_user=become_user,
            verbosity=verbosity,
            extra_vars=extra_vars or [],
            check=check,
            diff=False
        )
        self.redisKey = redisKey
        self.logId = logId        
        self.loader = DataLoader()
        self.inventory = MyInventory(resource=hosts)
        self.variable_manager = VariableManager(self.loader, self.inventory)
        self.variable_manager.extra_vars = load_extra_vars(loader=self.loader, options=self.options)
        self.variable_manager.options_vars = load_options_vars(self.options, "")
        self.passwords = passwords or {}
             
        

    def run_model(self,host_list, module_name, module_args):
        self.callback = ModelResultsCollector()
        play_source = dict(
            name="Ansible Ad-hoc",
            hosts=host_list,
            gather_facts=self.gather_facts,
            tasks=[dict(action=dict(module=module_name, args=module_args))]
        )        
        play = Play().load(play_source,loader=self.loader,variable_manager=self.variable_manager)
        tqm = None 
        try:
            tqm = TaskQueueManager(
                inventory=self.inventory,
                variable_manager=self.variable_manager,
                loader=self.loader,
                options=self.options,
                passwords=self.passwords,
                stdout_callback=self.callback
            )        
            tqm._stdout_callback = self.callback  
            C.HOST_KEY_CHECKING = False #关闭第一次使用ansible连接客户端是输入命令
            tqm.run(play)              
        except Exception as err: 
            print (err)
        finally:  
            if tqm is not None:  
                tqm.cleanup()  
            if self.loader:
                self.loader.cleanup_all_tmp_files()


    def run_playbook(self, host_list, playbook_path,extra_vars=dict()): 
        """ 
        run ansible palybook 
        """         
        try: 
            self.callback = PlayBookResultsCollector()  
            if isinstance(host_list, list):extra_vars['host'] = ','.join(host_list)
            else:extra_vars['host'] = host_list
            self.variable_manager.extra_vars = extra_vars            
            executor = PlaybookExecutor(  
                playbooks=[playbook_path], inventory=self.inventory, variable_manager=self.variable_manager, loader=self.loader,  
                options=self.options, passwords=self.passwords,  
            )  
            executor._tqm._stdout_callback = self.callback  
            C.HOST_KEY_CHECKING = False #关闭第一次使用ansible连接客户端是输入命令
            C.DEPRECATION_WARNINGS = False
            C.RETRY_FILES_ENABLED = False  
            executor.run()  
        except Exception as err: 
            print (err)
            return False


    def get_model_result(self):  
        self.results_raw = {'success':{}, 'failed':{}, 'unreachable':{}}  
        for host, result in self.callback.host_ok.items():  
            self.results_raw['success'][host] = result._result  


        for host, result in self.callback.host_failed.items():  
            self.results_raw['failed'][host] = result._result 

  
        for host, result in self.callback.host_unreachable.items():  
            self.results_raw['unreachable'][host]= result._result 

        return json.dumps(self.results_raw)  

    def get_playbook_result(self):  
        self.results_raw = {'skipped':{}, 'failed':{}, 'ok':{},"status":{},'unreachable':{},"changed":{}} 
        
        for host, result in self.callback.task_ok.items():
            self.results_raw['ok'][host] = result 
  
        for host, result in self.callback.task_failed.items():  
            self.results_raw['failed'][host] = result 
 
        for host, result in self.callback.task_status.items():
            self.results_raw['status'][host] = result 

        for host, result in self.callback.task_changed.items():
            self.results_raw['changed'][host] = result 

        for host, result in self.callback.task_skipped.items():
            self.results_raw['skipped'][host] = result 

        for host, result in self.callback.task_unreachable.items():
            self.results_raw['unreachable'][host] = result
        return self.results_raw

    
if __name__ == "__main__":
    resource = [
                    {"hostname": "192.168.88.234", "port": "22","username": "root", "password": "welliam","ip":"192.168.88.234","vars":{"name":"welliam"}},
                    {"hostname": "192.168.88.230", "port": "22","username": "root", "password": "welliam","ip":"192.168.88.230","vars":{"name":"alex"}}
                ]
    resource = { 
         "group1":{
               "hosts":[
                    {"hostname": "192.168.88.234", "port": "22","username": "root", "password": "welliam","ip":"192.168.88.234"},
                    {"hostname": "192.168.88.230", "port": "22","username": "root", "password": "welliam","ip":"192.168.88.230","vars":{"name":"welliam233"}},
                    {"hostname": "192.168.88.233", "port": "22","username": "root", "password": "welliam","ip":"192.168.88.233"}
                ],
               "vars":{"name":"welliam","age":24,"iphone":18620181259}
              },
         "group2":{
               "hosts":[
                    {"hostname": "192.168.88.235", "port": "22","username": "root", "password": "welliam","ip":"192.168.88.235"}
                ],
               "vars":{"name":"alex","age":30,"iphone":17012162020}
              }                
        }
#     myhosts = MyInventory(resource=resource)
#     print myhosts.groups["group1"].get_hosts()
#     print myhosts.groups["group1"].vars
    rbt = ANSRunner(hosts=resource)
#     rbt.run_model(host_list="group1,group2",module_name='template',module_args='src="/root/text.txt" dest="/tmp/text.log"')
#     print rbt.get_model_result()
    rbt.run_playbook(host_list="group1,group2",playbook_path='/mnt/OpsManage/upload/playbook/system.yml')
    print (rbt.get_playbook_result())