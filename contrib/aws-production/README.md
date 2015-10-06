### AWS Production Configuration

This is a set of opinionated scripts on how to run a good production deployment of Deis on AWS, use Bastion Hosts, and isolate deis itself from the internet and many other little goodies.

There are 2 directories (cluster & vpc) involved in the setup process that include independent scripts:

* `cluster/` - Sets up Deis and all of its bells and whistles in a private network setup
* `vpc/` - Sets up a Bastion and NAT hosts so *operators* can interface with the Deis installation from the outside world

Note: If you do not want to use your default `aws` cli profile for this setup then set `AWS_CLI_PROFILE` to the appropriate profile

#### Part I: Setting up the Bastion Cluster

Using a Bastion cluster, you can proxy requests from the internet to your Deis cluster and create a VPC that has the appropriate network subnets to accomplish that.

This cluster consists of a Bastion host running Ubuntu 14.04 and a NAT host running Amazon Linux NAT setup.

The following steps should be done inside the `vpc` directory:

Copy `vpc.parameters.json.example` to `vpc.parameters.json` and change any parameters needed. `KeyPair` is essential as it tells CloudFormation what AWS SSH Key to use but can also be used to change the instance sizes

If you need to generate a new ssh key then simply run

```
ssh-keygen -q -t rsa -f ~/.ssh/deis-bastion -N '' -C deis-bastion
    aws ec2 import-key-pair --key-name deis-bastion --public-key-material file://~/.ssh/deis-bastion.pub
```


* `DEIS_BASTION_SSH_KEY` By default `~/.ssh/<keypair>` is matched and uses the keypair name put into the parameters file

Or follow http://docs.deis.io/en/latest/installing_deis/aws/ for more information

Now run `./provision-vpc.sh` to provision and sit on your hands for a little bit.

Additional arguements are: <stack-name> and <template> (see bottom of the document for information on how to generate templates)

Follow the CLI instructions for any additional actions that need to be done.

*NOTE:* Currently this does not provision into an existing VPC

#### Part II: Provisioning Deis Cluster

With an existing VPC setup (using the steps above or done yourself) in place now it is time to setup Deis.

The following steps should be done in the `cluster` directory:

Copy `cluster.parameters.json.example` to `cluster.parameters.json` and change any parameters needed. `KeyPair` is essential as it tells CloudFormation what AWS SSH Key to use but can also be used to change the instance sizes. Right now same instance size is applied to all servers.

If you need to generate a new ssh key then simply run

```
ssh-keygen -q -t rsa -f ~/.ssh/deis -N '' -C deis
aws ec2 import-key-pair --key-name deis --public-key-material file://~/.ssh/deis.pub
```

Or follow http://docs.deis.io/en/latest/installing_deis/aws/ for more information

The Deis cluster can be launched into an existing VPC, be it the one created with the bastion setup above or one of your own making then some information bits need to be provided.

`BASTION_ID` is needed if you have chosen to go down the bastion host route- This is needed to configure various pieces of the Deis platform if behind the bestion host.
Setting this will auto discover the `VPC_ID` for you.

If you are provisioning into an existing VPC setup without a Bastion Host then the following applies:
Possible ENV vars that can be set, with `VPC_ID` being the only required one. The rest are auto discovered unless particular one should be set differently by hand

```
export VPC_ID=vpc-02ca8d67
export VPC_ZONES="us-west-2a us-west-2b us-west-2c"
export VPC_SUBNETS="subnet-9f5b0ffa subnet-d41c76a3 subnet-1e54d847
export VPC_PRIVATE_SUBNETS="subnet-9c5b0ff9 subnet-d51c76a2 subnet-1154d848"
```

With the above ENV vars in place you should have enough of a based information set to start spinning up Deis.

##### Configuring the shape and size of your cluster

There is a lot of flexibility in how planes can be isolated and how certian parts can be colocated. By default nothing is isolated.

Isolation is explained at

* http://docs.deis.io/en/latest/managing_deis/isolating-planes/#isolating-planes
* http://docs.deis.io/en/latest/managing_deis/isolating-etcd/

There are two ways to configure a cluster, configuring ENV vars on the system or generating a template a head of time and feeding that into the provision script.

* `python generate-template.py --help` will give you all the available options (beaware, there are a lot of options)
* See the bottom for all availble ENV options

Here is how to isolate the data plane into its own autoscaling group but also colocate the router with 6 minimum instances, using ENV vars

