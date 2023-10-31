if [[ -f "./conf/odoo.conf" ]]; then
  podman logs -f ${PWD##*/}
else
  echo "not in a project directory"
fi