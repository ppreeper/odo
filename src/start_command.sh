if [[ -f "./conf/odoo.conf" ]]; then
  if [ -z $ODOO_PORT ]; then
    if [[ -f ".envrc" ]]; then
      export ODOO_PORT=$(grep ODOO_PORT .envrc | awk '{print $2}' | awk -F'=' '{print $2}')
    else
      export ODOO_PORT=$(grep http_port conf/odoo.conf | awk -F'=' '{print $2}' | tr -d '[:space:]')
    fi
  fi
  echo podman run --rm --name ${POD} -p 8069:8069 -p 8072:8072 -v ${PWD}/conf:/opt/odoo/conf -v $ODOO_C:/opt/odoo/odoo -v $ODOO_E:/opt/odoo/enterprise -v $PWD/addons:/opt/odoo/addons -v ${PWD##*/}_data:/opt/odoo/data -d localhost/odoobase_bookworm:latest
else
  echo "not in a project directory"
fi