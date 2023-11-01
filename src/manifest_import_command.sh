if [[ -f "./conf/odoo.conf" ]]; then
  podman exec ${POD} oda_db.py -i
else
  echo "not in a project directory"
fi