from __future__ import print_function
import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import base64
from datetime import datetime
from bs4 import BeautifulSoup
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import globaldefs as gd
from models import Property, Transaction, Category
import re


def get_labels():
    # Call the Gmail API
    results = service.users().labels().list(userId='me').execute()
    labels = results.get('labels', [])

    if not labels:
        print('No labels found.')
    else:
        # print('Labels:')
        labels_dict = {}
        for label in labels:
            # print(label['name'], label['id'])
            labels_dict[label['name']] = label['id']
        return labels_dict


def get_categories():
    category_dict = {}
    categories = session.query(Category)

    for category in categories.all():
        category_dict[category.category] = category.id
    return category_dict


def get_properties():
    property_dict = {}
    properties = session.query(Property)

    for property in properties.all():
        property_dict[property.name] = property.id
    return property_dict


def parse_msg(msg):
    '''
    Simplify email data
    Returns: Dictionary
    '''
    from email.utils import parsedate_to_datetime
    email = {}
    email['id'] = msg.get('id')
    email['threadId'] = msg.get('threadId')
    email['labelIds'] = msg.get('labelIds')
    email['body'] = ''
    
    # Get Body
    if msg.get('payload').get('parts'):
        for part in msg.get('payload').get('parts'):
            try:
                email['body'] += base64.urlsafe_b64decode(part.get("body").get("data").encode("ASCII")).decode("utf-8")
            except Exception as e:
                print(e)
    elif msg.get('payload').get("body").get("data"):
        email['body'] = base64.urlsafe_b64decode(msg.get("payload").get("body").get("data").encode("ASCII")).decode("utf-8")
    else:
        email['body'] = msg.get("snippet") 
    
    for row in msg.get('payload').get('headers'):
        if row['name'] == 'to':
            email['Delivered-To'] = row['value']
        if row['name'] == 'From':
            email['from'] = row['value']
        if row['name'] == 'Subject':
            email['subject'] = row['value']
        if row['name'].lower() == 'date':
            email['date_received'] = parsedate_to_datetime(row['value'])
    return email


def bs_preprocess(html):
     """remove distracting whitespaces and newline characters"""
     import re
     pat = re.compile('(^[\s]+)|([\s]+$)', re.MULTILINE)
     html = re.sub(pat, '', html)       # remove leading and trailing whitespaces
     html = re.sub('\n', ' ', html)     # convert newlines to spaces
                                        # this preserves newline delimiters
     html = re.sub('[\s]+<', '<', html) # remove whitespaces before opening tags
     html = re.sub('>[\s]+', '>', html) # remove whitespaces after closing tags
     return html 


def socalgas(email):
    try:
        ignore_list = [
            'your bill from southern california gas company',
            'bill reminder',
        ]
        if email['subject'].lower() == '''your automatic monthly payment is scheduled''':
            soup = BeautifulSoup(bs_preprocess(email['body']))
            basetree = soup.find(string='Account Number:').find_parent('table')
            reference1 = basetree.find(string='Account Number:').find_parent('td').find_next_sibling('td').find_next_sibling('td').text.strip()
            total_amount = float(basetree.find(string='Payment Amount:').find_parent('td').find_next_sibling('td').find_next_sibling('td').text.strip('$').replace(',',''))
            date_due = datetime.strptime(basetree.find(string='Scheduled Payment Date:').find_parent('td').find_next_sibling('td').find_next_sibling('td').text.strip(),'%m/%d/%Y')
            cat = session.query(Category).filter_by(category='Utility - Gas').first()
            prop = session.query(Property).filter_by(name='Montclair House').first()
            # Add to database
            session.add(Transaction(property_id=prop.id, datetime_payment=date_due, category_id=cat.id, name='Southern California Gas Company', reference1=reference1, amount=-1*total_amount))
            session.commit()

            # Manage Inbox
            apply_labels = {
                'addLabelIds': [LABELS_DICT['housing'],LABELS_DICT['processed']],
                'removeLabelIds': [LABELS_DICT['UNREAD'], LABELS_DICT['INBOX']]
                }                
            service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()
        
        elif email['subject'].lower() in ignore_list:
            apply_labels = {
                'addLabelIds': [LABELS_DICT['housing'],LABELS_DICT['processed']],
                'removeLabelIds': [LABELS_DICT['UNREAD'], LABELS_DICT['INBOX']]
                }                
            service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()

    except Exception as e:
        print(e)
        apply_labels = {
            'addLabelIds': [LABELS_DICT['ERRORS']],
            }                
        service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()


