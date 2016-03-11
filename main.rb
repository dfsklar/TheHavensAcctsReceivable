require 'gmail'
require 'nokogiri'
load 'credentials.rb'

gmail = Gmail.new(Credentials::USERNAME, Credentials::PWD)

puts "Number to process: " + gmail.mailbox('vrbo_pending_processing').count.to_s


gmail.mailbox('vrbo_pending_processing').emails.each do |email|
  body_in_html = email.message.body.to_s
  doc = Nokogiri::parse (body_in_html)
  break
end
