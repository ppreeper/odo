function launch_json(){
[ -z ${2} ] && export PORT=8069 || export PORT=${2}
cat <<-_EOF_ | tee .vscode/launch.json > /dev/null
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Launch",
      "type": "python",
      "request": "launch",
      "stopOnEntry": false,
      "python": "\${command:python.interpreterPath}",
      "program": "\${workspaceRoot}/odoo/odoo-bin",
      "args": ["-c", "\${workspaceRoot}/conf/odoo.conf","-p","$ODOO_PORT"],
      "cwd": "\${workspaceRoot}",
      "env": {},
      "envFile": "\${workspaceFolder}/.env",
      "console": "integratedTerminal"
    }
  ]
}
_EOF_
}

function settings_json(){
[ -z ${1} ] && export PORT=8069 || export PORT=${1}
cat <<-_EOF_ | tee .vscode/settings.json > /dev/null
{
  "python.analysis.extraPaths": ["${2}", "${3}"],
  "python.linting.pylintEnabled": true,
  "python.linting.enabled": true,
  "python.terminal.executeInFileDir": true,
  "python.formatting.provider": "black"
}
_EOF_
}

if [[ -f "./conf/odoo.conf" ]]; then
  if [ -z $ODOO_PORT ]; then
    if [[ -f ".envrc" ]]; then
      export ODOO_PORT=$(grep ODOO_PORT .envrc | awk '{print $2}' | awk -F'=' '{print $2}')
    else
      export ODOO_PORT=$(grep http_port conf/odoo.conf | awk -F'=' '{print $2}' | tr -d '[:space:]')
    fi
  fi
  [ -z ${ODOO_C} ] && export ODOO_C="odoo"
  [ -z ${ODOO_E} ] && export ODOO_E="enterprise"

  mkdir -p .vscode
  settings_json $ODOO_PORT $ODOO_C $ODOO_E
  launch_json
else
  echo "not in a project directory"
fi