def sce(email):
    try:
        ignore_list = []        
        if email['subject'].lower() == '''bill is ready'''.lower():
            soup = BeautifulSoup(bs_preprocess(email['body']))
            basetree = soup.find(string='Account Number').find_parent('table').find_next('table')
            reference1 = basetree.find_next('td').text.strip()
            total_amount = float(basetree.find_next('td').find_next('td').find_next('td').text.strip('$').strip().replace(',', ''))
            date_due = datetime.strptime(basetree.find_next('td').find_next('td').find_next('td').find_next('td').text.strip(),'%m/%d/%Y')
            cat = session.query(Category).filter_by(category='Utility - Electric').first()
            prop = session.query(Property).filter_by(name='Montclair House').first()
            # Add to database
            session.add(Transaction(property_id=prop.id, datetime_payment=date_due, category_id=cat.id, name='Southern California Edison', reference1=reference1, amount=-1*total_amount))
            session.commit()

            # Manage Inbox
            apply_labels = {
                'addLabelIds': [LABELS_DICT['housing'],LABELS_DICT['processed']],
                'removeLabelIds': [LABELS_DICT['UNREAD'], LABELS_DICT['INBOX']]
                }                
            service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()
        
        elif email['subject'].lower() in ignore_list:
            apply_labels = {
                'addLabelIds': [LABELS_DICT['housing'],LABELS_DICT['processed']],
                'removeLabelIds': [LABELS_DICT['UNREAD'], LABELS_DICT['INBOX']]
                }                
            service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()

    except Exception as e:
        print(e)
        apply_labels = {
            'addLabelIds': [LABELS_DICT['ERRORS']],
            }                
        service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()        

def montclair_trash(email):
    try:
        ignore_list = [
            '''Your City of Montclair Bill is ready for your review'''.lower(),
            '''City of Montclair Upcoming Payment Reminder'''.lower(),
            '''City of Montclair Scheduled Payment Reminder'''.lower(),
        ]        

        subject_words = [item.lower() for item in email['subject'].split()]

        if email['subject'].lower() == '''City of Montclair Online Payment'''.lower():
            soup = BeautifulSoup(bs_preprocess(email['body']))
            # basetree = soup.find(string='Account Number').find_parent('tr').next_sibling.next_sibling
            reference1 = 'Account #: 025879-000'
            reference2 = soup.p.next_sibling.text.strip()
            total_amount = float(re.search("(?<=the amount of ).*(?= with)", soup.p.text).group().strip('$').strip())
            date_due = datetime.strptime(re.search("(?<=due date of ).*(?= .)", soup.p.text).group().strip(),'%m/%d/%Y')
            cat = session.query(Category).filter_by(category='Utility - Trash').first()
            prop = session.query(Property).filter_by(name='Montclair House').first()
            # Add to database
            session.add(Transaction(property_id=prop.id, datetime_payment=date_due, category_id=cat.id, name='City Of Montclair - Trash', reference1=reference1, reference2=reference2, amount=-1*total_amount))
            session.commit()

            # Manage Inbox
            apply_labels = {
                'addLabelIds': [LABELS_DICT['housing'],LABELS_DICT['processed']],
                'removeLabelIds': [LABELS_DICT['UNREAD'], LABELS_DICT['INBOX']]
                }                
            service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()

        if all(elem in subject_words for elem in ['recurring', 'payment', 'authorized.']):
            soup = BeautifulSoup(bs_preprocess(email['body']))
            reference1 = 'Account #: ' + soup.find(string='Account Number:').parent.find_next_sibling('td').text
            reference2 = 'Your Transaction ID is: ' + soup.find(string='Receipt Number:').parent.find_next_sibling('td').text
            total_amount = float(soup.find(string='Payment Amount:').parent.find_next_sibling('td').text.strip('$').strip())
            date_due = datetime.strptime(soup.find(string='Date:').parent.find_next_sibling('td').text.strip(),'%m/%d/%Y')
            cat = session.query(Category).filter_by(category='Utility - Trash').first()
            prop = session.query(Property).filter_by(name='Montclair House').first()
            # Add to database
            session.add(Transaction(property_id=prop.id, datetime_payment=date_due, category_id=cat.id, name='City Of Montclair - Trash', reference1=reference1, reference2=reference2, amount=-1*total_amount))
            session.commit()

            # Manage Inbox
            apply_labels = {
                'addLabelIds': [LABELS_DICT['housing'],LABELS_DICT['processed']],
                'removeLabelIds': [LABELS_DICT['UNREAD'], LABELS_DICT['INBOX']]
                }                
            service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()
        
        elif email['subject'].lower() in ignore_list:
            apply_labels = {
                'addLabelIds': [LABELS_DICT['housing'],LABELS_DICT['processed']],
                'removeLabelIds': [LABELS_DICT['UNREAD'], LABELS_DICT['INBOX']]
                }                
            service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()

    except Exception as e:
        print(e)
        apply_labels = {
            'addLabelIds': [LABELS_DICT['ERRORS']],
            }                
        service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute() 

