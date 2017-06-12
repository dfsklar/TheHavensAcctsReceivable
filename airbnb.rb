require 'gmail'
require 'nokogiri'
require 'mysql'
require 'money'
require 'monetize'
require 'money/bank/google_currency'
require 'csv'

load 'credentials.rb'


# Grab the Canadian exchange rate (1USD = ???CAD)
Money.use_i18n = false
# set default bank to instance of GoogleCurrency
Money.default_bank = Money::Bank::GoogleCurrency.new
# create a new money object, and use the standard #exchange_to method
money = Money.new(1_00, "USD") # amount is in cents
exchrate = money.exchange_to(:CAD).fractional / 100.0


# READS A CSV EXPORTED FROM AIRBNB
# The CSV should already be edited to show only the rows for the month to be processed.
# BUT IMPORTANT: The CSV's first line must indeed be the column-header row!  ESSENTIAL!



# Start_date is the "checkin date"
def create_mysql_row (date_income, customer, start_date, num_nights, invoice, balance, exch, comment)  
  comment = "#{comment} // Net incl GST #{balance}" 
  cmd = <<-END
  INSERT INTO BHreceiptsFromCustomers 
  (InvoiceID, CustName, DateCheckin, NumNights, PaymentMethod, PaymentDate, PaymentAmount, ExchRate_CdnToOneUSD, Commentary) 
  VALUES 
  ('#{invoice}', '#{customer}', STR_TO_DATE('#{start_date}','%m/%d/%Y'), #{num_nights}, 'AirBNB', STR_TO_DATE('#{date_income}','%m/%d/%Y'), #{balance}/1.05, #{exch}, '#{comment}'
  );
END
  cmd
end


mysql = Mysql.connect(Credentials::MYSQL['host'], Credentials::MYSQL['username'], Credentials::MYSQL['password'], 'sklarchin')


# Must be declared to ensure the intra-foreach equivalents are global, not intra locals
amount_paid_out = 0
date_paid_out = ''

csv_options = { headers: true }
CSV.foreach("/Users/sklard/Downloads/airbnb.csv", csv_options) do |row|
  if row['Type'] == 'Payout'
    amount_paid_out = row['Paid Out'].to_f

    # OK so airbnb has a stupid bug!
    # Their export CSV file starts with 3 binary characters, messing up the header row.
    # So I have to *inquire* the correct fieldname for the first column (the date column).
    date_field_name = row.headers[0]
    date_paid_out = row[date_field_name]
    if row['Currency'] != 'USD'
      raise "UNEXPECTED NON-USD CURRENCY"
    end
  elsif row['Type'] == 'Reservation' or row['Type'] == 'Resolution Payout'
    # In normal circumstances, this is conjoined with the "Payout" row just above it.
    if row['Amount'].to_f != amount_paid_out
      puts "UNEXPECTED SITUATION number 1  .... " + row['Amount'] + ' NOT EQUAL TO ' + amount_paid_out.to_s
    end
    # Let's emit!
    puts "LET US EMIT"
    sqlcmd = create_mysql_row date_paid_out, row['Guest'], row['Start Date'], row['Nights'], row['Confirmation Code'], row['Amount'], exchrate, row['Type']
    puts sqlcmd
    mysql.query sqlcmd   
  else
    puts "UNEXPECTED ACTIVITY TYPE" + row['Type']
  end
end
