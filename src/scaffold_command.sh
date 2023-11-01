if [[ -f "./conf/odoo.conf" ]]; then
  podman exec ${POD} odoo/odoo-bin scaffold ${args[module]} /opt/odoo/addons/.
else
  echo "not in a project directory"
fi