def mvwd(email):
    try:
        soup = BeautifulSoup(email['body'])
        # date_bill = soup.find(string='Bill Date:').next_element.text
        date_due = datetime.strptime(soup.find(string='Due Date:').next_element.text, '%m/%d/%Y') 
        total_amount = float(soup.find(string='Total Amount:').next_element.text.strip('$').replace(',', ''))
        cat = session.query(Category).filter_by(category='Utility - Water').first()
        prop = session.query(Property).filter_by(name='Montclair House').first()
        # Add to database
        session.add(Transaction(property_id=prop.id, datetime_payment=date_due, category_id=cat.id, name='Monte Vista Water District', amount=-1*total_amount))
        session.commit()

        # Manage Inbox
        apply_labels = {
            'addLabelIds': [LABELS_DICT['housing'],LABELS_DICT['processed']],
            'removeLabelIds': [LABELS_DICT['UNREAD'], LABELS_DICT['INBOX']]
            }                
        service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()
    except Exception as e:
        print(e)
        apply_labels = {
            'addLabelIds': [LABELS_DICT['ERRORS']],
            }                
        service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()


def spectrum(email):
    try:
        soup = BeautifulSoup(bs_preprocess(email['body']))
        # date_bill = soup.find(string='Bill Date:').next_element.text
        reference1 = soup.find(string='Account Number:').parent.next_sibling.text.strip()
        date_due = datetime.strptime(soup.find(string='Debit Date:').parent.next_sibling.text.strip(), '%m/%d/%Y') 
        total_amount = float(soup.find(string='Amount Due:').parent.next_sibling.text.strip('$').replace(',', ''))
        cat = session.query(Category).filter_by(category='Utility - Internet').first()
        prop = session.query(Property).filter_by(name='Montclair House').first()
        # Add to database
        session.add(Transaction(property_id=prop.id, datetime_payment=date_due, category_id=cat.id, name='Spectrum', reference1=reference1, amount=-1*total_amount))
        session.commit()

        # Manage Inbox
        apply_labels = {
            'addLabelIds': [LABELS_DICT['housing'],LABELS_DICT['processed']],
            'removeLabelIds': [LABELS_DICT['UNREAD'], LABELS_DICT['INBOX']]
            }                
        service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()
    except Exception as e:
        print(e)
        apply_labels = {
            'addLabelIds': [LABELS_DICT['ERRORS']],
            }                
        service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()



def zelle(email):
    try:
        tenants = ['ian james',]
        soup = BeautifulSoup(bs_preprocess(email['body']))
        reference1 = soup.find(string='Name').find_parent('td').find_next('td').text.strip()

        if reference1.lower() in tenants:
            reference2 = soup.find(string='Deposited into').find_parent('td').find_next('td').text
            total_amount = float(soup.find(string='Amount').find_parent('td').find_next('td').text.strip('$').replace(',', ''))
            cat = session.query(Category).filter_by(category='Rental Income').first()
            prop = session.query(Property).filter_by(name='Las Vegas Mermaid').first()
            # Add to database
            session.add(Transaction(property_id=prop.id, datetime_payment=email['date_received'], category_id=cat.id, name='Mermaid Rental Income', reference1=reference1, reference2=reference2, amount=total_amount))
            session.commit()

            # Manage Inbox
            apply_labels = {
                'addLabelIds': [LABELS_DICT['las vegas mermaid'],LABELS_DICT['processed']],
                }                
            service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()
        else:
            print(f'''Payee not recognized as a tenant: [ {reference1} ] ''')
            apply_labels = {
                'addLabelIds': [LABELS_DICT['ERRORS']],
                }                
            service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()
    except Exception as e:
        print(e)
        apply_labels = {
            'addLabelIds': [LABELS_DICT['ERRORS']],
            }                
        service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()



