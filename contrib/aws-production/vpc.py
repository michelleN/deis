import json
import subprocess
from collections import OrderedDict


class VPC(object):
    # So that the user can change profile without setting ENV vars
    id = None
    bastion_id = None
    aws_profile = None
    gateway = None
    bastion = []
    zones = []
    subnets = []
    private_subnets = []

    def __init__(self, vpc_id, bastion_id, aws_profile):
        self.id = vpc_id
        self.bastion_id = bastion_id
        self.aws_profile = aws_profile

    def discover(self):
        # This calls all the other commands
        if self.bastion_id:
            self.get_bastion_info(self.bastion_id)

        if not self.id:
            raise Exception('No VPC can be found')

        self.verify_vpc_exists()
        self.discover_subnets()

    def verify_vpc_exists(self):
        cmd = 'aws ec2 describe-vpcs --filter "Name=vpc-id,Values=%s" --output text' % self.id
        exists = self.run(cmd)
        if exists == '':
            raise Exception("VPC ID %s does not exist in this AWS setup" % self.id)

    def get_bastion_info(self, bastion_id):
        cmd = 'aws ec2 describe-instances --instance-ids %s --query \'Reservations[0].Instances[0].{"host": PublicIpAddress, "vpc_id": NetworkInterfaces[0].VpcId, "sg": SecurityGroups[0].GroupId}\'' % bastion_id
        bastion = self.run(cmd)
        bastion = json.loads(bastion)
        self.bastion = bastion
        self.id = bastion['vpc_id']

        return bastion

    # Get the internet gateway for the VPC
    def discover_gateway(self):
        if self.gateway:
            return self.gateway

        cmd = 'aws ec2 describe-internet-gateways --filters "Name=attachment.vpc-id,Values=%s" --query "InternetGateways[].InternetGatewayId" --output text' % self.id
        gateway = self.run(cmd)
        self.gateway = gateway.strip()
        return self.gateway

    # Gets all subnets and their AZs
    def discover_subnets(self):
        public_subnets = self.discover_public_subnets()
        cmd = 'aws ec2 describe-subnets --filters "Name=vpc-id,Values=%s" --query "sort_by(Subnets, &AvailabilityZone)[*].[AvailabilityZone, SubnetId]"' % self.id
        subnets = self.run(cmd)
        subnets = json.loads(subnets)
        data = {}
        for sub in subnets:
            zone, subnet = sub
            if zone not in data.keys():
                data[zone] = {}

            # False means private, True means public
            public = True if subnet in public_subnets else False
            data[zone][subnet] = public

        # dictionary sorted by key
        data = OrderedDict(sorted(data.items(), key=lambda t: t[0]))

        # Populate data structures
        for zone, subnets in data.iteritems():
            self.zones.append(zone)
            for subnet, public in subnets.iteritems():
                if public:
                    self.subnets.append(subnet)
                else:
                    self.private_subnets.append(subnet)

        return data

    # Gets all public subnets
    def discover_public_subnets(self):
        self.discover_gateway()
        cmd = 'aws ec2 describe-route-tables --filters "Name=vpc-id,Values=%s,Name=route.gateway-id,Values=%s" --query "RouteTables[].Associations[].SubnetId"' % (self.id, self.gateway)
        subnets = self.run(cmd)
        subnets = json.loads(subnets)
        return subnets

    def run(self, cmd):
        if self.aws_profile:
            cmd += " --profile %s" % self.aws_profile
        data, err = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE).communicate()
        if err:
            raise Exception("Command failed: " + err)
        return data

    # TODO: Gather the IP range people like, such as 10.0.x.y to add missing subnets into

if __name__ == '__main__':
    # This is for shell
    import argparse
    import os
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--vpc-id', help='VPC ID', metavar="<id>")
    group.add_argument('--bastion-id', help='Bastion Instance ID', metavar="<id>")
    parser.add_argument('--aws-profile', help='Sets which AWS Profile configured in the AWS CLI to use', metavar="<profile>", default=os.getenv("AWS_CLI_PROFILE"))
    parser.add_argument('--format', help='Display output in various different formats', choices=['shell', 'human', 'json'], default='shell')
    args = vars(parser.parse_args())
    vpc = VPC(args['vpc_id'], args['bastion_id'], args['aws_profile'])
    vpc.discover()

    if args['format'] == 'shell':
        output = 'DEIS_VPC_ID="%s"; ' % vpc.id
        output += 'DEIS_VPC_ZONES="%s"; ' % ' '.join(vpc.zones)
        output += 'DEIS_VPC_SUBNETS="%s"; ' % ' '.join(vpc.subnets)
        output += 'DEIS_VPC_PRIVATE_SUBNETS="%s"' % ' '.join(vpc.private_subnets)
        print output
    elif args['format'] == 'json':
        print json.dumps({'id': vpc.id, 'zones': vpc.zones, 'subnets': vpc.subnets, 'private_subnets': vpc.private_subnets})
    elif args['format'] == 'human':
        print 'VPC ID: %s' % vpc.id
        print 'VPC Availability Zones: %s' % ' '.join(vpc.zones)
        print 'VPC Public Subnets %s' % ' '.join(vpc.subnets)
        print 'VPC Private Subnets: %s' % ' '.join(vpc.private_subnets)

