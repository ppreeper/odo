if [[ -f "./conf/odoo.conf" ]]; then
  podman logs -f ${POD}
else
  echo "not in a project directory"
fi