def nvenergy(email):
    try:
        ignore_list = [
            '''Your energy bill is now available'''.lower()
        ]
        if email['subject'].lower() == '''NV Energy Alert: Payment Received'''.lower():
            soup = BeautifulSoup(bs_preprocess(email['body']))
            # date_bill = soup.find(string='Bill Date:').next_element.text
            reference1 = soup.find(string='Account Number:').parent.parent.b.next_element.next_element.strip()
            reference2 = 'Conf #: ' + soup.find(string='Confirmation Number:').find_next('b').text.strip()
            date_payment = datetime.strptime(soup.find(string='Payment Date:').find_next('b').text.strip(), '%B %d, %Y') 
            total_amount = float(soup.find(string='Payment Amount:').find_next('b').text.strip('$').strip().replace(',',''))
            cat = session.query(Category).filter_by(category='Utility - Electric').first()
            prop = session.query(Property).filter_by(name='Las Vegas Signature').first()
            # Add to database
            session.add(Transaction(property_id=prop.id, datetime_payment=date_payment, category_id=cat.id, name='NV Energy', reference1=reference1, reference2=reference2, amount=-1*total_amount))
            session.commit()

            # Manage Inbox
            apply_labels = {
                'addLabelIds': [LABELS_DICT['las vegas signature'],LABELS_DICT['processed']],
                'removeLabelIds': [LABELS_DICT['UNREAD'], LABELS_DICT['INBOX']]
                }                
            service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()

        elif email['subject'].lower() in ignore_list:
            apply_labels = {
                'addLabelIds': [LABELS_DICT['las vegas signature'],LABELS_DICT['processed']],
                'removeLabelIds': [LABELS_DICT['UNREAD'], LABELS_DICT['INBOX']]
                }                
            service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()

        else:
            # EMAIL Not recognized.
            apply_labels = {
                'addLabelIds': [LABELS_DICT['ERRORS']],
                }
            service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()
    except Exception as e:
        print(e)
        apply_labels = {
            'addLabelIds': [LABELS_DICT['ERRORS']],
            }
        service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()


def republicservices(email):
    try:
        ignore_list = [
            '''New Invoice from Republic Services'''.lower(),
            '''Thank You for Scheduling Your Online Payment'''.lower(),
        ]
        if email['subject'].lower() == '''Thank You for Your Payment'''.lower():
            soup = BeautifulSoup(bs_preprocess(email['body']))
            basetext = soup.p.next_sibling.next_sibling.text.strip()
            reference1 = '306200113580'
            date_payment = datetime.strptime(re.search("(((0?[1-9]|1[012])/(0?[1-9]|1\d|2[0-8])|(0?[13456789]|1[012])/(29|30)|(0?[13578]|1[02])/31)/(19|[2-9]\d)\d{2}|0?2/29/((19|[2-9]\d)(0[48]|[2468][048]|[13579][26])|(([2468][048]|[3579][26])00)))", basetext).group().strip(), '%m/%d/%Y')
            total_amount = float(re.search("\$(\d{1,3}(\,\d{3})*|(\d+))(\.\d{2})?", basetext).group().strip('$').strip())
            cat = session.query(Category).filter_by(category='Utility - Trash').first()
            prop = session.query(Property).filter_by(name='Las Vegas Mermaid').first()
            # Add to database
            session.add(Transaction(property_id=prop.id, datetime_payment=date_payment, category_id=cat.id, name='Republic Services', reference1=reference1, amount=-1*total_amount))
            session.commit()

            # Manage Inbox
            apply_labels = {
                'addLabelIds': [LABELS_DICT['las vegas mermaid'],LABELS_DICT['processed']],
                'removeLabelIds': [LABELS_DICT['UNREAD'], LABELS_DICT['INBOX']]
                }                
            service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()
        elif email['subject'].lower() in ignore_list:
            apply_labels = {
                'addLabelIds': [LABELS_DICT['las vegas mermaid'],LABELS_DICT['processed']],
                'removeLabelIds': [LABELS_DICT['UNREAD'], LABELS_DICT['INBOX']]
                }                
            service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()
        else:
            # EMAIL Not recognized.
            apply_labels = {
                'addLabelIds': [LABELS_DICT['ERRORS']],
                }
            service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()
    except Exception as e:
        print(e)
        apply_labels = {
            'addLabelIds': [LABELS_DICT['ERRORS']],
            }
        service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()



