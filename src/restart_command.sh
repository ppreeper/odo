function startOdoo(){
if [ -z $ODOO_PORT ]; then
    if [[ -f ".envrc" ]]; then
      export ODOO_PORT=$(grep ODOO_PORT .envrc | awk '{print $2}' | awk -F'=' '{print $2}')
    else
      export ODOO_PORT=$(grep http_port conf/odoo.conf | awk -F'=' '{print $2}' | tr -d '[:space:]')
    fi
  fi
  if [ -z $ODOO_IM_PORT ]; then
    if [[ -f ".envrc" ]]; then
      export ODOO_IM_PORT=$(grep ODOO_IM_PORT .envrc | awk '{print $2}' | awk -F'=' '{print $2}')
    else
      export ODOO_IM_PORT=$(grep longpolling_port conf/odoo.conf | awk -F'=' '{print $2}' | tr -d '[:space:]')
      export ODOO_IM_PORT=$(grep gevent_port conf/odoo.conf | awk -F'=' '{print $2}' | tr -d '[:space:]')
    fi
  fi

  V_CONF="-v ${PWD}/conf:/opt/odoo/conf"
  V_ODOO_C="-v ${ODOO_C}:/opt/odoo/odoo"
  ADDON_E=$(grep addons_path conf/odoo.conf | awk -F '=' '{print $2}' | awk -F',' '{print $2}')
  if [[ $ADDON_E == *"enterprise" ]]; then
    V_ODOO_E="-v ${ODOO_E}:/opt/odoo/enterprise"
  fi
  V_ADDONS="-v ${PWD}/addons:/opt/odoo/addons"
  V_DATA="-v ${1}_data:/opt/odoo/data"
  V_BACKUPS="-v ${PWD}/backups:/opt/odoo/backups"

  podman run --rm --name ${1} -p ${ODOO_PORT}:8069 -p ${ODOO_IM_PORT}:8072 ${V_CONF} ${V_ODOO_C} ${V_ODOO_E} ${V_ADDONS} ${V_DATA} ${V_BACKUPS} -d ${CONTAINER}
}

if [[ -f "./conf/odoo.conf" ]]; then
  ## stop
  podman stop "${POD}" || echo
  sleep 2
  ## start
  startOdoo ${POD}
else
  echo "not in a project directory"
fi