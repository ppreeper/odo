function envrc(){
[ -z ${2} ] && export PORT=8069 || export PORT=${2}
[ -z ${3} ] && export IM_PORT=8072 || export IM_PORT=${3}
cat <<-_EOF_ | tee .envrc > /dev/null
layout python3
export ODOO_V=${1}
export ODOO_PORT=${PORT}
export ODOO_IM_PORT=${IM_PORT}
export ODOO_C=\${HOME}/workspace/repos/odoo/${1}/odoo
export ODOO_E=\${HOME}/workspace/repos/odoo/${1}/enterprise
_EOF_
}

function configfile(){
if [[ "${2}" == "enterprise" ]]; then
  EPATH="/opt/odoo/enterprise,"
else
  EPATH=""
fi
cat <<-_EOF_ | tee conf/odoo.conf > /dev/null
[options]
addons_path = /opt/odoo/odoo/addons,${EPATH}/opt/odoo/addons
data_dir = /opt/odoo/data
admin_passwd = adminadmin
without_demo = all
csv_internal_sep = ;
server_wide_modules = base,web
db_host = ${IPV4}
db_port = 5432
db_maxconn = 24
db_user = odoodev
db_password = odooodoo
db_name = ${3}
db_template = template0
db_sslmode = disable
list_db = False
proxy = True
proxy_mode = True
http_enable = True
http_interface =
http_port = 8069
reportgz = False
syslog = True
log_level = debug
# log_db_level = warning
# log_handler = werkzeug:CRITICAL,odoo.api:DEBUG
log_handler = odoo.tools.convert:DEBUG
workers = 0
#max_cron_threads = 2
limit_memory_hard = 2684354560
limit_memory_soft = 2147483648
limit_request = 8192
limit_time_cpu = 1200
limit_time_real = 2400
_EOF_
}

function pipfile(){
cat <<-_EOF_ | tee Pipfile > /dev/null
[[source]]
url = "https://pypi.org/simple"
verify_ssl = true
name = "pypi"

[packages]
babel = "==2.9.1"
chardet = "==3.0.4"
cryptography = "==2.6.1"
decorator = "==4.4.2"
docutils = "==0.16"
ebaysdk = "==2.1.5"
freezegun = "==0.3.15"
geoip2 = "==2.9.0"
gevent = "==21.8.0"
google-auth = "==2.17.*"
greenlet = "==1.1.*"
idna = "==2.8"
jinja2 = "==2.11.3"
libsass = "==0.18.0"
lxml = "==4.6.5"
markupsafe = "==1.1.0"
num2words = "==0.5.6"
ofxparse = "==0.21"
paramiko = "==2.12.0"
passlib = "==1.7.3"
pillow = "==9.0.1"
polib = "==1.1.0"
"pdfminer.six" = "*"
psutil = "==5.6.7"
psycopg2-binary = "2.9.5"
pydot = "==1.4.1"
pyopenssl = "==19.0.0"
pypdf2 = "==1.26.0"
pyserial = "==3.4"
python-dateutil = "==2.8.2"
python-stdnum = "==1.13"
pytz = "*"
pyusb = "==1.0.2"
qrcode = "==6.1"
reportlab = "==3.5.59"
requests = "==2.25.1"
rjsmin = "==1.1.0"
urllib3 = "==1.26.5"
vobject = "==0.9.6.1"
werkzeug = "==2.0.3"
xlrd = "==1.2.0"
xlsxwriter = "==1.1.2"
xlwt = "==1.3.*"
zeep = "==3.4.0"

[dev-packages]
black="*"
yapf="*"
pylint="*"
pylint-odoo="*"

[requires]
python_version = "3"
_EOF_
}

PDIR=${HOME}/workspace/odoo/${args[projectname]}
mkdir -p ${PDIR}
cd ${PDIR}
envrc ${args[version]} ${args[oport]} ${args[gport]}
direnv allow >/dev/null
mkdir -p conf backups addons
configfile ${args[version]} ${args[edition]} ${args[projectname]}
pipfile
printf "To install python dev dependencies run:\npipenv install --dev\n\n"