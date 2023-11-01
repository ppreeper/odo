if [[ -f "./conf/odoo.conf" ]]; then
  read -r -p "Are you sure you want to change the admin password [YES/N] " response
  if [[ "$response" =~ ^(YES)$ ]]; then
    read -r -p "Are you sure you want to change the admin password [YES/N] " response
    if [[ "$response" =~ ^(YES)$ ]]; then
      admin_password=$(podman exec atest oda_db.py -p ${args[admin_password]})
      psql postgres://${args[--db_user]}:${args[--db_pass]}@${args[--host]}:${args[--port]}/${args[--db_name]} -t -c "update res_users set password='${admin_password}' where id=2;" >/dev/null
    fi
  fi
else
  echo "not in a project directory"
fi