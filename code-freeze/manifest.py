# type: ignore

include("$(PORT_DIR)/boards/manifest.py")

# individual files
module("main.py")
module("version.py")
module("default_config.py")

# packages
package("app")
package("bsp")
package("features")
package("tests")

# directories
freeze("lib")
