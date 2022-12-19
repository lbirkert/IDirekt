#  _____ _____ _____ _____  ______ _  _________ 
# |_   _|  __ \_   _|  __ \|  ____| |/ /__   __|
#   | | | |  | || | | |__) | |__  | ' /   | |   
#   | | | |  | || | |  _  /|  __| |  <    | |   
#  _| |_| |__| || |_| | \ \| |____| . \   | |   
# |_____|_____/_____|_|  \_\______|_|\_\  |_|   
#
# https://github.com/KotwOSS/IDirekt/blob/main/LICENSE
#
# (c) 2022 KotwOSS

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os, time, requests, smtplib, ssl
from typing import Dict
from dotenv import load_dotenv

version = "0.0.0"

def print_logo():
    print("""\
 _____ _____ _____ _____  ______ _  _________ 
|_   _|  __ \_   _|  __ \|  ____| |/ /__   __|
  | | | |  | || | | |__) | |__  | ' /   | |   
  | | | |  | || | |  _  /|  __| |  <    | |   
 _| |_| |__| || |_| | \ \| |____| . \   | |   
|_____|_____/_____|_|  \_\______|_|\_\  |_|   
    """)
    print(f"IDIREKT version {version} made by KotwOSS, Licensed under MIT\n")
    
def expect_env(env: str):
    val = os.getenv(env)
    if val == None:
        raise RuntimeError(f"Environment variable '{env}' is not set!")
    return val

class IservClient:
    base_headers: Dict[str, str] = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:102.0) Gecko/20100101 Firefox/102.0"
    }
    
    iserv_url: str
    username: str
    password: str
    
    session: requests.Session
    
    def __init__(self, iserv_url: str, username: str, password: str):
        self.iserv_url = iserv_url
        self.username = username
        self.password = password
        
        self.session = requests.Session()
    
    def login(self):
        headers = self.base_headers | {}
        response = self.session.post(f"{self.iserv_url}app/login", data={
            "_username": self.username,
            "_password": self.password
        }, headers=headers)
        
        if response.status_code != 200:
            raise RuntimeError(f"Error while logging in: {response.text}")
    
    def mail_message_unseen(self):
        headers = self.base_headers | {}
        response = self.session.get(f"{self.iserv_url}mail/api/message/list?path=INBOX&searchQuery[flagUnseen]=true&length=20&start=0&order[column]=date&order[dir]=desc",
                                    headers=headers)
        
        if response.status_code != 200:
            raise RuntimeError(f"Error while reading inbox: {response.text}")
        
        return response.json()
    
    def mail_message(self, msg: int):
        headers = self.base_headers | {}
        response = self.session.get(f"{self.iserv_url}mail/api/message?path=INBOX&msg={msg}",
                                    headers=headers)
        
        if response.status_code != 200:
            raise RuntimeError(f"Error while reading message {msg}: {response.text}")
        
        return response.json()
    
    def close(self):
        self.session.close()

print_logo()

load_dotenv()


context = ssl.create_default_context()

smtp_host = expect_env("SMTP_HOST")
smtp_port = int(expect_env("SMTP_PORT"))
smtp_user = expect_env("SMTP_USER")
smtp_password = expect_env("SMTP_PASSWORD")
smtp_recipents = expect_env("SMTP_RECIPENTS")
smtp_sender = expect_env("SMTP_SENDER")
smtp = smtplib.SMTP(smtp_host, smtp_port)
smtp.login(smtp_user, smtp_password)

iserv_url = expect_env("ISERV_URL")
iserv_username = expect_env("ISERV_USERNAME")
iserv_password = expect_env("ISERV_PASSWORD")

print(f"Using iserv server at {iserv_url}")

iserv_client = IservClient(iserv_url, iserv_username, iserv_password)

print(f"Loging in as {iserv_username}")

iserv_client.login()

try:
    while True:
        print("Reading INBOX...")
        
        try:
            result = iserv_client.mail_message_unseen()
            
            unseen = result["unseen"]
            
            if unseen == 0:
                print("No unseen mails")
            else:
                print(f"Found {unseen} unseen mail(s), forwarding")
                
                for message in result["data"]:
                    mail = iserv_client.mail_message(message["uid"])
                    
                    data = mail["data"]
                    senders = [
                        f"{sender['personal']} <{sender['bare_address']}>" 
                        for sender in data["from"]
                    ]
                    
                    recipents = [
                        f"{recipent['personal']} <{recipent['bare_address']}>" 
                        for recipent in data["to"]
                    ]
                    
                    msg = MIMEMultipart()
                    
                    msg["From"] = smtp_sender
                    msg["To"] = smtp_recipents
                    msg["Subject"] = "FWD: " + data["subject"]
                    
                    for content in data["contents"]:
                        body = f"{data['date']}:\n\n{', '.join(senders)} ->\n{', '.join(recipents)}\n\n"
                        body += content["raw"]
                        msg.attach(MIMEText(body, content["type"], "utf-8"))
                    
                    smtp.sendmail(smtp_sender, [s.strip() for s in smtp_recipents.split(",")], msg.as_string())
                    
                    print(f"Successfully forwarded mail '{data['subject']}'")
                    
        except RuntimeError as e:
            print(e)
            print("Failed, Relogin...")
            iserv_client.login()
        
        time.sleep(120)
except KeyboardInterrupt:
    print("Exitting...")

smtp.quit()
iserv_client.close()
