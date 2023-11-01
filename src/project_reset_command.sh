if [[ -f "./conf/odoo.conf" ]]; then
  read -r -p "Are you sure you want to reset the database? [YES/N] " response
  if [[ "$response" =~ ^(YES)$ ]]; then
    read -r -p "Are you **really** sure you want to reset the database? [YES/N] " response
    if [[ "$response" =~ ^(YES)$ ]]; then
      podman stop ${POD} || echo
      podman rm -f ${POD} || echo
      podman volume rm ${POD}_data || echo
      PGPASSWORD=${args[--pass]} dropdb -U ${args[--user]} -h ${args[--host]} -p ${args[--port]} -w -f ${args[--name]} >/dev/null
      echo "Project reset"
    fi
  fi
else
  echo "not in a project directory"
fi

