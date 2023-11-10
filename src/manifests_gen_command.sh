echo "# this file is located in 'src/manifests_gen_command.sh'"
echo "# code for 'odo manifests gen' goes here"
echo "# you can edit it freely and regenerate (it will not be overwritten)"
inspect_args


# function configfile(){
cat <<-_EOF_ | tee manifest.yaml > /dev/null
---
HelloWorldPeter
_EOF_
# }