def personalcapital(email):
    try:
        ignore_list = [
            
        ]
        if email['subject'].lower() == '''Your Daily Financial Monitor'''.lower():
            soup = BeautifulSoup(bs_preprocess(email['body']))
            basetext = soup.find(string='Transactions').find_next('table')
            if basetext:
                # Transactions found. Parse through transaction records.
                for row in basetext.find_all('tr'):
                    # date_payment = datetime.strptime(row.td.text.strip() + datetime.today().strftime("/%Y"), '%m/%d/%Y')
                    date_payment = datetime.strptime(row.td.text.strip() + email['date_received'].strftime("/%Y"), '%m/%d/%Y')
                    reference1 = row.td.next_sibling.text.strip()
                    reference2 = row.td.next_sibling.next_sibling.text.strip()
                    total_amount = float(row.td.next_sibling.next_sibling.next_sibling.text.strip('-').strip('$').replace(',','').strip())
                    
                    ref2_list = [item.lower() for item in reference2.split()]

                    # Las Vegas Mermaid Deposits
                    if all(elem in ref2_list for elem in ['depositteller','nv']):
                        # Check if transaction exists
                        trans = session.query(Transaction).filter_by(datetime_payment=date_payment).filter_by(amount=total_amount).first()
                        if trans:
                            print('Transaction already exists, skipping')
                        else:
                            cat = session.query(Category).filter_by(category='Rental Income').first()
                            prop = session.query(Property).filter_by(name='Las Vegas Mermaid').first()
                            
                            # Add to database
                            session.add(Transaction(property_id=prop.id, datetime_payment=date_payment, category_id=cat.id, name='Mermaid Rental Income', reference1=reference1, reference2=reference2, amount=total_amount))
                            session.commit()

                            # Manage Inbox
                            apply_labels = {
                                'addLabelIds': [LABELS_DICT['las vegas mermaid'],LABELS_DICT['processed']],
                                }                
                            service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()

                    # Las Vegas Property Tax *** Needs Manual Intervention ***
                    if all(elem in ref2_list for elem in ['clark','cty','tax']):
                        # Manage Inbox
                        apply_labels = {
                            'addLabelIds': [LABELS_DICT['needs attention'],LABELS_DICT['processed']],
                            }                
                        service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()

                    # Pet Insurance
                    if all(elem in ref2_list for elem in ['healthy','paws']):
                        # Check if transaction exists
                        trans = session.query(Transaction).filter_by(datetime_payment=date_payment).filter_by(name='Healthy Paws Pet Insurance').first()
                        if trans:
                            print('Transaction already exists, skipping')
                        else:
                            cat = session.query(Category).filter_by(category='Insurance - Pet').first()
                            prop = session.query(Property).filter_by(name='Buddy Chan').first()

                            # Add to database
                            session.add(Transaction(property_id=prop.id, datetime_payment=date_payment, category_id=cat.id, name='Healthy Paws Pet Insurance', reference1=reference1, reference2=reference2, amount=-1*total_amount))
                            session.commit()

                            # Manage Inbox
                            apply_labels = {
                                'addLabelIds': [LABELS_DICT['housing'],LABELS_DICT['processed']],
                                }                
                            service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()

                    # Auto Insurance
                    if all(elem in ref2_list for elem in ['prog','west','ins','prem']):
                        # Check if transaction exists
                        trans = session.query(Transaction).filter_by(datetime_payment=date_payment).filter_by(name='Progressive Insurance Premium').first()
                        if trans:
                            print('Transaction already exists, skipping')
                        else:
                            cat = session.query(Category).filter_by(category='Insurance - Auto').first()
                            prop = session.query(Property).filter_by(name='Subaru Forester').first()

                            # Add to database
                            session.add(Transaction(property_id=prop.id, datetime_payment=date_payment, category_id=cat.id, name='Progressive Insurance Premium', reference1=reference1, reference2=reference2, amount=-1*total_amount))
                            session.commit()

                            # Manage Inbox
                            apply_labels = {
                                'addLabelIds': [LABELS_DICT['housing'],LABELS_DICT['processed']],
                                }                
                            service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()

                    # Montclair Mortgage (Caliber Home Loans) 
                    if all(elem in ref2_list for elem in ['caliber','home','loa','draft']):
                        # Check if transaction exists
                        trans = session.query(Transaction).filter_by(datetime_payment=date_payment).filter_by(name='4184 Via Viola Montclair Mortgage').first()
                        if trans:
                            print('Transaction already exists, skipping')
                        else:
                            cat = session.query(Category).filter_by(category='Mortgage').first()
                            prop = session.query(Property).filter_by(name='Montclair House').first()

                            # Add to database
                            session.add(Transaction(property_id=prop.id, datetime_payment=date_payment, category_id=cat.id, name='4184 Via Viola Montclair Mortgage', reference1=reference1, reference2=reference2, amount=-1*total_amount))
                            session.commit()

                            # Manage Inbox
                            apply_labels = {
                                'addLabelIds': [LABELS_DICT['housing'],LABELS_DICT['processed']],
                                }                
                            service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()# Montclair Mortgage (Caliber Home Loans) 
                    
                    
                    # Montclair Bellafina HOA
                    if all(elem in ref2_list for elem in ['bellafina','hoa','dues']):
                        # Check if transaction exists
                        trans = session.query(Transaction).filter_by(datetime_payment=date_payment).filter_by(name='4184 Via Viola Montclair HOA').first()
                        if trans:
                            print('Transaction already exists, skipping')
                        else:
                            cat = session.query(Category).filter_by(category='HOA').first()
                            prop = session.query(Property).filter_by(name='Montclair House').first()

                            # Add to database
                            session.add(Transaction(property_id=prop.id, datetime_payment=date_payment, category_id=cat.id, name='4184 Via Viola Montclair HOA', reference1=reference1, reference2=reference2, amount=-1*total_amount))
                            session.commit()

                            # Manage Inbox
                            apply_labels = {
                                'addLabelIds': [LABELS_DICT['housing'],LABELS_DICT['processed']],
                                }                
                            service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()
                    

            # Nothing to categorize. Mark as Processed
            apply_labels = {
                'addLabelIds': [LABELS_DICT['processed']],
                }                
            service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()
                            
        elif email['subject'].lower() in ignore_list:
            apply_labels = {
                'addLabelIds': [LABELS_DICT['processed']],
                }                
            service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()
        else:
            # EMAIL Not recognized.
            apply_labels = {
                'addLabelIds': [LABELS_DICT['ERRORS']],
                }
            service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()
    except Exception as e:
        print(e)
        apply_labels = {
            'addLabelIds': [LABELS_DICT['ERRORS'], LABELS_DICT['UNREAD'], LABELS_DICT['INBOX']], 
            }
        service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()        



