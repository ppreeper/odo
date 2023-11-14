CDIR="${HOME}/.local/share/bash-completion/completions"
mkdir -p ${CDIR}
send_completions | tee ${CDIR}/odo.bash >/dev/null