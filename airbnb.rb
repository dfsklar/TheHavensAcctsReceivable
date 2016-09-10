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



# Start_date is the "checkin date"
def create_mysql_row (date_income, customer, start_date, num_nights, invoice, balance, exch, comment)  
  comment = "#{comment} // Net incl GST #{balance}" 
  cmd = <<-END
  INSERT INTO BHreceiptsFromCustomers 
  (InvoiceID, CustName, DateCheckin, NumNights, PaymentMethod, PaymentDate, PaymentAmount, ExchRate_CdnToOneUSD, Commentary) 
  VALUES 
  ('#{invoice}', '#{customer}', '#{start_date}', #{num_nights}, 'AirBNB', '#{date_income}', #{balance}/1.05, #{exch}, '#{comment}'
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
    date_paid_out = row['Date']
    if row['Currency'] != 'USD'
      raise "UNEXPECTED NON-USD CURRENCY"
    end
  elsif row['Type'] == 'Reservation' or row['Type'] == 'Resolution Payout'
    # In normal circumstances, this is conjoined with the "Payout" row just above it.
    if row['Amount'].to_f != amount_paid_out
      raise "UNEXPECTED SITUATION number 1"
    end
    # Let's emit!
    puts "LET US EMIT"
    puts date_paid_out
    sqlcmd = create_mysql_row date_paid_out, row['Guest'], row['Start Date'], row['Nights'], row['Confirmation Code'], amount_paid_out, exchrate, row['Type']
    puts sqlcmd
    # raise "MAKESURE"
    mysql.query sqlcmd   
  else
    raise "UNEXPECTED ACTIVITY TYPE"
  end
end