def firstresidential(email):
    try:
        ignore_list = [
            
        ]
        if email['subject'].lower() == '''Thank you for your recent payment'''.lower():
            soup = BeautifulSoup(bs_preprocess(email['body']))
            basetext = soup.find(string="Unit:").next_element
            if basetext:
                date_payment = datetime.today()
                reference1 = soup.find(string="Unit:").next_element.strip()
                reference2 = soup.find(string="Account Number:").next_element.strip()
                total_amount = float(soup.find(string="Payment Amount:").next_element.strip('$').replace(',','').strip())

                cat = session.query(Category).filter_by(category='HOA').first()
                prop = session.query(Property).filter_by(name='Las Vegas Rainbow Dream').first()

                # Add to database
                session.add(Transaction(property_id=prop.id, datetime_payment=date_payment, category_id=cat.id, name='First Service Residential', reference1=reference1, reference2=reference2, amount=-1*total_amount))
                session.commit()

                # Manage Inbox
                apply_labels = {
                    'addLabelIds': [LABELS_DICT['las vegas rainbow dream'],LABELS_DICT['processed']],
                    'removeLabelIds': [LABELS_DICT['UNREAD'], LABELS_DICT['INBOX']]
                    }                
                service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()
                            
        elif email['subject'].lower() in ignore_list:
            apply_labels = {
                'addLabelIds': [LABELS_DICT['processed']],
                }                
            service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()
        else:
            # EMAIL Not recognized.
            apply_labels = {
                'addLabelIds': [LABELS_DICT['ERRORS']],
                }
            service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()
    except Exception as e:
        print(e)
        apply_labels = {
            'addLabelIds': [LABELS_DICT['ERRORS'], LABELS_DICT['UNREAD'], LABELS_DICT['INBOX']], 
            }
        service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()  


