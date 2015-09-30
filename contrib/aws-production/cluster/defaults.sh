# Here be dragons. Beaware.

# This is all about figuring out the arguments to pass to template generating
# and generally what deis plane goes where

# Remove planes from the available set
unset_plane() {
  local remove=${1}[@]
  for i in ${!remove}; do
    for plane in ${available_planes[@]}; do
      if [[ $i == $plane ]]; then
        # hacky as hell, OSX doesn't have assoc arrays in bash, needs v4
        if [[ $i == 'control' ]]; then
          unset available_planes[0]
        elif [[ $i == 'data' ]]; then
          unset available_planes[1]
        elif [[ $i == 'router' ]]; then
          unset available_planes[2]
        fi
      fi
    done
  done
}

# Figure out which planes need to be verified user-data wise
available_planes=(control data router)
planes=()

# Figure out how many instances need to be monitored - Start with no instance to check on
DEIS_NUM_TOTAL_INSTANCES=0

# Collect arguments to pass into CloudFormation template generation script
GEN_ARGS=''

##### Control Plane #####
if [ -z "$DEIS_NUM_CONTROL_PLANE_INSTANCES" ]; then
  DEIS_NUM_CONTROL_PLANE_INSTANCES=3
fi

if [ -z "$DEIS_NUM_CONTROL_PLANE_INSTANCES_MAX" ]; then
  DEIS_NUM_CONTROL_PLANE_INSTANCES_MAX=9
fi

if [ -n "$DEIS_ISOLATE_CONTROL_PLANE" ]; then
  GEN_ARGS+=" --isolate-control-plane"
  GEN_ARGS+=" --control-plane-instances $DEIS_NUM_CONTROL_PLANE_INSTANCES"
  GEN_ARGS+=" --control-plane-instances-max $DEIS_NUM_CONTROL_PLANE_INSTANCES_MAX"

  let DEIS_NUM_TOTAL_INSTANCES=DEIS_NUM_TOTAL_INSTANCES+DEIS_NUM_CONTROL_PLANE_INSTANCES

  planes+=(control)
  unset available_planes[0]

  if [ -z "$DEIS_ISOLATE_CONTROL_PLANE" ]; then
    DEIS_ISOLATE_CONTROL_PLANE=''
  else
    GEN_ARGS+=" --control-plane-colocate $DEIS_CONTROL_PLANE_COLOCATE"
    # unset other planes as well
    arr=$(echo $DEIS_CONTROL_PLANE_COLOCATE | tr " " "\n")
    unset_plane arr
  fi
else
  DEIS_ISOLATE_CONTROL_PLANE=false
fi

##### Data Plane #####
if [ -z "$DEIS_NUM_DATA_PLANE_INSTANCES" ]; then
  DEIS_NUM_DATA_PLANE_INSTANCES=3
fi

if [ -z "$DEIS_NUM_DATA_PLANE_INSTANCES_MAX" ]; then
  DEIS_NUM_DATA_PLANE_INSTANCES_MAX=25
fi

if [ -n "$DEIS_ISOLATE_DATA_PLANE" ]; then
  GEN_ARGS+=" --isolate-data-plane"
  GEN_ARGS+=" --data-plane-instances $DEIS_NUM_DATA_PLANE_INSTANCES"
  GEN_ARGS+=" --data-plane-instances-max $DEIS_NUM_DATA_PLANE_INSTANCES_MAX"

  let DEIS_NUM_TOTAL_INSTANCES=DEIS_NUM_TOTAL_INSTANCES+DEIS_NUM_DATA_PLANE_INSTANCES

  planes+=(data)
  unset available_planes[1]

  if [ -z "$DEIS_DATA_PLANE_COLOCATE" ]; then
    DEIS_DATA_PLANE_COLOCATE=''
  else
    GEN_ARGS+=" --control-plane-colocate $DEIS_DATA_PLANE_COLOCATE"
    # unset other planes as well
    arr=$(echo $DEIS_DATA_PLANE_COLOCATE | tr " " "\n")
    unset_plane arr
  fi
else
  DEIS_ISOLATE_DATA_PLANE=false
fi

##### Router Mesh #####
if [ -z "$DEIS_NUM_ROUTER_MESH_INSTANCES" ]; then
  DEIS_NUM_ROUTER_MESH_INSTANCES=3
fi

if [ -z "$DEIS_NUM_ROUTER_MESH_INSTANCES_MAX" ]; then
  DEIS_NUM_ROUTER_MESH_INSTANCES_MAX=9
