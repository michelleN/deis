#!/usr/bin/env bash
#
# Usage: ./provision-vpc.sh [name]
# The [name] is the CloudFormation stack name, and defaults to 'deis-vpc'
# the [cf-template] the path to a pre-generated CF template, defaults to making one

set -e

THIS_DIR=$(cd $(dirname $0); pwd) # absolute path
PARENT_DIR=$(dirname $THIS_DIR)
CONTRIB_DIR=$(dirname $PARENT_DIR)

source $CONTRIB_DIR/utils.sh
source $PARENT_DIR/helpers.sh

# check for AWS API tools in $PATH
check_aws

# Figure out if there is a cluster param file
PARAMETERS_FILE=$THIS_DIR/vpc.parameters.json
if [ ! -f $PARAMETERS_FILE ]; then
    echo_red "Can not locate $(basename $PARAMETERS_FILE)"
    exit 1
fi

# Check if SSH is available using a nasty little python hack
check_sshkey $PARAMETERS_FILE

if [ -z "$1" ]; then
    STACK_NAME=deis-vpc
  else
    STACK_NAME=$1
fi

if [ -z "$2" ]; then
    TMPFILE=$(mktemp /tmp/deis.$STACK_NAME.XXXXXXXXXX)
    # TODO: Cleanup tmpfile on success
    $THIS_DIR/generate-template.py > $TMPFILE
    TEMPLATE=$TMPFILE
    echo_green "generated template can be found at ${TEMPLATE}"
else
    TEMPLATE=$2
fi

# Create an AWS cloudformation stack based on the a generated template
echo_green "Starting CloudFormation Stack creation"
template_source $TEMPLATE
aws cloudformation create-stack \
  $TEMPLATE_SOURCING \
  --stack-name $STACK_NAME \
  --parameters "$(<$PARAMETERS_FILE)" \
  --stack-policy-body "$(<$THIS_DIR/stack_policy.json)" \
  $EXTRA_AWS_CLI_ARGS


# Loop until stack creation is complete
ATTEMPTS=60
SLEEPTIME=10
COUNTER=1
INSTANCE_IDS=""
until [ "$STACK_STATUS" = "CREATE_COMPLETE" ]; do
  if [ $COUNTER -gt $ATTEMPTS ]; then
    echo "Provisioning failed"
    echo "Destroying stack $STACK_NAME"
    bailout $STACK_NAME
    exit 1
  fi

  STACK_STATUS=$(get_stack_status $STACK_NAME)
  if [ $STACK_STATUS != "CREATE_IN_PROGRESS" -a $STACK_STATUS != "CREATE_COMPLETE" ] ; then
    echo "error creating stack: "
    aws --output text cloudformation describe-stack-events \
        --stack-name $STACK_NAME \
        --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`].[LogicalResourceId,ResourceStatusReason]' \
        $EXTRA_AWS_CLI_ARGS
    bailout $STACK_NAME
    exit 1
  fi

  echo "Waiting for provisioning to complete ($STACK_STATUS, $(expr 61 - $COUNTER)0s) ..."
  sleep $SLEEPTIME

  let COUNTER=COUNTER+1
done

echo_green "\nYour Deis VPC was deployed to AWS CloudFormation as stack "$STACK_NAME".\n"

aws --output text cloudformation describe-stacks --stack-name $STACK_NAME $EXTRA_AWS_CLI_ARGS

echo_green "\nGrab the Bastion Instance ID and export it to BASTION_ID for the next step"
