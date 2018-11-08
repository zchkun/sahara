# Copyright (c) 2017 EasyStack Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from oslo_log import log as logging

from sahara import context
from sahara.i18n import _
from sahara.plugins import exceptions as ex
from sahara.plugins import provisioning as p
from sahara.plugins import utils
from sahara.plugins.zookeeper import config_helper as ch
from sahara.utils import cluster_progress_ops as cpo
from sahara.utils import remote


LOG = logging.getLogger(__name__)


class ZookeeperProvider(p.ProvisioningPluginBase):

    def get_versions(self):
        return ['3.4.8']

    def get_configs(self, hadoop_version):
        return ch.get_plugin_configs()

    def get_node_processes(self, hadoop_version):
        return {
            "Zookeeper": ['zookeeper']
        }

    def get_title(self):
        return "ZooKeeper Plugin"

    def get_description(self):
        return _('The Zookeeper plugin provide the ability to'
                 'launch a cluster installed zookeeper service')

    def validate(self, cluster):
        node_count = sum([ng.count for ng
                          in utils.get_node_groups(cluster, 'zookeeper')])
        if (node_count % 2 == 0 and node_count > 0):
            raise ex.InvalidComponentCountException(
                'zookeeper', 'odd number of', node_count)

    def validate_scaling(self, cluster, existing, additional):
        # TODO(shuyingya): seems like we don't need validating here
        # node_group = cluster.node_groups[0]
        # if (existing[node_group.id] % 2 == 0 and existing[node_group.id]>0):
        #     raise ex.InvalidComponentCountException(
        #         'zookeeper', 'odd number of', existing[node_group.id])
        pass

    def update_infra(self, cluster):
        pass

    def configure_cluster(self, cluster):
        instances = utils.get_instances(cluster)
        zk_conf = ch.generate_configs(instances)
        self._push_configs_to_nodes(cluster, instances, zk_conf)

    def start_cluster(self, cluster):
        instances = utils.get_instances(cluster)
        self._handle_zookeeper_processes(instances)

    def scale_cluster(self, cluster, instances):
        # configure all of instances
        zk_conf = ch.generate_configs(instances)
        self._push_configs_to_nodes(cluster, instances, zk_conf)
        # restart zookeeper
        self._handle_zookeeper_processes(instances, 'restart')
        LOG.info("Zookeeper service has been restarted")

    def decommission_nodes(self, cluster, to_be_deleted):
        decommission = False
        # remove surplus nodes
        instances = utils.get_instances(cluster)
        for i in to_be_deleted:
            instances.remove(i)
            decommission = True

        with context.ThreadGroup() as tg:
            for instance in instances:
                tg.spawn("zookeeper-stop-%s" % instance.instance_name,
                         self._handle_zookeeper, instance, "stop")

        if decommission:
            self._decommision_nodes(cluster, instances)

    def get_open_ports(self, node_group):
        return [2199, 2888, 3888]

    def _push_configs_to_nodes(self, cluster, instances, configs):
        cpo.add_provisioning_step(
            cluster.id, _("Push configs to node"), len(instances))

        with context.ThreadGroup() as tg:
            for i, instance in enumerate(instances):
                tg.spawn("zookeeper-configure-%s" %
                         instance.instance_name,
                         self._push_configs_to_node,
                         configs, instance, str(i))

    @cpo.event_wrapper(True)
    def _push_configs_to_node(self, configs, instance, server_id):
        file_zookeeper = {
            '/opt/zookeeper/zookeeper/conf/zoo.cfg': configs,
            '/var/zookeeper/myid': server_id
        }
        with remote.get_remote(instance) as r:
            r.write_files_to(file_zookeeper, run_as_root=True)

    def _handle_zookeeper_processes(self, instances, operation='start'):
        if len(instances) == 0:
            return

        cpo.add_provisioning_step(
            instances[0].cluster_id,
            utils.start_process_event_message("Zookeeper"),
            len(instances))

        with context.ThreadGroup() as tg:
            for instance in instances:
                tg.spawn("zookeeper-%s-%s" % (
                         operation, instance.instance_name),
                         self._handle_zookeeper, instance, operation)

    @cpo.event_wrapper(True)
    def _handle_zookeeper(self, instance, operation='start'):
        if operation not in ['start', 'stop', 'restart']:
            raise Exception("Weird operation.")
        with instance.remote() as r:
            r.execute_command(
                "/opt/zookeeper/zookeeper/bin/zkServer.sh %s" % operation,
                run_as_root=True
            )

    def _decommision_nodes(self, cluster, instances):
        zk_conf = ch.generate_configs(instances)
        self._push_configs_to_nodes(cluster, instances, zk_conf)
        # restart zookeeper
        self._handle_zookeeper_processes(instances, 'restart')
        LOG.info("Zookeeper service has been restarted")
