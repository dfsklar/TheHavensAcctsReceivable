require 'gmail'
require 'nokogiri'
require 'mysql'

load 'credentials.rb'



gmail = Gmail.new(Credentials::USERNAME, Credentials::PWD)

puts "Number to process: " + gmail.mailbox('vrbo_pending_processing').count.to_s

mysql_queue = [ ]

def cellval (cell)
  cell ? cell.content : ''
end

def celldollar (cell)
  cellval(cell).gsub(/[^\d\.-]/,'').to_f
end


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
        puts "Gross rent = #{balance}"
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
      end
      puts rowtype
    end
  end
  
  create_mysql_row accounting_date, customer, invoice, balance
  break
end


def create_mysql_row (accounting_date, customer, invoice, balance)
  cmd = "INSERT INTO "  
end


# mysql = Mysql.connect(Credentials::MYSQL['host'], Credentials::MYSQL['username'], Credentials::MYSQL['password'], 'sklarchin')
