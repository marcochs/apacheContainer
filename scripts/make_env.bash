#!/bin/bash

echo export RULE=$(cd ../tf; terraform output listener_rule_arn_dev) >> env.bash
echo export SVC_BLUE=$(cd ../tf; terraform output service_blue) >> env.bash
echo export SVC_GREEN=$(cd ../tf; terraform output service_green) >> env.bash
echo export TG_BLUE=$(cd ../tf; terraform output tg_blue) >> env.bash
echo export TG_GREEN=$(cd ../tf; terraform output tg_green) >> env.bash

