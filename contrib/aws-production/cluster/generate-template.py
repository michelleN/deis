#!/usr/bin/env python
import argparse
import json
import os
import urllib2
import yaml
import subprocess
import sys
import shutil

# hack since this is not a package
if __name__ == '__main__':
    if __package__ is None:
        from os import path
        sys.path.append( path.dirname( path.dirname( path.abspath(__file__) ) ) )
        from vpc import VPC
    else:
        from ..vpc import VPC

CURR_DIR = os.path.dirname(os.path.realpath(__file__))


def get_instance_sizes():
    # Seed in the base template
    template = json.load(open(os.path.join(CURR_DIR, 'cluster.template.json'), 'r'))
    return template['Parameters']['InstanceType']['AllowedValues']


class UniqueAppendAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        unique_values = [set(values)]
        setattr(namespace, self.dest, unique_values)

parser = argparse.ArgumentParser()
parser.add_argument('--channel', help='the CoreOS channel to use', default='stable')
parser.add_argument('--version', help='the CoreOS version to use', default='current')
parser.add_argument('--updating', help='Indicates template is in update mode and does not make a new discovery url', action='store_true')

parser.add_argument('--aws-profile', help='Sets which AWS Profile configured in the AWS CLI to use',
                    metavar="<profile>", default=os.getenv("AWS_CLI_PROFILE"))

group = parser.add_mutually_exclusive_group(required=True)
group.add_argument('--bastion-id', help='If a bastion host is being used then its EC2 instance ID is needed', metavar="<id>")
group.add_argument('--vpc-id', help='VPC ID', metavar="<id>")

group = parser.add_argument_group('VPC', 'VPC configuration for all the planes. Zones and subnets are auto discovered unless specified here')
group.add_argument('--vpc-zones', nargs='+', help='VPC Zones', metavar="<zones>")
group.add_argument('--vpc-subnets', nargs='+', help='VPC Subnets', metavar="<subnets>")
group.add_argument('--vpc-private-subnets', nargs='+', help='VPC Private Subnets', metavar="<subnets>")

group = parser.add_argument_group('control-plane', 'Setup configuration around the Control Plane')
group.add_argument('--isolate-control-plane',
                   help='Set if Control Plane should be isolated',
                   required=False, action='store_true')
group.add_argument('--control-plane-colocate',
                   help='Other planes that should be colocated with the Control Plane',
                   nargs='+', action=UniqueAppendAction, choices=['router', 'data'],
                   default=[])
group.add_argument('--control-plane-instances',
                   help='How many control plane instances to start',
                   type=int, metavar='<count>', default=3)
group.add_argument('--control-plane-instances-max',
                   help='How many control plane instances to scale to max',
                   type=int, metavar='<count>', default=9)
group.add_argument('--control-plane-instance-size',
                   help='AWS instance size, otherwise uses default in template',
                   metavar='<instance type>',
                   choices=get_instance_sizes())

group = parser.add_argument_group('data-plane', 'Setup configuration around the Data Plane')
group.add_argument('--isolate-data-plane',
                   help='Set if Data Plane should be isolated',
                   required=False, action='store_true')
group.add_argument('--data-plane-colocate',
                   help='Other planes that should be colocated with the Data Plane',
                   nargs='+', action=UniqueAppendAction, choices=['router', 'control'],
                   default=[])
group.add_argument('--data-plane-instances',
                   help='How many data plane instances to start',
                   type=int, metavar='<count>', default=3)
group.add_argument('--data-plane-instances-max',
                   help='How many data plane instances to scale to max',
                   type=int, metavar='<count>', default=25)
group.add_argument('--data-plane-instance-size',
                   help='AWS instance size, otherwise uses default in template',
                   metavar='<instance type>',
                   choices=get_instance_sizes())

group = parser.add_argument_group('router-mesh', 'Setup configuration around the Router Mesh')
group.add_argument('--isolate-router',
                   help='Set if Router Mesh should be isolated',
                   required=False, action='store_true')
group.add_argument('--router-mesh-colocate',
                   dest="router_plane_colocate",
                   help='Other planes that should be colocated with the Router Mesh',
                   nargs='+', action=UniqueAppendAction, choices=['data', 'control'],
                   default=[])
group.add_argument('--router-mesh-instances',
                   dest="router_plane_instances",
                   help='How many router mesh instances to start',
                   type=int, metavar='<count>', default=3)
group.add_argument('--router-mesh-instances-max',
                   dest="router_plane_instances_max",
                   help='How many router mesh instances to scale to max',
                   type=int, metavar='<count>', default=9)
