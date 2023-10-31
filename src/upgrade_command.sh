if [[ -f "./conf/odoo.conf" ]]; then
  if [ -z $ODOO_PORT ]; then
    if [[ -f ".envrc" ]]; then
      export ODOO_PORT=$(grep ODOO_PORT .envrc | awk '{print $2}' | awk -F'=' '{print $2}')
    else
      export ODOO_PORT=$(grep http_port conf/odoo.conf | awk -F'=' '{print $2}' | tr -d '[:space:]')
    fi
  fi
  echo podman exec ${PWD##*/} odoo/odoo-bin --no-http --stop-after-init -u ${args[modules]}
else
  echo "not in a project directory"
fi