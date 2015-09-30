# Helpers specific to the deis cluster setup / update

check_plane_user_data() {
    # Check that the CoreOS user-data file is valid
    for plane in "${planes[@]}"
    do
        $CONTRIB_DIR/util/check-user-data.sh $USER_DATA_DIR/$plane-plane-user-data
    done
}

get_elb_info() {
    # Get ELB public DNS name through cloudformation
    ELB_DNS_NAME=$(
      aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --max-items 1 \
        --query 'Stacks[].[ Outputs[?OutputKey==`DNSName`].OutputValue ]' \
        --output=text \
        $EXTRA_AWS_CLI_ARGS
    )

    # Get ELB friendly name through aws elb
    ELB_NAME=$(
      aws elb describe-load-balancers \
        --query "LoadBalancerDescriptions[?DNSName=='$ELB_DNS_NAME'].[ LoadBalancerName ]" \
        --output=text \
        $EXTRA_AWS_CLI_ARGS
    )
    echo_green "\nUsing ELB $ELB_NAME at $ELB_DNS_NAME\n\n"
}

get_first_instance() {
    if [ -n $FIRST_INSTANCE ]; then
        printf "$FIRST_INSTANCE"
    fi

    # Instances launched into a VPC may not have a PublicIPAddress
    for ip_type in PublicIpAddress PrivateIpAddress; do
      FIRST_INSTANCE=$(
        aws ec2 describe-instances \
            --filters Name=tag:aws:cloudformation:stack-name,Values=$STACK_NAME Name=instance-state-name,Values=running \
            --query "Reservations[].Instances[].[$ip_type][0]" \
            --output text \
            $EXTRA_AWS_CLI_ARGS
      )

      if [[ ! $FIRST_INSTANCE == "None" ]]; then
        printf "$FIRST_INSTANCE"
      fi
    done

    if [[ $FIRST_INSTANCE == "None" ]]; then
        # Make the varialbe empty so we don't have to compare against "None"
        $FIRST_INSTANCE=''
        printf "$FIRST_INSTANCE"
    fi
}

# Get Bastion Host
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

# Run commands via the bastion host if bastion is set
run () {
    cmd=$@
    if [ -n $BASTION_ID ]; then
        TUNNEL=''
        INSTANCE="$(get_first_instance)"
        if [ -n $INSTANCE ]; then
            TUNNEL="export DEISCTL_TUNNEL=$INSTANCE"
        fi

        ssh -o LogLevel=quiet \
            -oUserKnownHostsFile=/dev/null \
            -oStrictHostKeyChecking=no \
            ubuntu@$(get_bastion_host) "($TUNNEL && $cmd)" >/dev/null
    else
        $cmd >/dev/null
    fi
}
