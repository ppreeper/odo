if [[ -f "./conf/odoo.conf" ]]; then
  echo podman stop ${PWD##*/}
else
  echo "not in a project directory"
fi