# gmail_organizer

# Description
This is a personal script to parse through gmail account.
Going through each email, it will:
- Apply gmail labels according to personal rules (ex: Bills, Income, Scheduled Payments)
- Import Bills and Payment information to a personal database to query end of year finances

# Packages Utilized
- BeautifulSoup
- requests
- sqlalchemy
- Google API

# Setup
- Enable Gmail API
- Edit SECRET_KEY in globaldefs.py to your google secret key
- Edit DB_PROPERTIES in globaldefs.py to your database. Use sqlalchemy connection string format.
