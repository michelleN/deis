#!/usr/bin/env python
import json
import os
import subprocess
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--include-private-subnets', dest='include_private_subnets', required=False, default=os.getenv('INCLUDE_PRIVATE_SUBNETS', True), action='store_true')
args = vars(parser.parse_args())

CURR_DIR = os.path.dirname(os.path.realpath(__file__))

template = json.load(open(os.path.join(CURR_DIR, 'vpc.template.json'), 'r'))

if args['include_private_subnets']:
    # Get mappings from separate files
    regions = ['us-west-2', 'us-east-1', 'eu-west-1']
    nat = {}
    bastion = {}
    for region in regions:
        # NAT
        cmd = """aws ec2 describe-images \
                --profile %s \
                --region %s \
                --owners amazon \
                --filters 'Name=architecture,Values=x86_64' \
                          'Name=block-device-mapping.volume-type,Values=gp2' \
                          'Name=virtualization-type,Values=hvm' \
                          'Name=name,Values=amzn-ami-vpc-nat-hvm-*' \
                --query 'reverse(sort_by(Images, &CreationDate))[0].ImageId'""" % (os.getenv('AWS_DEFAULT_PROFILE', 'default'), region)

        image, err = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE).communicate()
        nat[region] = {"HVM": image.strip("\"\n")}

        # Bastion
        cmd = """aws ec2 describe-images \
                --profile %s \
                --region %s \
                --owners 099720109477 \
                --filters 'Name=architecture,Values=x86_64' \
                          'Name=block-device-mapping.volume-type,Values=gp2' \
                          'Name=virtualization-type,Values=hvm' \
                          'Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-trusty-14.04-amd64-server-*' \
                --query 'reverse(sort_by(Images, &CreationDate))[0].ImageId'""" % (os.getenv('AWS_DEFAULT_PROFILE', 'default'), region)

        image, err = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE).communicate()
        bastion[region] = {"HVM": image.strip("\"\n")}

    template['Mappings']['NatAMIs'] = nat
    template['Mappings']['BastionAMIs'] = bastion
else:
    # Skip anything related to the more robust network setup
    del template['Parameters']['KeyPair']
    del template['Parameters']['IamInstanceProfile']
    del template['Parameters']['SSHFrom']
    del template['Parameters']['NatInstanceType']
    del template['Parameters']['BastionInstanceType']
    del template['Parameters']['EC2VirtualizationType']
    del template['Parameters']['EC2EBSVolumeType']
    del template['Parameters']['AssociatePublicIP']
    del template['Parameters']['RootVolumeSize']
    del template['Mappings']['NatAMIs']
    del template['Mappings']['BastionAMIs']
    del template['Mappings']['SubnetConfig']['PrivateSubnet1']
    del template['Mappings']['SubnetConfig']['PrivateSubnet2']
    del template['Mappings']['SubnetConfig']['PrivateSubnet3']
    del template['Conditions']['UseIamInstanceProfile']
    del template['Resources']['PrivateSubnet1']
    del template['Resources']['PrivateSubnet2']
    del template['Resources']['PrivateSubnet3']
    del template['Resources']['PrivateRouteTable']
    del template['Resources']['PrivateRoute']
    del template['Resources']['PrivateSubnet1RouteTableAssociation']
    del template['Resources']['PrivateSubnet2RouteTableAssociation']
    del template['Resources']['PrivateSubnet3RouteTableAssociation']
    del template['Resources']['NatSecurityGroup']
    del template['Resources']['NatHost']
    del template['Resources']['NatIpAddress']
    del template['Resources']['BastionSecurityGroup']
    del template['Resources']['BastionHost']
    del template['Resources']['BastionIpAddress']
    del template['Outputs']['PrivateSubnet1Id']
    del template['Outputs']['PrivateSubnet2Id']
    del template['Outputs']['PrivateSubnet3Id']
    del template['Outputs']['BastionSecurityGroupId']
    del template['Outputs']['BastionElasticIp']

print json.dumps(template)
