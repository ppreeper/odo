if [[ -f "./conf/odoo.conf" ]]; then
  podman exec ${POD} odoo/odoo-bin --no-http --stop-after-init -u ${args[modules]}
else
  echo "not in a project directory"
fi