import sys
from terraobject import Terraobject
from swarm_tf.workers import WorkerVariables
from swarm_tf.workers import Worker
from swarm_tf.managers import ManagerVariables
from terrascript import provider, function, output
from terrascript.digitalocean.d import digitalocean_ssh_key as data_digitalocean_ssh_key
from swarm_tf.managers import Manager
from swarm_tf.common import VolumeClaim, get_user_data_script, create_firewall
from terrascript.digitalocean.r import *

# Setup
do_token = "<Place your digital ocean token here>"

# Common
domain = "swarmdemo.com"
region = "nyc3"
ssh_key_file = "~/.ssh/id_rsa"           # Need to be full path
user_data = get_user_data_script()

o = Terraobject()

o.terrascript.add(provider("digitalocean", token=do_token))

# ---------------------------------------------
# Get Existing Object at Digital Ocean
# ---------------------------------------------
do_sshkey = data_digitalocean_ssh_key("mysshkey", name="id_rsa")
o.terrascript.add(do_sshkey)
o.shared['sshkey'] = do_sshkey


# ---------------------------------------------
# Creating Swarm Manager
# ---------------------------------------------
managerVar = ManagerVariables()
managerVar.image = "ubuntu-18-04-x64"
managerVar.size = "s-1vcpu-1gb"
managerVar.name = "manager2"
managerVar.region = region
managerVar.domain = domain
managerVar.total_instances = 1
managerVar.user_data = user_data
managerVar.tags = ["cluster", "manager"]
managerVar.remote_api_ca = None
managerVar.remote_api_key = None
managerVar.remote_api_certificate = None
managerVar.ssh_keys = [do_sshkey.id]
managerVar.provision_ssh_key = ssh_key_file
managerVar.provision_user = "root"
managerVar.connection_timeout = "2m"
managerVar.create_dns = True

manager = Manager(o, managerVar)
manager.create_managers()

# ---------------------------------------------
# Creating Worker Nodes
# ---------------------------------------------
workerVar = WorkerVariables()
workerVar.image = "ubuntu-18-04-x64"
workerVar.size = "s-1vcpu-1gb"
workerVar.name = "worker2"
workerVar.region = region
workerVar.domain = domain
workerVar.total_instances = 2
workerVar.user_data = user_data
workerVar.tags = ["cluster", "worker"]
workerVar.manager_private_ip = o.shared["manager_nodes"][0].ipv4_address_private
workerVar.join_token = function.lookup(o.shared["swarm_tokens"].result, "worker", "")
workerVar.ssh_keys = [do_sshkey.id]
workerVar.provision_ssh_key = ssh_key_file
workerVar.provision_user = "root"
workerVar.persistent_volumes = None
workerVar.connection_timeout = "2m"
workerVar.create_dns = True

worker = Worker(o, workerVar)
worker.create_workers()

# ---------------------------------------------
# Creating Persistent Nodes
# ---------------------------------------------
workerVar.name = "persistent"
workerVar.persistent_volumes = [VolumeClaim(o, region, "volume-nyc3-01")]
workerVar.total_instances = 1
persistent_worker = Worker(o, workerVar)
persistent_worker.create_workers()

# ---------------------------------------------
# Creating Firewall
# ---------------------------------------------
create_firewall(o, domain=domain, inbound_ports=[22, 80, 443, 9000], tag="cluster")


# ---------------------------------------------
# Outputs
# ---------------------------------------------
o.terrascript.add(output("manager_ips",
                         value=[value.ipv4_address for value in o.shared["manager_nodes"]],
                         description="The manager nodes public ipv4 addresses"))

o.terrascript.add(output("manager_ips_private",
                         value=[value.ipv4_address_private for value in o.shared["manager_nodes"]],
                         description="The manager nodes private ipv4 addresses"))

o.terrascript.add(output("worker_ips",
                         value=[value.ipv4_address for value in o.shared["worker_nodes"]],
                         description="The worker nodes public ipv4 addresses"))

o.terrascript.add(output("worker_ips_private",
                         value=[value.ipv4_address_private for value in o.shared["worker_nodes"]],
                         description="The worker nodes private ipv4 addresses"))

o.terrascript.add(output("manager_token",
                         value=function.lookup(o.shared["swarm_tokens"].result, "manager", ""),
                         description="The Docker Swarm manager join token",
                         sensitive=True))

o.terrascript.add(output("worker_token",
                         value=function.lookup(o.shared["swarm_tokens"].result, "worker", ""),
                         description="The Docker Swarm worker join token",
                         sensitive=True))

o.terrascript.add(output("worker_ids",
                         value=[value.id for value in o.shared["worker_nodes"]]))

o.terrascript.add(output("manager_ids",
                         value=[value.id for value in o.shared["manager_nodes"]]))

o.terrascript.add(output("private_key_path", value=ssh_key_file))


if len(sys.argv) == 2 and sys.argv[1] == "label":
    for obj in o.shared["__variables"]:
        for i in range(1, obj["instances"]+1):
            print("docker node update --label-add type={0} {0}-{1:02d}".format(obj["type"], i))
else:
    print(o.terrascript.dump())

