if [[ -f "./conf/odoo.conf" ]]; then
  for bfile in ${args[file]}
  do
    podman exec ${POD} oda_db.py -r -d "${bfile}"
  done
else
  echo "not in a project directory"
fi