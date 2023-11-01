if [[ -f "./conf/odoo.conf" ]]; then
  podman exec ${POD} oda_db.py -b
else
  echo "not in a project directory"
fi