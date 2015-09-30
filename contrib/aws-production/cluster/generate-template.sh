# A simple wrapper around the gen-cluster-json.py script to source in ENV vars
THIS_DIR=$(cd $(dirname $0); pwd) # absolute path
PARENT_DIR=$(dirname $THIS_DIR)
CONTRIB_DIR=$(dirname $PARENT_DIR)
source $CONTRIB_DIR/utils.sh
source $PARENT_DIR/helpers.sh
source $THIS_DIR/defaults.sh

# Check for AWS API tools in $PATH
check_aws

if [ "$1" == 'updating' ]; then
  GEN_ARGS+=' --updating'
fi

$THIS_DIR/generate-template.py $GEN_ARGS --channel $COREOS_CHANNEL --version $COREOS_VERSION
