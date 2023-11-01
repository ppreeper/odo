if [[ -f "./conf/odoo.conf" ]]; then
  podman stop ${POD} || echo
else
  echo "not in a project directory"
fi