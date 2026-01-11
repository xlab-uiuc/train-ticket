#!/bin/bash

# Define necessary variables
mysqlCharts=deployment/kubernetes-manifests/quickstart-k8s/charts/mysql
nacosCharts=deployment/kubernetes-manifests/quickstart-k8s/charts/nacos
rabbitmqCharts=deployment/kubernetes-manifests/quickstart-k8s/charts/rabbitmq
nacosDBRelease="nacosdb"
nacosDBHost="${nacosDBRelease}-mysql-leader"
nacosDBUser="nacos"
nacosDBPass="Abcd1234#"
nacosDBName="nacos"
nacosRelease="nacos"
rabbitmqRelease="rabbitmq"
tsUser="ts"
tsPassword="Ts_123456"
tsDB="ts"
tsMysqlName="tsdb"
svc_list="assurance auth config consign-price consign contacts delivery food food-delivery inside-payment notification order-other order payment price route security station-food station ticket-office train-food train travel travel2 user voucher wait-order"

secret_yaml="deployment/kubernetes-manifests/quickstart-k8s/yamls/secret.yaml"
dp_sample_yaml="deployment/kubernetes-manifests/quickstart-k8s/yamls/deploy.yaml.sample"
sw_dp_sample_yaml="deployment/kubernetes-manifests/quickstart-k8s/yamls/sw_deploy.yaml.sample"
dp_yaml="deployment/kubernetes-manifests/quickstart-k8s/yamls/deploy.yaml"
sw_dp_yaml="deployment/kubernetes-manifests/quickstart-k8s/yamls/sw_deploy.yaml"

# Get the namespace from command line argument or set to "default" if not provided
namespace=${1:-default}

# Debug: Check if the charts exist
if [ ! -d "$mysqlCharts" ]; then
  echo "Error: MySQL charts directory not found at $mysqlCharts"
fi
if [ ! -d "$nacosCharts" ]; then
  echo "Error: Nacos charts directory not found at $nacosCharts"
fi

# Debug before running any command that depends on the working directory
echo "Before deploying Nacos. Current working directory: $(pwd)"

# Utility function to wait for all pods in a namespace to be ready
function wait_for_pods_ready {
  local namespace=$1
  echo "Waiting for all pods in namespace '$namespace' to be ready..."

  while true; do
    # Check the 'READY' column for pods that are not fully ready
    non_ready_pods=$(kubectl get pods -n "$namespace" --no-headers | awk '{split($2,a,"/"); if (a[1] != a[2]) print $1}' | wc -l)

    if [ "$non_ready_pods" -eq 0 ]; then
      echo "All pods in namespace '$namespace' are ready."
      break
    fi

    echo "$non_ready_pods pod(s) are not ready yet. Checking again in 10 seconds..."
    sleep 10
  done
}

# Step 1: Deploy infrastructure services
function deploy_infrastructures {
  echo "Start deployment Step <1/3>------------------------------------"
  echo "Start to deploy mysql cluster for nacos."
  helm install $nacosDBRelease --set mysql.mysqlUser=$nacosDBUser --set mysql.mysqlPassword=$nacosDBPass --set mysql.mysqlDatabase=$nacosDBName $mysqlCharts -n $namespace
  echo "Waiting for mysql cluster of nacos to be ready ......"
  kubectl rollout status statefulset/$nacosDBRelease-mysql -n $namespace
  echo "Finish nacos DB rollout.."
}

# Step 2: Patch Nacos MySQL cluster
function patch_nacos_mysql {
  echo "Patching Nacos MySQL cluster..."
  for pod in $(kubectl get pods -n "$namespace" --no-headers -o custom-columns=":metadata.name" | grep nacosdb-mysql); do
    kubectl exec "$pod" -n "$namespace" -- mysql -uroot -e "CREATE USER IF NOT EXISTS 'root'@'::1' IDENTIFIED WITH mysql_native_password BY '' ; GRANT ALL ON *.* TO 'root'@'::1' WITH GRANT OPTION ;"
    kubectl exec "$pod" -n "$namespace" -c xenon -- /sbin/reboot
  done
  wait_for_pods_ready $namespace
}

# Step 3: Deploy MySQL for Train Ticket services
function continue_deployment {
  echo "Start to deploy nacos."
  helm install $nacosRelease --set nacos.db.host=$nacosDBHost --set nacos.db.username=$nacosDBUser --set nacos.db.name=$nacosDBName --set nacos.db.password=$nacosDBPass $nacosCharts -n $namespace
  echo "Waiting for nacos to be ready ......"
  kubectl rollout status statefulset/$nacosRelease -n $namespace
  echo "Start to deploy rabbitmq."
  helm install $rabbitmqRelease $rabbitmqCharts -n $namespace
  echo "Waiting for rabbitmq to be ready ......"
  kubectl rollout status deployment/$rabbitmqRelease -n $namespace
  echo "Start deployment Step <2/3>: mysql cluster of train-ticket services----------------------"
  helm install $tsMysqlName --set mysql.mysqlUser=$tsUser --set mysql.mysqlPassword=$tsPassword --set mysql.mysqlDatabase=$tsDB $mysqlCharts -n $namespace 1>/dev/null
  echo "Waiting for mysql cluster of train-ticket to be ready ......"
  kubectl rollout status statefulset/${tsMysqlName}-mysql -n $namespace
  gen_secret_for_services $tsUser $tsPassword $tsDB "${tsMysqlName}-mysql-leader"
  echo "End deployment Step <2/3>-----------------------------------------------------------------"
}