def flagstar_bank(email):
    import re
    try:
        ignore_list = [
            
        ]
        if email['subject'].lower() == '''Your MyLoans payment has been processed'''.lower():
            soup = BeautifulSoup(bs_preprocess(email['body']))
            basetext = soup.h1.next_sibling
            if basetext:
                date_payment = email['date_received']
                reference1 = 'Parsed Email Confirmation'
                reference2 = ''
                total_amount = float(re.search("[\$]{1}[\d,]+\.?\d{0,2}", basetext.text).group().strip('$').replace(',','').strip())

                cat = session.query(Category).filter_by(category='Mortgage').first()
                prop = session.query(Property).filter_by(name='Montclair House').first()

                # Add to database
                session.add(Transaction(property_id=prop.id, datetime_payment=date_payment, category_id=cat.id, name='Flagstar Bank Mortgage Payment', reference1=reference1, reference2=reference2, amount=-1*total_amount))
                session.commit()

                # Manage Inbox
                apply_labels = {
                    'addLabelIds': [LABELS_DICT['housing'],LABELS_DICT['processed']],
                    'removeLabelIds': [LABELS_DICT['UNREAD'], LABELS_DICT['INBOX']]
                    }                
                service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()
                            
        elif email['subject'].lower() in ignore_list:
            apply_labels = {
                'addLabelIds': [LABELS_DICT['processed']],
                }                
            service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()
        else:
            # EMAIL Not recognized.
            apply_labels = {
                'addLabelIds': [LABELS_DICT['ERRORS']],
                }
            service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()
    except Exception as e:
        print(e)
        apply_labels = {
            'addLabelIds': [LABELS_DICT['ERRORS'], LABELS_DICT['UNREAD'], LABELS_DICT['INBOX']], 
            }
        service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()  


def clark_county_water(email):
    import re
    try:
        ignore_list = [
            
        ]
        email_list = [item.lower() for item in email['subject'].split()]
        # if email['subject'].lower() == '''Your MyLoans payment has been processed'''.lower():
        if all(elem in email_list for elem in ['clark','county','water','reclamation','payment','confirmation']):
            soup = BeautifulSoup(bs_preprocess(email['body']))
            basetext = soup.h3
            if basetext:
                date_payment = email['date_received']
                accntno = soup.find(string="Account Number:").find_parent("tr").find_next_sibling("tr").text
                invno = soup.find(string="Invoice Number:").find_parent("tr").find_next_sibling("tr").text
                message = soup.find(string="Message:").find_parent("tr").find_next_sibling("tr").text
                reference1 = message
                reference2 = f'''Accnt#: {accntno} | Inv#: {invno}'''
                total_amount = float(soup.find(string="Payment Amount:").find_parent("tr").find_next_sibling("tr").text.strip('$').replace(',','').strip())

                if accntno == '2236610000':
                    cat = session.query(Category).filter_by(category='Utility - Water').first()
                    prop = session.query(Property).filter_by(name='Las Vegas Mermaid').first()

                    # Add to database
                    session.add(Transaction(property_id=prop.id, datetime_payment=date_payment, category_id=cat.id, name='Clark County Water Reclamation District', reference1=reference1, reference2=reference2, amount=-1*total_amount))
                    session.commit()

                    # Manage Inbox
                    apply_labels = {
                        'addLabelIds': [LABELS_DICT['las vegas mermaid'],LABELS_DICT['processed']],
                        'removeLabelIds': [LABELS_DICT['UNREAD'], LABELS_DICT['INBOX']]
                        }                
                    service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()
                else:
                    # Account not recognized
                    apply_labels = {
                        'addLabelIds': [LABELS_DICT['ERRORS']],
                        }
                    service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()                

        # elif email['subject'].lower() in ignore_list:
        elif all(elem in email_list for elem in ['clark','county','water','reclamation','notification']):
            apply_labels = {
                'addLabelIds': [LABELS_DICT['processed']],
                }                
            service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()
        else:
            # EMAIL Not recognized.
            apply_labels = {
                'addLabelIds': [LABELS_DICT['ERRORS']],
                }
            service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()
    except Exception as e:
        print(e)
        apply_labels = {
            'addLabelIds': [LABELS_DICT['ERRORS'], LABELS_DICT['UNREAD'], LABELS_DICT['INBOX']], 
            }
        service.users().messages().modify(userId='me', id=email['id'], body=apply_labels).execute()          


