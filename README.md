# TheHavensAcctsReceivable

# VRBO

To perform a VRBO/HomeAway importation:

* Log into the gmail account for smc@gm

* Search for all emails meeting this:  vrbo direct 

* Mark them all with the label:  vrbo_pending_processing

* Run the vrbo.rb program to import all that info.


# AIRBNB

* Log into airbnb and go to host "transaction history"

* Set the month you want: e.g. "from aug" "to aug"

* Export CSV via the red-underlined link -- it does indeed honor the combobox date-range settings

* Rename the file to ~/Downloads/airbnb.csv

* ENSURE THE HEADER ROW IS PRESENT!  The csv must start with a header row naming the fields!

* Execute the airbnb.rb program