# Step 4: Patch Train Ticket MySQL cluster
function patch_tt_mysql {
  echo "Patching Train Ticket MySQL cluster..."
  for pod in $(kubectl get pods -n "$namespace" --no-headers -o custom-columns=":metadata.name" | grep tsdb-mysql); do
    kubectl exec "$pod" -n "$namespace" -- mysql -uroot -e "CREATE USER IF NOT EXISTS 'root'@'::1' IDENTIFIED WITH mysql_native_password BY '' ; GRANT ALL ON *.* TO 'root'@'::1' WITH GRANT OPTION ;"
    kubectl exec "$pod" -n "$namespace" -c xenon -- /sbin/reboot
  done
  wait_for_pods_ready $namespace
  
  # Fix max_connections issue - helm chart config doesn't apply properly
  echo "Setting max_connections=500 on all MySQL instances..."
  for pod in $(kubectl get pods -n "$namespace" --no-headers -o custom-columns=":metadata.name" | grep tsdb-mysql); do
    kubectl exec "$pod" -n "$namespace" -- mysql -uroot -e "SET GLOBAL max_connections = 500;" 2>/dev/null || true
  done
}

function gen_secret_for_tt {
  s="$1"
  name="ts-$s-mysql"
  hostVal="$2"
  userVal="$3"
  passVal="$4"
  dbVal="$5"

  prefix=`echo "${s}-mysql-" | tr '-' '_' | tr a-z A-Z`
  host=$prefix"HOST"
  port=$prefix"PORT"
  database=$prefix"DATABASE"
  user=$prefix"USER"
  pwd=$prefix"PASSWORD"

  cat>>$secret_yaml<<EOF
apiVersion: v1
kind: Secret
metadata:
  name: $name
type: Opaque
stringData:
  $host: "$hostVal"
  $port: "3306"
  $database: "$dbVal"
  $user: "$userVal"
  $pwd: "$passVal"
---
EOF
}

function gen_secret_for_services {
  mysqlUser="$1"
  mysqlPassword="$2"
  mysqlDatabase="$3"
  mysqlHost=""
  useOneHost=0

  if [ $# == 4 ]; then
    mysqlHost="$4"
    useOneHost=1
  fi
  rm $secret_yaml > /dev/null 2>&1
  touch $secret_yaml
  for s in $svc_list
  do
    if [ useOneHost == 0 ]; then
      mysqlHost="ts-$s-mysql-leader"
    fi
    gen_secret_for_tt $s $mysqlHost $mysqlUser $mysqlPassword $mysqlDatabase
  done
}

function update_tt_dp_cm {
  nacosCM="$1"
  rabbitmqCM="$2"

  cp $dp_sample_yaml $dp_yaml

  if [[ "$(uname)" == "Darwin" ]]; then
    sed -i "" "s/nacos/${nacosCM}/g" $dp_yaml
    sed -i "" "s/rabbitmq/${rabbitmqCM}/g" $dp_yaml
  else
    sed -i "s/nacos/${nacosCM}/g" $dp_yaml
    sed -i "s/rabbitmq/${rabbitmqCM}/g" $dp_yaml
  fi
}

# Step 6: Complete deployment of Train Ticket services
function complete_deployment {
  echo "Start deployment Step <3/3>: train-ticket services--------------------------------------------"
  echo "Start to deploy secret of train-ticket services."
  kubectl apply -f deployment/kubernetes-manifests/quickstart-k8s/yamls/secret.yaml -n $namespace > /dev/null

  echo "Deploying service configurations..."
  kubectl apply -f deployment/kubernetes-manifests/quickstart-k8s/yamls/svc.yaml -n $namespace > /dev/null

  echo "sw_dp_sample_yaml: $sw_dp_sample_yaml"
  echo "sw_dp_yaml: $sw_dp_yaml"


  # echo "Deploying train-ticket deployments..."
  update_tt_dp_cm $nacosRelease $rabbitmqRelease
  kubectl apply -f deployment/kubernetes-manifests/quickstart-k8s/yamls/deploy.yaml -n $namespace > /dev/null

  # Skywalking-ui is getting OOMKilled, might be issues with old image
  # I'm just commenting out for now since I'm not sure if we need it at all since we have prometheus and grafana

  # echo "Deploying train-ticket deployments with skywalking agent..."
  # update_tt_sw_dp_cm $nacosRelease $rabbitmqRelease
  # kubectl apply -f deployment/kubernetes-manifests/quickstart-k8s/yamls/sw_deploy.yaml -n $namespace > /dev/null

  # echo "Start deploy skywalking"
  # kubectl apply -f deployment/kubernetes-manifests/skywalking -n $namespace

  echo "Start deploy prometheus and grafana"
  kubectl apply -f deployment/kubernetes-manifests/prometheus
  
  echo "End deployment Step <3/3>----------------------------------------------------------------------"
}

# Main script execution
deploy_infrastructures
wait_for_pods_ready $namespace
patch_nacos_mysql
continue_deployment
wait_for_pods_ready $namespace
patch_tt_mysql
complete_deployment
wait_for_pods_ready $namespace