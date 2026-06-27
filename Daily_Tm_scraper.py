import imaplib, os , email , smtplib
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import pandas as pd
from io import StringIO
import datetime
from datetime import timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

load_dotenv()
IMAP_SERVER = os.getenv("IMAP_SERVER")
EMAIL_ID = os.getenv("EMAIL_ID")
APP_PASSWORD = os.getenv("APP_PASSWORD")
SENDER_MAIL = os.getenv("SENDER_MAIL")
OPHEAD_MAIL = os.getenv("OPHEAD_MAIL")
SENDER_MAIL_PASS = os.getenv("SENDER_MAIL_PASS")
CC_MAIL = os.getenv('CC_EMAIL')


mail = imaplib.IMAP4_SSL(IMAP_SERVER)
mail.login(EMAIL_ID, APP_PASSWORD)
mail.select("INBOX")

status, messages = mail.search(None, '(UNSEEN)')
email_ids = messages[0].split()

compilance = opposition = hearings = renewal = "<p>No data today.</p>"

compilance_parts = []
opposition_parts = []
hearings_parts = []
renewal_parts = []

if not email_ids:
    print("No new Related emails. Exiting cleanly.")
    mail.logout()
    exit(0)
for mail_id in email_ids:
    try:
        status,msg_data = mail.fetch(mail_id,"(RFC822)")
        raw_content = msg_data[0][1]
        msg = email.message_from_bytes(raw_content)
        subject = msg['subject']
        #---------------------RENEWAL----------------------------
        if 'Renewal Report for next 90 Days' in subject:

            html_content = None
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    html_content = part.get_payload(decode=True).decode('utf-8')
                    break

            soup = BeautifulSoup(html_content, "html.parser")
            # soup = BeautifulSoup(msg, "html.parser")
            table = soup.find("table")
            rene = pd.read_html(StringIO(str(table)))[0]
            rene = rene[['Appno','Class','TM Name','Company','Valid Up To Date']]
            # print(df)
            tod = datetime.datetime.today()
            tom = tod + timedelta(days=1)
            renewal = (rene['Valid Up To Date']== tod.strftime("%d/%m/%Y")) | (rene['Valid Up To Date']==tom.strftime("%d/%m/%Y"))
            print("RENEWAL")
            print(rene[renewal])
            # renewal = df[needed].to_html(index=False)
            renewal_parts.append(rene[renewal].to_html(index=False))
            # print(renewal)
            # df[needed].to_html("output.html", index=False)
        #---------------------------HEARING--------------------------
        elif "Hearing Report for next 30 days" in subject:
            html_content = None
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    html_content = part.get_payload(decode=True).decode('utf-8')
                    break

            soup = BeautifulSoup(html_content, "html.parser")
            # soup = BeautifulSoup(msg, "html.parser")
            table = soup.find("table")
            her = pd.read_html(StringIO(str(table)))[0]
            
            her = her[['Appno','Class','TM Name','Company','Hearing Date','Days Left','UserDetail']]
            hear = (pd.to_numeric(her['Days Left'], errors='coerce') <= 3)
            hearings = her[hear]
            print("HEARING")
            print(hearings)
            # hearings = hearings.to_html(index=False)
            hearings_parts.append(hearings.to_html(index=False))
            # print(hearings)
            # needed.to_html("hearings.html", index=False)
        #--------------------------OPPOSITION--------------------------------
        elif "Opposition Tracking & Compliance Report" in subject:
        
            html_content = None
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    html_content = part.get_payload(decode=True).decode('utf-8')
                    break

            soup = BeautifulSoup(html_content, "html.parser")
            # soup = BeautifulSoup(msg, "html.parser")
            table = soup.find_all("table")
            op = pd.read_html(StringIO(str(table[1])))[0]
            op = op.fillna('').astype(str).apply(lambda col: col.str.replace(r'\.0$', '', regex=True))

            oppo = (pd.to_numeric(op['DAYS LEFT'], errors='coerce') <= 6)
            print("OPPOSITION TRACKING")
            print(op[oppo])
            # opposition = df[oppo].to_html(index=False)
            opposition_parts.append(op[oppo].to_html(index=False))
            # print(opposition)
            # df[oppo].to_html("opposition.html", index=False)


        #------------------------------COMPLIANCE-------------------------
        elif 'Compliance Report for Next 30 days' in subject:
            # print(msg)
            # Extract HTML part
            html_content = None
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    html_content = part.get_payload(decode=True).decode('utf-8')
                    break

            soup = BeautifulSoup(html_content, "html.parser")
            # soup = BeautifulSoup(msg, "html.parser")
            table = soup.find("table")
            cdf = pd.read_html(StringIO(str(table)))[0]
            cdf = cdf.fillna('').astype(str).apply(lambda col: col.str.replace(r'\.0$', '', regex=True))
            cdf = cdf[['Appno','Class','TM Name','Company','Due At','Days Left']]
            # print(df)
            # tod = datetime.datetime.today()
            # tom = tod + timedelta(days=1)
            compilance = (pd.to_numeric(cdf['Days Left'], errors='coerce') <= 2)
            print("COMPILANCE")
            print(cdf[compilance])
            # compilance = cdf[compilance].to_html(index=False)
            compilance_parts.append(cdf[compilance].to_html(index=False))
            # print(compilance)
            # cdf[compilance].to_html("compilance.html", index=False)

        else:
            print(f'No email found in Hearing subjects, the subject was {subject}')

    except Exception as e:
        print(f"Error processing email {mail_id}: {e}")
        # ❌ do NOT mark as read

try:
    mail.logout()
except:
    pass

if not any([compilance_parts, opposition_parts, hearings_parts, renewal_parts]):
    print("Nothing to send today.")
    exit(0)

compilance = "".join(compilance_parts) or "<p>No data today.</p>"
opposition = "".join(opposition_parts) or "<p>No data today.</p>"
hearings = "".join(hearings_parts) or "<p>No data today.</p>"
renewal = "".join(renewal_parts) or "<p>No data today.</p>"


def send_mail(compilance, opposition, hearings,renewal,tod):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Scraped from TM-Pilot"
    msg["From"] = SENDER_MAIL
    msg["To"] = OPHEAD_MAIL #'tharani@unimarkslegal.com'
    # msg["Cc"] = CC_MAIL
    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif;">
        <h3>Selective Records {tod.strftime("%d/%m/%Y")}</h3>
        <h4>COMPILIANCE REPORT</h4>
        <p>{compilance}</p>
        <h4>OPPOSITION REPORT</h4>
        <p>{opposition}</p>

        <h4>HEARING REPORT</h4>
        <p>{hearings}</p>

        <h4>RENEWAL REPORT</h4>
        <p>{renewal}</p>
        <hr>
      </body>
    </html>
    """

    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(SENDER_MAIL, SENDER_MAIL_PASS)
        server.send_message(msg)


send_mail(compilance =compilance , opposition = opposition, hearings= hearings,renewal =renewal,tod=tod)
