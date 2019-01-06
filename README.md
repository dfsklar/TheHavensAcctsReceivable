# Preparing ubuntu

```
apt-get install ruby
apt-get install ruby-dev
apt-get install libmysqlclient-dev
gem install mysql
gem install gmail nokogiri money monetize google_currency
```

# VRBO

To perform a VRBO/HomeAway importation:

* Log into the gmail account for havensvrbo@gmail.com

* Mark all not-yet-processed with the label:  vrbo_pending_processing

* Run the vrbo.rb program to import all that info.


# AIRBNB

* Log into airbnb and go to host "transaction history"

* Set the month you want: e.g. "from aug" "to aug"

* Export CSV via the provided link -- it does indeed honor the combobox date-range settings

* Rename the file to ~/Downloads/airbnb.csv

* ENSURE THE HEADER ROW IS PRESENT!  The csv must start with a header row naming the fields!

* Execute the airbnb.rb program

