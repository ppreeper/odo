if [[ -f "./conf/odoo.conf" ]]; then
  [ -z ${ODOO_C} ] && export ODOO_C="odoo"
  [ -z ${ODOO_E} ] && export ODOO_E="enterprise"

cat <<-_EOF_ | tee pyrightconfig.json > /dev/null
{
  "venvPath": ".",
  "venv": ".direnv",
  "executionEnvironments": [
    {
      "root": ".",
      "extraPaths": [
        "${ODOO_C}",
        "${ODOO_E}",
        "addons"
        ]
    }
  ]
}
_EOF_

else
  echo "not in a project directory"
fi