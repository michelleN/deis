# Useful helpers that is shared across the various cluster scripts

# Change aws profiles is needed
# TODO change this perhaps so it is more deis specific?
if [ ! -z "$AWS_CLI_PROFILE" ]; then
    EXTRA_AWS_CLI_ARGS+="--profile $AWS_CLI_PROFILE"
fi

template_source() {
    TEMPLATE=$1
    TEMPLATE_SIZE=$(wc -c < $TEMPLATE)
    TEMPLATE_SOURCING="--template-body file://$TEMPLATE"
    if [[ "$TEMPLATE_SIZE" -gt "51200" ]]; then
        echo_yellow "Template file exceeds the 51,200 byte AWS CloudFormation limit. Uploading to S3"

        BUCKET=deis-cloudformation-templates
        if [[ $(aws s3 ls $EXTRA_AWS_CLI_ARGS | grep -v $BUCKET) ]]; then
            aws s3 mb s3://$BUCKET
            echo_green "Made s3 bucket $BUCKET to store the CF templates in"
        fi

        FILE=$(basename $TEMPLATE)
        aws s3 cp --acl private \
            --storage-class REDUCED_REDUNDANCY \
            --only-show-errors \
            $TEMPLATE s3://$BUCKET/$FILE \
            $EXTRA_AWS_CLI_ARGS

        TEMPLATE_SOURCING="--template-url https://$BUCKET.s3.amazonaws.com/$FILE"
        echo_green "S3 upload done to s3://$BUCKET/$FILE"
    fi
}

get_sshkey() {
  # Check if SSH is available using a nasty little python hack
  PARAMETERS=$1
  sshkey=$(python -c "import sys, json; data = json.load(open('$PARAMETERS')); sshkey = [row for row in data if 'KeyPair' in row.values()]; print sshkey[0]['ParameterValue']")
  echo $sshkey
}

check_sshkey() {
    PARAMETERS=$1

    sshkey=$(get_sshkey $PARAMETERS)
    echo_green "Verifying SSH Key $sshkey"
    if [ -z $sshkey ]; then
        echo_red "Could not locate a SSH Key Pair in the parameters file"
        echo_red "Follow the SSH Key Pair instructions at http://docs.deis.io/en/latest/installing_deis/aws/"
        exit 1
    else
        fingerprint=$(
            aws ec2 describe-key-pairs \
                --query "KeyPairs[?KeyName=='$sshkey'].[KeyFingerprint]" \
                --output text \
                $EXTRA_AWS_CLI_ARGS
        )

        if [ -z $fingerprint ]; then
           echo_red "SSH Key Pair '$sshkey' does not exist in AWS yet. Did you forgot to import it?"
           echo_red "Follow the SSH Key Pair instructions at http://docs.deis.io/en/latest/installing_deis/aws/"
           exit 1
        else
            if [ -z "$2" ]; then
                keypath="$HOME/.ssh/$sshkey"
            else
                # expand home directory
                keypath=$2
                keypath="${keypath/#\~/$HOME}"
            fi

            echo_green "Using $keypath as the private key to compare against"

            local_fingerprint=$(python $PARENT_DIR/ec2-fingerprint-key.py -p $keypath)
            if [ "$local_fingerprint" != "$fingerprint" ]; then
                echo_red "Local fingerprint of $keypath does not match the keypair '$sshkey' in AWS"
                echo_red "Local Fingerprint: $local_fingerprint"
                echo_red "AWS Fingerprint: $fingerprint"
                exit 1
            fi

            if ! ssh-add -l | grep -q $keypath; then
                echo_red "Could not locate $keypath in ssh-add -l - This is required for Deis"
                echo_red "Load the key with: ssh-add $keypath"
                exit 1
            fi
        fi
    fi

    echo_green "All SSH Keys look good to go!"
}

get_stack_status() {
    STACK_NAME=$1
    STACK_STATUS=$(
      aws cloudformation describe-stacks \
          --stack-name $STACK_NAME \
          --query 'Stacks[].StackStatus' \
          --output text \
          $EXTRA_AWS_CLI_ARGS
    )

    printf $STACK_STATUS
}

# Prepare bailout function to prevent us polluting the namespace
bailout() {
  aws cloudformation delete-stack --stack-name $EXTRA_AWS_CLI_ARGS $1
}

# Check for AWS API tools in $PATH
check_aws() {
  if ! which aws > /dev/null; then
    echo_red 'Please install the AWS command-line tool and ensure it is in your $PATH.'
    echo_red 'Running pip install -r requirements.txt should do the trick'
    exit 1
  fi
}

# Get Bastion Host based on the instance ID
get_bastion_host() {
    if [ -n $BASTION_HOST ]; then
        printf "$BASTION_HOST"
    fi

    BASTION_HOST=$(
      aws ec2 describe-instances \
        --instance-ids $BASTION_ID \
        --query 'Reservations[].Instances[0].PublicIpAddress' \
        --output text \
        $EXTRA_AWS_CLI_ARGS
    )

    printf "$BASTION_HOST"
}

# Copy a file to the bastion host
ssh_copy() {
  if [ -z $BASTION_ID ]; then
    echo_red "Bastion Host instance ID is not defined"
    exit 1
  fi

  scp -o UserKnownHostsFile=/dev/null \
      -o StrictHostKeyChecking=no \
      -o LogLevel=quiet \
      $1 ubuntu@$(get_bastion_host):$2 >/dev/null
}