fi

if [ -n "$DEIS_ISOLATE_ROUTER_MESH" ]; then
  GEN_ARGS+=" --isolate-router"
  GEN_ARGS+=" --router-mesh-instances $DEIS_NUM_ROUTER_MESH_INSTANCES"
  GEN_ARGS+=" --router-mesh-instances-max $DEIS_NUM_ROUTER_MESH_INSTANCES_MAX"

  let DEIS_NUM_TOTAL_INSTANCES=DEIS_NUM_TOTAL_INSTANCES+DEIS_NUM_ROUTER_MESH_INSTANCES

  planes+=(router)
  unset available_planes[2]

  if [ -z "$DEIS_ROUTER_MESH_COLOCATE" ]; then
    DEIS_ROUTER_MESH_COLOCATE=''
  else
    GEN_ARGS+=" --router-mesh-colocate $DEIS_ROUTER_MESH_COLOCATE"
    # unset other planes as well
    arr=$(echo $DEIS_ROUTER_MESH_COLOCATE | tr " " "\n")
    unset_plane arr
  fi
else
  DEIS_ISOLATE_ROUTER_MESH=false
fi

##### etcd #####
if [ -z "$DEIS_NUM_ETCD_INSTANCES" ]; then
  DEIS_NUM_ETCD_INSTANCES=3
fi

if [ -z "$DEIS_NUM_ETCD_INSTANCES_MAX" ]; then
  DEIS_NUM_ETCD_INSTANCES_MAX=9
fi

if [ -n "$DEIS_ISOLATE_ETCD" ]; then
  GEN_ARGS+=" --isolate-etcd"
  GEN_ARGS+=" --etcd-instances $DEIS_NUM_ETCD_INSTANCES"
  GEN_ARGS+=" --etcd-instances-max $DEIS_NUM_ETCD_INSTANCES_MAX"
  let DEIS_NUM_TOTAL_INSTANCES=DEIS_NUM_TOTAL_INSTANCES+DEIS_NUM_ETCD_INSTANCES
  planes+=(etcd)
else
  DEIS_ISOLATE_ETCD=false
fi

##### Combination Plane #####
if [ -z "$DEIS_NUM_INSTANCES" ]; then
  DEIS_NUM_INSTANCES=3
fi

if [ -z "$DEIS_NUM_INSTANCES_MAX" ]; then
  DEIS_NUM_INSTANCES_MAX=9
fi

GEN_ARGS+=" --other-plane-instances $DEIS_NUM_INSTANCES"
GEN_ARGS+=" --other-plane-instances-max $DEIS_NUM_INSTANCES_MAX"

# Account for instances that are in combonation plane
if [ "${#available_planes[@]}" != 0 ]; then
  let DEIS_NUM_TOTAL_INSTANCES=DEIS_NUM_TOTAL_INSTANCES+DEIS_NUM_INSTANCES
fi

# Rest of the template generation args
# Make sure we have all required info for the network
if [ -n $BASTION_ID ] || [ -n $VPC_ID ]; then
  if [ -z "$VPC_ID" ]; then
    # Use Bastion host to get VPC information
    vpc=$(python $PARENT_DIR/vpc.py --bastion-id $BASTION_ID)
  else
    vpc=$(python $PARENT_DIR/vpc.py --vpc-id $VPC_ID)
  fi

  eval $vpc  # Pull in the $DEIS_VPC_* vars
  if [ -n $BASTION_ID ]; then
    GEN_ARGS+=" --bastion-id $BASTION_ID"
  else
    GEN_ARGS+=" --vpc-id $VPC_ID"
  fi

  if [ -z "$VPC_ZONES" ]; then
    VPC_ZONES=$DEIS_VPC_ZONES
  fi

  if [ -z "$VPC_SUBNETS" ]; then
    VPC_SUBNETS=$DEIS_VPC_SUBNETS
  fi

  if [ -z "$VPC_PRIVATE_SUBNETS" ]; then
    VPC_PRIVATE_SUBNETS=$DEIS_VPC_PRIVATE_SUBNETS
  fi

  GEN_ARGS+=" --vpc-zones $VPC_ZONES"
  GEN_ARGS+=" --vpc-subnets $VPC_SUBNETS"
  if [ -n "$VPC_PRIVATE_SUBNETS" ]; then
    GEN_ARGS+=" --vpc-private-subnets $VPC_PRIVATE_SUBNETS"
  else
    GEN_ARGS+=" --vpc-private-subnets $VPC_SUBNETS"
  fi
fi