def main():
    """
    Manage inbox and record data to database
    """
    msgdata = []
    # category_dict = get_categories()
    # property_dict = get_properties()
    for message in messages:
        msgdata.append(service.users().messages().get(userId='me', id=message['id'], format='full').execute())
        current_email = parse_msg(msgdata[-1])
        print(current_email)
        
        # Go thru sorting rules
        if current_email['from'].lower() == '''SoCalGas <customerservice@socalgas.com>'''.lower():
            print('Southern California Gas Company Flow')
            socalgas(current_email)

        elif current_email['from'].lower() == '''Monte Vista Water District Online Bill Pay <montevista@onlinebiller.com>'''.lower() and current_email['subject'].lower() == '''Monte Vista Water District Online       Statement     Bill Available and AutoPayment Scheduled'''.lower():
            print('Monte Vista Water District Flow')
            mvwd(current_email)

        elif current_email['from'].lower() == '''Spectrum <Myaccount@spectrumemails.com>'''.lower():
            print('Spectrum Flow')
            spectrum(current_email)

        elif current_email['from'].lower() == '''sce@entnotification.sce.com'''.lower():
            print('Southern California Edison Flow')
            sce(current_email)

        elif current_email['from'].lower() in ['''NVEnergy <donotreply@alerts.nvenergy.com>'''.lower(), '''<DoNotReply@nvenergy.com>'''.lower()]:
            print('NV Energy Flow')
            nvenergy(current_email)

        elif current_email['from'].lower() == '''noreply@republicservices.com'''.lower():
            print('Republic Services Flow')
            republicservices(current_email)
        
        elif current_email['from'].lower() == '''City of Montclair <cityofmontclair@dpnetbill.com>'''.lower():
            print('City of Montclair Trash Flow')
            montclair_trash(current_email)

        elif current_email['from'].lower() == '''<DoNotReply@mail.clearwaterpay.net>'''.lower():
            print('City of Montclair Trash Flow')
            montclair_trash(current_email)

        elif current_email['from'].lower() == '''Personal Capital <service@personalcapital.com>'''.lower():
            print('Personal Capital Flow')
            personalcapital(current_email)

        elif current_email['from'].lower() == '''paymentPostingNoReply@fsresidential.com'''.lower():
            print('Lamplight Gardens First Residential Flow')
            firstresidential(current_email)

        elif current_email['from'].lower() == '''Citibank <alerts@info6.citi.com>'''.lower():
            print('Zelle Flow')
            zelle(current_email)

        elif current_email['from'].lower() == '''no-reply@alerts.flagstar.com'''.lower():
            print('Flagstar Bank')
            flagstar_bank(current_email)

        elif current_email['from'].lower() == '''Clark County Water Reclamation District <no-reply@invoicecloud.net>'''.lower():
            print('Clark County Water Reclamation District')
            clark_county_water(current_email)

        else:
            pass


# if __name__ == '__main__':
#     main()
engine = create_engine(gd.DB_PROPERTIES)
Session = sessionmaker(bind = engine)
session = Session()

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://mail.google.com/',
    'https://www.googleapis.com/auth/gmail.compose',
    'https://www.googleapis.com/auth/gmail.insert',
    'https://www.googleapis.com/auth/gmail.labels',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.send',
    ]


creds = None
# The file token.pickle stores the user's access and refresh tokens, and is
# created automatically when the authorization flow completes for the first
# time.
if os.path.exists('token.pickle'):
    with open('token.pickle', 'rb') as token:
        creds = pickle.load(token)
# If there are no (valid) credentials available, let the user log in.
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(
            'credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
    # Save the credentials for the next run
    with open('token.pickle', 'wb') as token:
        pickle.dump(creds, token)

service = build('gmail', 'v1', credentials=creds)

LABELS_DICT = get_labels()
results = service.users().messages().list(userId='me', labelIds=['INBOX'], q='is:unread has:nouserlabels').execute()
messages = results.get('messages', [])

if not messages:
    print('No messages found')
else:
    main()
    