group.add_argument('--router-mesh-instance-size',
                   dest="router_plane_instance_size",
                   help='AWS instance size, otherwise uses default in template',
                   metavar='<instance type>',
                   choices=get_instance_sizes())

group = parser.add_argument_group('etcd', 'Setup configuration around the etcd cluster')
group.add_argument('--isolate-etcd',
                   help='Set if etcd should be isolated',
                   required=False, action='store_true')
group.add_argument('--etcd-instances',
                   dest="etcd_plane_instances",
                   help='How many etcd mesh instances to start',
                   type=int, metavar='<count>', default=3)
group.add_argument('--etcd-instances-max',
                   dest="etcd_plane_instances_max",
                   help='How many etcd mesh instances to scale to max',
                   type=int, metavar='<count>', default=9)
group.add_argument('--etcd-instance-size',
                   dest="etcd_plane_instance_size",
                   help='AWS instance size, otherwise uses default in template',
                   metavar='<instance type>',
                   choices=get_instance_sizes())

group = parser.add_argument_group('other', 'Setup configuration around the planes that are not isolated out specifically')
group.add_argument('--other-plane-instances',
                   help='How many instances to start',
                   type=int, metavar='<count>', default=3)
group.add_argument('--other-plane-instances-max',
                   help='How many instances to scale to max',
                   type=int, metavar='<count>', default=9)
group.add_argument('--other-plane-instance-size',
                   help='AWS instance size, otherwise uses default in template',
                   metavar='<instance type>',
                   choices=get_instance_sizes())

args = vars(parser.parse_args())

# Add AWS-specific units to the shared user-data
FORMAT_DOCKER_VOLUME = '''
  [Unit]
  Description=Formats the added EBS volume for Docker
  ConditionPathExists=!/etc/docker-volume-formatted
  [Service]
  Type=oneshot
  RemainAfterExit=yes
  ExecStart=/usr/sbin/wipefs -f /dev/xvdf
  ExecStart=/usr/sbin/mkfs.ext4 -i 4096 -b 4096 /dev/xvdf
  ExecStart=/bin/touch /etc/docker-volume-formatted
'''
MOUNT_DOCKER_VOLUME = '''
  [Unit]
  Description=Mount Docker volume to /var/lib/docker
  Requires=format-docker-volume.service
  After=format-docker-volume.service
  Before=docker.service
  [Mount]
  What=/dev/xvdf
  Where=/var/lib/docker
  Type=ext4
'''
DOCKER_DROPIN = '''
  [Unit]
  Requires=var-lib-docker.mount
  After=var-lib-docker.mount
'''
FORMAT_ETCD_VOLUME = '''
  [Unit]
  Description=Formats the etcd device
  ConditionPathExists=!/etc/etcd-volume-formatted
  [Service]
  Type=oneshot
  RemainAfterExit=yes
  ExecStart=/usr/sbin/wipefs -f /dev/xvdg
  ExecStart=/usr/sbin/mkfs.ext4 -i 4096 -b 4096 /dev/xvdg
  ExecStart=/bin/touch /etc/etcd-volume-formatted
'''
MOUNT_ETCD_VOLUME = '''
  [Unit]
  Description=Mounts the etcd volume
  Requires=format-etcd-volume.service
  After=format-etcd-volume.service
  [Mount]
  What=/dev/xvdg
  Where=/media/etcd
  Type=ext4
'''
PREPARE_ETCD_DATA_DIRECTORY = '''
  [Unit]
  Description=Prepares the etcd data directory
  Requires=media-etcd.mount
  After=media-etcd.mount
  Before=etcd2.service
  [Service]
  Type=oneshot
  RemainAfterExit=yes
  ExecStart=/usr/bin/chown -R etcd:etcd /media/etcd
'''
ETCD_DROPIN = '''
  [Unit]
  Requires=prepare-etcd-data-directory.service
  After=prepare-etcd-data-directory.service
'''


# Diffs a list
def diff(a, b):
    b = set(b)
    return [aa for aa in a if aa not in b]


def discovery_url():
    # Ensure the cluster has the latest user-data
    os.chdir(os.path.realpath(os.path.join(CURR_DIR, '..', '..', '..')))  # Just to get to the deis root
    cmd = "make discovery-url"
    _, err = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE).communicate()
    if err:
        print err
        raise
    os.chdir(CURR_DIR)


