# check_hp_photosmart_5520
Just a small Icinga2/Nagios plugin which I wrote for a studies class. It can provide data of HP Photosmart 5520 devices (currently only color fill-level is supported).

## Usage
> check_hp_photosmart_5520.py [-h] --hostname HOSTNAME --fill-level FILL_LEVEL [FILL_LEVEL ...]

>  --hostname HOSTNAME   Full qualified name or IP-address of printer
>
>  --fill-level FILL_LEVEL [FILL_LEVEL ...] Color-fill-level to check (color-name warning-percentage-level critical-percentage-level)
>
> -h, --help            show this help message and exit


**--fill-level** requires the color-name, the warning percentage-level and the critical percentage-level e.g.
> python3 check_hp_photosmart_5520.py --host 192.168.1.2 --fill-level Magenta 30 10

**--fill-level** also supports to be called multiple times e.g.
> python3 check_hp_photosmart_5520.py --host 192.168.1.2 --fill-level Magenta 30 10 --fill-level Black 30 10

However, since this caused some problems passing it to Icinga, all colors can be provided using **--fill-level** one time e.g.
> python3 check_hp_photosmart_5520.py --host 192.168.1.2 --fill-level Magenta 30 10 Black 30 10

## Installation
Download check_hp_photosmart_5520.py and copy it into the Nagios plugin folder
> git clone https://github.com/monstermichl/check_hp_photosmart_5520
>
> cd check_hp_photosmart_5520
>
> sudo cp check_hp_photosmart_5520.py /usr/lib/nagios/plugins/

Make it executable
> cd /usr/lib/nagios/plugins/
>
> sudo chmod a+x check_hp_photosmart_5520.py

Restart Icinga2/Nagios
> sudo systemctl restart icinga2

## Issues
I had to deal with the issue that Icinga tried to pass the given **--fill-level** argument as one string. So the argument was
> --fill-level Magenta 30 10 Black 30 10

and Icinga passed it as
> --fill-level "Magenta 30 10 Black 30 10"

My workaround for this issue was to pass only the first argument with the argument name (**--fill-level** Magenta), added an extra Command argument for each --fill-level part-argument (e.g. 30, 10, Black, 30, ...) and suppressed the argument name (**--fill-level**) for at each one. Maybe there's a better solution. If so, please let me know :)