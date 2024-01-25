# EventBus


## Routing?

* src/dst
* eid
* local:
  * ping
  * get_XXX

## Response

* append '_' to request type
* e.g. get_config -> get_config_

## Event Types

* state_update

* get_config
* get_state
* get_log

* reset_config

* ota

* exec
* eval
* print
* restart
* fput
* fget

* cmd_turn_on
* cmd_turn_off
* cmd_brightness