def coreos_amis(channel, version):
    url = "http://{channel}.release.core-os.net/amd64-usr/{version}/coreos_production_ami_all.json".format(channel=channel, version=version)
    try:
        amis = json.load(urllib2.urlopen(url))
    except (IOError, ValueError):
        print "The URL {} is invalid.".format(url)
        raise

    return dict(map(lambda n: (n['name'], dict(PV=n['pv'], HVM=n['hvm'])), amis['amis']))


def prepare_user_data(filename, planes=['control', 'data', 'router'], worker=False):
    # Define units that are going to be added to the default coreos user-data
    new_units = [
        dict({'name': 'format-docker-volume.service', 'command': 'start', 'content': FORMAT_DOCKER_VOLUME}),
        dict({'name': 'var-lib-docker.mount', 'command': 'start', 'content': MOUNT_DOCKER_VOLUME}),
        dict({'name': 'docker.service', 'drop-ins': [{'name': '90-after-docker-volume.conf', 'content': DOCKER_DROPIN}]}),
        dict({'name': 'format-etcd-volume.service', 'command': 'start', 'content': FORMAT_ETCD_VOLUME}),
        dict({'name': 'media-etcd.mount', 'command': 'start', 'content': MOUNT_ETCD_VOLUME}),
        dict({'name': 'prepare-etcd-data-directory.service', 'command': 'start', 'content': PREPARE_ETCD_DATA_DIRECTORY}),
        dict({'name': 'etcd2.service', 'drop-ins': [{'name': '90-after-etcd-volume.conf', 'content': ETCD_DROPIN}]})
    ]

    # coreos-cloudinit will start the units in order, so we want these to be processed before etcd/fleet
    # are started
    with open(filename, 'r') as handle:
        data = yaml.safe_load(handle)
        data['coreos']['units'] = new_units + data['coreos']['units']

    # sort out the planes that should be on this setup
    p = []
    for plane in planes:
        # if statements due to non-consistent naming
        if plane == 'control':
            p.append('controlPlane=true')
        elif plane == 'data':
            p.append('dataPlane=true')
        elif plane == 'router':
            p.append('routerMesh=true')

    if not p:
        # no planes, etcd isolation going on
        del data['coreos']['fleet']['metadata']
    else:
        data['coreos']['fleet']['metadata'] = ','.join(p)

    # if etcd should be in proxy mode
    if worker:
        data['coreos']['etcd2']['proxy'] = 'on'

    dump = yaml.dump(data, default_flow_style=False)
    # Configure etcd to use its EBS volume
    dump = dump.replace('ETCD_HOST_DATA_DIR=/var/lib/etcd2', 'ETCD_HOST_DATA_DIR=/media/etcd')
    return dump


def add_user_data(template, namespace, planes=[], worker=False):
    # Copy coreos user-data over
    coreos_userdata = os.path.realpath(os.path.join(CURR_DIR, '..', '..', 'coreos', 'user-data'))
    final_userdata = os.path.join(CURR_DIR, 'user-data', namespace.lower() + '-plane-user-data')
    shutil.copy2(coreos_userdata, final_userdata)

    # Prepare the user_data and decorate with new thing as needed
    data = prepare_user_data(final_userdata, planes, worker)

    header = ["#cloud-config", "---"]
    user_data = ["\n", header + data.split("\n")]
    template[namespace + 'PlaneLaunchConfig']['Properties']['UserData']['Fn::Base64']['Fn::Join'] = user_data
    return template


def add_plane(tp, template, worker=False, planes=[]):
    global elb_allocated  # This is nasty
    tp = tp.capitalize()

    plane = open(os.path.join(CURR_DIR, 'plane.template.json'), 'r').read()
    plane = plane.replace('Plane', tp + 'Plane').replace('deis-plane-node', 'deis-%s-plane-node' % tp.lower())
    plane = json.loads(plane)

    template['Resources'].update(add_user_data(plane, tp, planes, worker))
    min_instances = args[tp.lower() + '_plane_instances']
    max_instances = args[tp.lower() + '_plane_instances_max']
    template['Parameters'][tp + 'PlaneSize'] = {
        'Default': min_instances,
        'MinValue': min_instances,
        'Description': "Number of nodes in the cluster (%s-%s)" % (min_instances, max_instances),
        'Type': 'Number',
    }

    # Can't do this via Parameters
    template['Resources'][tp + 'PlaneAutoScale']['Properties']['MaxSize'] = max_instances

    # Update subnets and zones
    template['Resources'][tp + 'PlaneAutoScale']['Properties']['AvailabilityZones'] = vpc.zones
    template['Resources'][tp + 'PlaneAutoScale']['Properties']['VPCZoneIdentifier'] = vpc.private_subnets

    # Instance size
    if args[tp.lower() + '_plane_instance_size']:
        template['Resources'][tp + 'PlaneLaunchConfig']['Properties']['InstanceType'] = args[tp.lower() + '_plane_instance_size']

    if not elb_allocated and 'router' in planes:
        # Whatever plane serves the traffic needs this
        elb_allocated = True
        template['Resources'][tp + 'PlaneAutoScale']['Properties']['LoadBalancerNames'] = [
            {'Ref': "DeisWebELB"}
        ]

    return template


