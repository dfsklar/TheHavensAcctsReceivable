require 'gmail'
require 'nokogiri'
require 'mysql'
require 'money'
require 'monetize'
require 'money/bank/google_currency'

load 'credentials.rb'


# Grab the Canadian exchange rate (1USD = ???CAD)
Money.use_i18n = false
# set default bank to instance of GoogleCurrency
Money.default_bank = Money::Bank::GoogleCurrency.new
# create a new money object, and use the standard #exchange_to method
money = Money.new(1_00, "USD") # amount is in cents
exchrate = money.exchange_to(:CAD).fractional / 100.0



gmail = Gmail.new(Credentials::USERNAME, Credentials::PWD)

puts gmail.labels.all.to_s

puts "Number to process: " + gmail.mailbox('vrbo_pending_processing').count.to_s

mysql_queue = [ ]

def cellval (cell)
  cell ? cell.content : ''
end

def celldollar (cell)
  cellval(cell).gsub(/[^\d\.-]/,'').to_f
end

def create_mysql_row (date, customer, invoice, gross, balance, exch)  
  cmd = <<-END
  INSERT INTO BHreceiptsFromCustomers 
  (InvoiceID, CustName, DateCheckin, PaymentMethod, PaymentDate, PaymentAmount, ExchRate_CdnToOneUSD, Commentary) 
  VALUES 
  ('#{invoice}', '#{customer}', '#{date}', 'VRBO', '#{date}', #{balance}/1.05, #{exch}, 
  'Gross #{gross} // Net incl GST #{balance} // Checkin date unknown'
  );
END
  cmd
end


mysql = Mysql.connect(Credentials::MYSQL['host'], Credentials::MYSQL['username'], Credentials::MYSQL['password'], 'sklarchin')


gmail.mailbox('vrbo_pending_processing').emails.each do |email|
  accounting_date = email.message.date.to_s[0..9]
  body_in_html = email.message.body.to_s
  
  
  doc = Nokogiri::parse (body_in_html)
  nodeset_all_tables = doc.xpath('//table')
  the_table = nodeset_all_tables[4]
  the_rows = the_table.xpath('tr')
  customer = ""
  invoice = ""
  balance = 0
  grossrent = 0
  the_rows.each do |row|
    cells = row.xpath('td')
    case cells.count
    when 6
      rowtype = cellval(cells[2])
      dollaramt = celldollar(cells[5])
      case rowtype
      when 'Item'
        ignoreme = true
      when 'Rent'
        customer = cellval(cells[0])
        invoice = cellval(cells[1])
        grossrent = dollaramt
        puts "Gross rent = #{grossrent}"
      when String
        puts "Balance was adjusted by #{rowtype}"
        balance = balance + dollaramt
      else
        puts "WHAT ON EARTH IS THIS ROW"
      end
    when 2
      rowtype = cellval(cells[0])
      if rowtype == 'Total'
        balance = celldollar(cells[1])
        sqlcmd = create_mysql_row accounting_date, customer, invoice, grossrent, balance, exchrate
        puts sqlcmd
        mysql.query sqlcmd
      end
    end
  end
    
  email.move_to "vrbo_processed", "vrbo_pending_processing"
  email.flag :Deleted
  email.flag 'Deleted'
  email.flag 'deleted'
  email.remove_label "vrbo_pending_processing"
  
  break
end

