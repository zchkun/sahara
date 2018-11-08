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


def get_plugin_configs():
    return {}


def generate_configs(instances):
    conf = ["tickTime=2000",
            "dataDir=/var/zookeeper",
            "clientPort=2181",
            "initLimit=5",
            "syncLimit=2"]
    for index, instance in enumerate(instances):
        conf.append('server.%s=%s:2888:3888' %
                    (str(index), instance.instance_name))

    return '\n'.join(conf)