vpc = VPC(args['vpc_id'], args['bastion_id'], args['aws_profile'])
vpc.discover()
# Overwrite in case the user had specific opinions vs what's discovered
if args['vpc_zones']:
    vpc.zones = args['vpc_zones']
if args['vpc_private_subnets']:
    vpc.private_subnets = args['vpc_private_subnets']
if args['vpc_subnets']:
    vpc.subnets = args['vpc_subnets']

if not args['updating']:
    # Create a new discovery URL
    discovery_url()

# Figure out what goes where
elb_allocated = False  # downside is this will go to the first router seen
available_planes = ['control', 'router', 'data']
isolated_planes = {}

if args['isolate_router']:
    # Cleanup thanks to getenv
    if '' in args['router_plane_colocate']:
        args['router_plane_colocate'].remove('')
    args['router_plane_colocate'].append('router')
    isolated_planes.update({
        'router': {
            'worker': True,
            'planes': args['router_plane_colocate']
        }
    })
    available_planes = diff(available_planes, args['router_plane_colocate'])

if args['isolate_data_plane']:
    # Cleanup thanks to getenv
    if '' in args['data_plane_colocate']:
        args['data_plane_colocate'].remove('')
    args['data_plane_colocate'].append('data')
    isolated_planes.update({
        'data': {
            'worker': True,
            'planes': args['data_plane_colocate']
        }
    })
    available_planes = diff(available_planes, args['data_plane_colocate'])

if args['isolate_control_plane']:
    # Cleanup thanks to getenv
    if '' in args['control_plane_colocate']:
        args['control_plane_colocate'].remove('')
    args['control_plane_colocate'].append('control')
    # Make control plane the etcd "owner" if etcd isn't being isolated
    isolated_planes.update({
        'control': {
            'worker': not args['isolate_etcd'],
            'planes': args['control_plane_colocate']
        }
    })
    available_planes = diff(available_planes, args['control_plane_colocate'])

if args['isolate_etcd']:
    isolated_planes.update({'etcd': {'worker': False, 'planes': []}})

# Deal with rest of the planes that weren't isolated
if available_planes:
    worker = True
    if not args['isolate_etcd'] and 'control' in available_planes:
        worker = False

    isolated_planes.update({
        'other': {
            'worker': worker,
            'planes': available_planes
        }
    })

# Deal with the fact plane isolation + colocation = proxy on still due to lack of further smarts
if len(isolated_planes) == 1:
    key = isolated_planes.keys()[0]
    if 'control' in isolated_planes[key]['planes']:
        isolated_planes[key]['worker'] = False

# Seed in the base template
template = json.load(open(os.path.join(CURR_DIR, 'cluster.template.json'), 'r'))

# Setup each plane
for plane, info in isolated_planes.items():
    template = add_plane(plane, template, info['worker'], info['planes'])

# Add in the AMIs
template['Mappings']['CoreOSAMIs'] = coreos_amis(args['channel'], args['version'])

# Update VpcId fields
template['Resources']['DeisWebELBSecurityGroup']['Properties']['VpcId'] = vpc.id
template['Resources']['CoreOSSecurityGroup']['Properties']['VpcId'] = vpc.id

# Update subnets and zones
template['Resources']['DeisWebELB']['Properties']['Subnets'] = vpc.subnets

# Update ingress to the cluster based on whether a bastion server is being used
if args['bastion_id']:
    del template['Parameters']['SSHFrom']
    template['Parameters']['BastionSecurityGroupID']['Default'] = vpc.bastion['sg']
    del template['Resources']['CoreOSSecurityGroup']['Properties']['SecurityGroupIngress'][0]
else:
    del template['Parameters']['BastionSecurityGroupID']
    del template['Resources']['CoreOSSecurityGroup']['Properties']['SecurityGroupIngress'][1]

print json.dumps(template, separators=(',', ': '))
