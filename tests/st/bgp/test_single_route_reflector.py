# Copyright (c) 2016 Tigera, Inc. All rights reserved.
# Copyright 2015 Metaswitch Networks
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from nose.plugins.attrib import attr

from tests.st.test_base import TestBase
from tests.st.utils.constants import DEFAULT_IPV4_ADDR_1, DEFAULT_IPV4_ADDR_2
from tests.st.utils.docker_host import DockerHost
from tests.st.utils.route_reflector import RouteReflectorCluster


class TestSingleRouteReflector(TestBase):

    @attr('slow')
    def test_single_route_reflector(self):
        """
        Run a multi-host test using a single route reflector and global
        peering.
        """
        with DockerHost('host1') as host1, \
             DockerHost('host2') as host2, \
             RouteReflectorCluster(1, 1) as rrc:

            # Turn off the node-to-node mesh (do this from any host), and
            # change the default AS Number (arbitrary choice).
            host1.calicoctl("bgp default-node-as 64514")
            host1.calicoctl("bgp node-mesh off")

            # Create a profile to associate with both workloads
            host1.calicoctl("profile add TEST_GROUP")

            workload_host1 = host1.create_workload("workload1")
            workload_host2 = host2.create_workload("workload2")

            # Add containers to Calico
            host1.calicoctl("container add %s %s" % (workload_host1,
                                                     DEFAULT_IPV4_ADDR_1))
            host2.calicoctl("container add %s %s" % (workload_host2,
                                                     DEFAULT_IPV4_ADDR_2))

            # Now add the profiles - one using set and one using append
            host1.calicoctl("container %s profile set TEST_GROUP" % workload_host1)
            host2.calicoctl("container %s profile append TEST_GROUP" % workload_host2)

            # Allow network to converge (which it won't)
            try:
                workload_host1.assert_can_ping(DEFAULT_IPV4_ADDR_2, retries=5)
            except AssertionError:
                pass
            else:
                raise AssertionError("Hosts can ping each other")

            # Set global config telling all calico nodes to peer with the
            # route reflector.  This can be run from either host.
            rg = rrc.get_redundancy_group()
            assert len(rg) == 1
            host1.calicoctl("bgp peer add %s as 64514" % rg[0].ip)

            # Allow network to converge (which it now will).
            workload_host1.assert_can_ping(DEFAULT_IPV4_ADDR_2, retries=10)

            # And check connectivity in both directions.
            self.assert_ip_connectivity(workload_list=[workload_host1,
                                                       workload_host2],
                                        ip_pass_list=[DEFAULT_IPV4_ADDR_1,
                                                      DEFAULT_IPV4_ADDR_2])
