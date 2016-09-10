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
  comment = "Gross #{gross} // Net incl GST #{balance} // Checkin date unknown"
  if balance < 0
    comment = "REFUND due to ?cancel? // Net incl GST #{balance}" 
  end
  cmd = <<-END
  INSERT INTO BHreceiptsFromCustomers 
  (InvoiceID, CustName, DateCheckin, PaymentMethod, PaymentDate, PaymentAmount, ExchRate_CdnToOneUSD, Commentary) 
  VALUES 
  ('#{invoice}', '#{customer}', '#{date}', 'VRBO', '#{date}', #{balance}/1.05, #{exch}, '#{comment}'
  );
END
  cmd
end


mysql = Mysql.connect(Credentials::MYSQL['host'], Credentials::MYSQL['username'], Credentials::MYSQL['password'], 'sklarchin')


gmail.mailbox('vrbo_pending_processing').emails.each do |email|
  accounting_date = email.message.date.to_s[0..9]
  
  
  begin
    body_in_html = email.message.parts[1].body.to_s
    idx_table = 2
  rescue
    body_in_html = email.message.body.to_s
    idx_table = 4
  end
  
  is_recapture = body_in_html.include? "Recapture ACH"

  puts body_in_html
  
  doc = Nokogiri::parse(body_in_html)
  nodeset_all_tables = doc.xpath('//table')

  if false
    puts '------'
    puts '------'
    puts '------'
    puts '------0'
    puts nodeset_all_tables[0]
    puts '------1'
    puts nodeset_all_tables[1]
    puts '------2'
    puts nodeset_all_tables[2]
    puts '------3'
    puts nodeset_all_tables[3]
    puts '------'
    puts '------'
    puts '------'
  end
  
  the_table = nodeset_all_tables[idx_table]
  puts '%%%%%%%%%%%'
  puts the_table
  puts '***********'

  the_rows = the_table.xpath('//tr')
  puts 'SKLAR1'
  customer = ""
  invoice = ""
  balance = 0
  grossrent = 0
  the_rows.each do |row|
    puts 'SKLARabc'
    cells = row.xpath('td')
    puts cells.count
    case cells.count
    when 6
      puts 'SKLARdef'
      rowtype = cellval(cells[2])
      puts rowtype
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
        if is_recapture && (balance > 0)
          balance = 0 - balance
        end
        sqlcmd = create_mysql_row accounting_date, customer, invoice, grossrent, balance, exchrate
        puts sqlcmd
        # raise "MAKESURE"
        mysql.query sqlcmd
      end
    end
  end
    
  # raise 'DO NOT MOVE'

  email.move_to "vrbo_processed", "vrbo_pending_processing"
  # One of the following works - we don't know which one!
  email.flag :Deleted
  email.flag 'Deleted'
  email.flag 'deleted'
  email.remove_label "vrbo_pending_processing"
  
end

