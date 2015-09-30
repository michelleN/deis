#!/usr/bin/env bash
#
# Usage: ./update-cluster.sh [name] [cf-template]
# The [name] is the CloudFormation stack name, and defaults to 'deis-cluster'
# the [cf-template] the path to a pre-generated CF template, defaults to making one

set -e

THIS_DIR=$(cd $(dirname $0); pwd) # absolute path
PARENT_DIR=$(dirname $THIS_DIR)
CONTRIB_DIR=$(dirname $PARENT_DIR)
USER_DATA_DIR=$THIS_DIR/user-data

source $CONTRIB_DIR/utils.sh
source $THIS_DIR/defaults.sh
source $PARENT_DIR/helpers.sh
source $THIS_DIR/helpers.sh

# check for AWS API tools in $PATH
check_aws

# Figure out if there is a cluster param file
PARAMETERS_FILE=$THIS_DIR/cluster.parameters.json
if [ ! -f $PARAMETERS_FILE ]; then
    echo_red "Can not locate $(basename $PARAMETERS_FILE)"
    exit 1
fi

# Check if SSH is available specificed in cluster.parameters.json
check_sshkey $PARAMETERS_FILE

# Deal with inputs from the user
if [ -z "$1" ]; then
    STACK_NAME=deis-cluster
else
    STACK_NAME=$1
fi

if [ -z "$2" ]; then
    TMPFILE=$(mktemp /tmp/deis.$STACK_NAME.XXXXXXXXXX)
    $($THIS_DIR/generate-template.sh "updating") > $TMPFILE
    # TODO: Cleanup tmpfile on success
    TEMPLATE=$TMPFILE
    echo_green "generated template can be found at ${TEMPLATE}"
else
    TEMPLATE=$2
fi

# Check that the CoreOS user-data file is valid
check_plane_user_data

# update the AWS CloudFormation stack
echo_green "Starting CloudFormation Stack updating"
template_source $TEMPLATE
aws cloudformation update-stack \
  $TEMPLATE_SOURCING \
  --stack-name $STACK_NAME \
  --parameters "$(<$PARAMETERS_FILE)" \
  --stack-policy-body "$(<$THIS_DIR/stack_policy.json)" \
  $EXTRA_AWS_CLI_ARGS

# Loop until stack update is complete
ATTEMPTS=60
SLEEPTIME=10
COUNTER=1
until [ "$STACK_STATUS" = "UPDATE_COMPLETE" -o "$STACK_STATUS" = "UPDATE_COMPLETE_CLEANUP_IN_PROGRESS" ]; do
  if [ $COUNTER -gt $ATTEMPTS ]; then
    echo "Updating failed"
    exit 1
  fi

  STACK_STATUS=$(get_stack_status $STACK_NAME)
  if [ $STACK_STATUS != "UPDATE_IN_PROGRESS" -a $STACK_STATUS != "UPDATE_COMPLETE" -a $STACK_STATUS != "UPDATE_COMPLETE_CLEANUP_IN_PROGRESS" ] ; then
    echo "error updating stack: "
    aws --output text cloudformation describe-stack-events \
        --stack-name $STACK_NAME \
        --query 'StackEvents[?ResourceStatus==`UPDATE_FAILED`].[LogicalResourceId,ResourceStatusReason]' \
        $EXTRA_AWS_CLI_ARGS
    exit 1
  fi

  echo "Waiting for update to complete ($STACK_STATUS, $(expr 61 - $COUNTER)0s) ..."
  sleep $SLEEPTIME

  let COUNTER=COUNTER+1
done

echo_green "\nYour Deis cluster on AWS CloudFormation has been successfully updated.\n"