```
export DEIS_ISOLATE_DATA_PLANE=true
export DEIS_DATA_PLANE_COLOCATE=router
export DEIS_NUM_DATA_PLANE_INSTANCES=6
```

Now you can run

`./provision-cluster.sh isolation`

And voila. Magic.

##### Available ENV vars to configure Deis

* `DEIS_SSH_KEY` By default `~/.ssh/<keypair>` is matched and uses the keypair name put into the parameters file

###### Control Plane
* `DEIS_ISOLATE_CONTROL_PLANE` (Creates an AutoScale Group for the Control Plane)
* `DEIS_NUM_CONTROL_PLANE_INSTANCES` (Minimum servers in the AutoScale group)
* `DEIS_NUM_CONTROL_PLANE_INSTANCES_MAX` (Max servers in the AutoScale group)
* `DEIS_CONTROL_PLANE_INSTANCE_SIZE` (AWS instance size, otherwise default)
* `DEIS_COLOCATE_CONTROL_PLANE` (Colocates other planes on the same ASG.
	* Available options are router and data. Has to be passed in with a space separated. Example: `export DEIS_ISOLATE_CONTROL_PLANE=router data`

###### Data Plane
* `DEIS_ISOLATE_DATA_PLANE`
* `DEIS_NUM_DATA_PLANE_INSTANCES` (Minimum servers in the AutoScale group)
* `DEIS_NUM_DATA_PLANE_INSTANCES_MAX` (Max servers in the AutoScale group)
* `DEIS_DATA_PLANE_INSTANCE_SIZE` (AWS instance size, otherwise default)
* `DEIS_COLOCATE_DATA_PLANE` (Colocates other planes on the same ASG.
	* Available options are control and router. Has to be passed in with a space separated. Example: `export DEIS_ISOLATE_DATA_PLANE=control router`

###### Router Mesh
* `DEIS_ISOLATE_ROUTER_MESH`
* `DEIS_NUM_ROUTER_MESH_INSTANCES` (Minimum servers in the AutoScale group)
* `DEIS_NUM_ROUTER_MESH_INSTANCES_MAX` (Max servers in the AutoScale group)
* `DEIS_ROUTER_MESH_INSTANCE_SIZE` (AWS instance size, otherwise default)
* `DEIS_COLOCATE_ROUTER_MESH` (Colocates other planes on the same ASG.
	* Available options are control and data. Has to be passed in with a space separated. Example: `export DEIS_ISOLATE_CONTROL_PLANE=control data`

###### etcd

etcd is on the Control Plane if it is not configured to be isolated

* `DEIS_ISOLATE_ETCD` (Creats an AutoScale Group for etcd)
* `DEIS_NUM_ETCD_INSTANCES` (Minimum servers in the AutoScale group)
* `DEIS_NUM_ETCD_INSTANCES_MAX` (Max servers in the AutoScale group)
* `DEIS_ETCD_INSTANCE_SIZE` (AWS instance size, otherwise default)

###### Other Plane

Items that are not isolated **or** colocated on other servers goes to the **Other** plane

* `DEIS_NUM_INSTANCES` (Minimum servers in the AutoScale group)
* `DEIS_NUM_INSTANCES_MAX` (Max servers in the AutoScale group)
* `DEIS_INSTANCE_SIZE` (AWS instance size, otherwise default)

#### Updating Deis Cluster

Using the update script functions much as the provisioning script. Either pass in a new template or set all the appropriate ENV variables, to change the amount of servers, instance sizes or any other pieces and then run

`./update-cluster.sh cluster-name template.json` (omit any argument that you do not need)

This will kick off a CloudFormation update and AWS will start converging your cluster to match up.

*Note:* Scaling down will bring down servers and can cause instability, be careful with that.

#### Generating a CF Template for the Deis Cluster

Cluster Provisoning and Update scripts will generate templates for you on the fly but if you
would like to make one without any of the resource interaction with AWS then there are a few
different ways to achieve that:

* run `python generate-template.py` with all the appropriate flags. No ENV variables involved
* run `./generate-template.sh` - This will source in all the same ENV vars as the provioning and update scripts

Pipe it to a file as desired (append `> filename.json`) to keep the JSON handy to store in `git` or somewhere else.

If you have generated a template before but somehow lost it or have elected to keep the
primary copy with AWS then it is possible to get it back locally by running:

`aws cloudformation get-template --stack-name <stack_name> > my_fancy_production.json`
